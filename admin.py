from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import get_settings
from bot.utils.admin import is_admin
from bot.utils.runtime_settings import get_channel_username, set_channel_username
from database.crud import (
    get_user_with_stats_by_telegram_id,
    get_user_with_stats_by_username,
    list_users_with_stats,
)
from database.models import User
from database.session import async_session

router = Router()
settings = get_settings()


def _safe_name(name: str | None, max_len: int = 40) -> str:
    if not name:
        return "—"
    cleaned = " ".join(name.split())
    if len(cleaned) > max_len:
        return cleaned[: max_len - 1] + "…"
    return cleaned


def _nick(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    return "username yo'q"


def format_user_result(user: User, stats: dict) -> str:
    nick = _nick(user)
    name = _safe_name(user.full_name)
    correct = stats["correct_answers"]
    total = stats["total_answers"]
    wrong = stats.get("wrong_answers", total - correct)
    limit = settings.questions_per_user
    accuracy = round((correct / total) * 100, 1) if total else 0.0

    return (
        f"👤 Ism: <b>{name}</b>\n"
        f"📱 Username: <b>{nick}</b>\n"
        f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n\n"
        f"✅ To'g'ri: <b>{correct}</b>\n"
        f"❌ Noto'g'ri: <b>{wrong}</b>\n"
        f"📝 Jami: <b>{total}</b> / {limit}\n"
        f"📈 Aniqlik: <b>{accuracy}%</b>"
    )


def format_user_short(user: User, stats: dict) -> str:
    nick = _nick(user)
    name = _safe_name(user.full_name, 24)
    correct = stats["correct_answers"]
    total = stats["total_answers"]
    return (
        f"• <b>{nick}</b>\n"
        f"  Ism: {name}\n"
        f"  ID: <code>{user.telegram_id}</code>\n"
        f"  ✅ {correct}/{total}"
    )


@router.message(Command("admin"))
async def admin_panel(message: Message) -> None:
    if not is_admin(message.from_user):
        await message.answer("⛔ Sizda admin huquqi yo'q.")
        return

    async with async_session() as session:
        users_data = await list_users_with_stats(session, limit=20)

    channel = get_channel_username() or "sozlanmagan"
    lines = ["📊 <b>Admin panel</b> (faqat test natijalari)\n"]
    lines.append("\n👥 <b>Foydalanuvchilar:</b>\n")
    for user, stats in users_data:
        lines.append(format_user_short(user, stats))

    lines.append(
        f"\n📢 Majburiy kanal: @{channel}"
        if channel != "sozlanmagan"
        else "\n📢 Majburiy kanal: sozlanmagan"
    )
    lines.append("\n<b>Buyruqlar:</b>")
    lines.append("/users yoki /results — barcha natijalar")
    lines.append("/user @username — bitta foydalanuvchi")
    lines.append("/setchannel @kanal — majburiy obuna")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("setchannel"))
async def admin_set_channel(message: Message) -> None:
    if not is_admin(message.from_user):
        await message.answer("⛔ Sizda admin huquqi yo'q.")
        return

    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        current = get_channel_username() or "sozlanmagan"
        await message.answer(
            "Foydalanish: /setchannel @kanal_username\n"
            f"Hozirgi kanal: @{current}"
        )
        return

    channel = set_channel_username(args[1])
    await message.answer(
        f"✅ Majburiy kanal: @{channel}\n"
        "Bot kanalda admin ekanini tekshiring."
    )


async def _send_all_user_results(message: Message) -> None:
    async with async_session() as session:
        users_data = await list_users_with_stats(session, limit=50)

    if not users_data:
        await message.answer("Hali foydalanuvchi yo'q.")
        return

    chunks: list[str] = []
    current = "👥 <b>Foydalanuvchilar natijalari</b>\n\n"

    for user, stats in users_data:
        block = format_user_result(user, stats) + "\n\n──────────────\n\n"
        if len(current) + len(block) > 3800:
            chunks.append(current)
            current = block
        else:
            current += block

    chunks.append(current)
    for chunk in chunks:
        await message.answer(chunk, parse_mode="HTML")


@router.message(Command("users", "results"))
async def admin_users(message: Message) -> None:
    if not is_admin(message.from_user):
        await message.answer("⛔ Sizda admin huquqi yo'q.")
        return
    await _send_all_user_results(message)


@router.message(Command("user"))
async def admin_user_detail(message: Message) -> None:
    if not is_admin(message.from_user):
        await message.answer("⛔ Sizda admin huquqi yo'q.")
        return

    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Foydalanish:\n/user 123456789\n/user @username")
        return

    query = args[1].strip()
    async with async_session() as session:
        if query.startswith("@") or not query.isdigit():
            data = await get_user_with_stats_by_username(session, query)
        else:
            data = await get_user_with_stats_by_telegram_id(session, int(query))

    if not data:
        await message.answer("Foydalanuvchi topilmadi.")
        return

    user, stats = data
    await message.answer(format_user_result(user, stats), parse_mode="HTML")
