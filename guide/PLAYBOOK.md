# PLAYBOOK — what to write, where it goes

## The cadence

- **Daily (5–15 min):** one note in `content/daily/`. "Fixed the retry bug, learned X,
  here's a screenshot" is a perfect day.
- **Weekly (30 min):** on Sunday, skim the week and write one recap note. It becomes a
  longer YouTube video, an Instagram carousel, and a nice bookmark for followers.
- **Milestones:** releases, launches, "first 100 users" — break the rhythm with a
  bigger note; the pipeline doesn't care.

Consistency beats quality here. The point of the daily log is that it always exists.

## Two sources for every day

A day's note has two evidence sections, and they answer different questions:

- **In code** — what actually landed in the project repo. Pull the day's commits
  from `project-ada-xr` (`python scripts/ada.py code --date YYYY-MM-DD --stat`) and
  cite the short hash. This is where architecture, tests, refactors, fixes and
  parser/API work show up even when no recording captured them.
- **In the headset** — what was demonstrated on camera. Use the day script
  (`python scripts/ada.py find --date YYYY-MM-DD --grep "phrase"`) to pin each
  claim to a recording and a timecode. Put the citation on its own italic line,
  not in the bullet, so it stays out of the social posts:

  ```
  - **What I saw** — the result, with a real quote.
    *Evidence: `com.oculus.vrshell-20261018-173757-0.mp4` @ 1:00.*
  ```

The split matters: a transcript is good at proving a result was visible, but it
misses the code work that made it possible — and a commit log can't tell you
whether the thing actually worked in the room. Keep `Why / what I learned` and
`Next` after the two evidence sections.

## The daily note → platform mapping

`python scripts/ada.py outbox` derives everything from the note's frontmatter + bullets:

| Field | Feeds |
| --- | --- |
| `title` | Site headline, YouTube title, Facebook intro |
| `summary` | The hook — X, Threads, Instagram caption, YouTube description |
| First 1–2 `In the headset` bullets | Cooked into X / Threads / Instagram |
| `In code` + `In the headset` bullets | Facebook and YouTube description, grouped; X thread mixes the first two of each |
| `tags` | Hashtags (Instagram/TikTok/YouTube), YouTube tags |
| `media.images` | Instagram (and X/Threads/Facebook take the first), site |
| `media.video` | YouTube, TikTok, Instagram reel, Threads |
| `overrides.<platform>` | Exact text for that platform — wins over everything |

Rules of thumb:
- **`summary` is the most important line.** A headline someone would read in a feed,
  not a meeting memo. One sentence, concrete, no hype.
- Bullets should stand alone — each may become a solo post line.
- Links: Threads and Facebook get the day's page link automatically; X leaves it out
  by default (reach); Instagram captions can't link at all.

## Per-platform notes

### X — tight and link-free
- 280 characters; the outbox uses `summary` + up to 2 bullets.
- No link in the post by default; your bio carries the URL.
- `thread: true` in config.yaml splits the bullets into a numbered thread.

### Threads — link cards are free
- 500 characters. Text posts get a link preview card to the day's page — the best
  click-through platform in this setup.
- Attach the image/video if the manifest lists one.

### Instagram — JPEG-only, no links in captions
- Caption: `summary` + 2 bullets + hashtags; point to "link in bio".
- Images must be JPEG: `sips -s format jpeg in.png --out in.jpg`.
- One image → post; 2–10 images → carousel (first image sets the crop; square).
- Video → Reels; vertical (9:16), ≤90s for reach.

### Facebook — the "complete" version
- Longer text is fine; full summary + bullets + link (preview card automatic).

### TikTok — post from the app
- Needs `media.video`. Upload in the app, paste the caption, use the app's
  sounds/hashtags/cover tools.
- Vertical 9:16, 15–60s. Screen recordings with captions work fine for dev content.

### YouTube — long-form + Shorts
- Needs `media.video`; the outbox file has TITLE and DESCRIPTION sections.
- Links are free here — the description includes the full notes link.
- Vertical ≤3 min → a Short; add `#Shorts` to the description.

## Making the clips (cheap and fast)

Screen recordings are the default content. On macOS: `Cmd+Shift+5` → record a window.
One ffmpeg pass makes a vertical version for Reels/TikTok/Shorts:

```bash
ffmpeg -i demo.mp4 -vf "crop=ih*9/16:ih,scale=1080:1920" -c:a copy vertical.mp4
```

Keep clips short (≤60s) and under ~50 MB so they live happily in this repo (GitHub
blocks files over 100 MB). Bigger/longer videos: upload to YouTube and skip in-repo
hosting; only keep what Reels/TikTok need.

File layout: `content/media/<date>/name.ext`, referenced in the note's frontmatter as
`<date>/name.ext`.

## Voice — a few rules that keep a devlog readable

- **Concrete over clever.** "Cut cold-start publish time from 4.1s to 0.9s" beats
  "major performance improvements".
- **First person, plain tense.** "I tried X. It broke. Switched to Y."
- **Admit the bad days.** "Spent 3 hours on a CORS bug" is relatable content.
- **No hype words** (revolutionary, game-changing, excited to announce).
- **One idea per bullet.** They get quoted individually on social.
- **Include numbers** when you have them — numbers are the strongest hook devlog
  content has.

Example pairs:

| Don't | Do |
| --- | --- |
| "Made great progress on the editor today 🚀" | "The editor now autosaves every 3s to a temp file. Undo survives a crash now." |
| "Working on performance improvements" | "Profiled the parser: 62% of time was regex. Replaced one with a hand-rolled scanner: 3.4x faster." |

## Some days you won't feel like it

Publish anyway, small. "Wrote the docs for the config file" is a real day. The archive
is the point; readers forgive quiet days far more than they forgive a project that
vanishes.

## When to cut a platform

After two weeks, look at which outbox files you actually used. Anything you skipped
most days: set `enabled: false` in config.yaml. Fewer, better posts.
