# SETUP — connect each platform, click by click

Do these in any order. After each one, run `python scripts/ada.py status` — it shows
which credentials are present and which are still missing. Nothing here costs money
except the optional X credits (X has no free tier anymore; $5 lasts about a year at
one post per day).

---

## 0. One-time local setup (already done if the venv exists)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Guide for filling `.env`: each section below names its exact variables.

---

## 1. Threads (free, easiest — do this first)

Prereq: a Threads account (it's your Instagram account).

1. Go to <https://developers.facebook.com/apps> → **Create app**.
   - Name: anything (e.g. "ada-media publishing"), contact email: yours.
   - Use case: pick the one that mentions **Threads** (or "Other" → add products later).
2. In the app dashboard, **Add product → Threads** (API setup).
3. Under *Threads tester*, **add your Threads account**. Then open the Threads app
   (Settings → Account → Website permissions → accept the invite) — this makes you
   a tester of your own app, which is all a solo project needs.
4. Back in the dashboard, use the **Generate access token** button next to your
   account. Copy the token.
5. Get your numeric user ID:

   ```bash
   curl "https://graph.threads.net/v1.0/me?fields=id,username&access_token=YOUR_TOKEN"
   ```

6. Fill in `.env`:
   - `META_APP_ID`, `META_APP_SECRET` (from App settings → Basic)
   - `THREADS_USER_ID` (the `id` from step 5)
   - `THREADS_ACCESS_TOKEN` (from step 4; valid ~60 days — refresh with
     `python scripts/ada.py auth meta`)

Why this works for a solo project: the app stays in **Development mode** with you as
a tester, which is the documented path for your own accounts. Only when *other people*
would use your app does full review/app-live matter.

---

## 2. Instagram (free)

Prereqs:
- Your Instagram account must be a **professional account** (IG app → Settings →
  Account type → *Switch to professional* → Business or Creator). Without this,
  there is no API at all.
- Instagram must be linked to a Facebook **Page** (the API setup will offer to create
  one; you can make a Page for the project — it also feeds step 3).

1. Same Meta app as above → **Add product → Instagram** → choose
   **API setup with Instagram login** (a.k.a. "Instagram API with Instagram Login").
2. Add your Instagram account, generate the access token (the dashboard has a
   **Generate token** flow — log in with the IG account when it asks).
3. Get your IG user ID:

   ```bash
   curl "https://graph.instagram.com/v25.0/me?fields=user_id,username&access_token=YOUR_TOKEN"
   ```

4. Fill in `.env`: `IG_USER_ID`, `IG_ACCESS_TOKEN`.

Notes:
- The token is long-lived (~60 days). Refresh with `python scripts/ada.py auth meta`.
- Images must be **JPEG** (officially). The publish preview warns you if they're not;
  convert with `sips -s format jpeg image.png --out image.jpg` (macOS) or any editor.
- Discoverability slider: in the IG app, enable "Share to Threads" alternatives etc.
  as you like — not required.

---

## 3. Facebook Page (free API — but read the catch)

1. Create a Page for the project (Facebook → Pages → Create). Skip if you have one.
2. Meta app → **Add product → Pages API** ("Manage everything on your Page" use case).
3. Make yourself admin of both app and Page (you are) — in Development mode you can
   already generate a **page access token**.
4. Quick way to get the token: **Graph API Explorer**
   (<https://developers.facebook.com/tools/explorer/>) → select your app → permissions
   `pages_manage_posts`, `pages_show_list`, `pages_read_engagement` → *Generate access
   token* → then:

   ```bash
   curl "https://graph.facebook.com/v25.0/me/accounts?access_token=YOUR_USER_TOKEN"
   ```

   Grab the Page `id` and its `access_token`.
5. Fill in `.env`: `FB_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN`.

**The catch:** while the app is in Development mode, posts from the API are visible
only to page admins. Making them public requires **App Review** ("Manage everything on
your Page" use case). Reviewers want: app in Live mode, a screencast of your app
doing the full flow, privacy policy URL, data-deletion URL. Doable, mostly paperwork.
Until then, keep `facebook.enabled: false` in `config.yaml` — or publish with it and
see your own posts only.

---

## 4. TikTok (free — inbox drafts, no audit needed)

1. <https://developers.tiktok.com> → sign up as a developer → **create an app**.
2. Add products: **Login Kit** and **Content Posting API**.
   - Scopes: `video.upload` (inbox drafts — no audit needed).
     Add `video.publish` only if you later go for the Direct Post audit.
3. In the app settings, register a redirect URI, e.g. `https://localhost/ada` — it must
   match `TIKTOK_REDIRECT_URI` in `.env` exactly.
4. Fill in `.env`: `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REDIRECT_URI`.
5. Get the refresh token (one time):

   ```bash
   python scripts/ada.py auth tiktok            # prints an authorization URL
   # open it, log in as your TikTok account, approve
   # the browser lands on a page that fails to load — that's fine
   # copy the `code=...` value from the address bar
   python scripts/ada.py auth tiktok --code=THE_CODE
   ```

   The script stores `TIKTOK_REFRESH_TOKEN` in `.env`; access tokens are refreshed
   automatically forever after.

**How posting works in inbox mode (the default):** the script uploads your video to
TikTok's servers and you get a notification *"Draft ready in your inbox"* — open the
TikTok app, tap the notification, add caption/sounds, publish. You stay in control,
TikTok stays happy, no audit required. Direct API posting (`mode: direct`) needs the
passed audit and generally is not worth it for a solo project.

---

## 5. YouTube (free)

1. <https://console.cloud.google.com> → create a project (any name).
2. **APIs & Services → Library → "YouTube Data API v3" → Enable**.
3. **OAuth consent screen**: External; add yourself as a **test user**; app name etc.
   You can leave it unpublished — test users can use it indefinitely for their own
   accounts.
4. **Credentials → Create credentials → OAuth client ID → type: Desktop app.**
5. Fill in `.env`: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`.
6. One-time authorization (opens a browser):

   ```bash
   python scripts/ada.py auth youtube
   ```

   The refresh token is stored in `.state/youtube_token.json` (gitignored).

Quota: 10,000 units/day; an upload costs 1,600 — about 6/day, far above needs.

---

## 6. X / Twitter (optional — pay-per-use since Feb 2026)

The free API tier was discontinued for new developers in February 2026. Current
model: **pay-per-use**, minimum $5 of prepaid credits.

- **$0.015** per post (text or with image)
- **$0.20** per post **that contains a link** ← this is why our X posts are link-free
- $5 ≈ 500 link-free posts ≈ more than a year of daily notes

1. <https://console.x.com> → create a project/app (sign in with the X account you'll
   post from; it must be a developer account).
2. **Keys and tokens** → generate: API key & secret, access token & secret (with
   *Read and write* permission).
3. Fill in `.env`: `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET`.
4. Add credits in the console (billing). Failed requests aren't charged.
5. Keep `links_in_posts: false` in `config.yaml`. The preview will flag any accidental
   link before you post.

---

## Verifying everything

```bash
python scripts/ada.py status            # credentials present? last posts per platform
python scripts/ada.py publish           # dry run — shows every platform's exact post
python scripts/ada.py publish --live    # the real thing
```

If an API rejects a call, the error text is printed verbatim (X/Meta/TikTok/YouTube
messages are usually self-explanatory), and the other platforms still go out — one
failure never blocks the rest.
