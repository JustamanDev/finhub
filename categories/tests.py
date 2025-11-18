from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from datetime import date, timedelta
from categories.models import Category
from budgets.models import Budget


class CategoryModelTestCase(TestCase):
    """
    Comprehensive unit tests for Category model.
    
    Tests cover:
    - Model creation and validation
    - Constraints and uniqueness 
    - String representation
    - Budget-related methods
    - Edge cases and error handling
    """
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123',
        )
        
    def test_category_creation_income(self):
        """Test creating income category with valid data."""
        category = Category.objects.create(
            name='Зарплата',
            type=Category.INCOME,
            color='#00B894',
            icon='💰',
            user=self.user,
        )
        
        self.assertEqual(category.name, 'Зарплата')
        self.assertEqual(category.type, Category.INCOME)
        self.assertEqual(category.color, '#00B894')
        self.assertEqual(category.icon, '💰')
        self.assertEqual(category.user, self.user)
        self.assertTrue(category.is_active)
        self.assertIsNotNone(category.created_at)
        self.assertIsNotNone(category.updated_at)
        
    def test_category_creation_expense(self):
        """Test creating expense category with valid data."""
        category = Category.objects.create(
            name='Продукты',
            type=Category.EXPENSE,
            color='#FF6B6B',
            icon='🛒',
            user=self.user,
        )
        
        self.assertEqual(category.type, Category.EXPENSE)
        self.assertTrue(category.is_active)
        
    def test_category_str_representation(self):
        """Test string representation of category."""
        category = Category.objects.create(
            name='Транспорт',
            type=Category.EXPENSE,
            user=self.user,
        )
        
        expected = "Транспорт (Расход)"
        self.assertEqual(str(category), expected)
        
    def test_category_unique_constraint(self):
        """Test unique constraint for user, name, type."""
        # Create first category
        Category.objects.create(
            name='Еда',
            type=Category.EXPENSE,
            user=self.user,
        )
        
        # Try to create duplicate - should raise IntegrityError
        with self.assertRaises(IntegrityError):
            Category.objects.create(
                name='Еда',
                type=Category.EXPENSE,
                user=self.user,
            )
            
    def test_category_different_users_same_name(self):
        """Test same category name for different users is allowed."""
        Category.objects.create(
            name='Общая категория',
            type=Category.EXPENSE,
            user=self.user,
        )
        
        # Should not raise error for different user
        category2 = Category.objects.create(
            name='Общая категория',
            type=Category.EXPENSE,
            user=self.other_user,
        )
        
        self.assertIsNotNone(category2.id)
        
    def test_category_same_name_different_type(self):
        """Test same name with different type is allowed."""
        Category.objects.create(
            name='Подарки',
            type=Category.INCOME,
            user=self.user,
        )
        
        # Should not raise error for different type
        category2 = Category.objects.create(
            name='Подарки',
            type=Category.EXPENSE,
            user=self.user,
        )
        
        self.assertIsNotNone(category2.id)
        
    def test_category_default_values(self):
        """Test default values are set correctly."""
        category = Category.objects.create(
            name='Тест',
            type=Category.INCOME,
            user=self.user,
        )
        
        self.assertEqual(category.color, '#007BFF')
        self.assertEqual(category.icon, '💰')
        self.assertTrue(category.is_active)
        
    def test_has_active_budget_false(self):
        """Test has_active_budget when no budget exists."""
        category = Category.objects.create(
            name='Без бюджета',
            type=Category.EXPENSE,
            user=self.user,
        )
        
        self.assertFalse(category.has_active_budget)
        
    def test_has_active_budget_true(self):
        """Test has_active_budget when active budget exists."""
        category = Category.objects.create(
            name='С бюджетом',
            type=Category.EXPENSE,
            user=self.user,
        )
        
        # Create active budget
        Budget.objects.create(
            category=category,
            amount=10000,
            start_date=date.today() - timedelta(days=5),
            end_date=date.today() + timedelta(days=25),
            user=self.user,
        )
        
        self.assertTrue(category.has_active_budget)
        
    def test_get_current_budget_none(self):
        """Test get_current_budget when no budget exists."""
        category = Category.objects.create(
            name='Без бюджета',
            type=Category.EXPENSE,
            user=self.user,
        )
        
        budget = category.get_current_budget()
        self.assertIsNone(budget)
        
    def test_get_current_budget_exists(self):
        """Test get_current_budget when budget exists."""
        category = Category.objects.create(
            name='С бюджетом',
            type=Category.EXPENSE,
            user=self.user,
        )
        
        budget = Budget.objects.create(
            category=category,
            amount=15000,
            start_date=date.today() - timedelta(days=3),
            end_date=date.today() + timedelta(days=27),
            user=self.user,
        )
        
        current_budget = category.get_current_budget()
        self.assertEqual(current_budget, budget)
        
    def test_get_budget_info_none(self):
        """Test get_budget_info when no budget exists."""
        category = Category.objects.create(
            name='Без бюджета',
            type=Category.EXPENSE,
            user=self.user,
        )
        
        budget_info = category.get_budget_info()
        self.assertIsNone(budget_info)
        
    def test_get_budget_info_with_budget(self):
        """Test get_budget_info returns correct data structure."""
        category = Category.objects.create(
            name='С бюджетом',
            type=Category.EXPENSE,
            user=self.user,
        )
        
        budget = Budget.objects.create(
            category=category,
            amount=20000,
            start_date=date.today().replace(day=1),
            end_date=date.today().replace(day=28),
            user=self.user,
        )
        
        budget_info = category.get_budget_info()
        
        self.assertIsNotNone(budget_info)
        self.assertIn('budget_amount', budget_info)
        self.assertIn('spent_amount', budget_info)
        self.assertIn('remaining_amount', budget_info)
        self.assertIn('spent_percentage', budget_info)
        self.assertIn('is_overspent', budget_info)
        self.assertIn('days_remaining', budget_info)
        self.assertEqual(budget_info['budget_amount'], budget.amount)
        
    def test_category_ordering(self):
        """Test categories are ordered by type, then name."""
        # Create categories in reverse order
        cat_z = Category.objects.create(
            name='Z категория',
            type=Category.EXPENSE,
            user=self.user,
        )
        cat_income = Category.objects.create(
            name='Доход А',
            type=Category.INCOME,
            user=self.user,
        )
        cat_a = Category.objects.create(
            name='A категория',
            type=Category.EXPENSE,
            user=self.user,
        )
        
        # Get ordered queryset
        categories = list(Category.objects.filter(user=self.user).order_by('type', 'name'))
        
        # Should be ordered: income first, then expenses alphabetically
        # Note: income type should come first alphabetically ('income' < 'expense')
        income_cats = [c for c in categories if c.type == Category.INCOME]
        expense_cats = [c for c in categories if c.type == Category.EXPENSE]
        
        self.assertEqual(len(income_cats), 1)
        self.assertEqual(len(expense_cats), 2)
        self.assertEqual(income_cats[0], cat_income)
        
        # Check expense categories are alphabetically ordered
        self.assertEqual(expense_cats[0].name, 'A категория')
        self.assertEqual(expense_cats[1].name, 'Z категория')
        
    def test_inactive_category(self):
        """Test inactive category behavior."""
        category = Category.objects.create(
            name='Неактивная',
            type=Category.EXPENSE,
            user=self.user,
            is_active=False,
        )
        
        self.assertFalse(category.is_active)
