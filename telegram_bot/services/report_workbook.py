"""Два Excel-файла: месяц и год. Графики и полоски, без срезов и сводных."""

from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal

from xlsxwriter.utility import xl_range, xl_rowcol_to_cell

from telegram_bot.services.report_figures import (
    MONTHS,
    MONTHS_OF,
    MONTHS_SHORT,
    CategoryRow,
    CategoryYearRow,
    DayRow,
    EnvelopeRow,
    Flow,
    GoalRow,
    LedgerTx,
    MonthReport,
    MonthSlot,
    Tx,
    WeekRow,
    YearReport,
)

INK = '#1F2937'
MUTED = '#6B7280'
CARD = '#F8FAFC'
LINE = '#E5E7EB'
WHITE = '#FFFFFF'
INCOME = '#1F7A4D'
EXPENSE = '#C2410C'
RESERVE = '#1D4E89'
FREE = '#0F766E'
BAD = '#B91C1C'
CURRENT = '#EFF6FF'

STATUS = {
    'active': 'активна',
    'paused': 'пауза',
    'completed': 'завершена',
    'cancelled': 'отменена',
    'archived': 'в архиве',
}
ENTRY = {
    'deposit': 'Пополнение',
    'withdraw': 'Снятие',
    'spend': 'Покупка',
}

READING = (
    'Свободно = доходы − расходы − отложено. '
    'Отложено — взносы в цели и конверты минус снятия и покупки из них. '
    'Это не остаток на банковском счёте.'
)


def render_month_workbook(
    report: MonthReport,
    recurring_rows: tuple[str, ...] = (),
    debt_rows: tuple[str, ...] = (),
) -> bytes:
    book = _Book()
    _write_month_overview(book, report)
    _write_month_categories(book, report)
    _write_reserves(book, report.goals, report.envelopes, report.unit, 'месяц')
    _write_journal(book, report.transactions, report.ledger, report.unit, with_month=False)
    _write_side_sheet(book, 'Повторы', '#7C3AED', recurring_rows, 'Повторов нет.')
    _write_side_sheet(book, 'Долги', '#B45309', debt_rows, 'Открытых долгов нет.')
    return book.save()


def render_year_workbook(
    report: YearReport,
    recurring_rows: tuple[str, ...] = (),
    debt_rows: tuple[str, ...] = (),
) -> bytes:
    book = _Book()
    _write_year_overview(book, report)
    _write_year_categories(book, report)
    _write_reserves(book, report.goals, report.envelopes, report.unit, 'год')
    _write_journal(book, report.transactions, report.ledger, report.unit, with_month=True)
    _write_side_sheet(book, 'Повторы', '#7C3AED', recurring_rows, 'Повторов нет.')
    _write_side_sheet(book, 'Долги', '#B45309', debt_rows, 'Открытых долгов нет.')
    return book.save()


def _write_side_sheet(book: _Book, name: str, color: str, rows: tuple[str, ...], empty: str) -> None:
    """Отдельный лист. Соседний модуль сюда не пишет."""
    sheet = book.add(name, color)
    sheet.set_column(0, 0, 72)
    sheet.write(0, 0, name, book.title)
    if not rows:
        sheet.write(2, 0, empty, book.subtitle)
        return
    for index, line in enumerate(rows):
        sheet.write(index + 2, 0, line, book.text)


