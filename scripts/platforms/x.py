"""X / Twitter — pay-per-use API (no free tier for new developers since Feb 2026).

Posting costs ~$0.015 per post; a post containing a link costs ~$0.20, which is why
config.yaml keeps `links_in_posts: false`. OAuth 1.0a user context via requests-oauthlib.
Endpoints: POST /2/tweets, POST /2/media/upload (base64 JSON, images).
"""
from __future__ import annotations

import base64
import mimetypes

import requests
from requests_oauthlib import OAuth1

from lib import config

NAME = "x"
LABEL = "X / Twitter"
ENV_KEYS = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
API = "https://api.x.com/2"


def is_enabled() -> bool:
    return bool(config.social(NAME).get("enabled"))


def missing_env() -> list[str]:
    return [key for key in ENV_KEYS if not config.env(key)]


def _auth() -> OAuth1:
    key, secret, token, token_secret = (config.env(k) for k in ENV_KEYS)
    return OAuth1(key, secret, token, token_secret)


def texts(day) -> list[str]:
    if config.social(NAME).get("thread"):
        return day.x_thread()
    return [day.x_text()]


def preview(day) -> dict:
    posts = texts(day)
    has_link = any("http" in p for p in posts)
    cost = sum(0.20 if "http" in p else 0.015 for p in posts)
    warnings = []
    if has_link and not config.social(NAME).get("links_in_posts"):
        warnings.append("contains a link → ~$0.20/post instead of ~$0.015; remove it or set links_in_posts: true")
    return {
        "text": "\n---\n".join(posts),
        "media": [f"image: {rel}" for rel in day.images[:4]],
        "note": f"{len(posts)} post(s) · estimated cost ≈ ${cost:.3f} (pay-per-use)",
        "warnings": warnings,
    }


def publish(day) -> dict:
    auth = _auth()

    media_ids = []
    for rel in day.images[:4]:
        path = day.media_path(rel)
        if not path.exists():
            raise RuntimeError(f"media file not found: {path}")
        payload = {
            "media": base64.b64encode(path.read_bytes()).decode("ascii"),
            "media_category": "tweet_image",
            "media_type": mimetypes.guess_type(path.name)[0] or "image/jpeg",
        }
        resp = requests.post(f"{API}/media/upload", auth=auth, json=payload, timeout=120)
        if resp.status_code >= 400:
            raise RuntimeError(f"X media upload {resp.status_code}: {resp.text[:300]}")
        media_ids.append(resp.json()["data"]["id"])

    ids: list[str] = []
    reply_to = None
    for index, text in enumerate(texts(day)):
        body: dict = {"text": text}
        if index == 0 and media_ids:
            body["media"] = {"media_ids": media_ids}
        if reply_to:
            body["reply"] = {"in_reply_to_tweet_id": reply_to}
        resp = requests.post(f"{API}/tweets", auth=auth, json=body, timeout=60)
        if resp.status_code == 402:
            raise RuntimeError("X returned 402 CreditsDepleted — add credits at console.x.com")
        if resp.status_code >= 400:
            raise RuntimeError(f"X API {resp.status_code}: {resp.text[:300]}")
        tweet_id = resp.json()["data"]["id"]
        ids.append(tweet_id)
        reply_to = tweet_id

    return {
        "id": ids[0],
        "url": f"https://x.com/i/status/{ids[0]}",
        "note": f"thread of {len(ids)}" if len(ids) > 1 else "",
    }
