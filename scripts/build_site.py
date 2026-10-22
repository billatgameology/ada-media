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
    description = html.escape(str(proj.get("description") or proj.get("tagline") or ""))
    repo = html.escape(str(proj.get("repo_url") or "#"))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{description}">
<link rel="stylesheet" href="style.css">
<link rel="alternate" type="application/rss+xml" title="{name} feed" href="feed.xml">
</head>
<body>
<header class="site">
  <a class="brand" href="#top">{name}</a>
  <nav aria-label="Project links">
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


def _previous_attempts(data: dict) -> list[dict]:
    attempts = data.get("attempts") or []
    if not isinstance(attempts, list):
        return []
    previous = [
        {**item, "number": item.get("number") or index}
        for index, item in enumerate(attempts, 1)
        if not item.get("current")
    ]
    return sorted(previous, key=lambda item: int(item["number"]), reverse=True)


def _attempts_section(data: dict, attempts: list[dict]) -> str:
    if not attempts:
        return ""
    intro = data.get("intro") or {}
    eyebrow = html.escape(str(intro.get("eyebrow") or ""))
    title = html.escape(str(intro.get("title") or "Previous attempts"))
    body = html.escape(str(intro.get("body") or ""))
    eyebrow_html = f'<p class="eyebrow">{eyebrow}</p>' if eyebrow else ""
    body_html = f'<p class="attempts-intro">{body}</p>' if body else ""

    items = []
    for item in attempts:
        number = str(item["number"]).zfill(2)
        when = html.escape(str(item.get("when") or ""))
        name = html.escape(str(item.get("title") or ""))
        text = html.escape(str(item.get("text") or ""))
        video = str(item.get("youtube") or "").strip()
        video_url = html.escape(str(item.get("youtube_url") or f"https://youtu.be/{video}"))
        classes = "attempt"
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
        items.append(
            f'<li class="{classes}" id="attempt-{html.escape(str(item["number"]))}">'
            f'<div class="attempt-copy">'
            f'<div class="attempt-head"><span class="attempt-number">{html.escape(number)}</span>'
            f'<span class="attempt-when">{when}</span></div>'
            f'<h3>{name}</h3><p class="attempt-text">{text}</p></div>'
            f'{media}{video_link}</li>'
        )

    return f"""<section class="attempts" id="attempts">
{eyebrow_html}
<h2>{title}</h2>
{body_html}
<ol class="attempt-list" reversed start="{html.escape(str(attempts[0]['number']))}">
{''.join(items)}
</ol>
</section>"""


def _timeline_nav(days: list[content.Day], attempts: list[dict]) -> str:
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

    overview = '<a class="nav-overview" href="#latest">Latest progress</a>\n' if days else ""
    if days:
        overview += '<a class="nav-overview" href="#current-log">The current log</a>\n'
    history = ""
    if attempts:
        links = "".join(
            f'<li><a href="#attempt-{html.escape(str(item["number"]))}">'
            f'{html.escape(str(item["number"]).zfill(2))} · '
            f'{html.escape(str(item.get("title") or ""))}</a></li>'
            for item in attempts
        )
        history = f'<p class="nav-label">Previous attempts</p><ul class="nav-attempts">{links}</ul>'
    return f"""<aside class="timeline-nav" aria-label="Timeline navigation">
{overview}<p class="nav-label">Daily log</p>
{''.join(months)}
{history}
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


def _why(day: content.Day) -> str:
    if not day.why:
        return ""
    return (
        '<p class="entry-why"><span>Why it matters</span> '
        f'{html.escape(day.why)}</p>'
    )


def _featured_progress(days: list[content.Day]) -> str:
    if not days:
        return ""
    # Keep the newest recorded demo visible even when a later note has no media.
    day = next((d for d in days if d.gif or d.video or d.images), days[0])
    title = html.escape(day.title or day.date)
    date = html.escape(day.date)
    label = "Latest prototype" if day.gif or day.video or day.images else "Latest progress"
    return f"""<section class="featured" id="latest" aria-labelledby="latest-title">
<div class="featured-heading">
<h2 class="eyebrow" id="latest-title">{label}</h2>
<time datetime="{date}">{html.escape(_short_date(day.date))}, {html.escape(day.date[:4])}</time>
</div>
<h3>{title}</h3>
{_entry_media(day, True)}
<p class="featured-summary">{html.escape(day.summary)}</p>
{_why(day)}
<a class="attempt-link" href="#{date}">Read this build note ↓</a>
</section>"""


def _entry(day: content.Day, first: bool) -> str:
    title = html.escape(day.title or day.date)
    points = "".join(f"<li>{html.escape(item)}</li>" for item in _highlights(day))
    return f"""<li class="entry" id="{html.escape(day.date)}">
<time class="entry-date" datetime="{html.escape(day.date)}">{html.escape(_pretty_date(day.date))}</time>
<h3>{title}</h3>
{_entry_media(day, first)}
<ul class="entry-highlights">{points}</ul>
{_why(day)}
</li>"""


def _timeline_page(days: list[content.Day], proj: dict) -> str:
    name = html.escape(str(proj.get("name") or ""))
    tagline = html.escape(str(proj.get("tagline") or ""))
    description = html.escape(str(proj.get("description") or ""))
    introduction = html.escape(str(proj.get("introduction") or ""))
    attempts_data = content.load_attempts()
    previous = _previous_attempts(attempts_data)
    attempts_html = _attempts_section(attempts_data, previous)
    current = next((item for item in attempts_data.get("attempts", []) if item.get("current")), {})
    current_label = (
        f'<span class="log-attempt">Attempt {html.escape(str(current["number"]))}</span>'
        if current.get("number") else ""
    )
    current_intro = (
        f'<p class="log-intro">{html.escape(str(current["text"]))}</p>'
        if current.get("text") else ""
    )
    actions = '<a href="#latest">Latest progress ↓</a>' if days else ""
    if attempts_html:
        actions += '<a href="#attempts">Previous attempts ↓</a>'
    entries = "".join(_entry(day, index == 0) for index, day in enumerate(days))
    body = f"""<main class="layout">
{_timeline_nav(days, previous)}
<div class="intro">
<p class="eyebrow">An open experiment · Development journal</p>
<h1 id="top">{name}</h1>
<p class="tagline">{tagline}</p>
<p class="project-description">{description}</p>
<p class="project-introduction">{introduction}</p>
<div class="intro-actions">{actions}</div>
</div>
<div class="timeline">
{_featured_progress(days)}
<h2 class="log-title" id="current-log">The current log {current_label}</h2>
{current_intro}
<ol class="timeline-list">
{entries}
</ol>
{attempts_html}
</div>
</main>
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
        body_html = f"<p>{html.escape(day.summary)}</p><ul>{points}</ul>{_why(day)}".replace("]]>", "]]&gt;")
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