class _Book:
    def __init__(self) -> None:
        import xlsxwriter

        self.output = io.BytesIO()
        self.workbook = xlsxwriter.Workbook(self.output, {'in_memory': True})
        self.workbook.formats[0].set_font_name('Calibri')
        self.workbook.formats[0].set_font_size(11)
        self.workbook.formats[0].set_font_color(INK)
        self._build_formats()

    def save(self) -> bytes:
        self.workbook.close()
        self.output.seek(0)
        return self.output.read()

    def add(self, name: str, color: str):
        sheet = self.workbook.add_worksheet(name)
        sheet.hide_gridlines(2)
        sheet.set_tab_color(color)
        return sheet

    def _build_formats(self) -> None:
        wb = self.workbook

        def fmt(**opts):
            base = {'font_name': 'Calibri', 'font_color': INK, 'font_size': 11}
            base.update(opts)
            return wb.add_format(base)

        self.title = fmt(bold=True, font_size=22)
        self.subtitle = fmt(font_size=11, font_color=MUTED)
        self.section = fmt(bold=True, font_size=14)
        self.note = fmt(font_size=10, font_color=MUTED, text_wrap=True, italic=True)
        self.header = fmt(
            bold=True, font_size=10, font_color=WHITE, bg_color=INK,
            text_wrap=True, valign='vcenter',
        )
        self.header_now = fmt(
            bold=True, font_size=10, font_color=WHITE, bg_color=FREE,
            text_wrap=True, valign='vcenter', align='center',
        )
        self.text = fmt(valign='vcenter')
        self.text_now = fmt(valign='vcenter', bg_color=CURRENT)
        self.muted = fmt(font_color=MUTED, valign='vcenter')
        self.total = fmt(bold=True, bg_color='#F3F4F6', valign='vcenter')
        self.money = fmt(num_format='#,##0', valign='vcenter')
        self.money_now = fmt(num_format='#,##0', valign='vcenter', bg_color=CURRENT)
        self.money_bad = fmt(num_format='#,##0', font_color=BAD, valign='vcenter')
        self.money_bad_now = fmt(num_format='#,##0', font_color=BAD, valign='vcenter', bg_color=CURRENT)
        self.money_total = fmt(num_format='#,##0', bold=True, bg_color='#F3F4F6', valign='vcenter')
        self.money_total_bad = fmt(
            num_format='#,##0', bold=True, font_color=BAD, bg_color='#F3F4F6', valign='vcenter',
        )
        self.journal = fmt(num_format='#,##0.00', valign='vcenter')
        self.journal_bad = fmt(num_format='#,##0.00', font_color=BAD, valign='vcenter')
        self.percent = fmt(num_format='0.0%', valign='vcenter')
        self.percent_now = fmt(num_format='0.0%', valign='vcenter', bg_color=CURRENT)
        self.percent_bad = fmt(num_format='0.0%', font_color=BAD, valign='vcenter')
        self.percent_total = fmt(num_format='0.0%', bold=True, bg_color='#F3F4F6', valign='vcenter')
        self.date = fmt(num_format='dd.mm.yyyy', valign='vcenter')
        self.date_muted = fmt(num_format='dd.mm.yyyy', font_color=MUTED, valign='vcenter')
        self.tile_label = fmt(
            font_size=10, font_color=MUTED, bg_color=CARD, valign='bottom', indent=1,
        )
        self.dash = fmt(font_size=20, bold=True, font_color=MUTED, bg_color=CARD, valign='vcenter', indent=1)
        self.tile = {
            'income': fmt(font_size=20, bold=True, font_color=INCOME, bg_color=CARD, num_format='#,##0', valign='vcenter', indent=1),
            'expense': fmt(font_size=20, bold=True, font_color=EXPENSE, bg_color=CARD, num_format='#,##0', valign='vcenter', indent=1),
            'reserve': fmt(font_size=20, bold=True, font_color=RESERVE, bg_color=CARD, num_format='#,##0', valign='vcenter', indent=1),
            'free': fmt(font_size=20, bold=True, font_color=FREE, bg_color=CARD, num_format='#,##0', valign='vcenter', indent=1),
            'bad': fmt(font_size=20, bold=True, font_color=BAD, bg_color=CARD, num_format='#,##0', valign='vcenter', indent=1),
            'ink': fmt(font_size=20, bold=True, font_color=INK, bg_color=CARD, num_format='0.0%', valign='vcenter', indent=1),
        }
        self.accent = {
            'income': fmt(bg_color=INCOME),
            'expense': fmt(bg_color=EXPENSE),
            'reserve': fmt(bg_color=RESERVE),
            'free': fmt(bg_color=FREE),
            'bad': fmt(bg_color=BAD),
            'ink': fmt(bg_color=INK),
        }

    def chart(self, kind: str):
        chart = self.workbook.add_chart({'type': kind})
        chart.set_chartarea({'border': {'none': True}, 'fill': {'color': WHITE}})
        chart.set_plotarea({'border': {'none': True}})
        chart.set_legend({
            'position': 'bottom',
            'font': {'name': 'Calibri', 'size': 10, 'color': INK},
        })
        return chart


