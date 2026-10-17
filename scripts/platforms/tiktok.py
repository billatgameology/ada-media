"""TikTok — free Content Posting API.

Default mode is `inbox`: the video is uploaded to TikTok's servers and YOU get a
"draft ready" notification in the TikTok app — no audit required, nothing publishes
without your tap. `direct` mode (config.yaml) posts publicly via the API, which
requires a passed app audit (see guide/SETUP.md §4).

Auth: one-time code exchange (`python scripts/ada.py auth tiktok`), then the refresh
token in .env is rotated automatically on every publish (stored in .state/).
"""
from __future__ import annotations

import time
from urllib.parse import urlencode

import requests

from lib import config, state

NAME = "tiktok"
LABEL = "TikTok"
ENV_KEYS = ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN"]
OPEN = "https://open.tiktokapis.com/v2"


def is_enabled() -> bool:
    return bool(config.social(NAME).get("enabled"))


def missing_env() -> list[str]:
    return [key for key in ENV_KEYS if not config.env(key)]


def _mode() -> str:
    return "direct" if str(config.social(NAME).get("mode")) == "direct" else "inbox"


# ── auth ────────────────────────────────────────────────────────────────
def auth_url() -> str:
    scopes = "video.upload,video.publish" if _mode() == "direct" else "video.upload"
    params = {
        "client_key": config.env("TIKTOK_CLIENT_KEY"),
        "scope": scopes,
        "response_type": "code",
        "redirect_uri": config.env("TIKTOK_REDIRECT_URI"),
        "state": "ada",
    }
    return "https://www.tiktok.com/v2/auth/authorize/?" + urlencode(params)


def exchange_code(code: str) -> str:
    resp = requests.post(f"{OPEN}/oauth/token/", data={
        "client_key": config.env("TIKTOK_CLIENT_KEY"),
        "client_secret": config.env("TIKTOK_CLIENT_SECRET"),
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": config.env("TIKTOK_REDIRECT_URI"),
    }, timeout=60)
    data = resp.json()
    if "refresh_token" not in data:
        raise RuntimeError(f"TikTok token exchange failed: {resp.text[:400]}")
    config.update_env("TIKTOK_REFRESH_TOKEN", data["refresh_token"])
    return data.get("open_id", "")


def _access_token() -> str:
    cache = state.load_json("tiktok_tokens.json", {}) or {}
    if cache.get("access_token") and float(cache.get("expires_at", 0)) > time.time() + 120:
        return cache["access_token"]

    resp = requests.post(f"{OPEN}/oauth/token/", data={
        "client_key": config.env("TIKTOK_CLIENT_KEY"),
        "client_secret": config.env("TIKTOK_CLIENT_SECRET"),
        "grant_type": "refresh_token",
        "refresh_token": config.env("TIKTOK_REFRESH_TOKEN"),
    }, timeout=60)
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(
            f"TikTok token refresh failed: {resp.text[:300]} "
            f"— re-run: python scripts/ada.py auth tiktok"
        )
    state.save_json("tiktok_tokens.json", {
        "access_token": data["access_token"],
        "expires_at": time.time() + int(data.get("expires_in", 86400)),
    })
    if data.get("refresh_token"):
        config.update_env("TIKTOK_REFRESH_TOKEN", data["refresh_token"])
    return data["access_token"]


# ── publishing ─────────────────────────────────────────────────────────
def preview(day) -> dict:
    media, warnings = [], []
    if day.video:
        path = day.media_path(day.video)
        size = f"{path.stat().st_size / 1e6:.1f} MB" if path.exists() else "missing!"
        media.append(f"video: {day.video} ({size})")
    else:
        warnings.append("TikTok requires a video — set media.video in the note")

    if _mode() == "inbox":
        note = "uploads to your TikTok inbox as a draft — you finish posting in the app"
        text = "(no caption sent — you set it in the TikTok app)"
    else:
        note = (f"DIRECT POST (privacy: {config.social(NAME).get('privacy_level', 'SELF_ONLY')}) "
                f"— public visibility requires a passed TikTok audit")
        text = day.tiktok_caption()
    return {"text": text, "media": media, "note": note, "warnings": warnings}


def publish(day) -> dict:
    if not day.video:
        raise RuntimeError("no video for TikTok — set media.video in the note")
    path = day.media_path(day.video)
    if not path.exists():
        raise RuntimeError(f"video file not found: {path}")

    token = _access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
    size = path.stat().st_size
    source = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1}

    if _mode() == "inbox":
        resp = requests.post(f"{OPEN}/post/publish/inbox/video/init/", headers=headers,
                             json={"source_info": source}, timeout=60)
    else:
        resp = requests.post(f"{OPEN}/post/publish/video/init/", headers=headers, json={
            "post_info": {
                "title": day.tiktok_caption(),
                "privacy_level": config.social(NAME).get("privacy_level", "SELF_ONLY"),
                "disable_comment": False,
                "disable_duet": False,
                "disable_stitch": False,
            },
            "source_info": source,
        }, timeout=60)

    payload = resp.json()
    error = payload.get("error") or {}
    if resp.status_code >= 400 or error.get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok init failed: {resp.text[:400]}")
    data = payload["data"]
    upload_url, publish_id = data["upload_url"], data["publish_id"]

    with open(path, "rb") as fh:
        upload = requests.put(upload_url, headers={
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{size - 1}/{size}",
        }, data=fh, timeout=900)
    if upload.status_code >= 400:
        raise RuntimeError(f"TikTok upload failed: {upload.status_code} {upload.text[:300]}")

    status, deadline = "", time.time() + 240
    while time.time() < deadline:
        try:
            fetched = requests.post(f"{OPEN}/post/publish/status/fetch/", headers=headers,
                                    json={"publish_id": publish_id}, timeout=30).json()
            status = (fetched.get("data") or {}).get("status") or ""
        except Exception:
            status = ""
        if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX", "FAILED"):
            break
        time.sleep(5)
    if status == "FAILED":
        raise RuntimeError("TikTok reported FAILED — check video specs (format/size/duration)")

    result = {"id": publish_id, "url": "", "mode": _mode()}
    if _mode() == "inbox":
        result["note"] = "draft uploaded — finish it in the TikTok app (check your inbox)"
    else:
        result["note"] = f"status: {status or 'unknown'}"
    return result
