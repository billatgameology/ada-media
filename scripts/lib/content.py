"""Load daily notes and derive the per-platform texts from them."""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import config

DAILY_DIR = config.root() / "content" / "daily"
MEDIA_DIR = config.root() / "content" / "media"
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")


def _plain(text: str) -> str:
    """Strip the light markdown (backticks, bold/italic) that social captions can't render."""
    text = text.replace("`", "")
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    return text.strip()


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _split_frontmatter(raw: str):
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            front = yaml.safe_load(parts[1]) or {}
            return front, parts[2].lstrip("\n")
    return {}, raw


@dataclass
class Day:
    date: str
    title: str = ""
    summary: str = ""
    tags: list = field(default_factory=list)
    images: list = field(default_factory=list)
    video: str = ""
    overrides: dict = field(default_factory=dict)
    draft: bool = False
    body_md: str = ""

    # ── helpers ────────────────────────────────────────────────────────
    def bullets(self) -> list[str]:
        out = []
        for line in self.body_md.splitlines():
            stripped = line.strip()
            if stripped.startswith("- ") and stripped != "-":
                out.append(_plain(stripped[2:].strip()))
        return out

    def site_filename(self) -> str:
        return f"{self.date}.html"

    def site_url(self) -> str:
        base = str(config.project().get("site_url") or "").rstrip("/")
        return f"{base}/{self.site_filename()}"

    def media_url(self, rel: str) -> str:
        base = str(config.project().get("site_url") or "").rstrip("/")
        return f"{base}/media/{rel}"

    def media_path(self, rel: str) -> Path:
        return MEDIA_DIR / rel

    def _ov(self, key: str, default: str = "") -> str:
        value = (self.overrides or {}).get(key, default)
        return value.strip() if isinstance(value, str) and value.strip() else default

    def _yt_override(self) -> dict:
        value = (self.overrides or {}).get("youtube") or {}
        return value if isinstance(value, dict) else {}

    def hashtags(self) -> str:
        cfg = config.social("instagram")
        tags = list(cfg.get("hashtags") or []) + list(self.tags or [])
        seen = dict.fromkeys(str(t).replace(" ", "") for t in tags if t)
        return " ".join(f"#{t}" for t in seen)

    # ── derived texts, one per target ──────────────────────────────────
    def x_text(self) -> str:
        custom = self._ov("x")
        if custom:
            return _clip(custom, 280)
        link = self.site_url() if config.social("x").get("include_link") else ""
        budget = 280 - (len(link) + 2 if link else 0)
        parts = [self.summary or self.title]
        for bullet in self.bullets()[:2]:
            if len("\n\n".join(parts + [bullet])) <= budget:
                parts.append(bullet)
            else:
                break
        text = _clip("\n\n".join(p for p in parts if p), budget)
        if link and "http" not in text:
            text = f"{text}\n\n{link}"
        return text

    def x_thread(self) -> list[str]:
        custom = self._ov("x")
        if custom:
            return [_clip(custom, 280)]
        posts = [_clip(self.summary or self.title, 280)]
        posts += [_clip(b, 280) for b in self.bullets()[:4]]
        if config.social("x").get("include_link") and not any("http" in p for p in posts):
            posts.append(self.site_url())
        return [p for p in posts if p]

    def threads_text(self) -> str:
        custom = self._ov("threads")
        if custom:
            return _clip(custom, 500)
        parts = [self.summary or self.title]
        for bullet in self.bullets()[:2]:
            if len("\n\n".join(parts + [bullet])) <= 480:  # leave room for the link card line
                parts.append(bullet)
            else:
                break
        return _clip("\n\n".join(p for p in parts if p), 500)

    def instagram_caption(self) -> str:
        custom = self._ov("instagram")
        if custom:
            return _clip(custom, 2200)
        text = self.summary or self.title
        bullets = self.bullets()
        if bullets:
            text += "\n\n" + "\n".join(f"• {b}" for b in bullets[:2])
        tags = self.hashtags()
        if tags:
            text += "\n\n" + tags
        return _clip(text, 2200)

    def facebook_text(self) -> str:
        custom = self._ov("facebook")
        if custom:
            return custom
        parts = [self.title, self.summary]
        bullets = self.bullets()
        if bullets:
            parts.append("\n".join(f"- {b}" for b in bullets[:5]))
        parts.append(self.site_url())
        return "\n\n".join(p for p in parts if p)

    def tiktok_caption(self) -> str:
        custom = self._ov("tiktok")
        if custom:
            return _clip(custom, 2200)
        return _clip(self.summary or self.title, 2200)

    def youtube_title(self) -> str:
        return _clip(str(self._yt_override().get("title") or self.title or self.date), 100)

    def youtube_description(self) -> str:
        custom = self._yt_override().get("description")
        if isinstance(custom, str) and custom.strip():
            return _clip(custom, 5000)
        parts = [self.summary]
        bullets = self.bullets()
        if bullets:
            parts.append("\n".join(f"- {b}" for b in bullets))
        parts.append(f"Full notes: {self.site_url()}")
        tags = self.hashtags()
        if tags:
            parts.append(tags)
        return _clip("\n\n".join(p for p in parts if p), 5000)


def load_day(date: str | None = None) -> Day:
    date = date or dt.date.today().isoformat()
    path = DAILY_DIR / f"{date}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"no daily note for {date} — create one with:  python scripts/ada.py daily --date {date}"
        )
    front, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    media = front.get("media") or {}
    return Day(
        date=date,
        title=front.get("title") or "",
        summary=_plain(str(front.get("summary") or "")),
        tags=list(front.get("tags") or []),
        images=list(media.get("images") or []),
        video=media.get("video") or "",
        overrides=front.get("overrides") or {},
        draft=bool(front.get("draft")),
        body_md=body,
    )


def all_days() -> list[Day]:
    days = []
    for path in sorted(DAILY_DIR.glob("*.md")):
        match = DATE_RE.match(path.name)
        if match:
            days.append(load_day(match.group(1)))
    return sorted(days, key=lambda d: d.date, reverse=True)
