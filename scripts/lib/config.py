"""Configuration: config.yaml + .env, loaded once and shared."""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

with open(ROOT / "config.yaml", encoding="utf-8") as fh:
    _CONFIG = yaml.safe_load(fh) or {}


def root() -> Path:
    return ROOT


def project() -> dict:
    return _CONFIG.get("project") or {}


def meta_version() -> str:
    return str((_CONFIG.get("meta") or {}).get("api_version") or "v25.0")


def social(name: str) -> dict:
    return (_CONFIG.get("social") or {}).get(name) or {}


def drafting() -> dict:
    return _CONFIG.get("drafting") or {}


def env(key: str, default=None):
    """Environment value, treating empty strings as missing."""
    value = os.environ.get(key)
    return default if value in (None, "") else value


def update_env(key: str, value: str) -> None:
    """Set KEY=value in .env, preserving everything else. Used by token refreshers."""
    path = ROOT / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out, replaced = [], False
    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.environ[key] = value
