"""Bot sozlamalari — barcha maxfiy ma'lumotlar .env faylidan olinadi."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


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
    reward_per_correct: int
    min_withdrawal: int
    questions_per_user: int
    admin_contact_username: str
    channel_username: str


def get_settings() -> Settings:
    admin_raw = os.getenv("ADMIN_IDS", "")
    admin_ids = frozenset(
        int(x.strip()) for x in admin_raw.split(",") if x.strip().isdigit()
    )

    usernames_raw = os.getenv("ADMIN_USERNAMES", "")
    admin_usernames = frozenset(
        x.strip().lstrip("@").lower()
        for x in usernames_raw.split(",")
        if x.strip()
    )

    return Settings(
        bot_token=os.getenv("BOT_TOKEN", ""),
        admin_ids=admin_ids,
        admin_usernames=admin_usernames,
        database_url=_resolve_database_url(
            os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./quiz_bot.db")
        ),
        reward_per_correct=int(os.getenv("REWARD_PER_CORRECT_ANSWER", "500")),
        min_withdrawal=int(os.getenv("MIN_WITHDRAWAL_AMOUNT", "50000")),
        questions_per_user=int(os.getenv("QUESTIONS_PER_USER", "100")),
        admin_contact_username=os.getenv("ADMIN_CONTACT_USERNAME", "")
        .strip()
        .lstrip("@"),
        channel_username=os.getenv("CHANNEL_USERNAME", "").strip().lstrip("@"),
    )
