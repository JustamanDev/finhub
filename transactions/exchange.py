"""Курсы валют к рублю: официальный XML ЦБ, не чаще одного раза в сутки."""

import logging
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from transactions.currencies import RUB, VND, is_known

logger = logging.getLogger('transactions.exchange')

CBR_DAILY_URL = 'https://www.cbr.ru/scripts/XML_daily.asp'
MOSCOW = ZoneInfo('Europe/Moscow')
MONEY = Decimal('0.01')
RATE_QUANT = Decimal('0.0000000001')


class ExchangeRateUnavailable(Exception):
    """Нет ни свежего, ни сохранённого курса."""

    def __init__(self, currency: str | None = None) -> None:
        if currency:
            message = (
                f'Не удалось получить курс {currency}. '
                'Попробуйте ещё раз чуть позже.'
            )
        else:
            message = (
                'Не удалось получить курс. '
                'Попробуйте ещё раз чуть позже.'
            )
        super().__init__(message)


@dataclass(frozen=True)
class CbrQuote:
    code: str
    rate_date: date
    nominal: int
    value: Decimal
    rate: Decimal


# Старое имя: тесты и get_vnd_rub_rate говорят про донг.
CbrVndQuote = CbrQuote


def moscow_today() -> date:
    """Сутки курса — по Москве, как у ЦБ. TIME_ZONE проекта — UTC."""
    return datetime.now(MOSCOW).date()


def _quote_from_valute(valute, rate_date: date) -> CbrQuote | None:
    code = (valute.findtext('CharCode') or '').strip().upper()
    if not code:
        return None
    nominal = int((valute.findtext('Nominal') or '1').strip())
    raw_value = (
        (valute.findtext('Value') or '')
        .replace('\xa0', '')
        .replace(' ', '')
        .replace(',', '.')
    )
    if not raw_value:
        return None
    value = Decimal(raw_value)
    if nominal <= 0 or value <= 0:
        return None
    rate = (value / Decimal(nominal)).quantize(RATE_QUANT)
    return CbrQuote(
        code=code,
        rate_date=rate_date,
        nominal=nominal,
        value=value,
        rate=rate,
    )


def parse_cbr_quotes(payload: str) -> dict[str, CbrQuote]:
    """Все котировки из ежедневного XML ЦБ: код → рубли за 1 единицу."""
    root = ET.fromstring(payload)
    rate_date = datetime.strptime(root.attrib['Date'], '%d.%m.%Y').date()
    quotes: dict[str, CbrQuote] = {}
    for valute in root.findall('Valute'):
        quote = _quote_from_valute(valute, rate_date)
        if quote is not None:
            quotes[quote.code] = quote
    if not quotes:
        raise ExchangeRateUnavailable()
    return quotes


def parse_cbr_vnd_xml(payload: str) -> CbrQuote:
    """Достаёт котировку VND из ежедневного XML ЦБ."""
    quotes = parse_cbr_quotes(payload)
    quote = quotes.get(VND)
    if quote is None:
        raise ExchangeRateUnavailable(VND)
    return quote


