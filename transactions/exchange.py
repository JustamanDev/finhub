"""Курс донга к рублю: официальный XML ЦБ, не чаще одного раза в сутки."""

import logging
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from transactions.currencies import RUB, VND

logger = logging.getLogger('transactions.exchange')

CBR_DAILY_URL = 'https://www.cbr.ru/scripts/XML_daily.asp'
MOSCOW = ZoneInfo('Europe/Moscow')
MONEY = Decimal('0.01')
RATE_QUANT = Decimal('0.0000000001')


class ExchangeRateUnavailable(Exception):
    """Нет ни свежего, ни сохранённого курса."""

    def __init__(self) -> None:
        super().__init__(
            'Не удалось получить курс донга к рублю. '
            'Попробуйте ещё раз чуть позже.',
        )


@dataclass(frozen=True)
class CbrVndQuote:
    rate_date: date
    nominal: int
    value: Decimal
    rate: Decimal


def moscow_today() -> date:
    """Сутки курса — по Москве, как у ЦБ. TIME_ZONE проекта — UTC."""
    return datetime.now(MOSCOW).date()


def parse_cbr_vnd_xml(payload: str) -> CbrVndQuote:
    """Достаёт котировку VND из ежедневного XML ЦБ."""
    root = ET.fromstring(payload)
    rate_date = datetime.strptime(root.attrib['Date'], '%d.%m.%Y').date()
    for valute in root.findall('Valute'):
        if (valute.findtext('CharCode') or '').strip().upper() != 'VND':
            continue
        nominal = int((valute.findtext('Nominal') or '1').strip())
        raw_value = (
            (valute.findtext('Value') or '')
            .replace('\xa0', '')
            .replace(' ', '')
            .replace(',', '.')
        )
        value = Decimal(raw_value)
        if nominal <= 0 or value <= 0:
            break
        rate = (value / Decimal(nominal)).quantize(RATE_QUANT)
        return CbrVndQuote(
            rate_date=rate_date,
            nominal=nominal,
            value=value,
            rate=rate,
        )
    raise ExchangeRateUnavailable()


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
    """Перевод в рубли с сохранением знака."""
    return (signed_original * rate).quantize(MONEY, rounding=ROUND_HALF_UP)


def apply_entered_amount(transaction, signed_original: Decimal, currency: str) -> None:
    """
    Записывает исходную сумму и рублёвый итог.

    Для рублей курс не запрашивается. Для донгов курс фиксируется на операции.
    """
    signed_original = Decimal(signed_original)
    if currency == VND:
        quote = get_vnd_rub_rate()
        transaction.currency = VND
        transaction.original_amount = signed_original
        transaction.exchange_rate = quote.rate
        transaction.rate_date = quote.rate_date
        transaction.rate_nominal = quote.nominal
        transaction.amount = rub_amount(signed_original, quote.rate)
        return

    transaction.currency = RUB
    transaction.original_amount = signed_original
    transaction.exchange_rate = Decimal('1')
    transaction.rate_date = None
    transaction.rate_nominal = 1
    transaction.amount = signed_original.quantize(MONEY, rounding=ROUND_HALF_UP)


def convert_magnitude_to_rub(amount: Decimal) -> Decimal:
    """Положительная сумма в донгах → рубли. Для лимитов и целей."""
    quote = get_vnd_rub_rate()
    return rub_amount(abs(Decimal(amount)), quote.rate)

