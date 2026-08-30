"""Barcha bot handlerlari: start, test (quiz), natija, top, admin panel."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import BotCommand, BotCommandScopeDefault, CallbackQuery, Message
from aiogram.types import User as TgUser

import database as db
import models
from config import settings
from keyboards import (
    answer_keyboard,
    main_menu_keyboard,
    reply_main_keyboard,
    subscribe_keyboard,
)

router = Router()

TZ_UZ = timezone(timedelta(hours=5))

USER_COMMANDS = [
    BotCommand(command="start", description="Botni ishga tushirish / menyu"),
    BotCommand(command="quiz", description="Test boshlash"),
    BotCommand(command="stats", description="Natijangiz"),
    BotCommand(command="top", description="Top 10 reyting"),
    BotCommand(command="help", description="Yordam va qoidalar"),
]

HELP_TEXT = (
    "📌 <b>Qoidalar</b>\n"
    "• Bu bot faqat test uchun — pul mukofoti yo'q\n"
    "• Avval kanalga majburiy obuna bo'lish kerak\n"
    "• Har bir savolga faqat bir marta javob berish mumkin\n"
    f"• Har foydalanuvchiga {settings.questions_per_user} ta savol\n"
    "• Savollar va A/B/C/D variantlari har safar aralashadi\n"
    "• /stats — o'z natijangiz\n"
    "• /top — eng yaxshi natijalar"
)


# ---------------------------------------------------------------------------
# Yordamchi funksiyalar
# ---------------------------------------------------------------------------

def is_admin(user: TgUser) -> bool:
    if user.id in settings.admin_ids:
        return True
    if user.username and user.username.lower() in settings.admin_usernames:
        return True
    return False


async def setup_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeDefault())


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    channel = await models.get_channel_username()
    if not channel:
        return True
    try:
        member = await bot.get_chat_member(chat_id=f"@{channel}", user_id=user_id)
        if member.status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }:
            return True
        if member.status == ChatMemberStatus.RESTRICTED:
            return bool(getattr(member, "is_member", False))
        return False
    except (TelegramBadRequest, TelegramForbiddenError):
        return False
    except Exception:
        return False


async def ensure_subscribed(event: Message | CallbackQuery) -> bool:
    user = event.from_user
    if is_admin(user):
        return True

    channel = await models.get_channel_username()
    if not channel:
        return True

    if await is_subscribed(event.bot, user.id):
        return True

    text = (
        "🔒 <b>Majburiy obuna</b>\n\n"
        f"Botdan foydalanish uchun avval @{channel} kanaliga obuna bo'ling.\n"
        "Keyin «✅ Obunani tekshirish» tugmasini bosing."
    )
    markup = subscribe_keyboard(channel)

    if isinstance(event, CallbackQuery):
        await event.answer("Avval kanalga obuna bo'ling", show_alert=True)
        try:
            await event.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            await event.message.answer(text, parse_mode="HTML", reply_markup=markup)
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=markup)
    return False


def welcome_text(full_name: str, admin: bool = False, channel: str = "") -> str:
    text = (
        f"Salom, {full_name}!\n\n"
        "Bu <b>tarix testi</b> boti. Savollarga javob bering va natijangizni ko'ring.\n\n"
        f"📝 Har bir foydalanuvchiga: <b>{settings.questions_per_user}</b> ta savol\n"
        "🔀 Savollar va variantlar har safar aralashadi\n"
        "🏆 /top — eng yaxshi natijalar\n"
    )
    if channel:
        text += f"📢 Test uchun obuna: <b>@{channel}</b>\n"
    text += (
        "\nBuyruqlar:\n"
        "/quiz — test\n"
        "/stats — natija\n"
        "/top — reyting\n"
        "/help — yordam"
    )
    if admin:
        text += (
            "\n\n🔐 <b>Admin:</b>\n"
            "/admin — panel\n"
            "/results — barcha natijalar\n"
            "/user @username — bitta foydalanuvchi\n"
            "/setchannel @kanal — majburiy obuna"
        )
    return text


def _fmt_dt(value: datetime | None) -> str:
    if not value:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(TZ_UZ).strftime("%d.%m.%Y %H:%M")


def _safe_name(name: str | None, max_len: int = 40) -> str:
    if not name:
        return "—"
    cleaned = " ".join(name.split())
    if len(cleaned) > max_len:
        return cleaned[: max_len - 1] + "…"
    return cleaned


def option_text(question: models.Question, letter: str) -> str:
    mapping = {
        "A": question.option_a,
        "B": question.option_b,
        "C": question.option_c,
        "D": question.option_d,
    }
    return mapping[letter.upper()]


def shuffle_options(question: models.Question) -> tuple[str, list[str]]:
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
    async with models.async_session() as session:
        user = await db.get_or_create_user(
            session,
            telegram_id=telegram_id,
            username=target.from_user.username if target.from_user else None,
            full_name=target.from_user.full_name if target.from_user else None,
        )
        answered = await db.count_user_answers(session, user.id)
        question = await db.get_unanswered_question(session, user.id)

    if not question:
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

    text, option_map = shuffle_options(question)
    progress = answered + 1
    header = f"📊 {progress}/{settings.questions_per_user}\n\n"
    await target.answer(
        header + text,
        reply_markup=answer_keyboard(question.id, option_map),
        parse_mode="HTML",
    )


async def _stats_text(user_id: int, username: str | None, full_name: str | None) -> str:
    async with models.async_session() as session:
        user = await db.get_or_create_user(
            session, telegram_id=user_id, username=username, full_name=full_name
        )
        stats = await db.get_user_stats(session, user.id)

    total = stats["total_answers"]
    correct = stats["correct_answers"]
    wrong = stats["wrong_answers"]
    limit = settings.questions_per_user
    remaining = max(0, limit - total)
    accuracy = round((correct / total) * 100, 1) if total else 0.0
    now = datetime.now(TZ_UZ).strftime("%d.%m.%Y %H:%M")
    nick = f"@{username}" if username else "—"

    return (
        "📊 <b>Natijangiz</b>\n"
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


def format_user_result(user: models.User, stats: dict) -> str:
    nick = f"@{user.username}" if user.username else "username yo'q"
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


def format_user_short(user: models.User, stats: dict) -> str:
    nick = f"@{user.username}" if user.username else "username yo'q"
    name = _safe_name(user.full_name, 24)
    correct = stats["correct_answers"]
    total = stats["total_answers"]
    return f"• <b>{nick}</b>\n  Ism: {name}\n  ID: <code>{user.telegram_id}</code>\n  ✅ {correct}/{total}"


# ---------------------------------------------------------------------------
# /start, /help, bosh menyu
# ---------------------------------------------------------------------------

@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    async with models.async_session() as session:
        await db.get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
        )

    if not is_admin(message.from_user):
        if not await ensure_subscribed(message):
            return

    channel = await models.get_channel_username()
    await message.answer(
        welcome_text(message.from_user.full_name or "do'st", is_admin(message.from_user), channel),
        reply_markup=reply_main_keyboard(),
        parse_mode="HTML",
    )
    await message.answer(
        "⬇️ Tezkor menyu:", reply_markup=main_menu_keyboard(), parse_mode="HTML"
    )


@router.message(Command("help"))
@router.message(F.text == "❓ Yordam")
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "show_help")
async def cb_help(callback: CallbackQuery) -> None:
    await callback.answer()
    try:
        await callback.message.edit_text(
            HELP_TEXT, parse_mode="HTML", reply_markup=main_menu_keyboard()
        )
    except Exception:
        await callback.message.answer(
            HELP_TEXT, parse_mode="HTML", reply_markup=main_menu_keyboard()
        )


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    channel = await models.get_channel_username()
    text = welcome_text(callback.from_user.full_name or "do'st", is_admin(callback.from_user), channel)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=main_menu_keyboard())


# ---------------------------------------------------------------------------
# Test (quiz)
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "check_subscribe")
async def check_subscribe(callback: CallbackQuery) -> None:
    channel = await models.get_channel_username()
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
    await callback.message.answer(
        f"❌ Hali obuna bo'lmadingiz.\nAvval kanalga kiring: https://t.me/{channel}",
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

    async with models.async_session() as session:
        user = await db.get_or_create_user(
            session,
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            full_name=callback.from_user.full_name,
        )
        question = await db.get_question_by_id(session, question_id)
        if not question:
            await callback.answer("Savol topilmadi", show_alert=True)
            return
        try:
            is_correct = await db.submit_answer(session, user, question, selected)
        except ValueError:
            await callback.answer("⚠️ Bu savolga allaqachon javob berilgan!", show_alert=True)
            return

    if is_correct:
        text = "✅ To'g'ri javob!"
    else:
        text = f"❌ Noto'g'ri.\nTo'g'ri javob: {option_text(question, question.correct_option)}"

    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

    await send_next_question(callback.message, callback.from_user.id)


# ---------------------------------------------------------------------------
# Natija / statistika
# ---------------------------------------------------------------------------

@router.message(Command("stats", "balance", "natija"))
@router.message(F.text.in_({"📊 Natija", "💰 Balans"}))
async def show_stats(message: Message) -> None:
    if not await ensure_subscribed(message):
        return
    text = await _stats_text(
        message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu_keyboard())


@router.callback_query(F.data.in_({"show_balance", "show_stats"}))
async def cb_show_stats(callback: CallbackQuery) -> None:
    if not await ensure_subscribed(callback):
        return
    await callback.answer()
    text = await _stats_text(
        callback.from_user.id, callback.from_user.username, callback.from_user.full_name
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=main_menu_keyboard())


# ---------------------------------------------------------------------------
# Top reyting
# ---------------------------------------------------------------------------

MEDALS = ["🥇", "🥈", "🥉"]


def _format_top(rows: list) -> str:
    if not rows:
        return "🏆 Hali reyting bo'sh.\nTest ishlaganlar shu yerda ko'rinadi."
    lines = ["🏆 <b>Top 10 reyting</b>\n"]
    for i, (user, stats) in enumerate(rows, start=1):
        medal = MEDALS[i - 1] if i <= 3 else f"{i}."
        nick = f"@{user.username}" if user.username else (user.full_name or "—")
        lines.append(
            f"{medal} <b>{nick}</b>\n   ✅ {stats['correct_answers']}/{stats['total_answers']}"
        )
    return "\n".join(lines)


@router.message(Command("top"))
@router.message(F.text == "🏆 Top")
@router.callback_query(F.data == "show_top")
async def show_top(event: Message | CallbackQuery) -> None:
    if not await ensure_subscribed(event):
        return

    async with models.async_session() as session:
        rows = await db.get_top_players(session, limit=10)

    text = _format_top(rows)

    if isinstance(event, CallbackQuery):
        await event.answer()
        try:
            await event.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard())
        except Exception:
            await event.message.answer(text, parse_mode="HTML", reply_markup=main_menu_keyboard())
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=main_menu_keyboard())


# ---------------------------------------------------------------------------
# Admin panel
# ---------------------------------------------------------------------------

@router.message(Command("admin"))
async def admin_panel(message: Message) -> None:
    if not is_admin(message.from_user):
        await message.answer("⛔ Sizda admin huquqi yo'q.")
        return

    async with models.async_session() as session:
        users_data = await db.list_users_with_stats(session, limit=20)

    channel = await models.get_channel_username() or "sozlanmagan"
    lines = ["📊 <b>Admin panel</b> (faqat test natijalari)\n"]
    lines.append("\n👥 <b>Foydalanuvchilar:</b>\n")
    for user, stats in users_data:
        lines.append(format_user_short(user, stats))
    lines.append(
        f"\n📢 Majburiy kanal: @{channel}" if channel != "sozlanmagan" else "\n📢 Majburiy kanal: sozlanmagan"
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
        current = await models.get_channel_username() or "sozlanmagan"
        await message.answer(
            f"Foydalanish: /setchannel @kanal_username\nHozirgi kanal: @{current}"
        )
        return

    channel = await models.set_channel_username(args[1])
    await message.answer(
        f"✅ Majburiy kanal: @{channel}\nBot kanalda admin ekanini tekshiring."
    )


async def _send_all_user_results(message: Message) -> None:
    async with models.async_session() as session:
        users_data = await db.list_users_with_stats(session, limit=50)

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

    async with models.async_session() as session:
        data = await db.get_user_with_stats(session, args[1])

    if not data:
        await message.answer("Foydalanuvchi topilmadi.")
        return

    user, stats = data
    await message.answer(format_user_result(user, stats), parse_mode="HTML")