def fetch_cbr_vnd_quote(url: str = CBR_DAILY_URL, timeout: float = 15) -> CbrVndQuote:
    """Один HTTP-запрос к ЦБ. Кодировка ответа часто windows-1251."""
    request = urllib.request.Request(
        url,
        headers={'User-Agent': 'FinHub/1.0 (personal finance bot)'},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning('CBR request failed: %s', exc)
        raise ExchangeRateUnavailable() from exc

    if b'windows-1251' in raw[:200].lower():
        text = raw.decode('cp1251')
    else:
        text = raw.decode('utf-8')
    return parse_cbr_vnd_xml(text)


def fetch_cbr_quotes(url: str = CBR_DAILY_URL, timeout: float = 15) -> dict[str, CbrQuote]:
    """Один HTTP-запрос: все валюты дневной котировки ЦБ."""
    request = urllib.request.Request(
        url,
        headers={'User-Agent': 'FinHub/1.0 (personal finance bot)'},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning('CBR request failed: %s', exc)
        raise ExchangeRateUnavailable() from exc

    if b'windows-1251' in raw[:200].lower():
        text = raw.decode('cp1251')
    else:
        text = raw.decode('utf-8')
    return parse_cbr_quotes(text)


def get_vnd_rub_rate(*, force: bool = False):
    """
    Курс VND→RUB на сегодня по Москве.

    Повторный вызов в те же сутки берёт строку из базы.
    Если ЦБ недоступен — последний сохранённый курс.
    """
    from transactions.models import ExchangeRate

    today = moscow_today()
    if not force:
        cached = (
            ExchangeRate.objects.filter(
                base_currency=VND,
                quote_currency=RUB,
                fetched_on=today,
            )
            .order_by('-rate_date')
            .first()
        )
        if cached is not None:
            return cached

    try:
        quote = fetch_cbr_vnd_quote()
    except ExchangeRateUnavailable:
        fallback = (
            ExchangeRate.objects.filter(
                base_currency=VND,
                quote_currency=RUB,
            )
            .order_by('-rate_date', '-fetched_on')
            .first()
        )
        if fallback is not None:
            logger.warning(
                'Using stored VND rate from %s after CBR failure',
                fallback.rate_date,
            )
            return fallback
        raise

    rate, _created = ExchangeRate.objects.update_or_create(
        rate_date=quote.rate_date,
        base_currency=VND,
        quote_currency=RUB,
        defaults={
            'nominal': quote.nominal,
            'value': quote.value,
            'rate': quote.rate,
            'source': 'cbr',
            'fetched_on': today,
        },
    )
    return rate


def rub_amount(signed_original: Decimal, rate: Decimal) -> Decimal:
    """Перевод по курсу с сохранением знака. Курс — единицы отчёта за 1 единицу ввода."""
    return (signed_original * rate).quantize(MONEY, rounding=ROUND_HALF_UP)


def _store_cbr_quote(quote: CbrQuote, today: date):
    from transactions.models import ExchangeRate

    row, _created = ExchangeRate.objects.update_or_create(
        rate_date=quote.rate_date,
        base_currency=quote.code,
        quote_currency=RUB,
        defaults={
            'nominal': quote.nominal,
            'value': quote.value,
            'rate': quote.rate,
            'source': 'cbr',
            'fetched_on': today,
        },
    )
    return row


def get_rub_per_unit(code: str, *, force: bool = False):
    """
    Рублей за 1 единицу валюты на сегодня по Москве.

    Для рублей курс равен 1 и в ЦБ не ходит. Остальные валюты — из XML ЦБ.
    Повтор в те же сутки читает ExchangeRate. Если ЦБ молчит — последний сохранённый курс.
    """
    from transactions.models import ExchangeRate

    if code == RUB:
        return CbrQuote(
            code=RUB,
            rate_date=moscow_today(),
            nominal=1,
            value=Decimal('1'),
            rate=Decimal('1'),
        )
    if code == VND:
        return get_vnd_rub_rate(force=force)

    today = moscow_today()
    if not force:
        cached = (
            ExchangeRate.objects.filter(
                base_currency=code,
                quote_currency=RUB,
                fetched_on=today,
            )
            .order_by('-rate_date')
            .first()
        )
        if cached is not None:
            return cached

    try:
        quotes = fetch_cbr_quotes()
    except ExchangeRateUnavailable:
        fallback = (
            ExchangeRate.objects.filter(
                base_currency=code,
                quote_currency=RUB,
            )
            .order_by('-rate_date', '-fetched_on')
            .first()
        )
        if fallback is not None:
            logger.warning(
                'Using stored %s rate from %s after CBR failure',
                code,
                fallback.rate_date,
            )
            return fallback
        raise ExchangeRateUnavailable(code) from None

    saved = {
        quote.code: _store_cbr_quote(quote, today)
        for quote in quotes.values()
    }
    row = saved.get(code)
    if row is None:
        raise ExchangeRateUnavailable(code)
    return row


def convert_factor(source: str, target: str) -> Decimal:
    """Сколько единиц target за 1 единицу source. Через рубль ЦБ."""
    if source == target:
        return Decimal('1')
    source_quote = get_rub_per_unit(source)
    target_quote = get_rub_per_unit(target)
    return (Decimal(source_quote.rate) / Decimal(target_quote.rate)).quantize(RATE_QUANT)


def apply_entered_amount(
    transaction,
    signed_original: Decimal,
    currency: str,
    base: str | None = None,
) -> None:
    """
    Записывает исходную сумму и итог в базовой валюте.

    Курс фиксируется на операции. Если валюта ввода совпадает с базовой, ЦБ не нужен.
    """
    from transactions.currencies import base_for_user

    signed_original = Decimal(signed_original)
    if not is_known(currency):
        currency = RUB
    if base is None:
        base = base_for_user(getattr(transaction, 'user', None))
    if not is_known(base):
        base = RUB

    transaction.currency = currency
    transaction.original_amount = signed_original
    transaction.report_currency = base
    if currency == base:
        transaction.exchange_rate = Decimal('1')
        transaction.rate_date = None
        transaction.rate_nominal = 1
        transaction.amount = signed_original.quantize(MONEY, rounding=ROUND_HALF_UP)
        return

    entry = get_rub_per_unit(currency)
    anchor = get_rub_per_unit(base)
    rate = (Decimal(entry.rate) / Decimal(anchor.rate)).quantize(RATE_QUANT)
    transaction.exchange_rate = rate
    shown = entry if currency != RUB else anchor
    transaction.rate_date = shown.rate_date
    transaction.rate_nominal = shown.nominal if currency != RUB else 1
    transaction.amount = rub_amount(signed_original, rate)


def convert_magnitude(amount: Decimal, source: str, target: str) -> Decimal:
    """Положительная сумма из source в target. Для лимитов и целей."""
    factor = convert_factor(source, target)
    return rub_amount(abs(Decimal(amount)), factor)


def convert_magnitude_to_rub(amount: Decimal) -> Decimal:
    """Положительная сумма в донгах → рубли. Для лимитов и целей."""
    return convert_magnitude(amount, VND, RUB)


def rescale_user_books(user, old_base: str, new_base: str) -> Decimal:
    """
    Пересчитывает уже записанные суммы в новую базовую валюту по сегодняшнему курсу.

    Исходная сумма операции не меняется. Меняются итог, курс к базе, лимиты и цели.
    """
    from django.db import transaction as db_transaction

    from budgets.models import Budget
    from goals.models import Goal

    factor = convert_factor(old_base, new_base)
    if old_base == new_base:
        return factor

    def scale(value: Decimal) -> Decimal:
        return (Decimal(value) * factor).quantize(MONEY, rounding=ROUND_HALF_UP)

    with db_transaction.atomic():
        from transactions.models import Transaction

        for row in Transaction.objects.filter(user=user):
            row.amount = scale(row.amount)
            row.exchange_rate = (Decimal(row.exchange_rate) * factor).quantize(RATE_QUANT)
            row.report_currency = new_base
            row.save(update_fields=['amount', 'exchange_rate', 'report_currency', 'updated_at'])
        for budget in Budget.objects.filter(user=user):
            budget.amount = scale(budget.amount)
            budget.save(update_fields=['amount', 'updated_at'])
        for goal in Goal.objects.filter(user=user):
            if goal.target_amount is not None:
                goal.target_amount = scale(goal.target_amount)
                goal.save(update_fields=['target_amount', 'updated_at'])
            for entry in goal.entries.all():
                entry.amount = scale(entry.amount)
                entry.save(update_fields=['amount', 'updated_at'])
    return factor


def change_base_currency(telegram_user, new_base: str) -> None:
    """Меняет базовую валюту и пересчитывает уже записанные суммы."""
    from django.db import transaction as db_transaction

    from transactions.currencies import base_currency_of, is_known

    if not is_known(new_base):
        raise ExchangeRateUnavailable(new_base)
    old_base = base_currency_of(telegram_user)
    if old_base == new_base:
        return
    with db_transaction.atomic():
        rescale_user_books(telegram_user.user, old_base, new_base)
        telegram_user.base_currency = new_base
        telegram_user.save(update_fields=['base_currency', 'updated_at'])

