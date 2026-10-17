"""Video library: scan the watch folders, probe metadata, keep the catalog.

Everything lands in catalog/ (gitignored): index.json (machine view), catalog.md
(human view) and transcripts/ (written by transcribe.py).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from lib import config

CATALOG_DIR = config.root() / "catalog"
TRANSCRIPT_DIR = CATALOG_DIR / "transcripts"
INDEX_PATH = CATALOG_DIR / "index.json"

DEFAULT_EXTS = [".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"]
STATUS_LABELS = {
    "done": "done",
    "pending": "pending",
    "changed": "changed — re-run transcribe",
    "failed": "failed",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")
    return text[:60] or "video"


def video_id(path: Path) -> str:
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:8]
    return f"{_slug(path.stem)}-{digest}"


def length_str(seconds) -> str:
    try:
        seconds = float(seconds or 0)
    except (TypeError, ValueError):
        return "?"
    minutes, secs = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def watch_cfg() -> dict:
    return config.media_watch()


def _roots() -> list[Path]:
    return [Path(str(p)).expanduser() for p in (watch_cfg().get("roots") or [])]


def find_videos() -> list[Path]:
    cfg = watch_cfg()
    exts = {str(e).lower() for e in (cfg.get("extensions") or DEFAULT_EXTS)}
    excludes = [str(t) for t in (cfg.get("exclude_dirs") or [])]
    min_bytes = int(cfg.get("min_size_mb") or 0) * 1024 * 1024
    found: list[Path] = []
    for root in _roots():
        if not root.is_dir():
            print(f"  watch root missing, skipped: {root}")
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith(".") and not any(tok in d for tok in excludes)
            ]
            for name in filenames:
                if name.startswith(".") or Path(name).suffix.lower() not in exts:
                    continue
                path = Path(dirpath) / name
                try:
                    stat = path.stat()
                except OSError:
                    continue
                if stat.st_size < min_bytes:
                    continue
                if time.time() - stat.st_mtime < 30:  # likely still being written
                    continue
                found.append(path)
    return sorted(found, key=str)


def _root_of(path: Path, roots: list[Path]) -> str:
    for root in roots:
        try:
            path.relative_to(root)
            return str(root)
        except ValueError:
            continue
    return str(path.parent)


def probe(path: Path) -> dict:
    """Metadata via ffprobe; returns {} when ffprobe is unavailable or fails."""
    data = {}
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=180,
        )
        if out.returncode == 0:
            data = json.loads(out.stdout)
    except Exception:
        data = {}

    def num(value):
        try:
            return round(float(value), 3)
        except (TypeError, ValueError):
            return None

    fmt = data.get("format") or {}
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})

    fps = None
    rate = str(video.get("avg_frame_rate") or "")
    try:
        top, _, bottom = rate.partition("/")
        fps = round(float(top) / float(bottom), 3) if float(bottom) else None
    except (TypeError, ValueError):
        fps = None

    return {
        "duration": num(fmt.get("duration")),
        "width": video.get("width"),
        "height": video.get("height"),
        "fps": fps,
        "codec": video.get("codec_name") or "",
        "audio_codec": audio.get("codec_name") or "",
        "created": (fmt.get("tags") or {}).get("creation_time") or "",
    }


def load_index() -> dict:
    if INDEX_PATH.exists():
        try:
            return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"videos": {}}


def save_index(index: dict) -> None:
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = INDEX_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(INDEX_PATH)


def catalog() -> dict:
    """Scan the watch folders, update the index, return a summary."""
    roots = _roots()
    known = load_index().get("videos") or {}
    fresh: dict[str, dict] = {}
    new = changed = 0

    for path in find_videos():
        stat = path.stat()
        ident = video_id(path)
        old = known.get(ident) or {}
        unchanged = (
            old.get("size") == stat.st_size
            and abs(float(old.get("mtime") or 0) - stat.st_mtime) < 1
        )

        entry = {k: old.get(k) for k in
                 ("duration", "width", "height", "fps", "codec", "audio_codec", "created")}
        if not unchanged:
            entry.update(probe(path))

        transcript = old.get("transcript") or {}
        if not unchanged:
            if transcript.get("status") == "done":
                transcript = {**transcript, "status": "changed"}
            elif transcript.get("status") == "failed":
                transcript = {**transcript, "status": "pending"}
            elif not transcript:
                transcript = {"status": "pending"}
            if old:
                changed += 1
            else:
                new += 1

        entry.update({
            "id": ident,
            "path": str(path),
            "root": _root_of(path, roots),
            "name": path.name,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "missing": False,
            "transcript": transcript or {"status": "pending"},
        })
        fresh[ident] = entry

    for ident, old in known.items():
        if ident not in fresh:
            gone = dict(old)
            gone["missing"] = True
            fresh[ident] = gone

    present = [e for e in fresh.values() if not e.get("missing")]
    statuses = [(e.get("transcript") or {}).get("status") for e in present]
    per_root: dict[str, int] = {}
    for entry in present:
        per_root[entry.get("root", "?")] = per_root.get(entry.get("root", "?"), 0) + 1

    index = {"generated": _now(), "roots": [str(r) for r in roots], "videos": fresh}
    save_index(index)
    _write_markdown(index)

    return {
        "total": len(present),
        "duration": length_str(sum(e.get("duration") or 0 for e in present)),
        "roots": per_root,
        "done": sum(1 for s in statuses if s == "done"),
        "pending": sum(1 for s in statuses if s not in ("done", "failed")),
        "failed": sum(1 for s in statuses if s == "failed"),
        "new": new,
        "changed": changed,
        "missing": len(fresh) - len(present),
    }


def _write_markdown(index: dict) -> None:
    entries = sorted(
        index.get("videos", {}).values(),
        key=lambda e: e.get("mtime") or 0,
        reverse=True,
    )
    present = [e for e in entries if not e.get("missing")]
    total = sum(e.get("duration") or 0 for e in present)
    lines = [
        "# Video catalog",
        "",
        f"{len(present)} recordings · {length_str(total)} of footage · updated {index.get('generated', '')}",
        "",
        "| recorded | recording | length | size | resolution | transcript |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in present:
        when = datetime.fromtimestamp(entry.get("mtime") or 0).strftime("%Y-%m-%d %H:%M")
        size_mb = (entry.get("size") or 0) / (1024 * 1024)
        width, height = entry.get("width"), entry.get("height")
        res = f"{width}×{height}" if width and height else "?"
        name = str(entry.get("name") or "").replace("|", "\\|")
        status = (entry.get("transcript") or {}).get("status") or "pending"
        if status == "done":
            transcript = f"[done](transcripts/{entry['id']}.txt)"
        else:
            transcript = STATUS_LABELS.get(status, status)
        lines.append(
            f"| {when} | {name} | {length_str(entry.get('duration'))} "
            f"| {size_mb:.0f} MB | {res} | {transcript} |"
        )
    missing = [e for e in entries if e.get("missing")]
    if missing:
        lines += ["", f"_{len(missing)} recording(s) no longer on disk (kept in index.json)._"]
    lines += ["", "Watch roots:", ""] + [f"- `{r}`" for r in index.get("roots", [])]
    (CATALOG_DIR / "catalog.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
