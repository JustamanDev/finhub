"""Финансист: режим вопроса, JSON-ответ, статья, долги и повторы в снимке."""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from categories.models import Category
from debts.models import Debt
from recurring.models import RecurringTemplate
from telegram_bot.handlers.base import BaseHandler
from telegram_bot.keyboards.actions import ActionKeyboard
from telegram_bot.models import TelegramUser
from telegram_bot.services.advisor_article import render_advisor_article
from telegram_bot.services.advisor_mode import (
    ADVISOR_ARMED_KEY,
    arm_advisor_mode,
    clear_advisor_mode,
    is_money_entry,
    take_advisor_mode,
)
from telegram_bot.services.voice_advisor_executor import (
    AdvisorAnswer,
    parse_advisor_payload,
)


class AdvisorModelSplitTests(TestCase):
    def test_button_uses_reasoning_model_and_facts_stay_fast(self):
        from unittest.mock import patch

        from telegram_bot.services.voice_advisor_executor import (
            completion_kwargs,
            resolve_advisor_call,
        )

        with (
            patch(
                'telegram_bot.services.voice_advisor_executor.advisor_llm_model',
                return_value='gpt-6-luna',
            ),
            patch(
                'telegram_bot.services.voice_advisor_executor.advisor_reasoning_effort',
                return_value='low',
            ),
            patch(
                'telegram_bot.services.voice_advisor_executor.voice_llm_model',
                return_value='gpt-4o-mini',
            ),
        ):
            model, effort = resolve_advisor_call('advice')
            advice = completion_kwargs(model=model, effort=effort, use_json=True)
            self.assertEqual(model, 'gpt-6-luna')
            self.assertEqual(advice['reasoning_effort'], 'low')
            self.assertNotIn('temperature', advice)

            fact_model, fact_effort = resolve_advisor_call('fact')
            fact = completion_kwargs(
                model=fact_model,
                effort=fact_effort,
                use_json=True,
            )
            self.assertEqual(fact_model, 'gpt-4o-mini')
            self.assertNotIn('reasoning_effort', fact)
            self.assertEqual(fact['temperature'], 0.2)


class AdvisorModeTests(TestCase):
    def test_menu_has_financier_button(self):
        markup = ActionKeyboard.get_main_menu_keyboard()
        buttons = [
            button
            for row in markup.inline_keyboard
            for button in row
        ]
        financier = [button for button in buttons if button.callback_data == 'ask_advisor']
        self.assertEqual(len(financier), 1)
        self.assertEqual(financier[0].text, 'Финансист')
        self.assertEqual(len(markup.inline_keyboard[-1]), 1)

    def test_arm_is_one_shot_and_expires(self):
        context = type('Ctx', (), {'user_data': {}})()
        arm_advisor_mode(context, now=1_000)
        self.assertEqual(take_advisor_mode(context, now=1_100), 'active')
        self.assertEqual(take_advisor_mode(context, now=1_100), 'off')

        arm_advisor_mode(context, now=1_000)
        self.assertEqual(take_advisor_mode(context, now=2_000), 'expired')
        self.assertNotIn(ADVISOR_ARMED_KEY, context.user_data)

    def test_clear_and_money_entry(self):
        context = type('Ctx', (), {'user_data': {ADVISOR_ARMED_KEY: 10}})()
        clear_advisor_mode(context)
        self.assertEqual(take_advisor_mode(context), 'off')
        self.assertTrue(is_money_entry('500 кофе'))
        self.assertFalse(is_money_entry('как оптимизировать расходы'))

    def test_start_clears_armed_mode(self):
        from asgiref.sync import async_to_sync

        user = User.objects.create_user(username='advisor-mode', password='x')
        telegram_user = TelegramUser.objects.create(
            user=user,
            telegram_id=424242,
            username='advisor-mode',
        )
        context = type('Ctx', (), {'user_data': {ADVISOR_ARMED_KEY: 10, 'voice_dialog': {}}})()
        async_to_sync(BaseHandler().clear_transient_input)(telegram_user, context)
        self.assertNotIn(ADVISOR_ARMED_KEY, context.user_data)
        self.assertNotIn('voice_dialog', context.user_data)


