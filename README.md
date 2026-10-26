# ada-media — a daily build log, and a content studio

One repo for the whole social side of the project. Write **one markdown note a day**;
the repo turns it into a single-page public timeline (GitHub Pages) plus
copy-paste-ready posts for **X, Threads, Instagram, Facebook, TikTok and YouTube**.
You post them yourself — no API keys, tokens, audits, per-post fees or rate limits
to babysit. The content is the hard part; the plumbing shouldn't be.

## How a day works

```bash
source .venv/bin/activate

python scripts/ada.py daily          # 1. create content/daily/YYYY-MM-DD.md (prefilled with recent code commits)
# ...edit it: title, summary, 3 highlights, "In code" and "In the headset" bullets...
#    code:     python scripts/ada.py code --date YYYY-MM-DD --stat
#    evidence: python scripts/ada.py find --date YYYY-MM-DD --grep "phrase"
#    preview:  python scripts/ada.py gif --date YYYY-MM-DD  (2-10s loop from content/gifs.yaml)
# ...drop media in content/media/ if you have it...

python scripts/ada.py outbox         # 2. write copy-paste-ready posts to outbox/<date>/
python scripts/ada.py build          # 3. rebuild the site
git add -A && git commit -m "daily: $(date +%F)" && git push

# 4. open outbox/<date>/manifest.txt — paste each .txt file into its platform's
#    composer, attach the media it lists, post. One note, six posts, ~10 minutes.
```

Posting from your phone works too: the outbox is committed, so open the repo (or the
site) on mobile, copy, paste, post. Media URLs for download are in the manifest.

## One-time setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## What's here

| Path | What it is |
| --- | --- |
| `content/daily/` | One markdown file per day — the single source of truth |
| `content/media/` | Images, short videos and generated GIF previews referenced by daily notes |
| `content/gifs.yaml` | The chosen 2–10s GIF moment for each day (recording + start + duration) |
| `content/attempts.yaml` | Attempt history and YouTube links |
| `content/templates/` | The daily note template |
| `scripts/ada.py` | CLI: `daily`, `outbox`, `build`, `preview`, `status`, `catalog`, `transcribe`, `watch`, `clip`, `gif`, `story`, `code`, `find` |
| `scripts/outbox.py` | Turns a note into the per-platform post files |
| `scripts/catalog.py` | Scans the watch folders into a video catalog |
| `scripts/transcribe.py` | Local Whisper transcription of cataloged recordings |
| `catalog/` | Video catalog + transcripts (local, gitignored — `guide/MEDIA.md`) |
| `outbox/` | Generated posts, one folder per day — copy-paste-ready (+ manifest) |
| `docs/` | The built single-page timeline + RSS (served by GitHub Pages) |
| `site_assets/` | Stylesheet for the built site |
| `guide/` | `PLAYBOOK.md` (what to write), `POSTING.md` (how to post), `PLAN.md` (roadmap), `MEDIA.md` (video library) |

## One note → six versions

The outbox derives everything from the note's frontmatter and bullets:

| Field | Feeds |
| --- | --- |
| `title` | Timeline headline, YouTube title, Facebook intro |
| `summary` | The hook — X, Threads, Instagram caption, YouTube description |
| `highlights` | Exactly three bullets on the timeline for that day |
| `why` | Optional "Why it matters" context on the site and in RSS |
| `demo_url` | Links the timeline headline to the demo; adds a "Watch the demo" link in RSS |
| `## In the headset` bullets | First two are cooked into X / Threads / Instagram |
| `## In code` + `## In the headset` bullets | Facebook and YouTube descriptions, grouped; X thread mixes the first two of each |
| `tags` | Hashtags (Instagram/TikTok/YouTube) |
| `media.gif` | Timeline GIF; X / Threads / Facebook attachment; Instagram gets the JPEG cover |
| `media.images` / `media.video` | What to attach on each platform |
| `overrides.<platform>` | Exact per-platform text, when auto-derived isn't right |

Evidence lines (`*Evidence: `file` @ 1:23.*`) stay out of every post and the
timeline — they're only for finding the footage again.

Link policy: Threads text posts and every Facebook post include the day's timeline
anchor; Threads media posts use the GIF instead. X leaves links out by default
(links reduce reach — flip `x.include_link` to change); Instagram captions can't
have clickable links ("link in bio").

## Site

One page: Ada's vision, daily entries from newest to oldest, then previous
attempts from newest to oldest (3 → 2 → 1):
<https://billatgameology.github.io/ada-media> · RSS: <https://billatgameology.github.io/ada-media/feed.xml>

The project name, tagline and introduction live in `config.yaml` under `project`.
The newest published daily entry comes first. Drafts stay unpublished.
The history copy and embeds live in `content/attempts.yaml`; rebuild after editing it.
Earlier attempts appear at the bottom with individual links in the left navigation.
On mobile, navigation folds into a "Browse the log" row; choosing an entry closes it.
Add an optional `why` sentence to selected daily notes to explain what the milestone
changes about the interaction, alongside the three technical highlights.

## Video library (catalog + transcripts)

Recording folders (screen captures, device footage) get cataloged and transcribed
locally — free, nothing uploaded, everything under `catalog/`:

```bash
python scripts/ada.py catalog       # scan → catalog/index.json + catalog/catalog.md
python scripts/ada.py transcribe    # local whisper → catalog/transcripts/<id>.{txt,srt,json}
python scripts/ada.py watch         # do both on a loop — hands-off monitoring
python scripts/ada.py clip --id <id>  # auto highlight reel (transcript-scored) → catalog/clips/
python scripts/ada.py gif --all      # 2-10s loops from content/gifs.yaml → content/media/gifs/
python scripts/ada.py story --date <day>  # all of a day's clips → script, journal draft, day reel
```

Watch folders, model and exclusions live in `config.yaml` → `media_watch` / `transcribe`.
`catalog/` is gitignored on purpose (personal recordings, public repo). Details and an
optional hourly launchd agent: `guide/MEDIA.md`.

If you ever want automation back: `guide/PLAN.md` explains where the old API
publishing implementation lives (it's in the first git commit).