def _write_month_overview(book: _Book, report: MonthReport) -> None:
    ws = book.add('Обзор', RESERVE)
    for col in range(9):
        ws.set_column(col, col, 16)
    ws.merge_range(0, 0, 0, 8, f'{MONTHS[report.month - 1].capitalize()} {report.year}', book.title)
    ws.set_row(0, 30)
    ws.merge_range(
        1, 0, 1, 10,
        f'Суммы в {report.currency_phrase} · {report.generated_label}',
        book.subtitle,
    )
    _tiles(book, ws, 3, report.flow)
    _tiles(book, ws, 7, report.flow, second=True)
    ws.merge_range(11, 0, 11, 8, report.comparison, book.note)
    ws.set_row(11, 32)
    row = 12
    if report.pace:
        ws.merge_range(row, 0, row, 8, report.pace, book.note)
        ws.set_row(row, 32)
        row += 1
    row += 1
    chart_row = row
    row += 18

    row = _section(book, ws, row, 'Недели')
    ws.write_row(row, 0, ('Неделя', 'Доходы', 'Расходы', 'Отложено', 'Свободно'), book.header)
    ws.set_row(row, 22)
    row += 1
    for week in report.weeks:
        _write_week(book, ws, row, week)
        row += 1

    row += 1
    row = _section(book, ws, row, 'Дни')
    ws.merge_range(
        row, 0, row, 5,
        'Свободно с 1-го числа копится только внутри этого месяца.',
        book.note,
    )
    row += 1
    ws.write_row(
        row, 0,
        ('Дата', 'Доходы', 'Расходы', 'Отложено', 'Свободно за день', 'Свободно с 1-го'),
        book.header,
    )
    ws.set_row(row, 30)
    row += 1
    first_day = row
    for day in report.days:
        _write_day(book, ws, row, day)
        row += 1
    last_day = row - 1

    chart = book.chart('column')
    chart.add_series(_column_series('Доходы', 'Обзор', first_day, last_day, 1, INCOME))
    chart.add_series(_column_series('Расходы', 'Обзор', first_day, last_day, 2, EXPENSE))
    chart.add_series({
        'name': 'Свободно с 1-го',
        'categories': ['Обзор', first_day, 0, last_day, 0],
        'values': ['Обзор', first_day, 5, last_day, 5],
        'type': 'line',
        'line': {'color': FREE, 'width': 2.25},
        'marker': {
            'type': 'circle', 'size': 5,
            'border': {'color': FREE}, 'fill': {'color': WHITE},
        },
    })
    chart.set_title({'name': 'Движение по дням', 'name_font': _chart_title_font()})
    chart.set_y_axis(_money_axis(report.unit))
    chart.set_x_axis({
        'num_font': {'name': 'Calibri', 'size': 8, 'rotation': -45, 'color': MUTED},
        'line': {'color': LINE},
        'major_gridlines': {'visible': False},
        'interval_unit': 2,
    })
    chart.set_size({'width': 820, 'height': 260})
    ws.insert_chart(chart_row, 0, chart)


def _write_month_categories(book: _Book, report: MonthReport) -> None:
    ws = book.add('Категории', EXPENSE)
    ws.set_column(0, 0, 36)
    ws.set_column(1, 5, 16)
    ws.merge_range(0, 0, 0, 5, 'Куда ушло и откуда пришло', book.title)
    ws.set_row(0, 30)
    ws.merge_range(1, 0, 1, 5, f'Суммы в {report.currency_phrase}. Лимит — месячный, если он включён.', book.subtitle)

    row = 3
    ws.write(row, 0, 'Расходы', book.section)
    row += 1
    header = row
    ws.write_row(row, 0, ('Категория', 'Факт', 'Доля', 'Лимит', 'Осталось', '% лимита'), book.header)
    ws.set_row(row, 22)
    row += 1
    first = row
    for item in report.expenses:
        _write_category(book, ws, row, item)
        row += 1
    if report.expenses:
        last_expense = row - 1
        _write_category_total(book, ws, row, report.flow.expenses, first)
        ws.conditional_format(first, 5, last_expense, 5, {
            'type': 'data_bar',
            'bar_color': EXPENSE,
            'min_type': 'num',
            'min_value': 0,
            'max_type': 'num',
            'max_value': 1,
        })
        ws.conditional_format(first, 5, last_expense, 5, {
            'type': 'cell',
            'criteria': '>',
            'value': 1,
            'format': book.percent_bad,
        })
        ws.autofilter(header, 0, last_expense, 5)
        _expense_chart(book, ws, first, min(last_expense, first + 11))
        row += 1
    else:
        ws.write(row, 0, 'Расходов за этот месяц нет.', book.muted)
        row += 1

    row += 1
    ws.write(row, 0, 'Доходы', book.section)
    row += 1
    ws.write_row(row, 0, ('Категория', 'Сумма', 'Доля'), book.header)
    row += 1
    for item in report.incomes:
        ws.write(row, 0, item.label, book.text)
        _money_cell(book, ws, row, 1, item.amount)
        _ratio_cell(book, ws, row, 2, item.share)
        row += 1
    if report.incomes:
        ws.write(row, 0, 'Итого', book.total)
        ws.write_number(row, 1, _num(report.flow.income), book.money_total)
        ws.write_number(row, 2, 1, book.percent_total)
    else:
        ws.write(row, 0, 'Доходов за этот месяц нет.', book.muted)
    ws.freeze_panes(header + 1, 0)


