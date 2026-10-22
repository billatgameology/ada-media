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
  clip        cut an automatic highlight reel from a recording
  gif         cut a short looping GIF preview from a recording
  story       build a day's story: one script, highlights and a reel from all its clips
  code        list the code repo's commits for a day (for the note's "In code" section)
  find        search a day script for a phrase and print its recording + timecode
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_site  # noqa: E402
import catalog  # noqa: E402
import clip  # noqa: E402
import gif  # noqa: E402
import outbox  # noqa: E402
import story  # noqa: E402
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
    text = (template.replace("{{date}}", date)
            .replace("{{code_url}}", str(config.project().get("code_url") or ""))
            .replace("{{context}}", _git_context() or "(no commits found)"))
    path.write_text(text, encoding="utf-8")
    print(f"created {path.relative_to(ROOT)}")
    print("edit it, then:")
    print("  python scripts/ada.py outbox    # prepare the posts for manual publishing")
    print("  python scripts/ada.py build     # rebuild the site")
    print(f"  git add -A && git commit -m 'daily: {date}' && git push")
    return 0


def _code_repo() -> Path:
    """The project repo whose commits feed the note's "In code" section."""
    cfg = config.drafting()
    raw = str(cfg.get("code_repo") or cfg.get("context_git") or ".")
    repo = Path(raw).expanduser()
    return repo if repo.is_absolute() else (ROOT / repo)


def _git_context() -> str:
    cfg = config.drafting()
    repo = _code_repo()
    count = int(cfg.get("context_commits") or 8)
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "log", "--oneline", f"-{count}"],
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


def cmd_clip(args) -> int:
    try:
        entry = clip.load_entry(args.id)
        segments = clip.segments(entry)
    except RuntimeError as exc:
        print(exc)
        return 1
    try:
        if args.range:
            plan = clip.plan_from_ranges(segments, [clip.parse_range(r) for r in args.range])
        elif args.plan:
            plan = clip.load_plan(args.plan)
        else:
            plan = clip.auto_plan(segments, target=args.target, max_blocks=args.max_blocks)
    except RuntimeError as exc:
        print(exc)
        return 1
    if not plan:
        print("no usable speech found in this recording")
        return 1

    total = sum(b["end"] - b["start"] for b in plan)
    print(f"highlight plan for {entry.get('name')} · {total:.0f}s across {len(plan)} block(s):")
    for block in plan:
        marker = f"score {block['score']}" if block.get("score") is not None else "manual"
        text = " ".join(block["text"].split())[:72]
        print(f"  {clip.stamp(block['start'])}–{clip.stamp(block['end'])} "
              f"({block['end'] - block['start']:.0f}s · {marker})  {text}")

    try:
        result = clip.cut_reel(entry, plan, segments, vertical=args.vertical, burn=args.burn)
    except RuntimeError as exc:
        print(exc)
        return 1
    print(f"reel → {result['reel'].relative_to(ROOT)}  ({result['duration']:.0f}s)")
    print(f"  subtitles: {result['srt'].relative_to(ROOT)}")
    print(f"  edit the plan and re-cut with:  --plan {result['plan_path'].relative_to(ROOT)}")
    return 0


def cmd_gif(args) -> int:
    try:
        return gif.run(date=args.date, all_days=args.all, width=args.width, fps=args.fps,
                       colors=args.colors, duration=args.duration)
    except RuntimeError as exc:
        print(exc)
        return 1


def cmd_story(args) -> int:
    try:
        return story.run(args.date, target=args.target, top=args.top, make_reel=not args.no_reel,
                         plan_path=args.plan, vertical=args.vertical, burn=args.burn)
    except RuntimeError as exc:
        print(exc)
        return 1


