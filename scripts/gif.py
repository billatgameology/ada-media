"""Short looping GIF previews from cataloged recordings.

The clip list lives in content/gifs.yaml so each day's chosen moment is visible
and editable. GIFs land in content/media/gifs/<date>.gif, where the build and
the outbox both pick them up through the note's media.gif field.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

import catalog
from lib import config

GIF_DIR = config.root() / "content" / "media" / "gifs"
MANIFEST = config.root() / "content" / "gifs.yaml"


def parse_time(value) -> float:
    """Accept 83, "1:23" or "0:01:23"."""
    if isinstance(value, (int, float)):
        return float(value)
    total = 0.0
    for part in str(value).strip().split(":"):
        total = total * 60 + float(part)
    return total


def load_clips() -> dict:
    if not MANIFEST.exists():
        raise RuntimeError(f"no clip list at {MANIFEST.relative_to(config.root())}")
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}
    clips = data.get("clips") or {}
    if not isinstance(clips, dict):
        raise RuntimeError(f"{MANIFEST.relative_to(config.root())}: 'clips' must be a mapping")
    return clips


def find_entry(recording: str) -> dict:
    videos = catalog.load_index().get("videos") or {}
    matches = [
        entry for entry in videos.values()
        if not entry.get("missing")
        and recording in (entry.get("name"), entry.get("id"))
    ]
    if not matches:
        matches = [
            entry for entry in videos.values()
            if not entry.get("missing")
            and recording.lower() in f"{entry.get('name', '')} {entry.get('id', '')}".lower()
        ]
    if not matches:
        raise RuntimeError(f"no cataloged recording matches {recording!r} — run: ada.py catalog")
    if len(matches) > 1:
        names = ", ".join(str(entry.get("name")) for entry in matches[:5])
        raise RuntimeError(f"{recording!r} matches {len(matches)} recordings: {names} — use the full name")
    return matches[0]


def cut(entry: dict, start: float, duration: float, out: Path,
        width: int = 640, fps: int = 10, colors: int = 64) -> dict:
    source = Path(entry["path"])
    if not source.exists():
        raise RuntimeError(f"recording is missing: {source}")

    total = float(entry.get("duration") or 0)
    start = max(0.0, float(start))
    duration = max(5.0, min(float(duration), 10.0))
    if total:
        start = min(start, max(0.0, total - 0.5))
        duration = min(duration, max(0.5, total - start))

    out.parent.mkdir(parents=True, exist_ok=True)
    palette = (
        f"fps={fps},scale={width}:-1:flags=lanczos,"
        "split[s0][s1];"
        f"[s0]palettegen=max_colors={colors}:stats_mode=diff[p];"
        "[s1][p]paletteuse=dither=none:diff_mode=rectangle"
    )
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-ss", f"{start:.3f}", "-i", str(source),
            "-t", f"{duration:.3f}",
            "-filter_complex", palette,
            "-loop", "0", str(out),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        tail = " | ".join((result.stderr or "").strip().splitlines()[-4:])
        raise RuntimeError(f"ffmpeg failed: {tail}")

    # A still cover for platforms that don't animate GIF uploads (Instagram).
    cover = out.with_suffix(".jpg")
    still_at = start + min(0.5, duration / 2)
    still = subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-ss", f"{still_at:.3f}", "-i", str(source),
            "-frames:v", "1", "-q:v", "2", str(cover),
        ],
        capture_output=True, text=True,
    )
    if still.returncode != 0:
        cover = None

    return {"path": out, "cover": cover, "start": start, "duration": duration,
            "size_mb": out.stat().st_size / (1024 * 1024)}


def run(date: str | None = None, all_days: bool = False,
        width: int = 640, fps: int = 10, colors: int = 64,
        duration: float | None = None) -> int:
    clips = load_clips()
    if all_days:
        dates = sorted(clips)
    elif date:
        if date not in clips:
            raise RuntimeError(
                f"no GIF clip defined for {date} in content/gifs.yaml"
                + (" — that day has no recording" if date == "2026-10-14" else "")
            )
        dates = [date]
    else:
        raise RuntimeError("choose --date YYYY-MM-DD or --all")

    GIF_DIR.mkdir(parents=True, exist_ok=True)
    for day in dates:
        spec = clips[day] or {}
        entry = find_entry(str(spec.get("recording") or ""))
        seconds = float(duration if duration is not None else spec.get("duration") or 8)
        out = GIF_DIR / f"{day}.gif"
        result = cut(entry, parse_time(spec.get("start") or 0), seconds, out,
                     width=width, fps=fps, colors=colors)
        cover = " + cover" if result.get("cover") else ""
        print(
            f"{day}  {entry.get('name')} @ {spec.get('start')}  "
            f"{result['duration']:.0f}s → {out.relative_to(config.root())}  "
            f"({result['size_mb']:.1f} MB{cover})"
        )
    return 0