def _write_year_overview(book: _Book, report: YearReport) -> None:
    ws = book.add('Обзор', RESERVE)
    widths = (22, 16, 16, 16, 16, 16, 16, 16, 22)
    for index, width in enumerate(widths):
        ws.set_column(index, index, width)
    ws.merge_range(0, 0, 0, 8, f'{report.year} год', book.title)
    ws.set_row(0, 30)
    ws.merge_range(
        1, 0, 1, 8,
        f'Суммы в {report.currency_phrase} · {report.generated_label}',
        book.subtitle,
    )
    _tiles(book, ws, 3, report.flow)
    _tiles(book, ws, 7, report.flow, second=True)
    ws.merge_range(
        11, 0, 11, 8,
        READING + ' Будущие месяцы пустые, пока не начались.',
        book.note,
    )
    ws.set_row(11, 36)

    header = 31
    ws.write_row(
        header, 0,
        (
            'Месяц', 'Доходы', 'Расходы', 'Остаток', 'Отложено', 'Свободно',
            'Норма сбережений', 'Траты в день', 'Расходы к прошлому месяцу',
        ),
        book.header,
    )
    ws.set_row(header, 32)
    first = header + 1
    for offset, slot in enumerate(report.months):
        _write_month_slot(book, ws, first + offset, slot, offset)
    last = first + 11
    total = last + 1
    average = total + 1
    ws.write(total, 0, 'Итого', book.total)
    ws.write(average, 0, 'Среднее', book.total)
    for col in range(1, 6):
        area = xl_range(first, col, last, col)
        ws.write_formula(total, col, f'=SUM({area})', book.money_total)
        ws.write_formula(average, col, f'=AVERAGE({area})', book.money)
    income_total = xl_rowcol_to_cell(total, 1)
    balance_total = xl_rowcol_to_cell(total, 3)
    ws.write_formula(
        total, 6,
        f'=IF({income_total}=0,"",{balance_total}/{income_total})',
        book.percent_total,
    )
    ws.write_formula(average, 6, f'=IFERROR(AVERAGE({xl_range(first, 6, last, 6)}),"")', book.percent)
    ws.write_formula(average, 7, f'=IFERROR(AVERAGE({xl_range(first, 7, last, 7)}),"")', book.money)
    ws.write_blank(total, 7, None, book.total)
    ws.write_blank(total, 8, None, book.total)
    ws.write_blank(average, 8, None, book.total)
    ws.conditional_format(first, 6, last, 6, {
        'type': 'data_bar',
        'bar_color': FREE,
        'bar_negative_color': BAD,
        'min_type': 'num',
        'min_value': 0,
        'max_type': 'num',
        'max_value': 1,
    })
    ws.merge_range(
        average + 2, 0, average + 2, 8,
        'Среднее — по месяцам, которые уже начались.',
        book.note,
    )

    chart = book.chart('column')
    chart.add_series(_column_series('Доходы', 'Обзор', first, last, 1, INCOME))
    chart.add_series(_column_series('Расходы', 'Обзор', first, last, 2, EXPENSE))
    chart.add_series({
        'name': 'Остаток',
        'categories': ['Обзор', first, 0, last, 0],
        'values': ['Обзор', first, 3, last, 3],
        'type': 'line',
        'line': {'color': RESERVE, 'width': 2.25},
        'marker': {
            'type': 'circle', 'size': 6,
            'border': {'color': RESERVE}, 'fill': {'color': WHITE},
        },
    })
    chart.set_title({'name': 'Движение по месяцам', 'name_font': _chart_title_font()})
    chart.set_y_axis(_money_axis(report.unit))
    chart.set_x_axis({
        'num_font': {'name': 'Calibri', 'size': 10, 'color': INK},
        'line': {'color': LINE},
        'major_gridlines': {'visible': False},
    })
    chart.set_size({'width': 860, 'height': 280})
    ws.insert_chart(13, 0, chart)


