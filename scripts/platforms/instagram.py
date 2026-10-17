"""Instagram — free "Instagram API with Instagram Login" (graph.instagram.com).

Professional account required. Images must be JPEG (officially); reels via video_url;
carousels up to 10. 100 API-published posts per 24h. Media must be publicly fetchable
(this repo's Pages site serves it) — the whole container flow is:
create container → poll status → media_publish.
"""
from __future__ import annotations

import time

import requests

from lib import config

NAME = "instagram"
LABEL = "Instagram"
ENV_KEYS = ["IG_USER_ID", "IG_ACCESS_TOKEN"]


def is_enabled() -> bool:
    return bool(config.social(NAME).get("enabled"))


def missing_env() -> list[str]:
    return [key for key in ENV_KEYS if not config.env(key)]


def _base() -> str:
    return f"https://graph.instagram.com/{config.meta_version()}"


def _post(path: str, data: dict) -> dict:
    resp = requests.post(f"{_base()}/{path}", data=data, timeout=120)
    if resp.status_code >= 400:
        raise RuntimeError(f"Instagram API {resp.status_code}: {resp.text[:400]}")
    return resp.json()


def _get(path: str, params: dict) -> dict:
    resp = requests.get(f"{_base()}/{path}", params=params, timeout=60)
    if resp.status_code >= 400:
        raise RuntimeError(f"Instagram API {resp.status_code}: {resp.text[:400]}")
    return resp.json()


def _wait(container_id: str, timeout_s: int = 300) -> None:
    token = config.env("IG_ACCESS_TOKEN")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        payload = _get(container_id, {"fields": "status_code,status", "access_token": token})
        status = payload.get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram container {status}: {payload.get('status')}")
        time.sleep(10)
    raise RuntimeError("Instagram container did not finish processing in time")


def _check_jpeg(rel: str) -> None:
    if not str(rel).lower().endswith((".jpg", ".jpeg")):
        raise RuntimeError(
            f"Instagram accepts JPEG images only — convert {rel} first, e.g.: "
            f"sips -s format jpeg content/media/{rel} --out content/media/{rel}.jpg"
        )


def preview(day) -> dict:
    media, warnings = [], []
    if day.video:
        media.append(f"reel: {day.video}")
    elif day.images:
        media = [f"image: {rel}" for rel in day.images]
        if len(day.images) > 1:
            media.insert(0, f"carousel of {min(len(day.images), 10)}")
    else:
        warnings.append("Instagram has no text-only posts — add media.images or media.video to the note")
    for rel in day.images:
        if not str(rel).lower().endswith((".jpg", ".jpeg")):
            warnings.append(f"{rel} is not a JPEG — Instagram will reject it")
    if day.video or day.images:
        warnings.append("media is fetched from the live site URL — commit & push before publishing")
    return {
        "text": day.instagram_caption(),
        "media": media,
        "note": "reel / carousel / single image via the Content Publishing API",
        "warnings": warnings,
    }


def publish(day) -> dict:
    user = config.env("IG_USER_ID")
    token = config.env("IG_ACCESS_TOKEN")
    caption = day.instagram_caption()
    common = {"access_token": token, "caption": caption}

    if day.video:
        container = _post(f"{user}/media", {
            **common, "media_type": "REELS", "video_url": day.media_url(day.video),
        })["id"]
        _wait(container)
    elif len(day.images) > 1:
        children = []
        for rel in day.images[:10]:
            _check_jpeg(rel)
            child = _post(f"{user}/media", {
                "access_token": token,
                "image_url": day.media_url(rel),
                "is_carousel_item": "true",
            })["id"]
            children.append(child)
        container = _post(f"{user}/media", {
            **common, "media_type": "CAROUSEL", "children": ",".join(children),
        })["id"]
        _wait(container)
    elif day.images:
        _check_jpeg(day.images[0])
        container = _post(f"{user}/media", {
            **common, "image_url": day.media_url(day.images[0]),
        })["id"]
        _wait(container)
    else:
        raise RuntimeError("no media for Instagram — add image(s) or a video to the note")

    published = _post(f"{user}/media_publish", {"access_token": token, "creation_id": container})["id"]
    permalink = ""
    try:
        info = _get(published, {"fields": "permalink", "access_token": token})
        permalink = info.get("permalink") or ""
    except Exception:
        pass
    return {"id": published, "url": permalink}


def refresh_token() -> str:
    """Refresh the ~60-day long-lived Instagram token."""
    token = config.env("IG_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("IG_ACCESS_TOKEN not set")
    resp = requests.get(
        "https://graph.instagram.com/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
        timeout=30,
    )
    data = resp.json()
    if not data.get("access_token"):
        raise RuntimeError(resp.text[:300])
    config.update_env("IG_ACCESS_TOKEN", data["access_token"])
    days = int(data.get("expires_in", 0)) // 86400
    return f"expires in ~{days} days"
