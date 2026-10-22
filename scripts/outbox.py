"""Generate copy-paste-ready posts for manual publishing.

Everything lands in outbox/<date>/: one plain-text file per platform (paste it into
the app as-is) plus manifest.txt with character counts, media to attach and warnings.
Nothing is sent anywhere — the repo only does the content work.
"""
from __future__ import annotations

from pathlib import Path

from lib import config, content


def _attach(day: content.Day, rel: str, kind: str) -> str:
    marker = "" if day.media_path(rel).exists() else "  ⚠ file missing locally"
    return f"attach {kind}: {rel}{marker}  ·  from phone: {day.media_url(rel)}"


def _threads_text(day: content.Day) -> str:
    text = day.threads_text()
    if day.video or day.gif or day.images:
        return text
    link = day.site_url()
    budget = 500 - len(link) - 2
    if len(text) > budget:
        text = text[: budget - 1].rstrip() + "…"
    return f"{text}\n\n{link}"


def generate(day: content.Day) -> Path:
    if day.draft:
        raise RuntimeError(f"{day.date} is marked 'draft: true' — remove that line to build its outbox")

    social = config.social
    out_dir = config.root() / "outbox" / day.date
    out_dir.mkdir(parents=True, exist_ok=True)

    files: list[tuple[str, str]] = []
    blocks: list[str] = []
    warnings: list[str] = []

    # ── X / Twitter ────────────────────────────────────────────────────
    if social("x").get("enabled"):
        posts = day.x_thread() if social("x").get("thread") else [day.x_text()]
        files.append(("x.txt", "\n\n---\n\n".join(posts) + "\n"))
        mode = f"thread of {len(posts)} — paste each block as a reply" if len(posts) > 1 else "single post"
        link = "link included" if any("http" in p for p in posts) else "no link (x.include_link in config.yaml)"
        lines = [f"X / Twitter — x.txt  ·  {mode}  ·  longest {max(len(p) for p in posts)}/280 chars  ·  {link}"]
        if day.gif:
            lines.append(f"  {_attach(day, day.gif, 'GIF')}")
        lines += [f"  {_attach(day, rel, 'image')}" for rel in day.images[:4]]
        blocks.append("\n".join(lines))

    # ── Threads ────────────────────────────────────────────────────────
    if social("threads").get("enabled"):
        text = _threads_text(day)
        files.append(("threads.txt", text + "\n"))
        kind = "media post" if (day.video or day.gif or day.images) else "text post (link preview card)"
        lines = [f"Threads — threads.txt  ·  {kind}  ·  {len(text)}/500 chars"]
        if day.video:
            lines.append(f"  {_attach(day, day.video, 'video')}")
        elif day.gif:
            lines.append(f"  {_attach(day, day.gif, 'GIF')}")
        elif day.images:
            lines.append(f"  {_attach(day, day.images[0], 'image')}")
        blocks.append("\n".join(lines))

    # ── Instagram ──────────────────────────────────────────────────────
    if social("instagram").get("enabled"):
        caption = day.instagram_caption()
        files.append(("instagram.txt", caption + "\n"))
        if day.video:
            lines = [f"Instagram — instagram.txt  ·  reel  ·  caption {len(caption)}/2200 chars",
                     f"  {_attach(day, day.video, 'video')}"]
        elif day.images:
            kind = (f"carousel of {min(len(day.images), 10)} — attach in listed order"
                    if len(day.images) > 1 else "single image")
            lines = [f"Instagram — instagram.txt  ·  {kind}  ·  caption {len(caption)}/2200 chars"]
            lines += [f"  {_attach(day, rel, 'image')}" for rel in day.images[:10]]
        elif day.gif:
            cover = str(Path(day.gif).with_suffix(".jpg"))
            if day.media_path(cover).exists():
                lines = [f"Instagram — instagram.txt  ·  JPEG cover  ·  caption {len(caption)}/2200 chars",
                         f"  {_attach(day, cover, 'JPEG cover')}",
                         f"  GIF for other platforms: {day.gif}"]
            else:
                lines = [f"Instagram — instagram.txt  ·  caption {len(caption)}/2200 chars  ·  GIF won't animate",
                         f"  preview only: {day.gif}",
                         "  attach a JPEG cover or the video instead"]
                warnings.append("Instagram does not animate GIF uploads — use a JPEG cover or the video, or skip Instagram")
        else:
            lines = ["Instagram — instagram.txt  ·  caption ready, but NO media"]
            warnings.append("Instagram has no text-only posts — add media.images (JPEG) or media.video, then re-run outbox")
        for rel in day.images:
            if not str(rel).lower().endswith((".jpg", ".jpeg")):
                warnings.append(f"{rel} is not a JPEG — convert with: sips -s format jpeg <file> --out <file>.jpg")
        blocks.append("\n".join(lines))

    # ── Facebook ───────────────────────────────────────────────────────
    if social("facebook").get("enabled"):
        text = day.facebook_text()
        files.append(("facebook.txt", text + "\n"))
        lines = [f"Facebook — facebook.txt  ·  {len(text)} chars  ·  site link included"]
        if day.gif:
            lines.append(f"  {_attach(day, day.gif, 'GIF')}")
        lines += [f"  {_attach(day, rel, 'photo')}" for rel in day.images[:10]]
        blocks.append("\n".join(lines))

    # ── TikTok ─────────────────────────────────────────────────────────
    if social("tiktok").get("enabled"):
        caption = day.tiktok_caption()
        files.append(("tiktok.txt", caption + "\n"))
        if day.video:
            lines = [f"TikTok — tiktok.txt  ·  caption for the app upload  ·  {len(caption)} chars",
                     f"  {_attach(day, day.video, 'video')}"]
        else:
            lines = ["TikTok — tiktok.txt  ·  caption ready, but there is no video"]
            warnings.append("TikTok needs a video — add media.video and re-run outbox, or skip it today")
        blocks.append("\n".join(lines))

    # ── YouTube ────────────────────────────────────────────────────────
    if social("youtube").get("enabled"):
        title = day.youtube_title()
        description = day.youtube_description()
        files.append(("youtube.txt", f"TITLE\n{title}\n\nDESCRIPTION\n{description}\n"))
        if day.video:
            lines = [f"YouTube — youtube.txt  ·  title {len(title)}/100 chars  ·  description {len(description)}/5000",
                     f"  {_attach(day, day.video, 'video')}",
                     "  vertical and ≤3 min? it becomes a Short — add #Shorts to the description"]
        else:
            lines = ["YouTube — youtube.txt  ·  title/description ready, but there is no video"]
            warnings.append("YouTube needs a video — add media.video and re-run outbox, or skip it today")
        blocks.append("\n".join(lines))

    for filename, text in files:
        (out_dir / filename).write_text(text, encoding="utf-8")

    manifest = [
        f"ada-media — posts for {day.date}",
        f"site post: {day.site_url()}",
        "",
        "copy each file into its platform's composer, attach the listed media, post.",
        "per-platform details: guide/POSTING.md",
        "",
    ] + blocks
    if warnings:
        manifest += ["", "warnings:"] + [f"  - {w}" for w in warnings]
    (out_dir / "manifest.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    return out_dir
