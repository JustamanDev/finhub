"""Ручной запрос курса VND→RUB. Обычно бот берёт его сам, раз в сутки."""

from django.core.management.base import BaseCommand

from transactions.exchange import get_vnd_rub_rate


class Command(BaseCommand):
    help = 'Забирает курс донга к рублю у ЦБ РФ и сохраняет его на сегодня.'

    def handle(self, *args, **options):
        rate = get_vnd_rub_rate(force=True)
        self.stdout.write(
            f'{rate.rate_date}: {rate.value} RUB за {rate.nominal} VND '
            f'({rate.rate} RUB за 1 VND)',
        )
