from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import get_settings
from bot.keyboards.inline import main_menu_keyboard
from bot.services.subscription import ensure_subscribed
from database.crud import get_or_create_user, get_user_stats
from database.session import async_session

router = Router()
settings = get_settings()
TZ_UZ = timezone(timedelta(hours=5))


def _fmt_dt(value: datetime | None) -> str:
    if not value:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(TZ_UZ).strftime("%d.%m.%Y %H:%M")


async def _stats_text(user_id: int, username: str | None, full_name: str | None) -> str:
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=user_id,
            username=username,
            full_name=full_name,
        )
        stats = await get_user_stats(session, user.id)
        await session.commit()

    total = stats["total_answers"]
    correct = stats["correct_answers"]
    wrong = stats["wrong_answers"]
    limit = settings.questions_per_user
    remaining = max(0, limit - total)
    accuracy = round((correct / total) * 100, 1) if total else 0.0
    now = datetime.now(TZ_UZ).strftime("%d.%m.%Y %H:%M")
    nick = f"@{username}" if username else "—"

    return (
        f"📊 <b>Natijangiz</b>\n"
        f"🕒 Yangilandi: <code>{now}</code>\n\n"
        f"👤 {full_name or '—'}\n"
        f"📱 Nik: {nick}\n\n"
        f"✅ To'g'ri: <b>{correct}</b>\n"
        f"❌ Noto'g'ri: <b>{wrong}</b>\n"
        f"📝 Jami: <b>{total}</b> / {limit}\n"
        f"📈 Aniqlik: <b>{accuracy}%</b>\n"
        f"⏳ Qolgan savollar: <b>{remaining}</b>\n\n"
        f"🕐 Oxirgi javob: {_fmt_dt(stats['last_answered_at'])}"
    )


@router.message(Command("stats", "balance", "natija"))
@router.message(F.text.in_({"📊 Natija", "💰 Balans"}))
async def show_stats(message: Message) -> None:
    if not await ensure_subscribed(message):
        return
    text = await _stats_text(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu_keyboard())


@router.callback_query(F.data.in_({"show_balance", "show_stats"}))
async def cb_show_stats(callback: CallbackQuery) -> None:
    if not await ensure_subscribed(callback):
        return
    await callback.answer()
    text = await _stats_text(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.full_name,
    )
    try:
        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=main_menu_keyboard()
        )
    except Exception:
        await callback.message.answer(
            text, parse_mode="HTML", reply_markup=main_menu_keyboard()
        )
