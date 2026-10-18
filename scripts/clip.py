"""Automatic highlight reels: score transcript moments, cut the best ones.

Local, free, no uploads. Reads the timed transcript, groups speech into blocks,
scores each block (development keywords, speech density, lexical diversity,
length sweet spot), then cuts the top blocks into one reel with ffmpeg.
Outputs land in catalog/clips/.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import catalog
import transcribe
from lib import config

CLIPS_DIR = catalog.CATALOG_DIR / "clips"

# Words that tend to mark "a development happened" in dev/demo recordings.
KEYWORDS = {
    "fixed", "fix", "works", "worked", "working", "bug", "error", "crash",
    "broke", "broken", "implemented", "added", "shipped", "finally",
    "learned", "decided", "switched", "changed", "improved", "faster",
    "success", "demo", "noteworthy", "feature", "problem", "issue",
    "instead", "replaced", "built", "created", "saved", "save", "done",
}
WORD_RE = re.compile(r"[A-Za-z']+")


def stamp(seconds: float) -> str:
    minutes, secs = divmod(int(round(seconds or 0)), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


# ── inputs ─────────────────────────────────────────────────────────────

def load_entry(only: str) -> dict:
    index = catalog.load_index()
    videos = index.get("videos") or {}
    matches = [
        e for e in videos.values()
        if not e.get("missing")
        and only.lower() in f"{e.get('id', '')} {e.get('name', '')}".lower()
    ]
    if not matches:
        raise RuntimeError(f"no cataloged recording matches {only!r} — run: ada.py catalog")
    if len(matches) > 1:
        names = ", ".join(str(m.get("name")) for m in matches[:5])
        raise RuntimeError(f"{only!r} matches {len(matches)} recordings: {names} — be more specific")
    return matches[0]


def segments(entry: dict) -> list[dict]:
    rel = (entry.get("transcript") or {}).get("json") or f"catalog/transcripts/{entry['id']}.json"
    path = config.root() / rel
    if not path.exists():
        raise RuntimeError(f"no transcript for {entry.get('name')} — run: ada.py transcribe")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("segments") or []


def parse_range(token: str) -> tuple[float, float]:
    def to_seconds(text: str) -> float:
        total = 0.0
        for part in text.strip().split(":"):
            total = total * 60 + float(part)
        return total

    if "-" not in token:
        raise RuntimeError(f"bad range {token!r} — use start-end like 3:12-4:00")
    left, _, right = token.partition("-")
    start, end = to_seconds(left), to_seconds(right)
    if end <= start:
        raise RuntimeError(f"bad range {token!r}: end must be after start")
    return start, end


def load_plan(path: str) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    blocks = data.get("blocks") if isinstance(data, dict) else data
    if not isinstance(blocks, list) or not blocks:
        raise RuntimeError(f"{path} has no blocks")
    return [
        {"start": float(b["start"]), "end": float(b["end"]),
         "text": str(b.get("text") or ""), "score": b.get("score")}
        for b in blocks
    ]


# ── scoring ────────────────────────────────────────────────────────────

def _blocks(segments: list[dict], gap: float = 2.5, max_len: float = 45.0) -> list[dict]:
    blocks: list[dict] = []
    current: dict | None = None
    for seg in segments:
        start = float(seg.get("start") or 0)
        end = float(seg.get("end") or 0)
        text = (seg.get("text") or "").strip()
        if not text or end <= start:
            continue
        if current and start - current["end"] <= gap and end - current["start"] <= max_len:
            current["end"] = end
            current["parts"].append((start, end, text))
        else:
            if current:
                blocks.append(current)
            current = {"start": start, "end": end, "parts": [(start, end, text)]}
    if current:
        blocks.append(current)
    for block in blocks:
        block["text"] = " ".join(p[2] for p in block["parts"]).strip()
    return blocks


def _score(block: dict) -> None:
    text = block["text"]
    words = [w.lower() for w in WORD_RE.findall(text)]
    score = float(min(sum(1 for w in words if w in KEYWORDS), 5)) * 3.0

    spoken = sum(p[1] - p[0] for p in block["parts"]) or (block["end"] - block["start"])
    density = len(text) / max(spoken, 1.0)
    score += 2.0 if density > 6 else (1.0 if density > 4.5 else 0.0)

    if words:
        diversity = len(set(words)) / len(words)
        if len(words) >= 12 and diversity < 0.35:      # loops like "Thank you. Thank you."
            score -= 8.0
        elif diversity > 0.65:
            score += 1.0

    duration = block["end"] - block["start"]
    if 10 <= duration <= 40:
        score += 2.0
    elif duration < 6:
        score -= 2.0
    block["score"] = round(score, 1)


def auto_plan(segments: list[dict], target: float = 90.0, max_blocks: int = 6) -> list[dict]:
    blocks = _blocks(segments)
    for block in blocks:
        _score(block)
    ranked = sorted(blocks, key=lambda b: (b["score"], b["end"] - b["start"]), reverse=True)

    chosen: list[dict] = []
    total = 0.0
    for block in ranked:
        if len(chosen) >= max_blocks:
            break
        duration = block["end"] - block["start"]
        if chosen and (block["score"] < -2 or total + duration > target * 1.35):
            continue
        chosen.append(block)
        total += duration
        if total >= target:
            break
    if not chosen:  # nothing scored well; fall back to the longest blocks
        chosen = sorted(blocks, key=lambda b: b["end"] - b["start"], reverse=True)[:max_blocks]
    return sorted(chosen, key=lambda b: b["start"])


def plan_from_ranges(segments: list[dict], ranges: list[tuple[float, float]]) -> list[dict]:
    plan = []
    for start, end in ranges:
        text = " ".join(
            (s.get("text") or "").strip() for s in segments
            if float(s.get("end") or 0) > start and float(s.get("start") or 0) < end
        )
        plan.append({"start": round(start, 2), "end": round(end, 2), "score": None, "text": text.strip()})
    return plan


# ── cutting ────────────────────────────────────────────────────────────

def _run(cmd: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
    if result.returncode != 0:
        tail = " | ".join((result.stderr or "").strip().splitlines()[-4:])
        raise RuntimeError(f"ffmpeg failed: {tail}")


def _reel_segments(segments: list[dict], plan: list[dict]) -> list[dict]:
    out, offset = [], 0.0
    for block in plan:
        start, end = block["start"], block["end"]
        for seg in segments:
            seg_start = float(seg.get("start") or 0)
            seg_end = float(seg.get("end") or 0)
            if seg_end <= start or seg_start >= end:
                continue
            out.append({
                "start": offset + max(seg_start, start) - start,
                "end": offset + min(seg_end, end) - start,
                "text": (seg.get("text") or "").strip(),
            })
        offset += end - start
    return out


def cut_reel(entry: dict, plan: list[dict], segments: list[dict],
             vertical: bool = False, burn: bool = False) -> dict:
    source = Path(entry["path"])
    if entry.get("duration"):
        for block in plan:  # transcript timestamps can overshoot the file end
            block["end"] = min(block["end"], float(entry["duration"]))
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{entry['id']}-reel" + ("-vertical" if vertical else "")
    base = CLIPS_DIR / stem
    tmp = CLIPS_DIR / f".{entry['id']}-parts"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    for i, block in enumerate(plan):
        _run([
            "ffmpeg", "-y", "-v", "error",
            "-ss", f"{block['start']:.3f}", "-i", str(source),
            "-t", f"{block['end'] - block['start']:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-movflags", "+faststart",
            f"{i:02d}.mp4",
        ], cwd=tmp)

    listing = tmp / "list.txt"
    listing.write_text("".join(f"file '{i:02d}.mp4'\n" for i in range(len(plan))), encoding="utf-8")
    raw = base.with_suffix(".raw.mp4")
    _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "list.txt",
          "-c", "copy", str(raw)], cwd=tmp)
    shutil.rmtree(tmp)

    srt = base.with_suffix(".srt")
    srt.write_text(transcribe._srt(_reel_segments(segments, plan)), encoding="utf-8")
    plan_path = base.with_suffix(".plan.json")
    plan_path.write_text(json.dumps({"source": entry.get("name"), "blocks": plan}, indent=2) + "\n",
                         encoding="utf-8")

    final = base.with_suffix(".mp4")
    if vertical or burn:
        if vertical:
            chain = (
                "[0:v]split=2[bg][fg];"
                "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,gblur=sigma=25[bgb];"
                "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fgs];"
                "[bgb][fgs]overlay=(W-w)/2:(H-h)/2"
            )
            chain += f",subtitles={srt.name}[v]" if burn else "[v]"
        else:
            chain = f"[0:v]subtitles={srt.name}[v]"
        _run([
            "ffmpeg", "-y", "-v", "error", "-i", raw.name,
            "-filter_complex", chain, "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
            "-c:a", "copy", "-movflags", "+faststart", final.name,
        ], cwd=CLIPS_DIR)
        raw.unlink()
    else:
        raw.replace(final)

    return {
        "reel": final,
        "srt": srt,
        "plan_path": plan_path,
        "duration": sum(b["end"] - b["start"] for b in plan),
    }
