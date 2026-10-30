"""Render the daily notes into one static timeline in docs/ (served by GitHub Pages)."""
from __future__ import annotations

import datetime as dt
import email.utils
import hashlib
import html
import shutil
from pathlib import Path

from lib import config, content


def _shell(proj: dict, title: str, body: str) -> str:
    name = html.escape(str(proj.get("name") or ""))
    tagline = html.escape(str(proj.get("tagline") or ""))
    description = html.escape(str(proj.get("description") or proj.get("tagline") or ""))
    repo = html.escape(str(proj.get("repo_url") or "#"))
    style_version = hashlib.sha256((config.root() / "site_assets" / "style.css").read_bytes()).hexdigest()[:12]
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{description}">
<link rel="stylesheet" href="style.css?v={style_version}">
<link rel="icon" type="image/svg+xml" href="favicon.svg">
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
                f'allow="accelerometer; autoplay; clipboard-write; compute-pressure; encrypted-media; gyroscope; picture-in-picture; web-share" '
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


def _ordinal(number: int) -> str:
    suffix = "th" if 10 <= number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def _timeline_nav(days: list[content.Day], attempts: list[dict]) -> str:
    groups: dict[str, list[content.Day]] = {}
    for day in days:
        groups.setdefault(day.date[:7], []).append(day)

    months = []
    for _month, entries in groups.items():
        links = "".join(
            f'<li><a href="#{html.escape(day.date)}">{html.escape(_short_date(day.date))}</a></li>'
            for day in entries
        )
        months.append(
            f'<details class="nav-month">'
            f'<summary>{html.escape(_month_label(entries[0].date))}</summary>'
            f'<ul>{links}</ul>'
            f'</details>'
        )

    overview = (
        '<a class="nav-overview" href="#roadmap">Development timeline</a>\n'
        '<a class="nav-overview" href="#latest">Latest progress</a>\n'
    ) if days else ""
    history = ""
    if attempts:
        links = "".join(
            f'<li><a href="#attempt-{html.escape(str(item["number"]))}">'
            f'{html.escape(_ordinal(int(item["number"])))} '
            f'({html.escape(str(item.get("when") or "").rsplit(" ", 1)[-1])}) - '
            f'{html.escape(str(item.get("title") or ""))}</a></li>'
            for item in attempts
        )
        history = f'<p class="nav-label">Previous attempts</p><ul class="nav-attempts">{links}</ul>'
    return f"""<aside class="timeline-nav" aria-label="Timeline navigation">
<details class="nav-browser" open>
<summary class="nav-toggle">Browse the log</summary>
<div class="nav-content">
{overview}<p class="nav-label">Daily log</p>
{''.join(months)}
{history}
<a class="nav-top" href="#top">Back to top</a>
</div>
</details>
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


def _demo_link(day: content.Day) -> str:
    if not day.demo_url:
        return ""
    return (
        f'<p class="video-link"><a href="{html.escape(day.demo_url)}" target="_blank" rel="noopener">'
        'Watch the demo ↗</a></p>'
    )


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


def _entry(day: content.Day, first: bool) -> str:
    title = html.escape(day.title or day.date)
    if day.demo_url:
        title = (
            f'<a href="{html.escape(day.demo_url)}" target="_blank" rel="noopener">'
            f'{title}</a>'
        )
    points = "".join(f"<li>{html.escape(item)}</li>" for item in _highlights(day))
    return f"""<li class="entry" id="{html.escape(day.date)}">
<time class="entry-date" datetime="{html.escape(day.date)}">{html.escape(_pretty_date(day.date))}</time>
<h2>{title}</h2>
{_entry_media(day, first)}
<ul class="entry-highlights">{points}</ul>
{_why(day)}
</li>"""


def _roadmap_section() -> str:
    return """<section class="roadmap" id="roadmap" aria-labelledby="roadmap-title">
