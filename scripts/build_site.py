"""Render the daily notes into one static timeline in docs/ (served by GitHub Pages)."""
from __future__ import annotations

import datetime as dt
import email.utils
import html
import shutil
from pathlib import Path

from lib import config, content


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
  <a class="brand" href="#top">{name}</a>
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


def _date(value: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def _pretty_date(value: str) -> str:
    day = _date(value)
    if not day:
        return value
    return f"{day.strftime('%A, %B')} {day.day}, {day.year}"


def _short_date(value: str) -> str:
    day = _date(value)
    if not day:
        return value
    return f"{day.strftime('%b')} {day.day}"


def _month_label(value: str) -> str:
    day = _date(value)
    if not day:
        return value
    return f"{day.strftime('%B')} {day.year}"


def _attempts_section(data: dict) -> str:
    attempts = data.get("attempts") or []
    if not isinstance(attempts, list) or not attempts:
        return ""
    intro = data.get("intro") or {}
    eyebrow = html.escape(str(intro.get("eyebrow") or ""))
    title = html.escape(str(intro.get("title") or "Four starts"))
    body = html.escape(str(intro.get("body") or ""))
    eyebrow_html = f'<p class="eyebrow">{eyebrow}</p>' if eyebrow else ""
    body_html = f'<p class="attempts-intro">{body}</p>' if body else ""

    items = []
    for index, item in enumerate(attempts, 1):
        number = str(item.get("number") or index).zfill(2)
        when = html.escape(str(item.get("when") or ""))
        name = html.escape(str(item.get("title") or ""))
        text = html.escape(str(item.get("text") or ""))
        video = str(item.get("youtube") or "").strip()
        video_url = html.escape(str(item.get("youtube_url") or f"https://youtu.be/{video}"))
        classes = "attempt"
        if item.get("current"):
            classes += " current"
        if item.get("vertical"):
            classes += " has-short"
        media = ""
        video_link = ""
        if video:
            frame_class = "video-frame vertical" if item.get("vertical") else "video-frame"
            media = (
                f'<figure class="{frame_class}">'
                f'<iframe src="https://www.youtube-nocookie.com/embed/{html.escape(video)}" '
                f'title="Ada attempt {number}: {name}" loading="lazy" '
                f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
                f'allowfullscreen></iframe></figure>'
            )
            video_link = (
                f'<p class="video-link"><a href="{video_url}" target="_blank" rel="noopener">'
                f'Watch on YouTube ↗</a></p>'
            )
        action = ""
        if item.get("current"):
            action = '<a class="attempt-link" href="#current-log">Read the current log ↓</a>'
        items.append(
            f'<li class="{classes}">'
            f'<div class="attempt-copy">'
            f'<div class="attempt-head"><span class="attempt-number">{html.escape(number)}</span>'
            f'<span class="attempt-when">{when}</span></div>'
            f'<h3>{name}</h3><p class="attempt-text">{text}</p>{action}</div>'
            f'{media}{video_link}</li>'
        )

    return f"""<section class="attempts" id="attempts">
{eyebrow_html}
<h2>{title}</h2>
{body_html}
<ol class="attempt-list">
{''.join(items)}
</ol>
</section>"""


def _timeline_nav(days: list[content.Day], has_attempts: bool = False) -> str:
    groups: dict[str, list[content.Day]] = {}
    for day in days:
        groups.setdefault(day.date[:7], []).append(day)

    months = []
    for index, (_month, entries) in enumerate(groups.items()):
        links = "".join(
            f'<li><a href="#{html.escape(day.date)}">{html.escape(_short_date(day.date))}</a></li>'
            for day in entries
        )
        opened = " open" if index == 0 else ""
        months.append(
            f'<details class="nav-month"{opened}>'
            f'<summary>{html.escape(_month_label(entries[0].date))}</summary>'
            f'<ul>{links}</ul>'
            f'</details>'
        )

    overview = '<a class="nav-overview" href="#attempts">The four attempts</a>\n' if has_attempts else ""
    label = "Daily log" if has_attempts else "Jump to"
    return f"""<aside class="timeline-nav" aria-label="Timeline navigation">
{overview}<p class="nav-label">{label}</p>
{''.join(months)}
<a class="nav-top" href="#top">Back to top</a>
</aside>"""


def _entry_media(day: content.Day, first: bool) -> str:
    title = html.escape(day.title or day.date)
    if day.gif:
        loading = "eager" if first else "lazy"
        return (
            f'<figure class="entry-media">'
            f'<img src="media/{html.escape(str(day.gif))}" alt="{title}" '
            f'width="640" height="360" loading="{loading}" decoding="async">'
            f'</figure>'
        )
    if day.video:
        return (
            f'<figure class="entry-media">'
            f'<video controls autoplay loop muted playsinline '
            f'src="media/{html.escape(str(day.video))}"></video>'
            f'</figure>'
        )
    images = "".join(
        f'<img src="media/{html.escape(str(img))}" alt="">'
        for img in day.images
    )
    if images:
        return f'<figure class="entry-media">{images}</figure>'
    return ""


def _highlights(day: content.Day) -> list[str]:
    if day.highlights:
        return day.highlights[:3]
    fallback = day.code_bullets()[:2] + day.demo_bullets()[:1]
    if not fallback:
        fallback = day.bullets()[:3]
    return fallback


def _entry(day: content.Day, first: bool) -> str:
    title = html.escape(day.title or day.date)
    points = "".join(f"<li>{html.escape(item)}</li>" for item in _highlights(day))
    return f"""<li class="entry" id="{html.escape(day.date)}">
<time class="entry-date" datetime="{html.escape(day.date)}">{html.escape(_pretty_date(day.date))}</time>
<h3>{title}</h3>
{_entry_media(day, first)}
<ul class="entry-highlights">{points}</ul>
</li>"""


def _timeline_page(days: list[content.Day], proj: dict) -> str:
    name = html.escape(str(proj.get("name") or ""))
    tagline = html.escape(str(proj.get("tagline") or ""))
    attempts_html = _attempts_section(content.load_attempts())
    entries = "".join(_entry(day, index == 0) for index, day in enumerate(days))
    body = f"""<div class="layout">
{_timeline_nav(days, bool(attempts_html))}
<div class="intro">
<h1 id="top">{name}</h1>
<p class="tagline">{tagline}</p>
</div>
<main class="timeline">
{attempts_html}
<h2 class="log-title" id="current-log">The current log</h2>
<ol class="timeline-list">
{entries}
</ol>
</main>
</div>
<script>
(() => {{
  const sync = () => {{
    const hash = location.hash;
    document.querySelectorAll(".timeline-nav a").forEach((link) => {{
      const active = link.getAttribute("href") === hash;
      link.classList.toggle("active", active);
      if (active) {{
        link.setAttribute("aria-current", "location");
        const month = link.closest("details");
        if (month) month.open = true;
      }} else {{
        link.removeAttribute("aria-current");
      }}
    }});
  }};
  addEventListener("hashchange", sync);
  sync();
}})();
</script>"""
    return _shell(proj, f"{proj.get('name', '')} — {proj.get('tagline', '')}", body)


def _feed_xml(days: list[content.Day], proj: dict) -> str:
    site = str(proj.get("site_url") or "").rstrip("/")
    items = []
    for day in days[:20]:
        url = f"{site}/#{day.date}"
        try:
            when = dt.datetime.fromisoformat(day.date).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            when = dt.datetime.now(dt.timezone.utc)
        points = "".join(f"<li>{html.escape(item)}</li>" for item in _highlights(day))
        body_html = f"<p>{html.escape(day.summary)}</p><ul>{points}</ul>".replace("]]>", "]]&gt;")
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

    media_src = root / "content" / "media"
    for day in days:
        for rel in [day.gif, day.video, *day.images]:
            if rel and not (media_src / rel).is_file():
                raise SystemExit(f"missing media for {day.date}: {rel}")
    for path in media_src.rglob("*"):
        if path.is_file() and path.stat().st_size == 0:
            raise SystemExit(f"empty media file: {path.relative_to(media_src)}")

    # The site is one page now; remove old per-day pages from previous builds.
    for old in docs.glob("*.html"):
        if old.name != "index.html":
            old.unlink()

    (docs / "index.html").write_text(_timeline_page(days, proj), encoding="utf-8")
    (docs / "feed.xml").write_text(_feed_xml(days, proj), encoding="utf-8")
    (docs / ".nojekyll").write_text("", encoding="utf-8")
    shutil.copyfile(root / "site_assets" / "style.css", docs / "style.css")

    media_dst = docs / "media"
    if media_dst.exists():
        shutil.rmtree(media_dst)
    copied, large = 0, []
    for path in sorted(media_src.rglob("*")):
        if path.is_dir() or path.name.startswith("."):
            continue
        rel = path.relative_to(media_src)
        size = path.stat().st_size
        if size == 0:
            raise SystemExit(f"refusing to publish empty media file: {rel}")
        target = media_dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        copied += 1
        size_mb = size / (1024 * 1024)
        if size_mb > 95:
            large.append(f"{rel} ({size_mb:.0f} MB)")

    if verbose:
        print(f"built {len(days)} timeline entries → docs/  ({copied} media file(s))")
        for item in large:
            print(f"  warning: {item} is near GitHub's 100 MB file limit")
    return docs / "index.html"