def cmd_code(args) -> int:
    repo = _code_repo()
    date = args.date or dt.date.today().isoformat()
    if not (repo / ".git").exists():
        print(f"code repo not found: {repo}  (set drafting.code_repo in config.yaml)")
        return 1
    result = subprocess.run(
        ["git", "-C", str(repo), "log",
         f"--since={date} 00:00:00", f"--until={date} 23:59:59",
         "--reverse", "--date=format:%H:%M", "--pretty=format:%h%x09%ad%x09%s"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print(result.stderr.strip() or "git log failed")
        return 1
    commits = [line.split("\t", 2) for line in result.stdout.splitlines() if line.strip()]
    print(f"{repo.name} — {date}")
    if not commits:
        print("  no commits on this date")
    for short, stamp, subject in commits:
        extra = ""
        if args.stat:
            stat = subprocess.run(
                ["git", "-C", str(repo), "show", "--shortstat", "--format=", short],
                capture_output=True, text=True, timeout=30,
            ).stdout.strip()
            if stat:
                extra = f"  ({stat})"
        print(f"  {short}  {stamp}  {subject}{extra}")
        if args.body:
            body = subprocess.run(
                ["git", "-C", str(repo), "show", "-s", "--format=%b", short],
                capture_output=True, text=True, timeout=30,
            ).stdout.strip()
            for line in body.splitlines():
                print(f"      {line}")
    dirty = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True, text=True, timeout=30,
    ).stdout.strip()
    if dirty:
        print("\nuncommitted changes:")
        for line in dirty.splitlines():
            print(f"  {line}")
    return 0


def _script_rows(path: Path):
    """Yield (start_clock, recording, timecode, text) from a day script."""
    clock = recording = None
    for line in path.read_text(encoding="utf-8").splitlines():
        header = re.match(r"^## \[(\d\d:\d\d)\] (.+?)  \((\d+:\d\d)\)", line)
        if header:
            clock, recording = header.group(1), header.group(2)
            continue
        row = re.match(r"^\[(\d+:\d\d)\] (.*)", line)
        if row and recording:
            yield clock, recording, row.group(1), row.group(2)


def cmd_find(args) -> int:
    date = args.date or dt.date.today().isoformat()
    path = ROOT / "catalog" / "stories" / f"{date}.script.md"
    if not path.exists():
        print(f"no day script for {date} — run: python scripts/ada.py story --date {date} --no-reel")
        return 1
    try:
        patterns = [re.compile(p, re.I) for p in args.grep]
    except re.error as exc:
        print(f"bad pattern: {exc}")
        return 1
    shown = 0
    for clock, recording, stamp, text in _script_rows(path):
        if any(p.search(text) for p in patterns):
            print(f"{recording}  [{clock}] @ {stamp}  {text}")
            shown += 1
            if args.limit and shown >= args.limit:
                break
    if not shown:
        print("no matches")
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

    p = sub.add_parser("clip", help="cut an automatic highlight reel from a recording")
    p.add_argument("--id", required=True, help="recording id or filename substring")
    p.add_argument("--target", type=int, default=90, help="rough target length in seconds (default 90)")
    p.add_argument("--max-blocks", type=int, default=6, help="max highlight blocks (default 6)")
    p.add_argument("--range", action="append", default=[],
                   help="manual range like 3:12-4:00 (repeatable; skips auto-picking)")
    p.add_argument("--plan", help="path to a plan json to use instead of auto-picking")
    p.add_argument("--vertical", action="store_true",
                   help="9:16 with blurred background, for TikTok/Reels/Shorts")
    p.add_argument("--burn", action="store_true", help="burn the subtitles into the video")
    p.set_defaults(func=cmd_clip)

    p = sub.add_parser("gif", help="cut a 5-10s looping GIF preview from a recording")
    p.add_argument("--date", help="YYYY-MM-DD from content/gifs.yaml")
    p.add_argument("--all", action="store_true", help="cut every clip in content/gifs.yaml")
    p.add_argument("--duration", type=float, help="override seconds (5-10)")
    p.add_argument("--width", type=int, default=480, help="pixel width (default 480)")
    p.add_argument("--fps", type=int, default=8, help="frames per second (default 8)")
    p.add_argument("--colors", type=int, default=64, help="palette colors (default 64)")
    p.set_defaults(func=cmd_gif)

    p = sub.add_parser("story", help="build a day's story from all its recordings")
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--target", type=int, default=150, help="rough reel length in seconds (default 150)")
    p.add_argument("--top", type=int, default=12, help="how many candidates to list (default 12)")
    p.add_argument("--no-reel", action="store_true", help="skip cutting the reel")
    p.add_argument("--plan", help="cut the reel from this plan json instead of auto-picking")
    p.add_argument("--vertical", action="store_true", help="9:16 reel")
    p.add_argument("--burn", action="store_true", help="burn subtitles into the reel")
    p.set_defaults(func=cmd_story)

    p = sub.add_parser("code", help="list the code repo's commits for a day")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p.add_argument("--stat", action="store_true", help="include files/insertions/deletions")
    p.add_argument("--body", action="store_true", help="include commit message bodies")
    p.set_defaults(func=cmd_code)

    p = sub.add_parser("find", help="search a day script for a phrase and print recording + timecode")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p.add_argument("--grep", action="append", required=True, metavar="PATTERN",
                   help="regex to search for (repeatable)")
    p.add_argument("--limit", type=int, default=30, help="stop after N matches (default 30)")
    p.set_defaults(func=cmd_find)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
