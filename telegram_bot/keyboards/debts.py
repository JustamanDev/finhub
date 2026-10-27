from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def debts_menu_keyboard(debts) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text='➕ Новый долг', callback_data='debt_add')],
    ]
    for debt in debts:
        side = 'я должен' if debt.direction == 'owe' else 'мне должны'
        rows.append([
            InlineKeyboardButton(
                text=f'{debt.counterparty} · {side}',
                callback_data=f'debt_open_{debt.id}',
            ),
        ])
    rows.append([InlineKeyboardButton(text='🏠 Главное меню', callback_data='main_menu')])
    return InlineKeyboardMarkup(rows)


def debt_direction_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text='Я должен', callback_data='debt_dir_owe')],
        [InlineKeyboardButton(text='Мне должны', callback_data='debt_dir_owed')],
        [InlineKeyboardButton(text='🔙 Назад', callback_data='debts_menu')],
    ])


def debt_card_keyboard(debt_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text='Записать платёж', callback_data=f'debt_pay_{debt_id}')],
        [InlineKeyboardButton(text='🔙 К списку', callback_data='debts_menu')],
    ])
