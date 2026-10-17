"""Threads — free API (graph.threads.net).

Text ≤500 chars; text posts get a link preview card (we append the day's page URL when
there is no media). Media must be publicly fetchable — this repo's Pages site serves it.
Rate limit: 250 posts/24h (irrelevant at one a day).
"""
from __future__ import annotations

import time

import requests

from lib import config

NAME = "threads"
LABEL = "Threads"
ENV_KEYS = ["THREADS_USER_ID", "THREADS_ACCESS_TOKEN"]
HOST = "https://graph.threads.net/v1.0"


def is_enabled() -> bool:
    return bool(config.social(NAME).get("enabled"))


def missing_env() -> list[str]:
    return [key for key in ENV_KEYS if not config.env(key)]


def _final_text(day) -> str:
    text = day.threads_text()
    if day.video or day.images:
        return text
    link = day.site_url()
    max_text = 500 - len(link) - 2
    if len(text) > max_text:
        text = text[: max_text - 1].rstrip() + "…"
    return f"{text}\n\n{link}"


def _post(path: str, data: dict) -> dict:
    resp = requests.post(f"{HOST}/{path}", data=data, timeout=120)
    if resp.status_code >= 400:
        raise RuntimeError(f"Threads API {resp.status_code}: {resp.text[:400]}")
    return resp.json()


def _wait(container_id: str, timeout_s: int = 180) -> None:
    token = config.env("THREADS_ACCESS_TOKEN")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = requests.get(
            f"{HOST}/{container_id}",
            params={"fields": "status,error_message", "access_token": token},
            timeout=30,
        )
        payload = resp.json()
        status = payload.get("status")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Threads container {status}: {payload.get('error_message')}")
        time.sleep(5)
    raise RuntimeError("Threads container did not finish processing in time")


def preview(day) -> dict:
    return {
        "text": _final_text(day),
        "media": (
            [f"video: {day.video}"] if day.video else
            [f"image: {rel}" for rel in day.images[:20]] if day.images else []
        ),
        "note": "text with link card" if not (day.video or day.images) else "media post (fetched from the live site)",
        "warnings": (
            ["media is fetched from the live site URL — commit & push before publishing"]
            if (day.video or day.images) else []
        ),
    }


def publish(day) -> dict:
    user = config.env("THREADS_USER_ID")
    token = config.env("THREADS_ACCESS_TOKEN")
    cfg = config.social(NAME)
    params: dict = {"access_token": token, "text": _final_text(day)}
    topic = str(cfg.get("topic_tag") or "").strip().lstrip("#")
    if topic:
        params["topic_tag"] = topic

    if day.video:
        params.update({"media_type": "VIDEO", "video_url": day.media_url(day.video)})
        container = _post(f"{user}/threads", params)["id"]
        _wait(container)
    elif len(day.images) > 1:
        children = []
        for rel in day.images[:20]:
            child = _post(f"{user}/threads", {
                "access_token": token,
                "media_type": "IMAGE",
                "image_url": day.media_url(rel),
                "is_carousel_item": "true",
            })["id"]
            children.append(child)
        params.update({"media_type": "CAROUSEL", "children": ",".join(children)})
        container = _post(f"{user}/threads", params)["id"]
        _wait(container)
    elif day.images:
        params.update({"media_type": "IMAGE", "image_url": day.media_url(day.images[0])})
        container = _post(f"{user}/threads", params)["id"]
        _wait(container)
    else:
        params["media_type"] = "TEXT"
        container = _post(f"{user}/threads", params)["id"]

    published = _post(f"{user}/threads_publish", {"access_token": token, "creation_id": container})["id"]
    permalink = ""
    try:
        info = requests.get(
            f"{HOST}/{published}",
            params={"fields": "permalink", "access_token": token},
            timeout=30,
        ).json()
        permalink = info.get("permalink") or ""
    except Exception:
        pass
    return {"id": published, "url": permalink}


def refresh_token() -> str:
    """Refresh the ~60-day long-lived token; returns a human hint of the new validity."""
    token = config.env("THREADS_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("THREADS_ACCESS_TOKEN not set")
    resp = requests.get(
        "https://graph.threads.net/refresh_access_token",
        params={"grant_type": "th_refresh_token", "access_token": token},
        timeout=30,
    )
    data = resp.json()
    if not data.get("access_token"):
        raise RuntimeError(resp.text[:300])
    config.update_env("THREADS_ACCESS_TOKEN", data["access_token"])
    days = int(data.get("expires_in", 0)) // 86400
    return f"expires in ~{days} days"
