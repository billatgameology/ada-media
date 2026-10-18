# MEDIA — the video library (catalog + transcripts)

Folders listed under `media_watch` in `config.yaml` are scanned for recordings
(screen captures, device footage). Each one gets cataloged, then transcribed
locally — free, on-device, nothing uploaded anywhere.

## Commands

```bash
python scripts/ada.py catalog                  # scan the folders → update catalog/
python scripts/ada.py transcribe               # transcribe new/changed recordings
python scripts/ada.py transcribe --limit 2     # just two (smallest first)
python scripts/ada.py transcribe --id oculus   # only names/ids containing "oculus"
python scripts/ada.py transcribe --force       # redo even the done ones
python scripts/ada.py watch --interval 600     # loop: scan + transcribe every 10 min
```

## What gets created (all local, gitignored)

| path | what |
| --- | --- |
| `catalog/index.json` | machine view: every recording, metadata, transcript status |
| `catalog/catalog.md` | human view: table with durations, sizes and transcript links |
| `catalog/transcripts/<id>.txt` | plain text — for drafting posts and daily notes |
| `catalog/transcripts/<id>.srt` | timed subtitles — video editors, YouTube captions |
| `catalog/transcripts/<id>.json` | segments + language + model (for future tooling) |

`<id>` is `name-<hash8>`, derived from the full path — stable across runs, so two
files with the same name never collide.

Behavior details:

- New or edited files are marked pending automatically; unchanged ones keep their transcript.
- Videos are found by extension and `min_size_mb`; folders whose names contain an
  `exclude_dirs` entry (`.fcpbundle`, `.localized`, `.tvlibrary`, …) are skipped —
  that's how the Final Cut project bundle and app-managed folders stay out.
- Files that disappear from disk stay in the index flagged `missing` (the transcript is kept).
- Files modified in the last 30 seconds are skipped — probably still being written.

## Transcription

- Engine: **mlx-whisper** on Apple Silicon (installed via `requirements.txt`). On other
  machines install `faster-whisper` and the CLI picks it up; set `transcribe.engine` to force one.
- Model (`transcribe.model`): `turbo` (default — fast and near-large quality), `large-v3`,
  `medium`, `small`, `base`, `tiny`, or any Hugging Face repo path. Models download once to
  `~/.cache/huggingface` (turbo ≈ 1.6 GB, small ≈ 0.5 GB).
- Speed on an M1 Pro: roughly 6–10× realtime — a 10-minute recording takes 1–2 minutes.
- Language is auto-detected; set `transcribe.language: en` (or another code) to force it.
- Metadata needs `ffmpeg`/`ffprobe` on PATH (already installed here); transcription reads
  the video files directly.

## Highlight reels (`clip`)

Turn a long recording into a short reel by mining its transcript — automatic,
local, free:

```bash
python scripts/ada.py clip --id 15-51-15                                  # auto-pick ~90s
python scripts/ada.py clip --id 15-51-15 --target 60 --vertical --burn   # 60s vertical + captions
python scripts/ada.py clip --id 15-51-15 --range 3:12-4:00 --range 16:40-17:30
```

How the auto-pick works: speech is grouped into blocks, and each block is scored by
"development" keywords (fixed, works, shipped, noteworthy…), speech density, lexical
diversity (repetitive loops are penalized) and a length sweet spot. The top blocks
up to ~`--target` seconds are cut and stitched back in chronological order.

Every run writes an editable plan to `catalog/clips/<id>-reel.plan.json` — tweak the
blocks and re-cut with `--plan <file>`. (Handing the plan file plus the transcript to
an AI assistant is a fast way to get a smarter cut list than any heuristic.)

Outputs (in `catalog/clips/`, gitignored):

| file | what |
| --- | --- |
| `<id>-reel.mp4` | the highlight reel (horizontal, or 9:16 with `--vertical`) |
| `<id>-reel.srt` | subtitles on the reel's own timeline |
| `<id>-reel.plan.json` | the blocks that were cut |

## Daily stories (all clips → one journal + reel)

`clip` works on one recording; `story` merges a whole day's recordings:

```bash
python scripts/ada.py story --date 2026-10-16                # script + candidates + auto reel + draft
python scripts/ada.py story --date 2026-10-16 --target 120   # shorter reel
python scripts/ada.py story --date 2026-10-16 --plan catalog/stories/2026-10-16.plan.json  # curated cut
```

What lands in `catalog/stories/` (gitignored):

| file | what |
| --- | --- |
| `<date>.script.md` | the whole day as one readable script — clips in order, timecoded |
| `<date>.candidates.json` | every positively-scored moment across all clips |
| `<date>.draft.md` | machine-drafted journal: timeline + top quotes |
| `<date>.md` | the real journal — written by you (or an assistant) from the script |
| `catalog/clips/<date>-day-reel.mp4` | auto highlight reel (+ `.srt`, `.plan.json`) |

The intended loop: run `story`, hand `<date>.script.md` + `<date>.candidates.json` to
yourself (or an assistant) and write the journal — what was worked on, what worked,
what didn't, the standout moments. Then re-cut the reel from a curated plan with
`--plan` (the plan format is just `{"blocks": [{"id", "start", "end"}]}`, ids from the
candidates file). To publish the journal, promote it to `content/daily/<date>.md` and
run `build`.

## Monitoring hands-off (optional)

Hourly launchd agent — create `~/Library/LaunchAgents/com.ada-media.watch.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.ada-media.watch</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>cd "/Users/billw/Code Files/ada-media" && .venv/bin/python scripts/ada.py catalog && .venv/bin/python scripts/ada.py transcribe</string>
  </array>
  <key>StartInterval</key><integer>3600</integer>
  <key>RunAtLoad</key><true/>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.ada-media.watch.plist   # start it
launchctl list | grep ada-media                                    # check it
launchctl unload ~/Library/LaunchAgents/com.ada-media.watch.plist  # stop it
```

Each run is a no-op when nothing changed. (Transcription is GPU-heavy; hourly is plenty.)

## Privacy & disk

- `catalog/` is **gitignored**: transcripts of personal recordings never get committed
  to a public repo. To track them anyway, remove `catalog/` from `.gitignore` — check
  what's inside first.
- Deleting `catalog/` is safe — `catalog` + `transcribe` rebuild it. The raw recordings
  in the watch folders are never touched.
- The whisper models live in `~/.cache/huggingface`, not the repo. If disk gets tight,
  `pip cache purge`, `brew cleanup` and clearing that cache are the usual reclaims —
  models re-download on demand.
