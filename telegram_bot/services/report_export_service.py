import io
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable

from asgiref.sync import sync_to_async
from django.contrib.auth.models import User

from transactions.models import Transaction

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExcelExportResult:
    filename: str
    content: bytes


class ReportExportService:
    """
    Генерация Excel-отчетов для Telegram-бота.

    Важно: сервис разделяет извлечение данных и рендеринг в Excel так, чтобы
    в будущем было легко добавлять новые листы (цели/рекомендации/прогнозы).
    """

    def __init__(self, user: User):
        self.user = user

    async def build_monthly_excel(
        self,
        year: int,
        month: int,
    ) -> ExcelExportResult:
        start_date, end_date = self._month_range(year, month)
        transactions = await self._get_transactions(start_date, end_date)

        report_title = f"FinHub — отчет за {month:02d}.{year}"
        filename = f"finhub_report_{year}-{month:02d}.xlsx"

        content = self._render_excel(
            report_title=report_title,
            start_date=start_date,
            end_date=end_date,
            transactions=transactions,
        )

        return ExcelExportResult(
            filename=filename,
            content=content,
        )

    @staticmethod
    def _month_range(year: int, month: int) -> tuple[date, date]:
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        return start_date, end_date

    async def _get_transactions(
        self,
        start_date: date,
        end_date: date,
    ) -> list[Transaction]:
        qs = (
            Transaction.objects.filter(
                user=self.user,
                date__gte=start_date,
                date__lt=end_date,
            )
            .select_related("category")
            .order_by("date", "id")
        )
        return await sync_to_async(list)(qs)

    def _render_excel(
        self,
        report_title: str,
        start_date: date,
        end_date: date,
        transactions: Iterable[Transaction],
    ) -> bytes:
        try:
            import xlsxwriter
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "xlsxwriter не установлен. Добавьте зависимость 'xlsxwriter' в проект."
            ) from exc

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})

        fmt_title = workbook.add_format(
            {
                "bold": True,
                "font_size": 16,
            }
        )
        fmt_h2 = workbook.add_format({"bold": True, "font_size": 12})
        fmt_header = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#F2F2F2",
                "border": 1,
            }
        )
        fmt_money = workbook.add_format({"num_format": "#,##0.00"})
        fmt_money_red = workbook.add_format({"num_format": "#,##0.00", "font_color": "#C00000"})
        fmt_date = workbook.add_format({"num_format": "dd.mm.yyyy"})

        # ---- агрегаты ----
        daily_income: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
        daily_expense: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))

        category_income: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        category_expense: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

        tx_rows: list[dict] = []

        for t in transactions:
            category_label = f"{getattr(t.category, 'icon', '')} {t.category.name}".strip()
            amount = Decimal(t.amount)

            if amount >= 0:
                daily_income[t.date] += amount
                category_income[category_label] += amount
                tx_type = "income"
            else:
                daily_expense[t.date] += abs(amount)
                category_expense[category_label] += abs(amount)
                tx_type = "expense"

            tx_rows.append(
                {
                    "date": t.date,
                    "type": tx_type,
                    "category": category_label,
                    "amount": amount,
                    "comment": t.description or "",
                    "id": t.id,
                }
            )

        total_income = sum(category_income.values(), Decimal("0"))
        total_expenses = sum(category_expense.values(), Decimal("0"))
        net = total_income - total_expenses

        # ---- sheet: Summary ----
        ws_summary = workbook.add_worksheet("Summary")
        ws_summary.set_column("A:A", 22)
        ws_summary.set_column("B:B", 22)
        ws_summary.set_column("C:C", 22)
        ws_summary.set_column("D:D", 22)

        ws_summary.write(0, 0, report_title, fmt_title)
        ws_summary.write(1, 0, "Период", fmt_h2)
        ws_summary.write(1, 1, f"{start_date.strftime('%d.%m.%Y')} – {(end_date).strftime('%d.%m.%Y')} (не включая)")
        ws_summary.write(2, 0, "Сформировано", fmt_h2)
        ws_summary.write(2, 1, datetime.now().strftime("%d.%m.%Y %H:%M"))

        ws_summary.write(4, 0, "Доходы", fmt_h2)
        ws_summary.write_number(4, 1, float(total_income), fmt_money)
        ws_summary.write(5, 0, "Расходы", fmt_h2)
        ws_summary.write_number(5, 1, float(total_expenses), fmt_money)
        ws_summary.write(6, 0, "Чистый cashflow", fmt_h2)
        ws_summary.write_number(6, 1, float(net), fmt_money if net >= 0 else fmt_money_red)

        # ---- sheet: Cashflow (daily) ----
        ws_cf = workbook.add_worksheet("Cashflow")
        ws_cf.freeze_panes(1, 0)
        ws_cf.set_column("A:A", 14)
        ws_cf.set_column("B:D", 16)
        ws_cf.set_column("E:E", 18)

        ws_cf.write(0, 0, "Дата", fmt_header)
        ws_cf.write(0, 1, "Доходы", fmt_header)
        ws_cf.write(0, 2, "Расходы", fmt_header)
        ws_cf.write(0, 3, "Net", fmt_header)
        ws_cf.write(0, 4, "Кумулятивный баланс", fmt_header)

        # полный диапазон дней месяца
        day = start_date
        cumulative = Decimal("0")
        r = 1
        while day < end_date:
            inc = daily_income.get(day, Decimal("0"))
            exp = daily_expense.get(day, Decimal("0"))
            day_net = inc - exp
            cumulative += day_net

            ws_cf.write_datetime(r, 0, datetime(day.year, day.month, day.day), fmt_date)
            ws_cf.write_number(r, 1, float(inc), fmt_money)
            ws_cf.write_number(r, 2, float(exp), fmt_money)
            ws_cf.write_number(r, 3, float(day_net), fmt_money if day_net >= 0 else fmt_money_red)
            ws_cf.write_number(r, 4, float(cumulative), fmt_money if cumulative >= 0 else fmt_money_red)

            r += 1
            day = date.fromordinal(day.toordinal() + 1)

        # График: кумулятивный баланс
        chart_balance = workbook.add_chart({"type": "line"})
        chart_balance.add_series(
            {
                "name": "Кумулятивный баланс",
                "categories": ["Cashflow", 1, 0, r - 1, 0],
                "values": ["Cashflow", 1, 4, r - 1, 4],
            }
        )
        chart_balance.set_title({"name": "Cashflow: кумулятивный баланс"})
        chart_balance.set_y_axis({"name": "₽"})
        ws_summary.insert_chart("D4", chart_balance, {"x_scale": 1.2, "y_scale": 1.2})

        # ---- sheet: Categories ----
        ws_cat = workbook.add_worksheet("Categories")
        ws_cat.freeze_panes(1, 0)
        ws_cat.set_column("A:A", 36)
        ws_cat.set_column("B:C", 18)

        ws_cat.write(0, 0, "Категория", fmt_header)
        ws_cat.write(0, 1, "Доходы", fmt_header)
        ws_cat.write(0, 2, "Расходы", fmt_header)

        cat_names = sorted(set(category_income.keys()) | set(category_expense.keys()))
        for idx, name in enumerate(cat_names, start=1):
            ws_cat.write(idx, 0, name)
            ws_cat.write_number(idx, 1, float(category_income.get(name, Decimal("0"))), fmt_money)
            ws_cat.write_number(idx, 2, float(category_expense.get(name, Decimal("0"))), fmt_money)

        # График: расходы по категориям (top 10)
        if cat_names:
            # Сделаем отдельный топ-10 по расходам
            top_exp = sorted(
                ((n, category_expense.get(n, Decimal("0"))) for n in cat_names),
                key=lambda x: x[1],
                reverse=True,
            )[:10]

            ws_summary.write(8, 0, "Топ расходов по категориям", fmt_h2)
            ws_summary.write(9, 0, "Категория", fmt_header)
            ws_summary.write(9, 1, "Расходы", fmt_header)
            for i, (n, v) in enumerate(top_exp, start=10):
                ws_summary.write(i, 0, n)
                ws_summary.write_number(i, 1, float(v), fmt_money)

            last_row = 10 + len(top_exp) - 1
            chart_exp_cat = workbook.add_chart({"type": "column"})
            chart_exp_cat.add_series(
                {
                    "name": "Расходы",
                    "categories": ["Summary", 10, 0, last_row, 0],
                    "values": ["Summary", 10, 1, last_row, 1],
                }
            )
            chart_exp_cat.set_title({"name": "Расходы по категориям (топ-10)"})
            chart_exp_cat.set_y_axis({"name": "₽"})
            ws_summary.insert_chart("D20", chart_exp_cat, {"x_scale": 1.2, "y_scale": 1.2})

        # ---- sheet: Transactions ----
        ws_tx = workbook.add_worksheet("Transactions")
        ws_tx.freeze_panes(1, 0)
        ws_tx.set_column("A:A", 12)
        ws_tx.set_column("B:B", 10)
        ws_tx.set_column("C:C", 32)
        ws_tx.set_column("D:D", 14)
        ws_tx.set_column("E:E", 50)
        ws_tx.set_column("F:F", 10)

        ws_tx.write(0, 0, "Дата", fmt_header)
        ws_tx.write(0, 1, "Тип", fmt_header)
        ws_tx.write(0, 2, "Категория", fmt_header)
        ws_tx.write(0, 3, "Сумма", fmt_header)
        ws_tx.write(0, 4, "Комментарий", fmt_header)
        ws_tx.write(0, 5, "ID", fmt_header)

        for idx, row in enumerate(tx_rows, start=1):
            ws_tx.write_datetime(idx, 0, datetime(row["date"].year, row["date"].month, row["date"].day), fmt_date)
            ws_tx.write(idx, 1, "Доход" if row["type"] == "income" else "Расход")
            ws_tx.write(idx, 2, row["category"])
            amt = Decimal(row["amount"])
            ws_tx.write_number(idx, 3, float(amt), fmt_money if amt >= 0 else fmt_money_red)
            ws_tx.write(idx, 4, row["comment"])
            ws_tx.write_number(idx, 5, int(row["id"]))

        workbook.close()
        output.seek(0)
        return output.read()

