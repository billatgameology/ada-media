#!/usr/bin/env python3
"""ada — the daily-notes publishing CLI for this repo.

Commands:
  daily     create today's note (prefilled with recent commits)
  build     rebuild the site into docs/
  preview   build, then open the site in a browser
  publish   dry-run preview of every platform post (--live to actually post)
  status    what's configured, what's been published
  auth      one-time platform logins: youtube | tiktok | meta
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_site  # noqa: E402
from lib import config, content, state  # noqa: E402
from platforms import REGISTRY, by_name  # noqa: E402

ROOT = config.root()


# ── commands ───────────────────────────────────────────────────────────

def cmd_daily(args) -> int:
    date = args.date or dt.date.today().isoformat()
    path = content.DAILY_DIR / f"{date}.md"
    if path.exists():
        print(f"{path.relative_to(ROOT)} already exists — edit it (or pass --date).")
        return 0
    template = (ROOT / "content" / "templates" / "daily.md").read_text(encoding="utf-8")
    text = template.replace("{{date}}", date).replace("{{context}}", _git_context() or "(no commits found)")
    path.write_text(text, encoding="utf-8")
    print(f"created {path.relative_to(ROOT)}")
    print("edit it, then:")
    print("  python scripts/ada.py build && git add -A && git commit -m 'daily: " + date + "' && git push")
    return 0


def _git_context() -> str:
    cfg = config.drafting()
    repo = str(cfg.get("context_git") or ".")
    count = int(cfg.get("context_commits") or 8)
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT / repo), "log", "--oneline", f"-{count}"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def cmd_build(args) -> int:
    build_site.build()
    return 0


def cmd_preview(args) -> int:
    index = build_site.build()
    webbrowser.open(index.as_uri())
    print(f"opened {index.relative_to(ROOT)}")
    return 0


def cmd_publish(args) -> int:
    try:
        day = content.load_day(args.date)
    except FileNotFoundError as exc:
        print(exc)
        return 1
    if day.draft:
        print(f"{day.date} is marked 'draft: true' — remove that line to publish it.")
        return 1

    if args.platforms:
        targets = [by_name(name.strip()) for name in args.platforms.split(",") if name.strip()]
    else:
        targets = [module for module in REGISTRY if module.is_enabled()]
    if not targets:
        print("no platforms enabled — check config.yaml")
        return 1

    live = args.live
    if live:
        print(f"LIVE PUBLISH  ·  {day.date}")
    else:
        print(f"DRY RUN  ·  {day.date}  ·  nothing posts without --live")
    done, skipped, failed = [], [], []
    published_days = (state.published().get("days") or {}).get(day.date) or {}

    for module in targets:
        print()
        print(f"── {module.LABEL} " + "─" * max(2, 48 - len(module.LABEL)))

        existing = published_days.get(module.NAME)
        if existing and not args.force:
            print(f"already published today ({existing.get('url') or existing.get('id') or 'ok'}) — use --force to override")
            skipped.append(module.NAME)
            continue

        try:
            info = module.preview(day)
        except Exception as exc:  # preview should not fail, but never block the rest
            print(f"preview failed: {exc}")
            failed.append(module.NAME)
            continue
        _print_preview(info)

        missing = module.missing_env()
        if missing:
            message = f"not configured yet — missing {', '.join(missing)} in .env (see guide/SETUP.md)"
            if live:
                print(f"skipping: {message}")
                skipped.append(module.NAME)
                continue
            print(f"({message})")

        if not live:
            continue

        try:
            result = module.publish(day)
        except Exception as exc:
            print(f"FAILED: {exc}")
            failed.append(module.NAME)
            continue
        state.record(day.date, module.NAME, result)
        shown = str(result.get("url") or result.get("id") or "ok")
        if result.get("note"):
            shown += f" — {result['note']}"
        print(f"published: {shown}")
        done.append(module.NAME)

    print()
    if live:
        print(f"summary: {len(done)} published · {len(skipped)} skipped · {len(failed)} failed")
    else:
        print("dry run complete. Review the previews above, then re-run with --live.")
    return 0 if not failed else 1


def _print_preview(info: dict) -> None:
    if info.get("note"):
        print(f"note: {info['note']}")
    text = str(info.get("text") or "")
    if text:
        print("text:")
        for line in text.splitlines():
            print(f"    {line}")
    for item in info.get("media") or []:
        print(f"media: {item}")
    for warning in info.get("warnings") or []:
        print(f"warning: {warning}")


def cmd_status(args) -> int:
    proj = config.project()
    print(f"{proj.get('name', '')} — {proj.get('site_url', '')}")
    print()
    print("platforms:")
    published_days = state.published().get("days") or {}
    for module in REGISTRY:
        enabled = "enabled " if module.is_enabled() else "disabled"
        missing = module.missing_env()
        creds = "credentials: ready" if not missing else f"credentials: missing {', '.join(missing)}"
        last = ""
        for date in sorted(published_days, reverse=True):
            entry = (published_days[date] or {}).get(module.NAME)
            if entry:
                last = f"  ·  last post {date}"
                if entry.get("url"):
                    last += f" ({entry['url']})"
                break
        print(f"  {module.LABEL:<16} {enabled}  ·  {creds}{last}")

    days = content.all_days()[:10]
    if days:
        print()
        print("recent notes   (* = posted, · = not yet, this platform):")
        names = [module.NAME for module in REGISTRY]
        for day in days:
            entries = published_days.get(day.date) or {}
            marks = " ".join(f"{name}{'*' if name in entries else '·'}" for name in names)
            title = (day.title or "")[:40]
            print(f"  {day.date}  {title:<42} {marks}")
    return 0


def cmd_auth(args) -> int:
    if args.provider == "youtube":
        import platforms.youtube as youtube

        youtube.auth_flow()
        return 0

    if args.provider == "tiktok":
        import platforms.tiktok as tiktok

        if args.code:
            open_id = tiktok.exchange_code(args.code)
            print(f"✓ TikTok connected (open_id: {open_id}) — refresh token stored in .env")
            return 0
        print("1. open this URL and approve with the TikTok account you post from:")
        print()
        print("   " + tiktok.auth_url())
        print()
        print("2. the redirect page will fail to load — that's fine.")
        print("   copy the `code=...` value from the browser's address bar")
        print("3. run:  python scripts/ada.py auth tiktok --code=THE_CODE")
        return 0

    if args.provider == "meta":
        import platforms.instagram as instagram
        import platforms.threads as threads

        for module in (instagram, threads):
            try:
                validity = module.refresh_token()
                print(f"✓ {module.LABEL}: token refreshed ({validity})")
            except Exception as exc:
                print(f"✗ {module.LABEL}: {exc}")
        return 0

    return 1


# ── entrypoint ─────────────────────────────────────────────────────────

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="ada",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("daily", help="create today's note")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p.set_defaults(func=cmd_daily)

    p = sub.add_parser("build", help="rebuild the site into docs/")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("preview", help="build, then open the site in a browser")
    p.set_defaults(func=cmd_preview)

    p = sub.add_parser("publish", help="preview every platform post; --live actually posts")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p.add_argument("--platforms", help="comma-separated subset, e.g. threads,youtube")
    p.add_argument("--live", action="store_true", help="actually publish (default is a dry run)")
    p.add_argument("--force", action="store_true", help="re-publish even if already posted today")
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("status", help="configuration + publish history")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("auth", help="one-time platform logins")
    p.add_argument("provider", choices=["youtube", "tiktok", "meta"])
    p.add_argument("--code", help="TikTok only: the code from the redirect URL")
    p.set_defaults(func=cmd_auth)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
