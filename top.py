from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards.inline import main_menu_keyboard
from bot.services.subscription import ensure_subscribed
from database.crud import get_top_players
from database.session import async_session

router = Router()

MEDALS = ["🥇", "🥈", "🥉"]


def _format_top(rows: list) -> str:
    if not rows:
        return "🏆 Hali reyting bo'sh.\nTest ishlaganlar shu yerda ko'rinadi."

    lines = ["🏆 <b>Top 10 reyting</b>\n"]
    for i, (user, stats) in enumerate(rows, start=1):
        medal = MEDALS[i - 1] if i <= 3 else f"{i}."
        nick = f"@{user.username}" if user.username else (user.full_name or "—")
        correct = stats["correct_answers"]
        total = stats["total_answers"]
        lines.append(
            f"{medal} <b>{nick}</b>\n"
            f"   ✅ {correct}/{total}"
        )
    return "\n".join(lines)


@router.message(Command("top"))
@router.message(F.text == "🏆 Top")
@router.callback_query(F.data == "show_top")
async def show_top(event: Message | CallbackQuery) -> None:
    if not await ensure_subscribed(event):
        return

    async with async_session() as session:
        rows = await get_top_players(session, limit=10)

    text = _format_top(rows)

    if isinstance(event, CallbackQuery):
        await event.answer()
        try:
            await event.message.edit_text(
                text, parse_mode="HTML", reply_markup=main_menu_keyboard()
            )
        except Exception:
            await event.message.answer(
                text, parse_mode="HTML", reply_markup=main_menu_keyboard()
            )
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=main_menu_keyboard())
