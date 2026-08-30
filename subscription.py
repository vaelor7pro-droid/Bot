"""Kanalga majburiy obuna tekshiruvi."""

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, Message
from aiogram.types import User as TgUser

from bot.keyboards.inline import subscribe_keyboard
from bot.utils.admin import is_admin
from bot.utils.runtime_settings import get_channel_username


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    channel = get_channel_username()
    if not channel:
        return True

    chat_id = f"@{channel}"
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        status = member.status
        if status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }:
            return True
        if status == ChatMemberStatus.RESTRICTED:
            return bool(getattr(member, "is_member", False))
        return False
    except (TelegramBadRequest, TelegramForbiddenError):
        return False
    except Exception:
        return False


def channel_link() -> str | None:
    channel = get_channel_username()
    if not channel:
        return None
    return f"https://t.me/{channel}"


def subscription_required() -> bool:
    return bool(get_channel_username())


async def ensure_subscribed(event: Message | CallbackQuery) -> bool:
    user: TgUser = event.from_user
    if is_admin(user):
        return True

    channel = get_channel_username()
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
