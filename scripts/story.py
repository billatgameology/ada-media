"""Daily stories: merge a day's recordings into one script, find the highlights,
cut a reel and draft a journal.

Machine part: day script, scored candidates across every clip, an auto reel and a
draft journal. Human part: read the script (or hand it to an assistant), write the
real story as <date>.md and re-cut from a curated plan with `story --plan`.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import catalog
import clip
from lib import config

STORIES_DIR = catalog.CATALOG_DIR / "stories"
DATE_RE = re.compile(r"(20\d{2})[-_. ]?(\d{2})[-_. ]?(\d{2})")
TIME_RE_BARE = re.compile(r"-(\d{2})(\d{2})(\d{2})-")         # …-20261016-181204-0.mp4
TIME_RE_DASH = re.compile(r" (\d{2})-(\d{2})-(\d{2})\.\w+$")  # … 15-51-15.mov


def entry_date(entry: dict) -> str:
    match = DATE_RE.search(entry.get("name") or "")
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return datetime.fromtimestamp(entry.get("mtime") or 0).strftime("%Y-%m-%d")


def _start_hint(entry: dict) -> tuple[int, int, int]:
    name = entry.get("name") or ""
    for pattern in (TIME_RE_BARE, TIME_RE_DASH):
        match = pattern.search(name)
        if match:
            return int(match.group(1)), int(match.group(2)), int(match.group(3))
    when = datetime.fromtimestamp(entry.get("mtime") or 0)
    return when.hour, when.minute, when.second


def day_entries(day: str) -> list[dict]:
    videos = catalog.load_index().get("videos") or {}
    out = [e for e in videos.values() if not e.get("missing") and entry_date(e) == day]
    return sorted(out, key=_start_hint)


def gather(day: str, target: float = 150.0, top: int = 12) -> dict:
    entries = day_entries(day)
    if not entries:
        raise RuntimeError(f"no recordings found for {day} — run: ada.py catalog")
    STORIES_DIR.mkdir(parents=True, exist_ok=True)

    transcripts: dict[str, list] = {}
    skipped: list[str] = []
    for entry in entries:
        try:
            transcripts[entry["id"]] = clip.segments(entry)
        except RuntimeError:
            skipped.append(str(entry.get("name")))

    script_lines = [f"# {day} — day script", "", f"{len(entries)} recordings", ""]
    total = 0.0
    for entry in entries:
        hour, minute, _ = _start_hint(entry)
        duration = float(entry.get("duration") or 0)
        total += duration
        script_lines.append(f"## [{hour:02d}:{minute:02d}] {entry.get('name')}  ({clip.stamp(duration)})")
        script_lines.append("")
        for seg in transcripts.get(entry["id"], []):
            text = (seg.get("text") or "").strip()
            if text:
                script_lines.append(f"[{clip.stamp(seg.get('start') or 0)}] {text}")
        script_lines.append("")
    script_path = STORIES_DIR / f"{day}.script.md"
    script_path.write_text("\n".join(script_lines) + "\n", encoding="utf-8")

    candidates: list[dict] = []
    for entry in entries:
        for block in clip._blocks(transcripts.get(entry["id"], [])):
            clip._score(block)
            if block["score"] > 0:
                candidates.append({
                    "id": entry["id"],
                    "name": entry.get("name"),
                    "start": round(block["start"], 2),
                    "end": round(block["end"], 2),
                    "score": block["score"],
                    "text": block["text"],
                })
    candidates.sort(key=lambda b: b["score"], reverse=True)
    candidates_path = STORIES_DIR / f"{day}.candidates.json"
    candidates_path.write_text(json.dumps({"date": day, "candidates": candidates}, indent=2) + "\n",
                               encoding="utf-8")

    order = {entry["id"]: i for i, entry in enumerate(entries)}
    chosen: list[dict] = []
    total_len = 0.0
    for candidate in candidates:
        if len(chosen) >= 10:
            break
        length = candidate["end"] - candidate["start"]
        if chosen and total_len + length > target * 1.3:
            continue
        chosen.append(dict(candidate))
        total_len += length
        if total_len >= target:
            break
    chosen.sort(key=lambda b: (order.get(b["id"], 99), b["start"]))

    return {
        "entries": entries,
        "total": total,
        "skipped": skipped,
        "script": script_path,
        "candidates_path": candidates_path,
        "candidate_count": len(candidates),
        "all_candidates": candidates,
        "top": candidates[:top],
        "chosen": chosen,
    }


def _draft_md(day: str, data: dict) -> str:
    lines = [
        f"# {day} — story (draft)",
        "",
        f"{len(data['entries'])} recordings · {clip.stamp(data['total'])} of footage · "
        f"{data['candidate_count']} positive moments found",
        "",
        "## Timeline",
        "",
    ]
    for entry in data["entries"]:
        hour, minute, _ = _start_hint(entry)
        best = next((c for c in data["all_candidates"] if c["id"] == entry["id"]), None)
        gist = f" — {' '.join(best['text'].split())[:90]}" if best else ""
        lines.append(f"- **{hour:02d}:{minute:02d}** `{entry.get('name')}` "
                     f"({clip.stamp(entry.get('duration'))}){gist}")
    lines += ["", "## Machine-picked highlights", ""]
    for i, candidate in enumerate(data["top"], 1):
        excerpt = " ".join(candidate["text"].split())[:150]
        lines.append(f"{i}. `{clip.stamp(candidate['start'])}–{clip.stamp(candidate['end'])}` · "
                     f"{candidate['name']} · score {candidate['score']} — “{excerpt}”")
    lines += [
        "",
        "## Files",
        "",
        f"- full script: `catalog/stories/{day}.script.md`",
        f"- candidates: `catalog/stories/{day}.candidates.json`",
        "- transcripts: `catalog/transcripts/`",
        f"- auto reel: `catalog/clips/{day}-day-reel.mp4`",
        "",
        "_Machine draft. Write the real journal from the script + candidates, save it as "
        f"`catalog/stories/{day}.md`. To publish it, promote to `content/daily/{day}.md` and run `build`._",
    ]
    return "\n".join(lines) + "\n"


def run(day: str, target: int = 150, top: int = 12, make_reel: bool = True,
        plan_path: str | None = None, vertical: bool = False, burn: bool = False) -> int:
    data = gather(day, target=float(target), top=top)

    def rel(path: Path) -> str:
        return str(path.relative_to(config.root()))

    print(f"{day} — {len(data['entries'])} recordings · {clip.stamp(data['total'])} of footage")
    if data["skipped"]:
        print(f"  skipped (no transcript): {', '.join(data['skipped'])}")
    print(f"  script → {rel(data['script'])}")
    print(f"  candidates: {data['candidate_count']} positive blocks → {rel(data['candidates_path'])}")
    if data["top"]:
        print("  top moments:")
        for candidate in data["top"][:8]:
            excerpt = " ".join(candidate["text"].split())[:56]
            print(f"    {clip.stamp(candidate['start'])}–{clip.stamp(candidate['end'])}"
                  f"  ({candidate['score']:>4})  {str(candidate['name'])[:30]:<30}  {excerpt}")

    if plan_path:
        plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
        blocks = plan.get("blocks") or []
        if not blocks:
            print(f"{plan_path} has no blocks")
            return 1
        stem = f"{day}-story-reel"
    else:
        blocks = data["chosen"]
        stem = f"{day}-day-reel"
    if make_reel and blocks:
        result = clip.cut_day_reel([dict(b) for b in blocks], stem, vertical=vertical, burn=burn)
        print(f"  reel → {rel(result['reel'])}  ({result['duration']:.0f}s)")
        print(f"    subtitles: {rel(result['srt'])} · plan: {rel(result['plan_path'])}")

    draft_path = STORIES_DIR / f"{day}.draft.md"
    draft_path.write_text(_draft_md(day, data), encoding="utf-8")
    print(f"  draft journal → {rel(draft_path)}")
    print(f"  write the real story at: catalog/stories/{day}.md (from the script + candidates)")
    return 0
