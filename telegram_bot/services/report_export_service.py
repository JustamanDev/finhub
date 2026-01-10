import io
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable

from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from goals.models import (
    Goal,
    GoalLedgerEntry,
)
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
        goals = await self._get_goals()
        goal_balances = await self._get_goal_balances()
        goal_entries = await self._get_goal_entries(start_date, end_date)

        report_title = f"FinHub — отчет за {month:02d}.{year}"
        filename = f"finhub_report_{year}-{month:02d}.xlsx"

        content = self._render_excel(
            report_title=report_title,
            start_date=start_date,
            end_date=end_date,
            transactions=transactions,
            goals=goals,
            goal_balances=goal_balances,
            goal_entries=goal_entries,
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

    async def _get_goals(self) -> list[Goal]:
        return await sync_to_async(list)(
            Goal.objects.filter(user=self.user).order_by('created_at', 'id')
        )

    async def _get_goal_balances(self) -> dict[int, Decimal]:
        qs = (
            GoalLedgerEntry.objects.filter(goal__user=self.user)
            .values('goal_id')
            .annotate(total=models.Sum('amount'))
        )
        rows = await sync_to_async(list)(qs)
        return {
            int(r['goal_id']): Decimal(r['total'] or 0)
            for r in rows
        }

    async def _get_goal_entries(
        self,
        start_date: date,
        end_date: date,
    ) -> list[GoalLedgerEntry]:
        start_dt = timezone.make_aware(datetime(start_date.year, start_date.month, start_date.day))
        end_dt = timezone.make_aware(datetime(end_date.year, end_date.month, end_date.day))
        qs = (
            GoalLedgerEntry.objects.filter(
                goal__user=self.user,
                occurred_at__gte=start_dt,
                occurred_at__lt=end_dt,
            )
            .select_related('goal')
            .order_by('occurred_at', 'id')
        )
        return await sync_to_async(list)(qs)

    def _render_excel(
        self,
        report_title: str,
        start_date: date,
        end_date: date,
        transactions: Iterable[Transaction],
        goals: list[Goal],
        goal_balances: dict[int, Decimal],
        goal_entries: list[GoalLedgerEntry],
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
        fmt_note = workbook.add_format({"font_color": "#666666", "text_wrap": True})
        fmt_header = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#F2F2F2",
                "border": 1,
            }
        )
        fmt_header_strong = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#E8E8E8",
                "border": 1,
            }
        )
        fmt_money = workbook.add_format({"num_format": "#,##0.00"})
        fmt_money_red = workbook.add_format({"num_format": "#,##0.00", "font_color": "#C00000"})
        fmt_money_bold = workbook.add_format({"num_format": "#,##0.00", "bold": True})
        fmt_money_bold_red = workbook.add_format(
            {"num_format": "#,##0.00", "bold": True, "font_color": "#C00000"}
        )
        fmt_date = workbook.add_format({"num_format": "dd.mm.yyyy"})

        # ---- агрегаты ----
        daily_income: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
        daily_expense: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
        daily_allocations: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))

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

        # Цели (ledger): дневные аллокации в цели (net)
        allocations_month = Decimal("0")
        deposits_by_goal: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        for e in goal_entries:
            d = e.occurred_at.date()
            daily_allocations[d] += Decimal(e.amount)
            allocations_month += Decimal(e.amount)
            if e.amount > 0:
                deposits_by_goal[int(e.goal_id)] += Decimal(e.amount)

        total_income = sum(category_income.values(), Decimal("0"))
        total_expenses = sum(category_expense.values(), Decimal("0"))
        net = total_income - total_expenses  # доходы - расходы (без целей)
        free_net = net - allocations_month   # свободно с учетом целей

        # ---- sheet: Сводка ----
        ws_summary = workbook.add_worksheet("Сводка")
        ws_summary.set_column("A:A", 22)
        ws_summary.set_column("B:B", 52)
        ws_summary.set_column("C:C", 22)
        ws_summary.set_column("D:D", 40)

        ws_summary.write(0, 0, report_title, fmt_title)
        ws_summary.write(1, 0, "Период", fmt_h2)
        ws_summary.write(
            1,
            1,
            f"{start_date.strftime('%d.%m.%Y')} – {(end_date).strftime('%d.%m.%Y')} (не включая)",
        )
        ws_summary.write(2, 0, "Сформировано", fmt_h2)
        ws_summary.write(2, 1, datetime.now().strftime("%d.%m.%Y %H:%M"))

        ws_summary.write(4, 0, "Доходы", fmt_h2)
        ws_summary.write_number(4, 1, float(total_income), fmt_money)
        ws_summary.write(5, 0, "Расходы", fmt_h2)
        ws_summary.write_number(5, 1, float(total_expenses), fmt_money)
        ws_summary.write(6, 0, "Денежный поток (доходы − расходы)", fmt_h2)
        ws_summary.write_number(6, 1, float(net), fmt_money if net >= 0 else fmt_money_red)
        ws_summary.write(7, 0, "Отложено в цели (net)", fmt_h2)
        ws_summary.write_number(
            7,
            1,
            float(allocations_month),
            fmt_money if allocations_month >= 0 else fmt_money_red,
        )
        ws_summary.write(8, 0, "Свободно (с учетом целей)", fmt_h2)
        ws_summary.write_number(8, 1, float(free_net), fmt_money if free_net >= 0 else fmt_money_red)

        ws_summary.write(10, 0, "Как читать этот отчет", fmt_h2)
        ws_summary.write(
            11,
            0,
            "• Сальдо дня (с учетом целей) = Доходы − Расходы − Отложено в цели (за день).\n"
            "• Накопленное сальдо = сумма «Сальдо дня» с начала месяца (стартуем с 0).\n"
            "  Это НЕ «баланс банковского счета», а динамика «свободно для трат» за месяц.\n"
            "• «Отложено в цели» — резервирование денег. Это не расход, но уменьшает «свободно».",
            fmt_note,
        )

        # ---- sheet: Кэшфлоу (daily) ----
        ws_cf = workbook.add_worksheet("Кэшфлоу")
        ws_cf.freeze_panes(1, 0)
        ws_cf.set_column("A:A", 14)
        ws_cf.set_column("B:F", 22)

        ws_cf.write(0, 0, "Дата", fmt_header)
        ws_cf.write(0, 1, "Доходы", fmt_header)
        ws_cf.write(0, 2, "Расходы", fmt_header)
        ws_cf.write(0, 3, "Отложено в цели (net)", fmt_header)
        ws_cf.write(0, 4, "Сальдо дня (с учетом целей)", fmt_header)
        ws_cf.write(0, 5, "Накопленное сальдо", fmt_header)

        # полный диапазон дней месяца
        day = start_date
        cumulative = Decimal("0")
        r = 1
        while day < end_date:
            inc = daily_income.get(day, Decimal("0"))
            exp = daily_expense.get(day, Decimal("0"))
            alloc = daily_allocations.get(day, Decimal("0"))
            day_net = inc - exp - alloc
            cumulative += day_net

            ws_cf.write_datetime(r, 0, datetime(day.year, day.month, day.day), fmt_date)
            ws_cf.write_number(r, 1, float(inc), fmt_money)
            ws_cf.write_number(r, 2, float(exp), fmt_money)
            ws_cf.write_number(r, 3, float(alloc), fmt_money if alloc >= 0 else fmt_money_red)
            ws_cf.write_number(r, 4, float(day_net), fmt_money if day_net >= 0 else fmt_money_red)
            ws_cf.write_number(r, 5, float(cumulative), fmt_money if cumulative >= 0 else fmt_money_red)

            r += 1
            day = date.fromordinal(day.toordinal() + 1)

        # График: кумулятивный баланс
        chart_balance = workbook.add_chart({"type": "line"})
        chart_balance.add_series(
            {
                "name": "Накопленное сальдо",
                "categories": ["Кэшфлоу", 1, 0, r - 1, 0],
                "values": ["Кэшфлоу", 1, 5, r - 1, 5],
            }
        )
        chart_balance.set_title({"name": "Свободно для трат (с учетом целей)"})
        chart_balance.set_y_axis({"name": "₽"})
        ws_summary.insert_chart("D4", chart_balance, {"x_scale": 1.2, "y_scale": 1.2})

        # ---- sheet: Цели ----
        ws_goals = workbook.add_worksheet("Цели")
        ws_goals.freeze_panes(1, 0)
        ws_goals.set_column("A:A", 28)
        ws_goals.set_column("B:B", 14)
        ws_goals.set_column("C:E", 16)
        ws_goals.set_column("F:F", 12)
        ws_goals.set_column("G:I", 18)

        ws_goals.write(0, 0, "Цель", fmt_header)
        ws_goals.write(0, 1, "Дедлайн", fmt_header)
        ws_goals.write(0, 2, "Цель (₽)", fmt_header)
        ws_goals.write(0, 3, "Накоплено (₽)", fmt_header)
        ws_goals.write(0, 4, "Осталось (₽)", fmt_header)
        ws_goals.write(0, 5, "Прогресс (%)", fmt_header)
        ws_goals.write(0, 6, "План/мес (₽)", fmt_header)
        ws_goals.write(0, 7, "Внесено в этом месяце (₽)", fmt_header)
        ws_goals.write(0, 8, "Осталось внести в этом месяце (₽)", fmt_header)

        # as_of: конец периода или сегодня (если это текущий месяц)
        as_of = min(timezone.localdate(), date.fromordinal(end_date.toordinal() - 1))
        for i, g in enumerate(goals, start=1):
            bal = goal_balances.get(int(g.id), Decimal("0"))
            if bal < 0:
                bal = Decimal("0")
            target_amt = Decimal(g.target_amount)
            remaining_amt = max(target_amt - bal, Decimal("0"))
            pct = Decimal("0")
            if target_amt > 0:
                pct = (bal / target_amt) * Decimal("100")

            plan_per_month = None
            if g.deadline and g.deadline >= as_of:
                months_remaining = (g.deadline.year - as_of.year) * 12 + (g.deadline.month - as_of.month) + 1
                if months_remaining > 0:
                    plan_per_month = (remaining_amt / Decimal(months_remaining)).quantize(Decimal("0.01"))

            deposited_month = deposits_by_goal.get(int(g.id), Decimal("0"))
            remaining_month = None
            if plan_per_month is not None:
                remaining_month = max(plan_per_month - deposited_month, Decimal("0"))

            ws_goals.write(i, 0, g.title)
            if g.deadline:
                ws_goals.write_datetime(i, 1, datetime(g.deadline.year, g.deadline.month, g.deadline.day), fmt_date)
            else:
                ws_goals.write(i, 1, "")
            ws_goals.write_number(i, 2, float(target_amt), fmt_money)
            ws_goals.write_number(i, 3, float(bal), fmt_money)
            ws_goals.write_number(i, 4, float(remaining_amt), fmt_money)
            ws_goals.write_number(i, 5, float(pct), workbook.add_format({"num_format": "0.0"}))
            if plan_per_month is not None:
                ws_goals.write_number(i, 6, float(plan_per_month), fmt_money)
            else:
                ws_goals.write(i, 6, "")
            ws_goals.write_number(i, 7, float(deposited_month), fmt_money)
            if remaining_month is not None:
                ws_goals.write_number(i, 8, float(remaining_month), fmt_money)
            else:
                ws_goals.write(i, 8, "")

        # ---- sheet: Операции целей ----
        ws_ops = workbook.add_worksheet("Операции целей")
        ws_ops.freeze_panes(1, 0)
        ws_ops.set_column("A:A", 12)
        ws_ops.set_column("B:B", 28)
        ws_ops.set_column("C:C", 16)
        ws_ops.set_column("D:D", 16)
        ws_ops.set_column("E:E", 50)

        ws_ops.write(0, 0, "Дата", fmt_header)
        ws_ops.write(0, 1, "Цель", fmt_header)
        ws_ops.write(0, 2, "Тип", fmt_header)
        ws_ops.write(0, 3, "Сумма (₽)", fmt_header)
        ws_ops.write(0, 4, "Комментарий", fmt_header)

        type_map = {
            GoalLedgerEntry.DEPOSIT: "Пополнение",
            GoalLedgerEntry.WITHDRAW: "Снятие",
            GoalLedgerEntry.SPEND: "Покупка",
        }
        for i, e in enumerate(goal_entries, start=1):
            d = e.occurred_at.date()
            ws_ops.write_datetime(i, 0, datetime(d.year, d.month, d.day), fmt_date)
            ws_ops.write(i, 1, e.goal.title if e.goal else "")
            ws_ops.write(i, 2, type_map.get(e.entry_type, e.entry_type))
            amt = Decimal(e.amount)
            ws_ops.write_number(i, 3, float(amt), fmt_money if amt >= 0 else fmt_money_red)
            ws_ops.write(i, 4, e.comment or "")

        # ---- sheet: Категории ----
        ws_cat = workbook.add_worksheet("Категории")
        ws_cat.freeze_panes(1, 0)
        ws_cat.set_column("A:A", 36)
        ws_cat.set_column("B:C", 18)
        ws_cat.set_column("D:D", 18)

        ws_cat.write(0, 0, "Категория", fmt_header)
        ws_cat.write(0, 1, "Доходы", fmt_header)
        ws_cat.write(0, 2, "Расходы", fmt_header)
        ws_cat.write(0, 3, "Сальдо", fmt_header)

        cat_names = sorted(set(category_income.keys()) | set(category_expense.keys()))
        for idx, name in enumerate(cat_names, start=1):
            ws_cat.write(idx, 0, name)
            inc_v = category_income.get(name, Decimal("0"))
            exp_v = category_expense.get(name, Decimal("0"))
            bal_v = inc_v - exp_v
            ws_cat.write_number(idx, 1, float(inc_v), fmt_money)
            ws_cat.write_number(idx, 2, float(exp_v), fmt_money)
            ws_cat.write_number(idx, 3, float(bal_v), fmt_money if bal_v >= 0 else fmt_money_red)

        # Итоговая строка
        total_row = len(cat_names) + 1
        ws_cat.write(total_row, 0, "ИТОГО", fmt_header_strong)
        ws_cat.write_number(total_row, 1, float(total_income), fmt_money_bold)
        ws_cat.write_number(total_row, 2, float(total_expenses), fmt_money_bold)
        ws_cat.write_number(
            total_row,
            3,
            float(net),
            fmt_money_bold if net >= 0 else fmt_money_bold_red,
        )

        # График: расходы по категориям (top 10)
        if cat_names:
            # Сделаем отдельный топ-10 по расходам
            top_exp = sorted(
                ((n, category_expense.get(n, Decimal("0"))) for n in cat_names),
                key=lambda x: x[1],
                reverse=True,
            )[:10]

            # топ-10 на сводке — ниже пояснений, чтобы не мешать
            ws_summary.write(13, 0, "Топ расходов по категориям", fmt_h2)
            ws_summary.write(14, 0, "Категория", fmt_header)
            ws_summary.write(14, 1, "Расходы", fmt_header)
            for i, (n, v) in enumerate(top_exp, start=15):
                ws_summary.write(i, 0, n)
                ws_summary.write_number(i, 1, float(v), fmt_money)

            last_row = 15 + len(top_exp) - 1
            chart_exp_cat = workbook.add_chart({"type": "column"})
            chart_exp_cat.add_series(
                {
                    "name": "Расходы",
                    "categories": ["Сводка", 15, 0, last_row, 0],
                    "values": ["Сводка", 15, 1, last_row, 1],
                }
            )
            chart_exp_cat.set_title({"name": "Расходы по категориям (топ-10)"})
            chart_exp_cat.set_y_axis({"name": "₽"})
            ws_summary.insert_chart("D20", chart_exp_cat, {"x_scale": 1.2, "y_scale": 1.2})

        # ---- sheet: Транзакции ----
        ws_tx = workbook.add_worksheet("Транзакции")
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

