# PLAN — where this is going

## The shape of the system

```
content/daily/2026-10-18.md          ← you write ONE file per day
        │
        ├─► scripts/ada.py outbox    → outbox/2026-10-18/ (copy-paste posts + manifest)
        │                                    │
        │                                    └─ you post each file manually, ~10 min
        │
        └─► scripts/ada.py build     → docs/ (site + RSS) → GitHub Pages (public home)
```

Content creation lives in this repo. Posting is a human step, on purpose: no API keys,
tokens, audits, per-post fees or rate limits — for one person posting once a day, hands
beat tokens, and nothing silently breaks.

## Phases

**Phase 0 — done (2026-10-17)**
- Repo + GitHub Pages site + RSS
- `ada.py`: `daily` / `outbox` / `build` / `preview` / `status`
- Day-1 note published to the site

**Phase 1 — use it daily for two weeks**
- One note a day; post from the outbox; notice which platforms feel worth the effort
- Cut the ones you skip (`enabled: false` in config.yaml) — fewer, better posts

**Phase 2 — media**
- Screen recordings into `content/media/<date>/`; vertical clips for TikTok/Reels/Shorts
  (ffmpeg one-liner in `guide/PLAYBOOK.md`)
- A weekly recap note every Sunday — a longer post, an Instagram carousel, a YouTube video

**Phase 3 — ideas, only if wanted**
- A tiny weekly metrics note (what landed) — plain text, same repo
- Post URLs appended to the daily frontmatter (the outbox stays the exact record)
- Automation, if you ever change your mind: commit `aae6fd3`
  (`git show aae6fd3 --stat`) contains a full API publishing implementation for all six
  platforms. It was built to whatever each API allowed — which was the problem. Revive
  it only if manual posting ever becomes the bottleneck.

## Open decisions (we can punt all of these)

- Which platforms actually earn a spot? Start with all six, cut to 3–4 after two weeks.
- Is a weekly recap worth the extra hour? (Usually the highest-value post of the week.)
- Where should the bio links live? (site URL in every profile; that's the funnel)
