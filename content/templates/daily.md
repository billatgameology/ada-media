---
date: "{{date}}"
title: ""              # headline shown on the site; also the YouTube title
summary: ""            # ONE good sentence — the hook for X, Threads, Instagram
highlights: []         # exactly 3 bullets for the single-page timeline
tags: []               # e.g. [devlog, python, api] — become hashtags
media:
  gif: ""              # e.g. "gifs/2026-10-18.gif" — short looping preview (see content/gifs.yaml)
  images: []           # e.g. ["2026-10-18/screenshot.png"] — files under content/media/
  video: ""            # e.g. "2026-10-18/demo.mp4" — one video for YouTube / TikTok / Reels
overrides: {}          # optional exact per-platform text (wins over auto-derived):
# x: "custom X text..."
# threads: "custom Threads text..."
# instagram: "custom caption..."
# facebook: "custom Facebook text..."
# tiktok: "custom TikTok caption..."
# youtube:
#   title: "custom video title"
#   description: "custom description"
---

## In code

*Commits below are in [project-ada-xr]({{code_url}}).*

<!-- .venv/bin/python scripts/ada.py code --date {{date}} --stat -->
-

## In the headset

<!-- .venv/bin/python scripts/ada.py find --date {{date}} --grep "phrase" -->
<!-- Evidence lines are italic and don't become bullets in the outbox. -->
-
  *Evidence: `recording.mp4` @ 1:23.*

## Why / what I learned

-

## Next

-

<!-- Draft context (invisible on the built site). Recent code commits:
{{context}}
-->