def _write_year_categories(book: _Book, report: YearReport) -> None:
    ws = book.add('Категории', EXPENSE)
    ws.set_column(0, 0, 32)
    ws.set_column(1, 12, 12)
    ws.set_column(13, 14, 14)
    ws.merge_range(0, 0, 0, 14, f'Категории · {report.year}', book.title)
    ws.set_row(0, 30)
    ws.write(1, 0, f'Суммы в {report.currency_phrase}.', book.subtitle)

    def block(start_row: int, title: str, rows: tuple[CategoryYearRow, ...]) -> int:
        ws.write(start_row, 0, title, book.section)
        header = start_row + 1
        labels = ['Категория', *MONTHS_SHORT, 'Год', 'Доля']
        for col, label in enumerate(labels):
            head = book.header_now if _is_current_month_col(report, col) else book.header
            ws.write(header, col, label, head)
        ws.set_row(header, 22)
        row = header + 1
        if not rows:
            ws.write(row, 0, 'Здесь пусто.', book.muted)
            return row + 1
        first = row
        for item in rows:
            _write_year_category(book, ws, row, item, report)
            row += 1
        ws.autofilter(header, 0, row - 1, 14)
        ws.freeze_panes(header + 1, 1)
        return row + 1

    # Два фильтра на одном листе Excel не живут. Доходы идут ниже и остаются на виду.
    next_row = block(3, 'Расходы по месяцам', report.expenses)
    income_header_owner = next_row
    ws.write(next_row, 0, 'Доходы по месяцам', book.section)
    header = next_row + 1
    for col, label in enumerate(('Категория', *MONTHS_SHORT, 'Год', 'Доля')):
        head = book.header_now if _is_current_month_col(report, col) else book.header
        ws.write(header, col, label, head)
    row = header + 1
    if not report.incomes:
        ws.write(row, 0, 'Здесь пусто.', book.muted)
        return
    for item in report.incomes:
        _write_year_category(book, ws, row, item, report)
        row += 1
    del income_header_owner


def _write_reserves(book: _Book, goals: tuple[GoalRow, ...], envelopes: tuple[EnvelopeRow, ...], unit: str, period: str) -> None:
    ws = book.add('Резервы', FREE)
    widths = (28, 14, 14, 16, 16, 16, 16, 16, 14, 16, 18, 16, 18)
    for index, width in enumerate(widths):
        ws.set_column(index, index, width)
    ws.merge_range(0, 0, 0, 8, 'Цели и конверты', book.title)
    ws.set_row(0, 30)
    ws.merge_range(
        1, 0, 1, 8,
        'Процент цели считается от накопленного. Покупка его не снижает, остаток при этом уменьшается. '
        f'Запас — на конец периода, движение — за {period}.',
        book.note,
    )
    ws.set_row(1, 32)
    ws.write(3, 0, 'Цели', book.section)
    headers = (
        'Цель', 'Статус', 'Дедлайн', f'Сумма цели ({unit})', f'Накоплено ({unit})',
        f'Потрачено ({unit})', f'Сейчас лежит ({unit})', f'Осталось ({unit})', 'Прогресс',
        f'План в месяц ({unit})', f'Внесено за {period} ({unit})',
        f'Снято за {period} ({unit})', f'Покупки за {period} ({unit})',
    )
    ws.write_row(4, 0, headers, book.header)
    ws.set_row(4, 36)
    row = 5
    if not goals:
        ws.write(row, 0, 'Активных целей нет.', book.muted)
        row += 1
    else:
        first = row
        for goal in goals:
            _write_goal(book, ws, row, goal)
            row += 1
        ws.conditional_format(first, 8, row - 1, 8, {
            'type': 'data_bar',
            'bar_color': RESERVE,
            'min_type': 'num',
            'min_value': 0,
            'max_type': 'num',
            'max_value': 1,
        })
    row += 2
    ws.write(row, 0, 'Конверты', book.section)
    row += 1
    ws.write_row(
        row, 0,
        (
            'Конверт', 'Статус', f'Внесено ({unit})', f'Потрачено ({unit})',
            f'Снято ({unit})', f'Остаток ({unit})',
            f'Внесено за {period} ({unit})', f'Потрачено за {period} ({unit})',
            f'Снято за {period} ({unit})',
        ),
        book.header,
    )
    ws.set_row(row, 36)
    row += 1
    if not envelopes:
        ws.write(row, 0, 'Активных конвертов нет.', book.muted)
        return
    for envelope in envelopes:
        _write_envelope(book, ws, row, envelope)
        row += 1
    ws.freeze_panes(5, 1)


