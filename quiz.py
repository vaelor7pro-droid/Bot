import random

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import get_settings
from bot.keyboards.inline import answer_keyboard, main_menu_keyboard, subscribe_keyboard
from bot.services.subscription import channel_link, ensure_subscribed, is_subscribed
from bot.utils.runtime_settings import get_channel_username
from database.crud import (
    count_user_answers,
    get_or_create_user,
    get_unanswered_questions,
    submit_answer,
)
from database.session import async_session

router = Router()
settings = get_settings()


def option_text(question, letter: str) -> str:
    mapping = {
        "A": question.option_a,
        "B": question.option_b,
        "C": question.option_c,
        "D": question.option_d,
    }
    return mapping[letter.upper()]


def shuffle_options(question) -> tuple[str, list[str]]:
    items = [
        ("A", question.option_a),
        ("B", question.option_b),
        ("C", question.option_c),
        ("D", question.option_d),
    ]
    random.shuffle(items)
    labels = ["A", "B", "C", "D"]
    option_map = [orig for orig, _ in items]
    lines = [f"❓ <b>Savol</b>\n\n{question.text}\n"]
    for label, (_, text) in zip(labels, items):
        lines.append(f"{label}) {text}")
    return "\n".join(lines), option_map


async def send_next_question(target: Message, telegram_id: int) -> None:
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=telegram_id,
            username=target.from_user.username if target.from_user else None,
            full_name=target.from_user.full_name if target.from_user else None,
        )
        answered = await count_user_answers(session, user.id)
        questions = await get_unanswered_questions(session, user.id, limit=1)
        await session.commit()

    if not questions:
        if answered >= settings.questions_per_user:
            msg = (
                f"🎉 Siz {settings.questions_per_user} ta savol limitiga yetdingiz!\n"
                "Natijangiz adminlarga ko'rinadi."
            )
        else:
            msg = (
                "🎉 Hozircha barcha mavjud savollarga javob berdingiz!\n"
                "Yangi savollar qo'shilguncha kuting."
            )
        await target.answer(msg, reply_markup=main_menu_keyboard())
        return

    q = questions[0]
    text, option_map = shuffle_options(q)
    progress = answered + 1
    header = f"📊 {progress}/{settings.questions_per_user}\n\n"
    await target.answer(
        header + text,
        reply_markup=answer_keyboard(q.id, option_map),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "check_subscribe")
async def check_subscribe(callback: CallbackQuery) -> None:
    channel = get_channel_username()
    if not channel:
        await callback.answer("Kanal hali sozlanmagan", show_alert=True)
        return

    if await is_subscribed(callback.bot, callback.from_user.id):
        await callback.answer("Obuna tasdiqlandi ✅", show_alert=True)
        try:
            await callback.message.edit_text(
                "✅ Obuna tasdiqlandi!\nEndi testni boshlashingiz mumkin.",
                reply_markup=main_menu_keyboard(),
            )
        except Exception:
            await callback.message.answer(
                "✅ Obuna tasdiqlandi!\nEndi testni boshlashingiz mumkin.",
                reply_markup=main_menu_keyboard(),
            )
        return

    await callback.answer("Hali obuna emassiz", show_alert=True)
    link = channel_link() or ""
    await callback.message.answer(
        f"❌ Hali obuna bo'lmadingiz.\nAvval kanalga kiring: {link}",
        reply_markup=subscribe_keyboard(channel),
    )


@router.message(Command("quiz"))
@router.message(F.text == "📝 Test boshlash")
@router.callback_query(F.data == "start_quiz")
async def start_quiz(event: Message | CallbackQuery) -> None:
    if not await ensure_subscribed(event):
        return
    if isinstance(event, CallbackQuery):
        await event.answer()
        await send_next_question(event.message, event.from_user.id)
    else:
        await send_next_question(event, event.from_user.id)


@router.callback_query(F.data.startswith("ans:"))
async def handle_answer(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Noto'g'ri ma'lumot", show_alert=True)
        return

    _, question_id_str, selected = parts
    question_id = int(question_id_str)

    async with async_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            full_name=callback.from_user.full_name,
        )

        from sqlalchemy import select

        from database.models import Question

        result = await session.execute(
            select(Question).where(Question.id == question_id)
        )
        question = result.scalar_one_or_none()

        if not question:
            await callback.answer("Savol topilmadi", show_alert=True)
            return

        try:
            is_correct, _reward = await submit_answer(session, user, question, selected)
            await session.commit()
        except ValueError:
            await session.rollback()
            await callback.answer(
                "⚠️ Bu savolga allaqachon javob berilgan!",
                show_alert=True,
            )
            return

    if is_correct:
        text = "✅ To'g'ri javob!"
    else:
        correct_text = option_text(question, question.correct_option)
        text = f"❌ Noto'g'ri.\nTo'g'ri javob: {correct_text}"

    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

    await send_next_question(callback.message, callback.from_user.id)
