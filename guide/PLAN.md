# PLAN — where this is going

## The shape of the system

```
content/daily/2026-10-17.md          ← you write ONE file per day
        │
        ├─► scripts/ada.py build     → docs/ (site + RSS) → GitHub Pages (public home)
        │
        └─► scripts/ada.py publish   → per-platform posts:
              X         short text (link-free, cheap)
              Threads   text + link card → your page
              Instagram image / reel / carousel
              Facebook  summary + link
              TikTok    video → inbox draft (you tap publish)
              YouTube   video → long-form or Short
```

Everything is files in this repo. "Publishing" is a script run. "The page" is the
repo itself rendered to `docs/` and served by GitHub Pages.

## Platform reality check — October 2026

| Platform | Cost | Automation level today | The catch |
| --- | --- | --- | --- |
| X / Twitter | Pay-per-use: ~$0.015/post, **$0.20 if the post contains a link**; min $5 top-up | Full: text, threads, up to 4 images | Free tier discontinued for new developers (Feb 2026). Keep links out of posts. $5 ≈ a year of daily posts. |
| Threads | Free | Full: text ≤500 chars, image, video, carousels, link preview cards | Media must be publicly fetchable — our Pages site serves it. 250 posts/24h (irrelevant at 1/day). |
| Instagram | Free | Full: images (JPEG only), reels, carousels (≤10) | Professional account required. 100 API posts/24h. No text-only posts, no links in captions. |
| Facebook Page | Free | Full: text + link, photo posts | **App Review required** before posts are publicly visible; until then they only show to page admins. |
| TikTok | Free | Semi: video lands in your **inbox as a draft**; you tap publish in the app | Public API posting (Direct Post) needs a passed app audit (weeks, mostly a UI/consent review). Our scripts support both modes. |
| YouTube | Free | Full: long-form + Shorts | Daily quota allows ~6 uploads/day. |

Second-wave platforms if you want more reach later — all free and script-friendly:
**Bluesky, Mastodon, LinkedIn (personal posts), Dev.to**. Not wired in yet on purpose.

## Phases

**Phase 0 — done (2026-10-17)**
- Repo + GitHub Pages site + RSS
- `ada.py` CLI: `daily`, `build`, `preview`, `publish` (dry-run), `status`, `auth`
- Platform modules for all six targets
- Day-1 note published to the site

**Phase 1 — connect and post daily for a week** (~1 hour of account setup)
- Threads, Instagram, YouTube, TikTok (inbox mode) — all free per `guide/SETUP.md`
- X only if you accept a one-time ~$5 of credits; otherwise X stays manual or skipped
- First live `publish --live`, then find your rhythm: one note a day, low effort, honest

**Phase 2 — video & long-form**
- Record screen/video, drop it in `content/media/<date>/`, publish: YouTube (long or Short) + Instagram reel + TikTok draft
- Weekly recap: stitch 5–7 daily notes into one "week in review" note (Sunday), good for one longer YouTube video and a carousel
- Optional: apply for the TikTok Direct Post audit and the Facebook App Review (both are mostly paperwork + a screencast; `guide/SETUP.md` documents what reviewers check)

**Phase 3 — automation & polish**
- Auto-publish on a schedule (macOS `launchd`/`cron` running `publish --live` each morning, or a GitHub Actions cron if you prefer cloud)
- Metrics pull script (views/likes per post → one CSV in `.state/`) to learn what lands
- Cross-linking: pin the site in bios, put handles in the site footer

## Open decisions (we can punt all of these)

- X: keep (needs ~$5) or drop for now?
- TikTok: stay in inbox-draft mode (fine forever) or invest in the audit?
- Facebook: worth the App Review, or skip FB and repurpose those posts for later Bluesky/LinkedIn?
- Repo visibility for `content/`: it's all public today (the site needs it). Personal-feeling notes can go in the HTML comment block or a `draft: true` flag that keeps a note unpublished.