def _write_journal(
    book: _Book,
    transactions: tuple[Tx, ...],
    ledger: tuple[LedgerTx, ...],
    unit: str,
    *,
    with_month: bool,
) -> None:
    ws = book.add('Журнал', '#64748B')
    widths = (14, 14, 12, 32, 16, 14, 16, 48, 12) if with_month else (14, 12, 32, 16, 14, 16, 48, 12)
    for index, width in enumerate(widths):
        ws.set_column(index, index, width)
    ws.merge_range(0, 0, 0, 6, 'Журнал', book.title)
    ws.set_row(0, 30)
    ws.write(1, 0, 'Фильтр в шапке таблицы операций. Сумма операции — в валюте отчёта, со знаком.', book.subtitle)

    headers = ['Дата', 'Тип', 'Категория', f'Сумма ({unit})', 'Валюта ввода', 'Сумма ввода', 'Комментарий', 'ID']
    if with_month:
        headers.insert(1, 'Месяц')
    header = 3
    for col, label in enumerate(headers):
        ws.write(header, col, label, book.header)
    ws.set_row(header, 22)
    row = header + 1
    for item in transactions:
        _write_tx(book, ws, row, item, with_month)
        row += 1
    if transactions:
        ws.autofilter(header, 0, row - 1, len(headers) - 1)
    else:
        ws.write(row, 0, 'Операций за этот период нет.', book.muted)
        row += 1
    ws.freeze_panes(header + 1, 0)

    row += 2
    ws.write(row, 0, 'Движения резерва', book.section)
    row += 1
    reserve_headers = ['Дата', 'Название', 'Где', 'Тип', f'Сумма ({unit})', 'Комментарий']
    if with_month:
        reserve_headers.insert(1, 'Месяц')
    for col, label in enumerate(reserve_headers):
        ws.write(row, col, label, book.header)
    row += 1
    if not ledger:
        ws.write(row, 0, 'Движений резерва нет.', book.muted)
        return
    for entry in ledger:
        _write_ledger(book, ws, row, entry, with_month)
        row += 1


def _tiles(book: _Book, ws, row: int, flow: Flow, *, second: bool = False) -> None:
    if second:
        specs = (
            (0, 'Отложено', flow.allocated, 'bad' if flow.allocated < 0 else 'reserve'),
            (3, 'Свободно', flow.free, 'bad' if flow.free < 0 else 'free'),
            (6, 'Норма сбережений', flow.savings_ratio(), 'ink'),
        )
    else:
        specs = (
            (0, 'Доходы', flow.income, 'income'),
            (3, 'Расходы', flow.expenses, 'expense'),
            (6, 'Остаток', flow.balance, 'bad' if flow.balance < 0 else 'free'),
        )
    ws.set_row(row, 18)
    ws.set_row(row + 1, 32)
    ws.set_row(row + 2, 6)
    for col, label, value, kind in specs:
        ws.merge_range(row, col, row, col + 2, label, book.tile_label)
        if value is None:
            ws.merge_range(row + 1, col, row + 1, col + 2, '—', book.dash)
        else:
            shown = float(value) if kind == 'ink' else _num(value)
            ws.merge_range(row + 1, col, row + 1, col + 2, shown, book.tile[kind])
        ws.merge_range(row + 2, col, row + 2, col + 2, '', book.accent[kind])


def _write_week(book: _Book, ws, row: int, week: WeekRow) -> None:
    ws.write(row, 0, _week_label(week), book.muted if week.future else book.text)
    if week.future:
        for col in range(1, 5):
            ws.write_blank(row, col, None, book.muted)
        return
    _money_cell(book, ws, row, 1, week.flow.income)
    _money_cell(book, ws, row, 2, week.flow.expenses)
    _money_cell(book, ws, row, 3, week.flow.allocated)
    _money_cell(book, ws, row, 4, week.flow.free)


def _write_day(book: _Book, ws, row: int, day: DayRow) -> None:
    ws.write_datetime(row, 0, _midnight(day.day), book.date_muted if day.future else book.date)
    if day.future:
        for col in range(1, 6):
            ws.write_blank(row, col, None, book.muted)
        return
    _money_cell(book, ws, row, 1, day.income)
    _money_cell(book, ws, row, 2, day.expenses)
    _money_cell(book, ws, row, 3, day.allocated)
    _money_cell(book, ws, row, 4, day.day_free)
    _money_cell(book, ws, row, 5, day.running_free)


def _write_category(book: _Book, ws, row: int, item: CategoryRow) -> None:
    ws.write(row, 0, item.label, book.text)
    _money_cell(book, ws, row, 1, item.amount)
    _ratio_cell(book, ws, row, 2, item.share)
    if item.limit is None:
        for col in range(3, 6):
            ws.write_blank(row, col, None, book.text)
        return
    _money_cell(book, ws, row, 3, item.limit)
    _money_cell(book, ws, row, 4, item.remaining or Decimal('0'))
    _ratio_cell(book, ws, row, 5, item.limit_ratio)


def _write_category_total(book: _Book, ws, row: int, total: Decimal, first: int) -> None:
    ws.write(row, 0, 'Итого', book.total)
    ws.write_formula(row, 1, f'=SUM({xl_range(first, 1, row - 1, 1)})', book.money_total)
    ws.write_number(row, 2, 1 if total else 0, book.percent_total)
    for col in range(3, 6):
        ws.write_blank(row, col, None, book.total)