<div class="roadmap-head">
<p class="eyebrow">Development timeline</p>
<h2 id="roadmap-title">Where this is going</h2>
<p class="roadmap-intro">A sequence of gates, not a calendar. Basic operations come first; the content workflow and MVP are earned on top. After the MVP, the roadmap splits into three parallel tracks.</p>
</div>
<ol class="roadmap-list">
<li class="roadmap-step is-now">
<div class="roadmap-card">
<p class="roadmap-kicker">Phase 1 · We are here</p>
<h3>Basic operations</h3>
<p class="roadmap-goal">Make the room dependable enough to build on.</p>
<ul class="roadmap-points">
<li>Voice, panels, media and gestures work without developer rescue.</li>
<li>Layouts, notes and positions survive save, reload and restore.</li>
<li>Failures are explicit and recoverable — no silent success.</li>
</ul>
<p class="roadmap-focus">Current focus: panel save/restore · voice overlap · whiteboard placement</p>
</div>
</li>
<li class="roadmap-step">
<div class="roadmap-card">
<p class="roadmap-kicker">Phase 2</p>
<h3>Content creation workflow</h3>
<p class="roadmap-goal">Complete one real creative job inside the room.</p>
<ul class="roadmap-points">
<li>Collect references, arrange them, and create the artifact in place.</li>
<li>The full loop survives interruption, save and reload.</li>
<li>The result is shareable without another tool doing the real work.</li>
</ul>
</div>
</li>
<li class="roadmap-step">
<div class="roadmap-card">
<p class="roadmap-kicker">Phase 3</p>
<h3>MVP</h3>
<p class="roadmap-goal">A first-time user can finish the core job in one session.</p>
<ul class="roadmap-points">
<li>One workflow runs end-to-end at acceptable speed.</li>
<li>Setup, onboarding and recovery no longer need the builder.</li>
<li>Real users can try it and show us where it breaks.</li>
</ul>
</div>
</li>
</ol>
<div class="roadmap-split">
<p class="roadmap-split-label">After the MVP gate — three parallel tracks</p>
<div class="roadmap-tracks">
<article class="roadmap-track">
<div class="roadmap-track-head">
<p class="roadmap-kicker">Track A</p>
<h3>Refine content creation</h3>
</div>
<div class="roadmap-track-body">
<p class="roadmap-goal">Make the proven workflow deeper, faster and worth returning to.</p>
<ul class="roadmap-points">
<li>Fix the friction real usage exposes.</li>
<li>Add templates, deeper editing and durable projects.</li>
</ul>
</div>
</article>
<article class="roadmap-track">
<div class="roadmap-track-head">
<p class="roadmap-kicker">Track B</p>
<h3>Use case #2 workflow</h3>
</div>
<div class="roadmap-track-body">
<p class="roadmap-goal">Test whether the same core can carry a second job.</p>
<ul class="roadmap-points">
<li>Name the use case and its success criteria.</li>
<li>Reuse the primitives; build a separate end-to-end workflow.</li>
</ul>
<p class="roadmap-open">Open decision: use case to be named.</p>
</div>
</article>
<article class="roadmap-track">
<div class="roadmap-track-head">
<p class="roadmap-kicker">Track C</p>
<h3>Multi-user room</h3>
</div>
<div class="roadmap-track-body">
<p class="roadmap-goal">Let several people join the same room and work with Ada together.</p>
<ul class="roadmap-points">
<li>Shared presence, panels, media and Ada state.</li>
<li>Per-person voice and controls without collisions.</li>
<li>Join permissions, identity and recovery when someone drops.</li>
</ul>
<p class="roadmap-open">Builds on the single-user room gate.</p>
</div>
</article>
</div>
</div>
<p class="roadmap-note">Working outline, 30 October 2026. No calendar estimates are shown because the basic-operations gate is still open.</p>
</section>"""


def _timeline_page(days: list[content.Day], proj: dict) -> str:
    name = html.escape(str(proj.get("name") or ""))
    tagline = html.escape(str(proj.get("tagline") or ""))
    description = html.escape(str(proj.get("description") or ""))
    introduction = html.escape(str(proj.get("introduction") or ""))
    attempts_data = content.load_attempts()
    previous = _previous_attempts(attempts_data)
    attempts_html = _attempts_section(attempts_data, previous)
    entries = "".join(_entry(day, index == 0) for index, day in enumerate(days))
    body = f"""<main class="layout">
{_timeline_nav(days, previous)}
<div class="intro">
<h1 id="top">{name}</h1>
<p class="tagline">{tagline}</p>
<p class="project-description">{description}</p>
<p class="project-introduction">{introduction}</p>
</div>
{_roadmap_section()}
<div class="timeline" id="latest">
<header class="devlog-head">
<p class="eyebrow">Devlog</p>
<h2>Latest progress</h2>
<p class="devlog-intro">What changed, what broke, and what comes next — newest first.</p>
</header>
<ol class="timeline-list" id="current-log" aria-label="Daily log">
{entries}
</ol>
{attempts_html}
</div>
</main>
<script>
(() => {{
  const browser = document.querySelector(".nav-browser");
  const mobile = matchMedia("(max-width: 820px)");
  const syncBrowser = () => {{ browser.open = !mobile.matches; }};
  mobile.addEventListener("change", syncBrowser);
  syncBrowser();
  browser.addEventListener("click", (event) => {{
    if (mobile.matches && event.target.closest("a[href^='#']")) browser.open = false;
  }});
  const sync = () => {{
    const hash = location.hash;
    document.querySelectorAll(".timeline-nav a").forEach((link) => {{
      const active = link.getAttribute("href") === hash;
      link.classList.toggle("active", active);
      if (active) {{
        link.setAttribute("aria-current", "location");
        const month = link.closest(".nav-month");
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
        body_html = f"<p>{html.escape(day.summary)}</p>{_demo_link(day)}<ul>{points}</ul>{_why(day)}".replace("]]>", "]]&gt;")
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
    for asset in ("style.css", "favicon.svg"):
        shutil.copyfile(root / "site_assets" / asset, docs / asset)

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
