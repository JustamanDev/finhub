from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_navigation_buttons(back_callback: Optional[str] = None) -> list[list[InlineKeyboardButton]]:
    buttons = []
    if back_callback:
        buttons.append([
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data=back_callback,
            ),
        ])
    buttons.append([
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu",
        ),
    ])
    return buttons


def attach_persistent_navigation(
    keyboard: InlineKeyboardMarkup,
    back_callback: Optional[str] = None,
) -> InlineKeyboardMarkup:
    buttons = [row[:] for row in keyboard.inline_keyboard]
    buttons.extend(get_navigation_buttons(back_callback))
    return InlineKeyboardMarkup(buttons)

