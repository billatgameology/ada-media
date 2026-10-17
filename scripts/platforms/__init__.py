"""One module per publishing target. Each implements:

    NAME, LABEL     — identifiers for the CLI
    ENV_KEYS        — env vars needed to post live
    is_enabled()    — whether config.yaml turns it on
    missing_env()   — which credentials are absent
    preview(day)    — what would be posted (no network calls)
    publish(day)    — perform the post; returns {id, url, note}

publish() is only ever called by the CLI after an explicit --live.
"""
from . import facebook, instagram, threads, tiktok, x, youtube  # noqa: F401

REGISTRY = [x, threads, instagram, facebook, tiktok, youtube]
_BY_NAME = {module.NAME: module for module in REGISTRY}


def by_name(name: str):
    try:
        return _BY_NAME[name]
    except KeyError:
        raise SystemExit(f"unknown platform '{name}' — options: {', '.join(_BY_NAME)}") from None
