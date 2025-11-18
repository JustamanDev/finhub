from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from categories.models import Category


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
            
        # Категории расходов
        expense_categories = [
            {'name': 'Продукты', 'icon': '🛒', 'color': '#FF6B6B'},
            {'name': 'Транспорт', 'icon': '🚗', 'color': '#4ECDC4'},
            {'name': 'Развлечения', 'icon': '🎬', 'color': '#45B7D1'},
            {'name': 'Коммунальные', 'icon': '🏠', 'color': '#96CEB4'},
            {'name': 'Здоровье', 'icon': '💊', 'color': '#FFEAA7'},
            {'name': 'Одежда', 'icon': '👕', 'color': '#DDA0DD'},
            {'name': 'Кафе/Рестораны', 'icon': '🍽️', 'color': '#FD79A8'},
            {'name': 'Покупки', 'icon': '🛍️', 'color': '#FDCB6E'},
            {'name': 'Образование', 'icon': '📚', 'color': '#6C5CE7'},
            {'name': 'Прочее', 'icon': '📝', 'color': '#A0A0A0'},
        ]
        
        # Категории доходов  
        income_categories = [
            {'name': 'Зарплата', 'icon': '💰', 'color': '#00B894'},
            {'name': 'Фриланс', 'icon': '💻', 'color': '#0984E3'},
            {'name': 'Инвестиции', 'icon': '📈', 'color': '#6C5CE7'},
            {'name': 'Подарки', 'icon': '🎁', 'color': '#E17055'},
            {'name': 'Прочее', 'icon': '💵', 'color': '#00CEC9'},
        ]
        
        created_count = 0
        
        # Создание категорий расходов
        for cat_data in expense_categories:
            category, created = Category.objects.get_or_create(
                user=user,
                name=cat_data['name'],
                type=Category.EXPENSE,
                defaults={
                    'icon': cat_data['icon'],
                    'color': cat_data['color']
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f"✅ Создана категория расходов: {category.name}")
            
        # Создание категорий доходов
        for cat_data in income_categories:
            category, created = Category.objects.get_or_create(
                user=user,
                name=cat_data['name'], 
                type=Category.INCOME,
                defaults={
                    'icon': cat_data['icon'],
                    'color': cat_data['color']
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f"✅ Создана категория доходов: {category.name}")
            
        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎉 Создано {created_count} новых категорий для пользователя {username}'
            )
        ) 