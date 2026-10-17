"""Configuration: config.yaml, loaded once and shared."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
with open(ROOT / "config.yaml", encoding="utf-8") as fh:
    _CONFIG = yaml.safe_load(fh) or {}


def root() -> Path:
    return ROOT


def project() -> dict:
    return _CONFIG.get("project") or {}


def social(name: str) -> dict:
    return (_CONFIG.get("social") or {}).get(name) or {}


def drafting() -> dict:
    return _CONFIG.get("drafting") or {}


def media_watch() -> dict:
    return _CONFIG.get("media_watch") or {}


def transcribe() -> dict:
    return _CONFIG.get("transcribe") or {}
