from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from categories.default_categories import ensure_default_categories


class Command(BaseCommand):
    help = 'Создать категории по умолчанию для пользователя'
    
    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Имя пользователя')
        
    def handle(self, *args, **options):
        username = options['username']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Пользователь {username} не найден'))
            return

        created_count = ensure_default_categories(user)

        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎉 Создано {created_count} новых категорий для пользователя {username}'
            )
        ) 