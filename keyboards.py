"""Inline va reply klaviaturalar."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def answer_keyboard(question_id: int, option_map: list[str]) -> InlineKeyboardMarkup:
    labels = ["A", "B", "C", "D"]
    row1 = [
        InlineKeyboardButton(
            text=labels[i], callback_data=f"ans:{question_id}:{option_map[i]}"
        )
        for i in range(2)
    ]
    row2 = [
        InlineKeyboardButton(
            text=labels[i], callback_data=f"ans:{question_id}:{option_map[i]}"
        )
        for i in range(2, 4)
    ]
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2])


def subscribe_keyboard(channel_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Kanalga obuna bo'lish",
                    url=f"https://t.me/{channel_username}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Obunani tekshirish", callback_data="check_subscribe"
                )
            ],
            [InlineKeyboardButton(text="⬅️ Menyuga", callback_data="main_menu")],
        ]
    )


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Test boshlash", callback_data="start_quiz")],
            [
                InlineKeyboardButton(text="📊 Natija", callback_data="show_stats"),
                InlineKeyboardButton(text="🏆 Top", callback_data="show_top"),
            ],
            [InlineKeyboardButton(text="❓ Yordam", callback_data="show_help")],
        ]
    )


def reply_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Test boshlash"), KeyboardButton(text="📊 Natija")],
            [KeyboardButton(text="🏆 Top"), KeyboardButton(text="❓ Yordam")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Menyudan tanlang...",
    )
