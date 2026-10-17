"""The publish ledger: what went out where, so nothing double-posts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import config

STATE_DIR = config.root() / ".state"


def _read(name: str, default):
    path = STATE_DIR / name
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return default
    return default


def _write(name: str, data) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    (STATE_DIR / name).write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def published() -> dict:
    return _read("published.json", {"days": {}})


def result_for(date: str, platform: str):
    return ((published().get("days") or {}).get(date) or {}).get(platform)


def record(date: str, platform: str, result: dict) -> None:
    data = published()
    entry = dict(result)
    entry["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data.setdefault("days", {}).setdefault(date, {})[platform] = entry
    _write("published.json", data)


def load_json(name: str, default=None):
    return _read(name, default)


def save_json(name: str, data) -> None:
    _write(name, data)