class AdvisorPayloadTests(TestCase):
    def test_fact_drops_actions_and_extra_tables(self):
        answer = parse_advisor_payload(
            '{"answer_kind":"fact","title":"Ноябрь","lead":"Расход 1500.",'
            '"actions":["Поставьте лимит"],"tables":["movement","goals","budgets"]}'
        )
        self.assertEqual(answer.actions, [])
        self.assertEqual(answer.tables, ['movement'])

    def test_clarify_has_no_tables(self):
        answer = parse_advisor_payload(
            '{"answer_kind":"clarify","title":"Уточнение","lead":"Какая цель?",'
            '"clarify":"Какая цель: отпуск или ремонт?","tables":["goals"],'
            '"actions":["Отложите 1000"]}'
        )
        self.assertEqual(answer.lead, 'Какая цель: отпуск или ремонт?')
        self.assertEqual(answer.tables, [])
        self.assertEqual(answer.actions, [])

    def test_advice_keeps_two_steps(self):
        answer = parse_advisor_payload(
            '{"answer_kind":"advice","title":"Ноябрь","lead":"Месяц в минусе.",'
            '"actions":["Сократите продукты","Поправьте лимит","Третий"],'
            '"tables":["movement","categories"]}'
        )
        self.assertEqual(len(answer.actions), 2)
        self.assertEqual(answer.tables, ['movement', 'categories'])

    def test_broken_json_is_rejected(self):
        with self.assertRaises(Exception):
            parse_advisor_payload('просто текст, не json')


class AdvisorArticleTests(TestCase):
    def test_tables_use_snapshot_and_skip_empty_debts(self):
        answer = AdvisorAnswer(
            answer_kind='advice',
            title='Ноябрь',
            lead='Расход выше дохода.',
            actions=['Поправьте лимит на продукты'],
            tables=['movement', 'debts', 'categories'],
        )
        snapshot = {
            'report_currency': 'RUB',
            'period': {'name': 'ноябрь 2026'},
            'month_totals': {
                'income': 0,
                'expenses': 1500,
                'balance': -1500,
                'free_funds': -1500,
            },
            'top_expense_categories': [
                {'name': 'Продукты', 'spent': 1500},
            ],
            'debts': [],
        }
        html, legacy = render_advisor_article(answer, snapshot)
        self.assertIn('<h1>Ноябрь</h1>', html)
        self.assertIn('1 500', html)
        self.assertIn('Продукты', html)
        self.assertNotIn('Долги', html)
        self.assertIn('Что сделать', html)
        self.assertIn('Поправьте лимит на продукты', legacy)
        self.assertIn('<table', html)


class AdvisorObligationsSnapshotTests(TestCase):
    def test_open_debts_and_active_repeats_only(self):
        from asgiref.sync import async_to_sync
        from telegram_bot.services.advisor_snapshot_service import (
            AdvisorSnapshotService,
        )

        user = User.objects.create_user(username='advisor-debts', password='x')
        food = Category.objects.create(
            user=user,
            name='Еда',
            type=Category.EXPENSE,
            icon='🥕',
        )
        Debt.objects.create(
            user=user,
            counterparty='Иван',
            direction=Debt.OWE,
            principal=Decimal('4000'),
            currency='RUB',
        )
        Debt.objects.create(
            user=user,
            counterparty='Архив',
            direction=Debt.OWED,
            principal=Decimal('900'),
            currency='RUB',
            is_open=False,
        )
        RecurringTemplate.objects.create(
            user=user,
            name='Аренда',
            category=food,
            periodicity=RecurringTemplate.MONTHLY,
            amount_kind=RecurringTemplate.EXACT,
            amount=Decimal('12000'),
            next_due=date(2026, 11, 20),
        )
        RecurringTemplate.objects.create(
            user=user,
            name='Старый',
            category=food,
            periodicity=RecurringTemplate.WEEKLY,
            amount_kind=RecurringTemplate.OPEN,
            next_due=date(2026, 11, 1),
            is_active=False,
        )
        snapshot = async_to_sync(AdvisorSnapshotService(user).build)()
        self.assertEqual(
            [(row['counterparty'], row['remaining']) for row in snapshot['debts']],
            [('Иван', 4000.0)],
        )
        self.assertNotIn('rate', snapshot['debts'][0])
        self.assertEqual(
            [row['name'] for row in snapshot['recurring']],
            ['Аренда'],
        )
        self.assertEqual(snapshot['recurring'][0]['amount'], 12000.0)
