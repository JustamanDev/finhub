from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def recurring_menu_keyboard(templates) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text='➕ Новый повтор', callback_data='recur_add')],
    ]
    for template in templates:
        mark = '' if template.is_active else '⏸ '
        rows.append([
            InlineKeyboardButton(
                text=f'{mark}{template.name}',
                callback_data=f'recur_open_{template.id}',
            ),
        ])
    rows.append([InlineKeyboardButton(text='🏠 Главное меню', callback_data='main_menu')])
    return InlineKeyboardMarkup(rows)


def recurring_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(text='💸 Расход', callback_data='recur_type_expense'),
            InlineKeyboardButton(text='💰 Доход', callback_data='recur_type_income'),
        ],
        [InlineKeyboardButton(text='🔙 Назад', callback_data='recur_menu')],
    ])


def recurring_category_keyboard(categories) -> InlineKeyboardMarkup:
    rows = []
    for index in range(0, len(categories), 2):
        pair = categories[index:index + 2]
        rows.append([
            InlineKeyboardButton(
                text=f'{category.icon} {category.name}',
                callback_data=f'recur_cat_{category.id}',
            )
            for category in pair
        ])
    rows.append([InlineKeyboardButton(text='🔙 Назад', callback_data='recur_menu')])
    return InlineKeyboardMarkup(rows)


def recurring_period_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text='Каждую неделю', callback_data='recur_every_weekly')],
        [InlineKeyboardButton(text='Каждый месяц', callback_data='recur_every_monthly')],
        [InlineKeyboardButton(text='Каждый год', callback_data='recur_every_yearly')],
        [InlineKeyboardButton(text='🔙 Назад', callback_data='recur_menu')],
    ])


def recurring_kind_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text='Точная сумма', callback_data='recur_kind_exact')],
        [InlineKeyboardButton(text='Диапазон', callback_data='recur_kind_range')],
        [InlineKeyboardButton(text='Сумма каждый раз своя', callback_data='recur_kind_open')],
        [InlineKeyboardButton(text='🔙 Назад', callback_data='recur_menu')],
    ])


def recurring_due_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text='Следующий раз — сегодня', callback_data='recur_due_today')],
        [InlineKeyboardButton(text='🔙 Назад', callback_data='recur_menu')],
    ])


def recurring_card_keyboard(template_id: int, active: bool) -> InlineKeyboardMarkup:
    toggle = 'Поставить на паузу' if active else 'Снова включить'
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text='Записать сумму', callback_data=f'recur_ask_{template_id}')],
        [InlineKeyboardButton(text=toggle, callback_data=f'recur_pause_{template_id}')],
        [InlineKeyboardButton(text='🔙 К списку', callback_data='recur_menu')],
    ])