def _write_month_slot(book: _Book, ws, row: int, slot: MonthSlot, index: int) -> None:
    current = slot.state == 'current'
    name_fmt = book.text_now if current else book.muted if slot.flow is None else book.text
    ws.write(row, 0, MONTHS[slot.month - 1].capitalize(), name_fmt)
    if slot.flow is None:
        for col in range(1, 9):
            ws.write_blank(row, col, None, book.muted)
        return
    money = book.money_now if current else book.money
    bad = book.money_bad_now if current else book.money_bad
    _signed(ws, row, 1, slot.flow.income, money, bad)
    _signed(ws, row, 2, slot.flow.expenses, money, bad)
    _signed(ws, row, 3, slot.flow.balance, money, bad)
    _signed(ws, row, 4, slot.flow.allocated, money, bad)
    _signed(ws, row, 5, slot.flow.free, money, bad)
    ratio_fmt = book.percent_now if current else book.percent
    if slot.flow.savings_ratio() is None:
        ws.write_blank(row, 6, None, name_fmt)
    else:
        ratio = slot.flow.savings_ratio()
        ws.write_number(row, 6, float(ratio), book.percent_bad if ratio < 0 else ratio_fmt)
    if slot.daily_expense is None:
        ws.write_blank(row, 7, None, name_fmt)
    else:
        ws.write_number(row, 7, _num(slot.daily_expense), money)
    if slot.expense_delta is None:
        ws.write_blank(row, 8, None, name_fmt)
    elif index == 0:
        _signed(ws, row, 8, slot.expense_delta, money, bad)
    else:
        current_cell = xl_rowcol_to_cell(row, 2)
        previous_cell = xl_rowcol_to_cell(row - 1, 2)
        ws.write_formula(row, 8, f'={current_cell}-{previous_cell}', money)


def _write_year_category(book: _Book, ws, row: int, item: CategoryYearRow, report: YearReport) -> None:
    ws.write(row, 0, item.label, book.text)
    for index, amount in enumerate(item.months):
        col = index + 1
        current = report.months[index].state == 'current'
        if amount is None:
            ws.write_blank(row, col, None, book.muted)
        else:
            ws.write_number(row, col, _num(amount), book.money_now if current else book.money)
    ws.write_number(row, 13, _num(item.total), book.money_total)
    _ratio_cell(book, ws, row, 14, item.share)


def _write_goal(book: _Book, ws, row: int, goal: GoalRow) -> None:
    ws.write(row, 0, goal.title, book.text)
    ws.write(row, 1, STATUS.get(goal.status, goal.status), book.text)
    if goal.deadline:
        ws.write_datetime(row, 2, _midnight(goal.deadline), book.date)
    else:
        ws.write_blank(row, 2, None, book.text)
    _money_cell(book, ws, row, 3, goal.target)
    _money_cell(book, ws, row, 4, goal.committed)
    _money_cell(book, ws, row, 5, goal.spent_total)
    _money_cell(book, ws, row, 6, goal.balance)
    _money_cell(book, ws, row, 7, goal.remaining)
    _ratio_cell(book, ws, row, 8, goal.progress)
    if goal.plan_per_month is None:
        ws.write_blank(row, 9, None, book.text)
    else:
        _money_cell(book, ws, row, 9, goal.plan_per_month)
    _money_cell(book, ws, row, 10, goal.period_deposited)
    _money_cell(book, ws, row, 11, goal.period_withdrawn)
    _money_cell(book, ws, row, 12, goal.period_spent)


def _write_envelope(book: _Book, ws, row: int, envelope: EnvelopeRow) -> None:
    ws.write(row, 0, envelope.title, book.text)
    ws.write(row, 1, STATUS.get(envelope.status, envelope.status), book.text)
    _money_cell(book, ws, row, 2, envelope.deposited)
    _money_cell(book, ws, row, 3, envelope.spent)
    _money_cell(book, ws, row, 4, envelope.withdrawn)
    _money_cell(book, ws, row, 5, envelope.balance)
    _money_cell(book, ws, row, 6, envelope.period_deposited)
    _money_cell(book, ws, row, 7, envelope.period_spent)
    _money_cell(book, ws, row, 8, envelope.period_withdrawn)


