# PLAYBOOK — what to write, where it goes

## The cadence

- **Daily (5–15 min):** one note in `content/daily/`. It doesn't have to be big —
  "fixed the retry bug, learned X, here's a screenshot" is a perfect day.
- **Weekly (30 min):** on Sunday, skim the week and write one recap note. It becomes a
  longer YouTube video, an Instagram carousel, and a nice bookmark for followers.
- **Milestones:** release posts, launches, "first 100 users." Break the daily rhythm
  with a bigger note; the pipeline doesn't care.

Consistency beats quality here. The point of the daily log is that it always exists.

## The daily note → platform mapping

The scripts derive everything from the note's frontmatter + bullets:

| Field | Feeds |
| --- | --- |
| `title` | Site headline, YouTube title, Facebook intro |
| `summary` | Hook line for X, Threads, Instagram caption, YouTube description |
| First 1–2 bullets | Cooked into X / Threads / IG posts |
| All bullets | Facebook post, YouTube description, TikTok caption (direct mode) |
| `tags` | IG/TikTok/YouTube hashtags, YouTube tags |
| `media.images` | Instagram (and X/FB/Threads take the first one), site |
| `media.video` | YouTube, TikTok, Instagram (as a reel), Threads |
| `overrides.<platform>` | Exact text for that platform — wins over everything |

Rules of thumb:
- **`summary` is the most important line.** Write it like a headline someone would
  read in a feed, not like a meeting memo. One sentence, concrete, no hype.
- Bullets should stand alone — no "see above". Each may become a solo post line.
- Don't write links into the body for X's sake; the publisher adds links only where
  they're free (Threads, Facebook, site, YouTube description).

## Per-platform notes

### X — link-free by default
- 280 characters. Our posts use `summary` + up to 2 bullets.
- Links cost $0.20 vs $0.015 — the config keeps them out. Your profile bio/website
  field is where the link lives.
- `thread: true` in config splits the bullets into a numbered thread (~4 posts).

### Threads — link cards are free
- 500 characters. Text posts get a link preview card to the day's page — the single
  best "click-through" platform in this setup.
- One `topic_tag` allowed (config.yaml). Good candidates: your niche (e.g. `opensource`).

### Instagram — JPEG-only, no links in captions
- Captions: `summary` + 2 bullets + hashtags. Point to "link in bio" if needed.
- Images must be **JPEG** officially: `sips -s format jpeg in.png --out in.jpg`.
- One image → post. 2–10 images → carousel (first image defines the crop; square).
- Video with `media_type=REELS`; post vertical (9:16), ≤90s for reach.

### Facebook — the "complete" version
- Longer text is fine (it's the least rate-limited). Full summary + bullets + link.
- Skip it for now if App Review feels like too much; flip `facebook.enabled` when ready.

### TikTok — inbox drafts
- Requires `media.video`. The script uploads it and you finish in the app
  (add trending sound, caption, hashtags — the app is better at that part anyway).
- Vertical 9:16, 15–60s. Screen recordings with captions work fine for dev content.

### YouTube — long-form + Shorts
- Set `media.video` to publish. Long-form: title = note title, description from the
  note, links included (free!).
- Shorts: same vertical clip used for TikTok/Reels, ≤3 min (automatic when vertical).
  Add `#Shorts` to the description for good measure.
- `privacy_status: public|unlisted|private` in config. Use `unlisted` while testing.

## Making the clips (cheap and fast)

Screen recordings are the default content. On macOS: `Cmd+Shift+5` → record a window.
Then one ffmpeg pass to make a vertical version for Reels/TikTok/Shorts:

```bash
# quick vertical crop of a wide screen recording (center crop)
ffmpeg -i demo.mp4 -vf "crop=ih*9/16:ih,scale=1080:1920" -c:a copy vertical.mp4
```

Keep clips short (≤60s) and under ~50 MB so they live happily in this repo
(GitHub blocks files over 100 MB). Bigger/longer videos: upload to YouTube and skip
in-repo hosting; only keep what Reels/TikTok need.

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

## What to do with a failed publish

`ada.py publish` prints the API's error verbatim and keeps going with the other
platforms. Common ones:

- **X 402 CreditsDepleted** → add credits in console.x.com.
- **Meta OAuthException 190** → token expired; `ada.py auth meta`.
- **IG "media not available"** → you referenced media that isn't pushed to the live
  site yet; `git push` and retry (the site takes ~30s to rebuild).
- **TikTok scope errors** → the app's portal scopes don't include `video.upload`.

After fixing, re-run `publish --live`; platforms already published today are skipped
(use `--force` to re-post deliberately).
