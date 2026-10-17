# ada-media — one repo, every platform

A daily build log that publishes itself. You write one markdown file per day; a small
Python CLI turns it into posts for **X, Threads, Instagram, Facebook, TikTok and
YouTube** — and builds the public page you're reading this repo for.

No CMS, no scheduler subscription, no dashboard. Content lives as plain files, the
site is served by GitHub Pages from `docs/`, and the publishing scripts are yours.

## How a day works

```bash
source .venv/bin/activate              # after the one-time setup below

python scripts/ada.py daily            # 1. create content/daily/YYYY-MM-DD.md (prefilled with recent commits)
# ...edit that file: title, summary, bullets, optionally drop media in content/media/...

python scripts/ada.py build            # 2. rebuild the site into docs/
git add -A && git commit -m "daily: $(date +%F)" && git push   # 3. site goes live

python scripts/ada.py publish          # 4. DRY RUN: previews the exact post for every platform
python scripts/ada.py publish --live   # 5. publish
```

`publish` is a dry run unless you pass `--live`. Nothing ever posts by accident.

## One-time setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env    # fill in credentials as you connect each platform
```

Then connect platforms using **`guide/SETUP.md`** — one section per platform, click by click.
Check everything with:

```bash
python scripts/ada.py status
```

## What this repo contains

| Path | What it is |
| --- | --- |
| `content/daily/` | One markdown file per day — the single source of truth |
| `content/media/` | Images and short videos referenced by daily notes |
| `content/templates/` | The daily note template |
| `scripts/ada.py` | CLI: `daily`, `build`, `preview`, `publish`, `status`, `auth` |
| `scripts/platforms/` | One module per platform (publish + preview logic) |
| `docs/` | The built static site + RSS feed (served by GitHub Pages) |
| `site_assets/` | Stylesheet for the built site |
| `guide/` | `PLAN.md` (roadmap), `SETUP.md` (accounts), `PLAYBOOK.md` (content strategy) |
| `.state/` | What was published where (so nothing double-posts) |

## The honest platform reality (October 2026)

| Platform | API cost | What runs automatically | The catch |
| --- | --- | --- | --- |
| **X / Twitter** | Pay-per-use (~$0.015/post; **$0.20 with a link**) | Text posts (+ threads, + images) | No free tier for new developers since Feb 2026; a one-time $5 of credits lasts ~a year at 1 post/day |
| **Threads** | Free | Text, images, video, link cards | Media must be hosted at a public URL (this repo's Pages site provides one) |
| **Instagram** | Free | Images, reels, carousels | Professional account required; images must be **JPEG**; media must be at a public URL |
| **Facebook Page** | Free | Text + link posts | Posts are only visible **to admins** until your Meta app passes App Review |
| **TikTok** | Free | Upload to your TikTok **inbox as a draft** (you tap publish) | Public API posting (Direct Post) requires passing an app audit — optional, later |
| **YouTube** | Free | Long-form + Shorts uploads | Daily quota (~6 uploads/day) — never a problem at this scale |

Details, decisions and phases: `guide/PLAN.md`. Content strategy and per-platform
tips: `guide/PLAYBOOK.md`.

## Site

The page you're publishing to: <https://billatgameology.github.io/ada-media>
RSS: <https://billatgameology.github.io/ada-media/feed.xml>
