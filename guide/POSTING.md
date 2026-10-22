# POSTING — how the manual part works

Everything is prepared in `outbox/<date>/`. For each platform: open the file, copy its
text, attach the media the manifest lists, post. Nothing else to remember.

Posting from your phone: the `outbox/` folder is committed, so it's readable on GitHub
mobile (or from the repo page). Each media file in the manifest has a `from phone:`
URL — open it on the phone to save/attach.

---

## X / Twitter — `x.txt`

- Single post, or a thread: blocks are separated by `---` — post them in order as replies.
- Attach the GIF and/or up to 4 images if listed.
- **No link in the post** (links reduce reach); the site URL lives in your bio.
  Flip `x.include_link: true` in config.yaml if you'd rather include it.

## Threads — `threads.txt`

- Text posts get a link preview card to the day's timeline anchor automatically.
- Attach the single image/video/GIF if the manifest lists one.

## Instagram — `instagram.txt`

- **Requires at least one image or video.**
- Images must be JPEG — convert first if needed:
  `sips -s format jpeg content/media/<file>.png --out content/media/<file>.jpg`
- Carousel: attach images in the order the manifest lists them.
- Animated GIFs won't animate on Instagram — use a JPEG cover or the video.
- Captions can't contain clickable links — keep the site URL in your IG bio.

## Facebook — `facebook.txt`

- The text includes the timeline anchor link; the preview card appears automatically.
- Attach photos/GIF if listed.

## TikTok — `tiktok.txt`

- Upload the video **in the app**, paste the caption, then let the app's tools do the
  rest (sounds, hashtags, cover) — they're better than anything pre-written.
- Vertical 9:16, 15–60s works best for dev content.

## YouTube — `youtube.txt`

- Two sections: `TITLE` and `DESCRIPTION`. Upload at studio.youtube.com (or the app).
- Vertical and ≤3 minutes → it becomes a Short; add `#Shorts` to the description.
- Links are free here — the description already includes the day's timeline anchor URL.

---

## After posting

Nothing to update. The outbox folder and the site stay as the exact record of what
went out, when, and in what wording.
