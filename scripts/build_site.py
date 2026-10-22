"""Render the daily notes into the static site in docs/ (served by GitHub Pages)."""
from __future__ import annotations

import datetime as dt
import email.utils
import html
import shutil
from pathlib import Path

import markdown

from lib import config, content

MD_EXTENSIONS = ["fenced_code", "tables", "sane_lists", "nl2br"]


def render_md(text: str) -> str:
    return markdown.markdown(text, extensions=MD_EXTENSIONS)


def _shell(proj: dict, title: str, body: str) -> str:
    name = html.escape(str(proj.get("name") or ""))
    tagline = html.escape(str(proj.get("tagline") or ""))
    repo = html.escape(str(proj.get("repo_url") or "#"))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{tagline}">
<link rel="stylesheet" href="style.css">
<link rel="alternate" type="application/rss+xml" title="{name} feed" href="feed.xml">
</head>
<body>
<header class="site">
  <a class="brand" href="index.html">{name}</a>
  <nav>
    <a href="{repo}">repo</a>
    <a href="feed.xml">rss</a>
  </nav>
</header>
{body}
<footer class="site">
  <p>{tagline}</p>
</footer>
</body>
</html>
"""


def _post_page(day: content.Day, proj: dict) -> str:
    title = day.title or day.date
    media_html = ""
    if day.gif:
        media_html += (f'<p class="media"><img src="media/{html.escape(str(day.gif))}" '
                       f'alt="{html.escape(title)}"></p>\n')
    for img in day.images:
        media_html += f'<p class="media"><img src="media/{html.escape(str(img))}" alt=""></p>\n'
    if day.video:
        media_html += f'<p class="media"><video controls src="media/{html.escape(str(day.video))}"></video></p>\n'
    body = f"""<article>
<h1>{html.escape(title)}</h1>
<p class="meta"><time>{html.escape(day.date)}</time></p>
{media_html}<div class="post-body">{render_md(day.body_md)}</div>
</article>"""
    return _shell(proj, f"{title} — {proj.get('name', '')}", body)


def _index_page(days: list[content.Day], proj: dict) -> str:
    items = []
    for day in days:
        cover = ""
        if day.gif:
            candidate = str(Path(day.gif).with_suffix(".jpg"))
            if (content.MEDIA_DIR / candidate).exists():
                cover = candidate
        thumb = ""
        if cover:
            thumb = (f'<a class="thumb-link" href="{html.escape(day.site_filename())}">'
                     f'<img class="thumb" src="media/{html.escape(cover)}" '
                     f'alt="{html.escape(day.title or day.date)}" loading="lazy"></a>')
        items.append(
            f"""<li>
{thumb}<div class="day-text">
<span class="date">{html.escape(day.date)}</span>
<a class="title" href="{html.escape(day.site_filename())}">{html.escape(day.title or day.date)}</a>
<p>{html.escape(day.summary)}</p>
</div>
</li>"""
        )
    body = f"""<h1>{html.escape(str(proj.get('name') or ''))}</h1>
<div class="post-body"><p>{html.escape(str(proj.get('tagline') or ''))}</p></div>
<ul class="feed">
{''.join(items)}
</ul>"""
    return _shell(proj, f"{proj.get('name', '')} — {proj.get('tagline', '')}", body)


def _feed_xml(days: list[content.Day], proj: dict) -> str:
    site = str(proj.get("site_url") or "").rstrip("/")
    items = []
    for day in days[:20]:
        url = f"{site}/{day.site_filename()}"
        try:
            when = dt.datetime.fromisoformat(day.date).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            when = dt.datetime.now(dt.timezone.utc)
        body_html = render_md(day.body_md).replace("]]>", "]]&gt;")
        items.append(
            f"""<item>
<title>{html.escape(day.title or day.date)}</title>
<link>{html.escape(url)}</link>
<guid>{html.escape(url)}</guid>
<pubDate>{email.utils.format_datetime(when)}</pubDate>
<description>{html.escape(day.summary)}</description>
<content:encoded><![CDATA[{body_html}]]></content:encoded>
</item>"""
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
<title>{html.escape(str(proj.get('name') or ''))}</title>
<link>{html.escape(site)}/</link>
<description>{html.escape(str(proj.get('tagline') or ''))}</description>
{''.join(items)}
</channel>
</rss>
"""


def build(verbose: bool = True) -> Path:
    root = config.root()
    proj = config.project()
    docs = root / "docs"
    docs.mkdir(exist_ok=True)
    days = [d for d in content.all_days() if not d.draft]

    for day in days:
        (docs / day.site_filename()).write_text(_post_page(day, proj), encoding="utf-8")
    (docs / "index.html").write_text(_index_page(days, proj), encoding="utf-8")
    (docs / "feed.xml").write_text(_feed_xml(days, proj), encoding="utf-8")
    (docs / ".nojekyll").write_text("", encoding="utf-8")
    shutil.copyfile(root / "site_assets" / "style.css", docs / "style.css")

    media_src = root / "content" / "media"
    media_dst = docs / "media"
    copied, large = 0, []
    for path in sorted(media_src.rglob("*")):
        if path.is_dir() or path.name.startswith("."):
            continue
        rel = path.relative_to(media_src)
        target = media_dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        copied += 1
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > 95:
            large.append(f"{rel} ({size_mb:.0f} MB)")

    if verbose:
        print(f"built {len(days)} note(s) → docs/  ({copied} media file(s))")
        for item in large:
            print(f"  warning: {item} is near GitHub's 100 MB file limit")
    return docs / "index.html"
