"""Статья финансиста: абзацы из ответа модели, таблицы из снимка."""

from __future__ import annotations

from html import escape
from typing import Any

from transactions.currencies import format_money

from telegram_bot.services.weekly_digest import _rich_table

_TABLE_ORDER_HINT = (
    'movement',
    'categories',
    'budgets',
    'goals',
    'goal_focus',
    'trend',
    'category',
    'debts',
    'recurring',
)

_PERIOD = {
    'weekly': 'каждую неделю',
    'monthly': 'каждый месяц',
    'yearly': 'каждый год',
}
_DIRECTION = {
    'owe': 'я должен',
    'owed': 'мне должны',
}


def render_advisor_article(
    answer: Any,
    snapshot: dict[str, Any],
) -> tuple[str, str]:
    """HTML статьи и запасной HTML без таблиц."""
    blocks = _blocks(answer.tables, snapshot)
    title = answer.title or 'Финансист'
    lead = answer.lead or ''
    body = answer.body or ''
    actions = list(answer.actions or [])

    rich_parts = [
        f'<h1>{escape(title)}</h1>',
        f'<p>{escape(lead)}</p>',
    ]
    legacy_parts = [
        f'<b>{escape(title)}</b>',
        escape(lead),
    ]
    if body:
        rich_parts.append(f'<p>{escape(body)}</p>')
        legacy_parts.append(escape(body))
    for block in blocks:
        rich_parts.append(
            _rich_table(block['caption'], block['headers'], block['rows']),
        )
        legacy_parts.append(f'<b>{escape(block["caption"])}</b>')
        legacy_parts.extend(escape(line) for line in block['plain'])
    if actions:
        rich_parts.append('<h2>Что сделать</h2>')
        rich_parts.extend(f'<p>• {escape(item)}</p>' for item in actions)
        legacy_parts.append('<b>Что сделать</b>')
        legacy_parts.extend(f'• {escape(item)}' for item in actions)
    return '\n'.join(rich_parts), '\n'.join(legacy_parts)


def _blocks(requested: list[str], snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    seen: list[str] = []
    for table_id in requested or []:
        if table_id in _TABLE_ORDER_HINT and table_id not in seen:
            seen.append(table_id)
    blocks: list[dict[str, Any]] = []
    for table_id in seen:
        block = _build_block(table_id, snapshot)
        if block is not None:
            blocks.append(block)
    return blocks


def _money(value: Any, currency: str | None) -> str:
    return format_money(value or 0, currency)


def _report_currency(snapshot: dict[str, Any]) -> str | None:
    return snapshot.get('report_currency')


def _build_block(table_id: str, snapshot: dict[str, Any]) -> dict[str, Any] | None:
    currency = _report_currency(snapshot)
    if table_id == 'movement':
        totals = snapshot.get('month_totals') or {}
        if not any(float(totals.get(key) or 0) for key in (
            'income', 'expenses', 'balance', 'free_funds',
        )):
            return None
        period = (snapshot.get('period') or {}).get('name') or 'Период'
        rows = [
            ('Доход', _money(totals.get('income'), currency)),
            ('Расход', _money(totals.get('expenses'), currency)),
            ('Баланс', _money(totals.get('balance'), currency), True),
            ('Свободно', _money(totals.get('free_funds'), currency), True),
        ]
        return _pack(f'Движение, {period}', ('Статья', 'Сумма'), rows)
    if table_id == 'categories':
        rows = [
            (row.get('name') or '—', _money(row.get('spent'), currency))
            for row in (snapshot.get('top_expense_categories') or [])
            if float(row.get('spent') or 0)
        ]
        return _pack('Куда ушли деньги', ('Категория', 'Сумма'), rows)
    if table_id == 'budgets':
        rows = [
            (
                row.get('category') or '—',
                _money(row.get('spent'), currency),
                _money(row.get('limit'), currency),
                _money(row.get('remaining'), currency),
            )
            for row in (snapshot.get('budgets') or [])
        ]
        return _pack('Лимиты', ('Категория', 'Факт', 'Лимит', 'Остаток'), rows)
    if table_id == 'goals':
        return _goals_block(snapshot.get('goals') or [], 'Цели и конверты')
    if table_id == 'goal_focus':
        focus = snapshot.get('goal_focus') or {}
        title = focus.get('title')
        if not title:
            return None
        matched = [
            row for row in (snapshot.get('goals') or [])
            if row.get('title') == title
        ]
        return _goals_block(matched, title)
    if table_id == 'trend':
        rows = [
            (
                row.get('name') or '—',
                _money(row.get('income'), currency),
                _money(row.get('expenses'), currency),
                _money(row.get('balance'), currency),
            )
            for row in (snapshot.get('monthly_series') or [])
        ]
        return _pack('Месяцы', ('Месяц', 'Доход', 'Расход', 'Баланс'), rows)
    if table_id == 'category':
        focus = snapshot.get('category_focus') or {}
        name = focus.get('name') or 'Категория'
        rows = [
            (row.get('name') or '—', _money(row.get('amount'), currency))
            for row in (snapshot.get('category_series') or [])
        ]
        return _pack(str(name), ('Месяц', 'Сумма'), rows)
    if table_id == 'debts':
        rows = []
        for row in snapshot.get('debts') or []:
            if float(row.get('remaining') or 0) <= 0:
                continue
            rows.append((
                row.get('counterparty') or '—',
                _DIRECTION.get(row.get('direction') or '', 'долг'),
                _money(row.get('remaining'), row.get('currency') or currency),
            ))
        return _pack('Долги', ('Кому', 'Направление', 'Остаток'), rows)
    if table_id == 'recurring':
        rows = []
        for row in snapshot.get('recurring') or []:
            rows.append((
                row.get('name') or '—',
                _due_label(row.get('next_due')),
                _PERIOD.get(row.get('periodicity') or '', 'повтор'),
                _recurring_amount(row, currency),
            ))
        return _pack('Повторы', ('Имя', 'Следующий раз', 'Ритм', 'Сумма'), rows)
    return None


def _goals_block(goals: list[dict[str, Any]], caption: str) -> dict[str, Any] | None:
    rows = []
    for row in goals:
        code = row.get('currency')
        if row.get('kind') == 'envelope':
            rows.append((
                row.get('title') or '—',
                'конверт',
                _money(row.get('balance'), code),
                '—',
            ))
            continue
        target = row.get('target')
        rows.append((
            row.get('title') or '—',
            'цель',
            _money(row.get('balance'), code),
            _money(target, code) if target else '—',
        ))
    return _pack(caption, ('Имя', 'Тип', 'Лежит', 'Цель'), rows)


def _recurring_amount(row: dict[str, Any], currency: str | None) -> str:
    if row.get('amount') is not None:
        return _money(row.get('amount'), currency)
    low, high = row.get('amount_min'), row.get('amount_max')
    if low is not None and high is not None:
        return f'{_money(low, currency)} – {_money(high, currency)}'
    return 'по факту'


def _due_label(value: Any) -> str:
    text = str(value or '')
    parts = text.split('-')
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        year, month, day = parts
        return f'{day}.{month}.{year}'
    return text or '—'


def _pack(
    caption: str,
    headers: tuple[str, ...],
    rows: list[tuple],
) -> dict[str, Any] | None:
    if not rows:
        return None
    plain = []
    for row in rows:
        cells = row[:-1] if isinstance(row[-1], bool) else row
        plain.append(' — '.join(str(cell) for cell in cells))
    return {
        'caption': caption,
        'headers': headers,
        'rows': rows,
        'plain': plain,
    }
