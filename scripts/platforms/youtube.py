"""YouTube — free Data API v3 (quota: ~6 uploads/day).

OAuth once (`python scripts/ada.py auth youtube`, opens a browser); the refresh token
is stored in .state/youtube_token.json and handled automatically after that.
"""
from __future__ import annotations

import json

from lib import config, state

NAME = "youtube"
LABEL = "YouTube"
ENV_KEYS = ["YT_CLIENT_ID", "YT_CLIENT_SECRET"]
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = "youtube_token.json"
# max title 100 chars, description 5000 — clipping happens in content.py


def is_enabled() -> bool:
    return bool(config.social(NAME).get("enabled"))


def missing_env() -> list[str]:
    missing = [key for key in ENV_KEYS if not config.env(key)]
    if not state.load_json(TOKEN_FILE):
        missing.append("(authorized token — run: python scripts/ada.py auth youtube)")
    return missing


def _client_config() -> dict:
    return {
        "installed": {
            "client_id": config.env("YT_CLIENT_ID"),
            "client_secret": config.env("YT_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def auth_flow() -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    missing = [key for key in ENV_KEYS if not config.env(key)]
    if missing:
        raise RuntimeError(f"set {', '.join(missing)} in .env first (see guide/SETUP.md §5)")
    flow = InstalledAppFlow.from_client_config(_client_config(), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    state.save_json(TOKEN_FILE, json.loads(creds.to_json()))
    print("✓ YouTube authorized — refresh token stored in .state/youtube_token.json")


def _creds():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    data = state.load_json(TOKEN_FILE)
    if not data:
        raise RuntimeError("YouTube not authorized yet — run: python scripts/ada.py auth youtube")
    creds = Credentials.from_authorized_user_info(data, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            state.save_json(TOKEN_FILE, json.loads(creds.to_json()))
        else:
            raise RuntimeError("YouTube token is invalid — re-run: python scripts/ada.py auth youtube")
    return creds


def preview(day) -> dict:
    warnings = []
    if not day.video:
        warnings.append("YouTube requires a video — set media.video in the note")
    privacy = config.social(NAME).get("privacy_status", "public")
    note = f"upload as {privacy}"
    if privacy == "public":
        note += " · vertical videos ≤3 min become Shorts (add #Shorts to the description)"
    return {
        "text": f"title: {day.youtube_title()}\n\ndescription:\n{day.youtube_description()}",
        "media": [f"video: {day.video}"] if day.video else [],
        "note": note,
        "warnings": warnings,
    }


def publish(day) -> dict:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    if not day.video:
        raise RuntimeError("no video for YouTube — set media.video in the note")
    path = day.media_path(day.video)
    if not path.exists():
        raise RuntimeError(f"video file not found: {path}")

    privacy = config.social(NAME).get("privacy_status", "public")
    youtube = build("youtube", "v3", credentials=_creds(), cache_discovery=False)
    body = {
        "snippet": {
            "title": day.youtube_title(),
            "description": day.youtube_description(),
            "tags": [str(t) for t in (day.tags or [])],
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(path), chunksize=8 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    try:
        while response is None:
            _, response = request.next_chunk()
    except HttpError as exc:
        hint = " (daily quota reached?)" if "quotaExceeded" in str(exc) else ""
        raise RuntimeError(f"YouTube upload failed{hint}: {str(exc)[:300]}") from exc

    video_id = response["id"]
    return {"id": video_id, "url": f"https://youtu.be/{video_id}", "note": f"privacy: {privacy}"}
