#!/usr/bin/env python3
"""ada — the daily-notes content studio CLI for this repo.

Commands:
  daily       create today's note (prefilled with recent commits)
  outbox      write copy-paste-ready posts for manual publishing to outbox/<date>/
  build       rebuild the site into docs/
  preview     build, then open the site in a browser
  status      recent notes, outbox state and the video library
  catalog     scan the watch folders and update the video catalog
  transcribe  transcribe new/changed recordings locally (whisper)
  watch       catalog + transcribe on a loop (foreground)
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_site  # noqa: E402
import catalog  # noqa: E402
import outbox  # noqa: E402
import transcribe  # noqa: E402
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

    index = catalog.load_index()
    videos = index.get("videos") or {}
    if videos:
        done = sum(1 for v in videos.values() if (v.get("transcript") or {}).get("status") == "done")
        pending = sum(
            1 for v in videos.values()
            if not v.get("missing") and (v.get("transcript") or {}).get("status") != "done"
        )
        print(f"library: {len(videos)} recordings · {done} transcribed · {pending} pending  (catalog/)")

    days = content.all_days()[:10]
    if days:
        print()
        print("recent notes   (o = outbox ready, · = not yet):")
        for day in days:
            ready = (ROOT / "outbox" / day.date / "manifest.txt").exists()
            title = (day.title or "")[:44]
            print(f"  {day.date}  {title:<46} {'o' if ready else '·'}")
    return 0


def cmd_catalog(args) -> int:
    summary = catalog.catalog()
    print(f"library — {summary['total']} recordings · {summary['duration']} of footage")
    for root, count in summary["roots"].items():
        print(f"  {count:>3}  {root}")
    print(f"  transcripts: {summary['done']} done · {summary['pending']} pending · {summary['failed']} failed")
    print(f"  new: {summary['new']} · changed: {summary['changed']} · missing: {summary['missing']}")
    print("  wrote catalog/index.json + catalog/catalog.md")
    return 0


def cmd_transcribe(args) -> int:
    return transcribe.run(limit=args.limit, only=args.id, force=args.force)


def cmd_watch(args) -> int:
    interval = max(30, int(args.interval or 600))
    print(f"watching for new recordings every {interval}s — ctrl-c to stop")
    try:
        while True:
            stamp = dt.datetime.now().strftime("%H:%M:%S")
            summary = catalog.catalog()
            if summary["pending"]:
                print(f"[{stamp}] {summary['total']} recordings · {summary['pending']} to transcribe "
                      f"(new {summary['new']}, changed {summary['changed']})")
                transcribe.run(limit=args.limit or None)
            else:
                print(f"[{stamp}] {summary['total']} recordings · nothing to transcribe")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("stopped")
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

    p = sub.add_parser("status", help="recent notes, outbox state and the video library")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("catalog", help="scan the watch folders and update the video catalog")
    p.set_defaults(func=cmd_catalog)

    p = sub.add_parser("transcribe", help="transcribe new/changed recordings locally")
    p.add_argument("--limit", type=int, help="max recordings to process this run")
    p.add_argument("--id", help="only recordings whose id or filename contains this")
    p.add_argument("--force", action="store_true", help="redo recordings already transcribed")
    p.set_defaults(func=cmd_transcribe)

    p = sub.add_parser("watch", help="catalog + transcribe on a loop (foreground)")
    p.add_argument("--interval", type=int, default=600, help="seconds between scans (default 600)")
    p.add_argument("--limit", type=int, help="max transcriptions per cycle")
    p.set_defaults(func=cmd_watch)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
