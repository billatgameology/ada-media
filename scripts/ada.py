#!/usr/bin/env python3
"""ada — the daily-notes content studio CLI for this repo.

Commands:
  daily     create today's note (prefilled with recent commits)
  outbox    write copy-paste-ready posts for manual publishing to outbox/<date>/
  build     rebuild the site into docs/
  preview   build, then open the site in a browser
  status    recent notes and their outbox state
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
import outbox  # noqa: E402
from lib import config, content  # noqa: E402

ROOT = config.root()
PLATFORMS = ["x", "threads", "instagram", "facebook", "tiktok", "youtube"]


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
    print("  python scripts/ada.py outbox    # prepare the posts for manual publishing")
    print("  python scripts/ada.py build     # rebuild the site")
    print(f"  git add -A && git commit -m 'daily: {date}' && git push")
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


def cmd_outbox(args) -> int:
    try:
        day = content.load_day(args.date)
    except FileNotFoundError as exc:
        print(exc)
        return 1
    try:
        out_dir = outbox.generate(day)
    except RuntimeError as exc:
        print(exc)
        return 1
    print((out_dir / "manifest.txt").read_text(encoding="utf-8"))
    print(f"outbox written to {out_dir.relative_to(ROOT)}/ — post each file manually (guide/POSTING.md).")
    return 0


def cmd_build(args) -> int:
    build_site.build()
    return 0


def cmd_preview(args) -> int:
    index = build_site.build()
    webbrowser.open(index.as_uri())
    print(f"opened {index.relative_to(ROOT)}")
    return 0


def cmd_status(args) -> int:
    proj = config.project()
    enabled = [name for name in PLATFORMS if config.social(name).get("enabled")]
    print(f"{proj.get('name', '')} — {proj.get('site_url', '')}")
    print(f"platforms (config.yaml): {', '.join(enabled) if enabled else 'none'}")

    days = content.all_days()[:10]
    if days:
        print()
        print("recent notes   (o = outbox ready, · = not yet):")
        for day in days:
            ready = (ROOT / "outbox" / day.date / "manifest.txt").exists()
            title = (day.title or "")[:44]
            print(f"  {day.date}  {title:<46} {'o' if ready else '·'}")
    return 0


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

    p = sub.add_parser("outbox", help="write copy-paste-ready posts to outbox/<date>/")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p.set_defaults(func=cmd_outbox)

    p = sub.add_parser("build", help="rebuild the site into docs/")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("preview", help="build, then open the site in a browser")
    p.set_defaults(func=cmd_preview)

    p = sub.add_parser("status", help="recent notes and their outbox state")
    p.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