def _write_tx(book: _Book, ws, row: int, item: Tx, with_month: bool) -> None:
    col = 0
    ws.write_datetime(row, col, _midnight(item.day), book.date)
    col += 1
    if with_month:
        ws.write(row, col, MONTHS[item.day.month - 1], book.text)
        col += 1
    ws.write(row, col, 'Доход' if item.amount > 0 else 'Расход', book.text)
    ws.write(row, col + 1, item.label, book.text)
    _journal_money(book, ws, row, col + 2, item.amount)
    ws.write(row, col + 3, item.currency, book.text)
    _journal_money(book, ws, row, col + 4, item.original_amount)
    ws.write(row, col + 5, item.description, book.text)
    ws.write_number(row, col + 6, item.id, book.text)


def _write_ledger(book: _Book, ws, row: int, entry: LedgerTx, with_month: bool) -> None:
    col = 0
    ws.write_datetime(row, col, _midnight(entry.day), book.date)
    col += 1
    if with_month:
        ws.write(row, col, MONTHS[entry.day.month - 1], book.text)
        col += 1
    ws.write(row, col, entry.title, book.text)
    ws.write(row, col + 1, 'конверт' if entry.is_envelope else 'цель', book.text)
    ws.write(row, col + 2, ENTRY.get(entry.entry_type, entry.entry_type), book.text)
    _journal_money(book, ws, row, col + 3, entry.amount)
    ws.write(row, col + 4, entry.comment, book.text)


def _expense_chart(book: _Book, ws, first: int, last: int) -> None:
    if last < first:
        return
    chart = book.chart('bar')
    chart.add_series({
        'name': 'Расходы',
        'categories': ['Категории', first, 0, last, 0],
        'values': ['Категории', first, 1, last, 1],
        'fill': {'color': EXPENSE},
        'gap': 40,
    })
    chart.set_legend({'none': True})
    chart.set_title({'name': 'Крупные расходы', 'name_font': _chart_title_font()})
    chart.set_x_axis(_money_axis(''))
    chart.set_y_axis({
        'reverse': True,
        'major_gridlines': {'visible': False},
        'line': {'none': True},
        'num_font': {'name': 'Calibri', 'size': 10, 'color': INK},
    })
    count = last - first + 1
    chart.set_size({'width': 520, 'height': max(180, 36 * count + 40)})
    ws.insert_chart(3, 7, chart)


def _column_series(name: str, sheet: str, first: int, last: int, col: int, color: str) -> dict:
    return {
        'name': name,
        'categories': [sheet, first, 0, last, 0],
        'values': [sheet, first, col, last, col],
        'fill': {'color': color},
        'gap': 70,
        'border': {'none': True},
    }


def _money_axis(unit: str) -> dict:
    axis = {
        'num_format': '#,##0',
        'num_font': {'name': 'Calibri', 'size': 9, 'color': MUTED},
        'line': {'none': True},
        'major_gridlines': {'visible': True, 'line': {'color': LINE}},
    }
    if unit:
        axis['name'] = unit
        axis['name_font'] = {'name': 'Calibri', 'size': 10, 'color': MUTED}
    return axis


def _chart_title_font() -> dict:
    return {'name': 'Calibri', 'size': 14, 'color': INK, 'bold': False}


def _section(book: _Book, ws, row: int, title: str) -> int:
    ws.write(row, 0, title, book.section)
    return row + 1


def _money_cell(book: _Book, ws, row: int, col: int, value: Decimal | None) -> None:
    if value is None:
        ws.write_blank(row, col, None, book.text)
        return
    ws.write_number(row, col, _num(value), book.money_bad if value < 0 else book.money)


def _journal_money(book: _Book, ws, row: int, col: int, value: Decimal) -> None:
    ws.write_number(row, col, _num(value), book.journal_bad if value < 0 else book.journal)


def _ratio_cell(book: _Book, ws, row: int, col: int, value: Decimal | None) -> None:
    if value is None:
        ws.write_blank(row, col, None, book.text)
        return
    ws.write_number(row, col, float(value), book.percent_bad if value < 0 else book.percent)


def _signed(ws, row: int, col: int, value: Decimal, money, bad) -> None:
    ws.write_number(row, col, _num(value), bad if value < 0 else money)


def _is_current_month_col(report: YearReport, col: int) -> bool:
    if not 1 <= col <= 12:
        return False
    return report.months[col - 1].state == 'current'


def _week_label(week: WeekRow) -> str:
    if week.start.month == week.end.month:
        return f'{week.start.day}–{week.end.day} {MONTHS_OF[week.start.month - 1]}'
    return (
        f'{week.start.day} {MONTHS_SHORT[week.start.month - 1]} – '
        f'{week.end.day} {MONTHS_SHORT[week.end.month - 1]}'
    )


def _midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day)


def _num(value: Decimal) -> float:
    return float(Decimal(value).quantize(Decimal('0.01')))
