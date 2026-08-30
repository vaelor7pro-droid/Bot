"""Ish vaqtidagi sozlamalar (kanal va h.k.) — .env ni buzmasdan."""

import json
from pathlib import Path

from bot.config import get_settings

RUNTIME_PATH = Path(__file__).resolve().parents[2] / "data" / "runtime.json"


def _load() -> dict:
    if not RUNTIME_PATH.exists():
        return {}
    try:
        return json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    RUNTIME_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_channel_username() -> str:
    data = _load()
    runtime = (data.get("channel_username") or "").strip().lstrip("@")
    if runtime:
        return runtime
    return get_settings().channel_username


def set_channel_username(username: str) -> str:
    clean = username.strip().lstrip("@")
    data = _load()
    data["channel_username"] = clean
    _save(data)
    return clean
