"""Каталог валют. Курсы к рублю публикует ЦБ, отчёты считаются в базовой валюте."""

from dataclasses import dataclass

from django.core.exceptions import ObjectDoesNotExist

RUB = 'RUB'
VND = 'VND'
USD = 'USD'
EUR = 'EUR'
CNY = 'CNY'

DEFAULT_INPUT = (RUB, VND)


@dataclass(frozen=True)
class CurrencySpec:
    code: str
    name: str
    reports_in: str
    symbol: str
    aliases: tuple[str, ...]


# Коды, которые есть в ежедневном XML ЦБ. Рубль — базовая котировка, в XML его нет.
CATALOG: tuple[CurrencySpec, ...] = (
    CurrencySpec(RUB, 'Рубли', 'рублях', '₽', ('рублей', 'рубля', 'рубль', 'руб', 'rur', 'rub', '₽', 'р')),
    CurrencySpec(USD, 'Доллар', 'долларах', '$', ('долларов', 'доллара', 'доллар', 'usd', 'бакс', '$')),
    CurrencySpec(EUR, 'Евро', 'евро', '€', ('евро', 'eur', '€')),
    CurrencySpec(CNY, 'Юань', 'юанях', '¥', ('юаней', 'юаня', 'юань', 'cny', 'yuan')),
    CurrencySpec(VND, 'Донг', 'донгах', '₫', ('донгов', 'донга', 'донг', 'dong', 'vnd', '₫', 'đ', 'д')),
    CurrencySpec('GBP', 'Фунт', 'фунтах', '£', ('фунтов', 'фунта', 'фунт', 'gbp', '£')),
    CurrencySpec('JPY', 'Иена', 'иенах', '¥', ('иен', 'иены', 'иена', 'jpy', 'yen')),
    CurrencySpec('CHF', 'Франк', 'франках', '₣', ('франков', 'франка', 'франк', 'chf')),
    CurrencySpec('KZT', 'Тенге', 'тенге', '₸', ('тенге', 'kzt', '₸')),
    CurrencySpec('TRY', 'Лира', 'лирах', '₺', ('лир', 'лиры', 'лира', 'try', '₺')),
    CurrencySpec('THB', 'Бат', 'батах', '฿', ('батов', 'бата', 'бат', 'thb', '฿')),
    CurrencySpec('KRW', 'Вона', 'вонах', '₩', ('вон', 'воны', 'вона', 'krw', '₩')),
    CurrencySpec('INR', 'Рупия', 'рупиях', '₹', ('рупий', 'рупии', 'рупия', 'inr', '₹')),
    CurrencySpec('AUD', 'Доллар AU', 'австралийских долларах', 'A$', ('aud',)),
    CurrencySpec('CAD', 'Доллар CA', 'канадских долларах', 'C$', ('cad',)),
    CurrencySpec('SGD', 'Доллар SG', 'сингапурских долларах', 'S$', ('sgd',)),
    CurrencySpec('HKD', 'Доллар HK', 'гонконгских долларах', 'HK$', ('hkd',)),
    CurrencySpec('PLN', 'Злотый', 'злотых', 'zł', ('злотых', 'злотый', 'pln')),
    CurrencySpec('SEK', 'Крона SE', 'шведских кронах', 'kr', ('sek',)),
    CurrencySpec('NOK', 'Крона NO', 'норвежских кронах', 'kr', ('nok',)),
    CurrencySpec('CZK', 'Крона CZ', 'чешских кронах', 'Kč', ('czk',)),
    CurrencySpec('HUF', 'Форинт', 'форинтах', 'Ft', ('форинт', 'huf')),
    CurrencySpec('AED', 'Дирхам', 'дирхамах', 'Dh', ('дирхам', 'aed')),
    CurrencySpec('BYN', 'Рубль BY', 'белорусских рублях', 'Br', ('byn',)),
    CurrencySpec('UAH', 'Гривна', 'гривнах', '₴', ('гривен', 'гривны', 'гривна', 'uah', '₴')),
    CurrencySpec('UZS', 'Сум', 'сумах', 'сум', ('сумов', 'сум', 'uzs')),
    CurrencySpec('KGS', 'Сом', 'сомах', 'сом', ('сомов', 'сом', 'kgs')),
    CurrencySpec('GEL', 'Лари', 'лари', '₾', ('лари', 'gel', '₾')),
    CurrencySpec('AMD', 'Драм', 'драмах', '֏', ('драмов', 'драм', 'amd', '֏')),
    CurrencySpec('AZN', 'Манат', 'манатах', '₼', ('манат', 'azn', '₼')),
)

BY_CODE = {item.code: item for item in CATALOG}
CURRENCY_CHOICES = [(item.code, item.name) for item in CATALOG]

_ALIAS_TO_CODE: dict[str, str] = {}
for _spec in CATALOG:
    for _alias in _spec.aliases:
        _ALIAS_TO_CODE[_alias.casefold()] = _spec.code


def default_input_currencies() -> list[str]:
    return [RUB, VND]


def is_known(code: str | None) -> bool:
    return bool(code) and code in BY_CODE


def symbol_of(code: str | None) -> str:
    spec = BY_CODE.get(code or '')
    if spec is None:
        return code or ''
    twins = [item for item in CATALOG if item.symbol == spec.symbol]
    if len(twins) > 1:
        return spec.code
    return spec.symbol


def button_label(code: str) -> str:
    spec = BY_CODE[code]
    return f'{spec.symbol} {spec.name}'


def reports_phrase(code: str | None) -> str:
    spec = BY_CODE.get(code or '')
    if spec is None:
        return 'базовой валюте'
    return spec.reports_in


def clean_codes(codes) -> list[str]:
    seen: list[str] = []
    for code in codes or []:
        if code in BY_CODE and code not in seen:
            seen.append(code)
    return seen


def normalize_currency_token(token: str | None) -> str | None:
    """Слово, код или символ → код каталога. Неизвестное → None."""
    if not token:
        return None
    cleaned = token.strip().casefold().rstrip('.')
    return _ALIAS_TO_CODE.get(cleaned)


def base_currency_of(telegram_user) -> str:
    code = getattr(telegram_user, 'base_currency', None) or RUB
    return code if code in BY_CODE else RUB


def input_codes_of(telegram_user) -> list[str]:
    cleaned = clean_codes(getattr(telegram_user, 'input_currencies', None))
    if cleaned:
        return cleaned
    return [RUB, VND]


def ordered_codes(codes) -> list[str]:
    rank = {spec.code: index for index, spec in enumerate(CATALOG)}
    return sorted(clean_codes(codes), key=lambda code: rank[code])


def prefs_tuple(telegram_user) -> tuple[str, list[str]]:
    """Базовая валюта и список кнопок ввода."""
    return base_currency_of(telegram_user), input_codes_of(telegram_user)


def base_for_user(user) -> str:
    """Базовая валюта Django-пользователя. Без Telegram-профиля — рубли."""
    if user is None or not getattr(user, 'pk', None):
        return RUB
    try:
        telegram_user = user.telegramuser
    except ObjectDoesNotExist:
        return RUB
    return base_currency_of(telegram_user)
