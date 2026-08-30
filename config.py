"""Bot sozlamalari. Barcha maxfiy ma'lumotlar muhit o'zgaruvchilaridan (environment
variables) olinadi — bu Railway kabi platformalarda ishlash uchun to'g'ri usul.
Lokal test uchun .env fayl ham qo'llab-quvvatlanadi (agar mavjud bo'lsa)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent


def _parse_admin_ids(raw: str) -> frozenset[int]:
    ids = set()
    for part in raw.split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            ids.add(int(part))
    return frozenset(ids)


def _parse_usernames(raw: str) -> frozenset[str]:
    return frozenset(
        part.strip().lstrip("@").lower() for part in raw.split(",") if part.strip()
    )


def _resolve_database_url(raw: str) -> str:
    raw = (raw or "").strip()
    default_db = ROOT / "quiz_bot.db"
    if not raw:
        return f"sqlite+aiosqlite:///{default_db.as_posix()}"
    if raw.startswith("sqlite+aiosqlite:///"):
        path_part = raw.replace("sqlite+aiosqlite:///", "", 1)
        if path_part.startswith("./") or (
            not path_part.startswith("/") and ":" not in path_part[:3]
        ):
            return f"sqlite+aiosqlite:///{default_db.as_posix()}"
        return raw
    return raw


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: frozenset[int]
    admin_usernames: frozenset[str]
    database_url: str
    questions_per_user: int
    channel_username: str
    questions_file: Path = field(default_factory=lambda: ROOT / "data" / "questions.json")


def get_settings() -> Settings:
    # Standart adminlar so'ralganidek o'rnatilgan; ADMIN_IDS orqali qo'shimcha
    # adminlar (vergul bilan ajratilgan) qo'shilishi mumkin.
    default_admins = ["6984301219", "6750507117"]
    admin_raw = os.getenv("ADMIN_IDS", ",".join(default_admins))
    for admin_id in default_admins:
        if admin_id not in admin_raw:
            admin_raw = admin_raw + f",{admin_id}" if admin_raw.strip() else admin_id

    return Settings(
        bot_token=os.getenv("BOT_TOKEN", "").strip(),
        admin_ids=_parse_admin_ids(admin_raw),
        admin_usernames=_parse_usernames(os.getenv("ADMIN_USERNAMES", "")),
        database_url=_resolve_database_url(os.getenv("DATABASE_URL", "")),
        questions_per_user=int(os.getenv("QUESTIONS_PER_USER", "100")),
        channel_username=os.getenv("CHANNEL_USERNAME", "").strip().lstrip("@"),
    )


settings = get_settings()
