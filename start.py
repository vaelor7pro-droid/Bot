from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BotCommand, BotCommandScopeDefault, CallbackQuery, Message

from bot.config import get_settings
from bot.keyboards.inline import main_menu_keyboard, reply_main_keyboard
from bot.services.subscription import ensure_subscribed, subscription_required
from bot.utils.admin import is_admin
from database.crud import get_or_create_user
from database.session import async_session

router = Router()
settings = get_settings()


USER_COMMANDS = [
    BotCommand(command="start", description="Botni ishga tushirish / menyu"),
    BotCommand(command="quiz", description="Test boshlash"),
    BotCommand(command="stats", description="Natijangiz"),
    BotCommand(command="top", description="Top 10 reyting"),
    BotCommand(command="help", description="Yordam va qoidalar"),
]


async def setup_bot_commands(bot) -> None:
    await bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeDefault())


def welcome_text(full_name: str, admin: bool = False) -> str:
    from bot.utils.runtime_settings import get_channel_username

    channel = get_channel_username()
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


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    async with async_session() as session:
        await get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
        )
        await session.commit()

    if subscription_required() and not is_admin(message.from_user):
        if not await ensure_subscribed(message):
            return

    await message.answer(
        welcome_text(message.from_user.full_name or "do'st", is_admin(message.from_user)),
        reply_markup=reply_main_keyboard(),
        parse_mode="HTML",
    )
    await message.answer(
        "⬇️ Tezkor menyu:",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("help"))
@router.message(F.text == "❓ Yordam")
async def cmd_help(message: Message) -> None:
    await message.answer(
        HELP_TEXT,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "show_help")
async def cb_help(callback: CallbackQuery) -> None:
    await callback.answer()
    try:
        await callback.message.edit_text(
            HELP_TEXT,
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
    except Exception:
        await callback.message.answer(
            HELP_TEXT,
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    text = welcome_text(
        callback.from_user.full_name or "do'st",
        is_admin(callback.from_user),
    )
    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
    except Exception:
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
