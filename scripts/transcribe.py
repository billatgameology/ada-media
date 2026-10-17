"""Local transcription for cataloged recordings.

Engines: mlx-whisper (Apple Silicon; installed via requirements.txt) or
faster-whisper (anywhere: pip install faster-whisper). Outputs land in
catalog/transcripts/<id>.{txt,srt,json}.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import catalog
from lib import config

MLX_MODELS = {
    "turbo": "mlx-community/whisper-large-v3-turbo",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "tiny": "mlx-community/whisper-tiny-mlx",
}
FASTER_MODELS = {
    "turbo": "large-v3-turbo",
    "large-v3": "large-v3",
    "medium": "medium",
    "small": "small",
    "base": "base",
    "tiny": "tiny",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def engine() -> str:
    want = str(config.transcribe().get("engine") or "auto").strip().lower()
    if want in ("mlx", "faster"):
        return want
    try:
        import mlx_whisper  # noqa: F401
        return "mlx"
    except ImportError:
        pass
    try:
        import faster_whisper  # noqa: F401
        return "faster"
    except ImportError:
        return ""


def _model() -> str:
    return str(config.transcribe().get("model") or "turbo").strip().lower() or "turbo"


def _language() -> str | None:
    lang = str(config.transcribe().get("language") or "auto").strip().lower()
    return None if lang in ("", "auto") else lang


def _mlx_repo(name: str) -> str:
    return name if "/" in name else MLX_MODELS.get(name, MLX_MODELS["turbo"])


def _faster_name(name: str) -> str:
    return name if "/" in name else FASTER_MODELS.get(name, FASTER_MODELS["turbo"])


def transcribe_file(path: Path, engine_name: str, model: str) -> dict:
    language = _language()
    if engine_name == "mlx":
        import mlx_whisper
        result = mlx_whisper.transcribe(
            str(path),
            path_or_hf_repo=_mlx_repo(model),
            language=language,
            condition_on_previous_text=False,
        )
        return {
            "engine": "mlx",
            "language": result.get("language") or "?",
            "text": result.get("text") or "",
            "segments": result.get("segments") or [],
        }

    import faster_whisper
    model_obj = faster_whisper.WhisperModel(_faster_name(model), device="auto", compute_type="auto")
    segments, info = model_obj.transcribe(str(path), language=language, condition_on_previous_text=False)
    segs = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
    return {
        "engine": "faster",
        "language": getattr(info, "language", "?") or "?",
        "text": "".join(s["text"] for s in segs),
        "segments": segs,
    }


def _ts(seconds) -> str:
    ms = int(round(max(0.0, float(seconds or 0)) * 1000))
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _srt(segments: list) -> str:
    blocks, index = [], 0
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        index += 1
        blocks.append(f"{index}\n{_ts(seg.get('start'))} --> {_ts(seg.get('end'))}\n{text}\n")
    return "\n".join(blocks)


def _write_outputs(entry: dict, result: dict) -> dict:
    catalog.TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    base = catalog.TRANSCRIPT_DIR / entry["id"]
    text = (result["text"] or "").strip()
    base.with_suffix(".txt").write_text(text + "\n", encoding="utf-8")
    base.with_suffix(".srt").write_text(_srt(result["segments"]), encoding="utf-8")
    payload = {
        "id": entry["id"],
        "path": entry["path"],
        "engine": result["engine"],
        "language": result["language"],
        "text": text,
        "segments": [
            {"start": round(float(s.get("start") or 0), 2),
             "end": round(float(s.get("end") or 0), 2),
             "text": (s.get("text") or "").strip()}
            for s in result["segments"]
        ],
    }
    base.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "done",
        "at": _now(),
        "engine": result["engine"],
        "model": _model(),
        "language": result["language"],
        "chars": len(text),
        "txt": f"catalog/transcripts/{entry['id']}.txt",
        "srt": f"catalog/transcripts/{entry['id']}.srt",
        "json": f"catalog/transcripts/{entry['id']}.json",
    }


def run(limit: int | None = None, only: str | None = None, force: bool = False) -> int:
    engine_name = engine()
    if not engine_name:
        print("no transcription engine installed.")
        print("  Apple Silicon:  .venv/bin/pip install mlx-whisper")
        print("  elsewhere:      .venv/bin/pip install faster-whisper")
        return 1

    index = catalog.load_index()
    videos = index.get("videos") or {}
    items = []
    for entry in videos.values():
        if entry.get("missing"):
            continue
        status = (entry.get("transcript") or {}).get("status")
        if only:
            haystack = f"{entry.get('id') or ''} {entry.get('name') or ''}".lower()
            if only.lower() not in haystack:
                continue
        if not force and status == "done":
            continue
        items.append(entry)
    if not items:
        print("nothing to transcribe — everything is done (use --force to redo).")
        return 0

    items.sort(key=lambda e: e.get("duration") or 1e9)  # shortest first: quick wins
    if limit:
        items = items[:limit]

    model = _model()
    print(f"transcribing {len(items)} recording(s) · engine {engine_name} · model {model}")
    ok = fail = 0
    for i, entry in enumerate(items, 1):
        name = entry.get("name") or entry.get("id")
        duration = entry.get("duration")
        print(f"[{i}/{len(items)}] {name}  ({catalog.length_str(duration)})")
        started = time.time()
        try:
            result = transcribe_file(Path(entry["path"]), engine_name, model)
        except KeyboardInterrupt:
            print("interrupted — progress saved")
            catalog.save_index(index)
            return 130
        except Exception as exc:  # one bad file shouldn't stop the batch
            entry["transcript"] = {"status": "failed", "error": str(exc)[:300], "at": _now()}
            catalog.save_index(index)
            print(f"    failed: {exc}")
            fail += 1
            continue
        entry["transcript"] = _write_outputs(entry, result)
        catalog.save_index(index)
        elapsed = max(time.time() - started, 0.1)
        speed = f"{duration / elapsed:.1f}× realtime" if duration else f"{elapsed:.0f}s"
        print(f"    done in {elapsed / 60:.1f} min ({speed}) · "
              f"{entry['transcript']['chars']} chars · {result['language']}")
        ok += 1

    print(f"finished: {ok} transcribed · {fail} failed")
    return 0 if fail == 0 else 1
