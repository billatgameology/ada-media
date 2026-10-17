"""Facebook Page — free Graph API, but read the catch.

Until your Meta app passes App Review, posts created by the API are visible to page
admins only (app in Development mode). The API mechanics are fully wired regardless,
so enable it in config.yaml whenever you decide to do the review — see guide/PLAN.md.
"""
from __future__ import annotations

import requests

from lib import config

NAME = "facebook"
LABEL = "Facebook Page"
ENV_KEYS = ["FB_PAGE_ID", "FB_PAGE_ACCESS_TOKEN"]


def is_enabled() -> bool:
    return bool(config.social(NAME).get("enabled"))


def missing_env() -> list[str]:
    return [key for key in ENV_KEYS if not config.env(key)]


def _base() -> str:
    return f"https://graph.facebook.com/{config.meta_version()}"


def preview(day) -> dict:
    return {
        "text": day.facebook_text(),
        "media": [f"photo: {day.images[0]}"] if day.images else [],
        "note": "full summary + link (links are free on Facebook)",
        "warnings": [
            "App Review note: until your Meta app passes review, API posts are visible to page admins only"
        ],
    }


def publish(day) -> dict:
    page = config.env("FB_PAGE_ID")
    token = config.env("FB_PAGE_ACCESS_TOKEN")
    text = day.facebook_text()

    if day.images:
        resp = requests.post(f"{_base()}/{page}/photos", data={
            "url": day.media_url(day.images[0]),
            "caption": text,
            "access_token": token,
        }, timeout=120)
    else:
        resp = requests.post(f"{_base()}/{page}/feed", data={
            "message": text,
            "access_token": token,
        }, timeout=60)

    if resp.status_code >= 400:
        raise RuntimeError(f"Facebook API {resp.status_code}: {resp.text[:400]}")
    post_id = resp.json().get("id") or resp.json().get("post_id") or ""
    return {"id": post_id, "url": f"https://www.facebook.com/{post_id}" if post_id else ""}
