from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from decimal import Decimal
from datetime import date, timedelta
from budgets.models import Budget
from categories.models import Category
from transactions.models import Transaction


class BudgetModelTestCase(TestCase):
    """
    Comprehensive unit tests for Budget model.
    
    Tests cover:
    - Model creation and validation
    - Complex business logic calculations
    - Property methods (spent_amount, remaining_amount, percentages)
    - Class methods (get_current_budget, create_monthly_budget)
    - Edge cases and error handling
    - Constraints and uniqueness
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
        
        # Create test categories (budgets only for expense categories)
        self.expense_category = Category.objects.create(
            name='Продукты',
            type=Category.EXPENSE,
            user=self.user,
        )
        self.income_category = Category.objects.create(
            name='Зарплата',
            type=Category.INCOME,
            user=self.user,
        )
        
    def test_budget_creation_monthly(self):
        """Test creating monthly budget with valid data."""
        start_date = date(2024, 12, 1)
        end_date = date(2024, 12, 31)
        
        budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('25000.00'),
            period_type=Budget.MONTHLY,
            start_date=start_date,
            end_date=end_date,
            user=self.user,
        )
        
        self.assertEqual(budget.category, self.expense_category)
        self.assertEqual(budget.amount, Decimal('25000.00'))
        self.assertEqual(budget.period_type, Budget.MONTHLY)
        self.assertEqual(budget.start_date, start_date)
        self.assertEqual(budget.end_date, end_date)
        self.assertEqual(budget.user, self.user)
        self.assertTrue(budget.is_active)
        self.assertIsNotNone(budget.created_at)
        
    def test_budget_str_representation(self):
        """Test string representation of budget."""
        budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('15000.00'),
            start_date=date(2024, 12, 1),
            end_date=date(2024, 12, 31),
            user=self.user,
        )
        
        expected = "Продукты: 15000.00 руб. (Месячный)"
        self.assertEqual(str(budget), expected)
        
    def test_budget_unique_constraint(self):
        """Test unique constraint for category, dates, user."""
        start_date = date(2024, 12, 1)
        end_date = date(2024, 12, 31)
        
        # Create first budget
        Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('20000.00'),
            start_date=start_date,
            end_date=end_date,
            user=self.user,
        )
        
        # Try to create duplicate - should raise IntegrityError
        with self.assertRaises(IntegrityError):
            Budget.objects.create(
                category=self.expense_category,
                amount=Decimal('30000.00'),
                start_date=start_date,
                end_date=end_date,
                user=self.user,
            )
            
    def test_spent_amount_no_transactions(self):
        """Test spent_amount when no transactions exist."""
        budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('10000.00'),
            start_date=date.today() - timedelta(days=5),
            end_date=date.today() + timedelta(days=25),
            user=self.user,
        )
        
        self.assertEqual(budget.spent_amount, Decimal('0.00'))
        
    def test_spent_amount_with_transactions(self):
        """Test spent_amount calculation with transactions."""
        budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('10000.00'),
            start_date=date.today() - timedelta(days=5),
            end_date=date.today() + timedelta(days=25),
            user=self.user,
        )
        
        # Create transactions within budget period
        Transaction.objects.create(
            amount=Decimal('2000.00'),
            category=self.expense_category,
            date=date.today() - timedelta(days=3),
            user=self.user,
        )
        
        Transaction.objects.create(
            amount=Decimal('1500.00'),
            category=self.expense_category,
            date=date.today(),
            user=self.user,
        )
        
        self.assertEqual(budget.spent_amount, Decimal('3500.00'))
        
    def test_spent_amount_transactions_outside_period(self):
        """Test spent_amount ignores transactions outside budget period."""
        budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('10000.00'),
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            user=self.user,
        )
        
        # Transaction before budget period (should be ignored)
        Transaction.objects.create(
            amount=Decimal('5000.00'),
            category=self.expense_category,
            date=date.today() - timedelta(days=1),
            user=self.user,
        )
        
        # Transaction within budget period (should be counted)
        Transaction.objects.create(
            amount=Decimal('2000.00'),
            category=self.expense_category,
            date=date.today() + timedelta(days=5),
            user=self.user,
        )
        
        # Transaction after budget period (should be ignored)
        Transaction.objects.create(
            amount=Decimal('3000.00'),
            category=self.expense_category,
            date=date.today() + timedelta(days=35),
            user=self.user,
        )
        
        self.assertEqual(budget.spent_amount, Decimal('2000.00'))
        
    def test_remaining_amount(self):
        """Test remaining_amount calculation."""
        budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('10000.00'),
            start_date=date.today() - timedelta(days=5),
            end_date=date.today() + timedelta(days=25),
            user=self.user,
        )
        
        # Create transaction
        Transaction.objects.create(
            amount=Decimal('3000.00'),
            category=self.expense_category,
            date=date.today(),
            user=self.user,
        )
        
        self.assertEqual(budget.remaining_amount, Decimal('7000.00'))
        
    def test_spent_percentage(self):
        """Test spent_percentage calculation."""
        budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('10000.00'),
            start_date=date.today() - timedelta(days=5),
            end_date=date.today() + timedelta(days=25),
            user=self.user,
        )
        
        # Create transaction for 25% of budget
        Transaction.objects.create(
            amount=Decimal('2500.00'),
            category=self.expense_category,
            date=date.today(),
            user=self.user,
        )
        
        self.assertEqual(budget.spent_percentage, 25.0)
        
    def test_spent_percentage_zero_budget(self):
        """Test spent_percentage when budget amount is zero."""
        budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('0.00'),
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            user=self.user,
        )
        
        self.assertEqual(budget.spent_percentage, 0)
        
    def test_remaining_percentage(self):
        """Test remaining_percentage calculation."""
        budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('10000.00'),
            start_date=date.today() - timedelta(days=5),
            end_date=date.today() + timedelta(days=25),
            user=self.user,
        )
        
        # Spend 30% of budget
        Transaction.objects.create(
            amount=Decimal('3000.00'),
            category=self.expense_category,
            date=date.today(),
            user=self.user,
        )
        
        self.assertEqual(budget.remaining_percentage, 70.0)
        
    def test_is_overspent_false(self):
        """Test is_overspent when within budget."""
        budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('10000.00'),
            start_date=date.today() - timedelta(days=5),
            end_date=date.today() + timedelta(days=25),
            user=self.user,
        )
        
        # Spend less than budget
        Transaction.objects.create(
            amount=Decimal('8000.00'),
            category=self.expense_category,
            date=date.today(),
            user=self.user,
        )
        
        self.assertFalse(budget.is_overspent)
        
    def test_is_overspent_true(self):
        """Test is_overspent when budget exceeded."""
        budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('10000.00'),
            start_date=date.today() - timedelta(days=5),
            end_date=date.today() + timedelta(days=25),
            user=self.user,
        )
        
        # Spend more than budget
        Transaction.objects.create(
            amount=Decimal('12000.00'),
            category=self.expense_category,
            date=date.today(),
            user=self.user,
        )
        
        self.assertTrue(budget.is_overspent)
        
    def test_days_remaining_active(self):
        """Test days_remaining for active budget."""
        budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('10000.00'),
            start_date=date.today() - timedelta(days=5),
            end_date=date.today() + timedelta(days=25),
            user=self.user,
        )
        
        self.assertEqual(budget.days_remaining, 26)  # 25 + 1 (today inclusive)
        
    def test_days_remaining_expired(self):
        """Test days_remaining for expired budget."""
        budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('10000.00'),
            start_date=date.today() - timedelta(days=35),
            end_date=date.today() - timedelta(days=5),
            user=self.user,
        )
        
        self.assertEqual(budget.days_remaining, 0)
        
    def test_days_total(self):
        """Test days_total calculation."""
        budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('10000.00'),
            start_date=date(2024, 12, 1),
            end_date=date(2024, 12, 31),
            user=self.user,
        )
        
        self.assertEqual(budget.days_total, 31)  # December has 31 days
        
    def test_daily_budget_remaining(self):
        """Test daily_budget_remaining calculation."""
        budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('10000.00'),
            start_date=date.today(),
            end_date=date.today() + timedelta(days=9),  # 10 days total
            user=self.user,
        )
        
        # Spend some money
        Transaction.objects.create(
            amount=Decimal('3000.00'),
            category=self.expense_category,
            date=date.today(),
            user=self.user,
        )
        
        # Remaining: 7000, Days remaining: 10, Daily: 700
        self.assertEqual(budget.daily_budget_remaining, Decimal('700.00'))
        
    def test_daily_budget_remaining_expired(self):
        """Test daily_budget_remaining for expired budget."""
        budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('10000.00'),
            start_date=date.today() - timedelta(days=35),
            end_date=date.today() - timedelta(days=5),
            user=self.user,
        )
        
        self.assertEqual(budget.daily_budget_remaining, Decimal('0.00'))
        
    def test_get_current_budget_none(self):
        """Test get_current_budget when no budget exists."""
        budget = Budget.get_current_budget(self.user, self.expense_category)
        self.assertIsNone(budget)
        
    def test_get_current_budget_exists(self):
        """Test get_current_budget when budget exists."""
        budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('15000.00'),
            start_date=date.today() - timedelta(days=5),
            end_date=date.today() + timedelta(days=25),
            user=self.user,
        )
        
        current = Budget.get_current_budget(self.user, self.expense_category)
        self.assertEqual(current, budget)
        
    def test_get_current_budget_inactive(self):
        """Test get_current_budget ignores inactive budgets."""
        Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('15000.00'),
            start_date=date.today() - timedelta(days=5),
            end_date=date.today() + timedelta(days=25),
            user=self.user,
            is_active=False,  # Inactive budget
        )
        
        current = Budget.get_current_budget(self.user, self.expense_category)
        self.assertIsNone(current)
        
    def test_create_monthly_budget(self):
        """Test create_monthly_budget class method."""
        budget = Budget.create_monthly_budget(
            user=self.user,
            category=self.expense_category,
            amount=Decimal('20000.00'),
            year=2024,
            month=12
        )
        
        self.assertEqual(budget.amount, Decimal('20000.00'))
        self.assertEqual(budget.period_type, Budget.MONTHLY)
        self.assertEqual(budget.start_date, date(2024, 12, 1))
        self.assertEqual(budget.end_date, date(2024, 12, 31))
        self.assertEqual(budget.user, self.user)
        self.assertEqual(budget.category, self.expense_category)
        
    def test_create_monthly_budget_december(self):
        """Test create_monthly_budget for December (year transition)."""
        budget = Budget.create_monthly_budget(
            user=self.user,
            category=self.expense_category,
            amount=Decimal('25000.00'),
            year=2024,
            month=12
        )
        
        self.assertEqual(budget.start_date, date(2024, 12, 1))
        self.assertEqual(budget.end_date, date(2024, 12, 31))
        
    def test_save_auto_end_date_monthly(self):
        """Test save method auto-sets end_date for monthly budget."""
        budget = Budget(
            category=self.expense_category,
            amount=Decimal('20000.00'),
            period_type=Budget.MONTHLY,
            start_date=date(2024, 6, 1),
            user=self.user,
        )
        budget.save()
        
        self.assertEqual(budget.end_date, date(2024, 6, 30))
        
    def test_budget_ordering(self):
        """Test budgets are ordered by start_date descending."""
        old_budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('10000.00'),
            start_date=date(2024, 10, 1),
            end_date=date(2024, 10, 31),
            user=self.user,
        )
        
        recent_budget = Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('15000.00'),
            start_date=date(2024, 12, 1),
            end_date=date(2024, 12, 31),
            user=self.user,
        )
        
        budgets = list(Budget.objects.filter(user=self.user))
        self.assertEqual(budgets[0], recent_budget)
        self.assertEqual(budgets[1], old_budget)
        
    def test_budget_different_users_isolation(self):
        """Test budgets are isolated between users."""
        Budget.objects.create(
            category=self.expense_category,
            amount=Decimal('10000.00'),
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            user=self.user,
        )
        
        # Create category and budget for other user
        other_category = Category.objects.create(
            name='Другая категория',
            type=Category.EXPENSE,
            user=self.other_user,
        )
        
        Budget.objects.create(
            category=other_category,
            amount=Decimal('20000.00'),
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            user=self.other_user,
        )
        
        user1_budgets = Budget.objects.filter(user=self.user)
        user2_budgets = Budget.objects.filter(user=self.other_user)
        
        self.assertEqual(user1_budgets.count(), 1)
        self.assertEqual(user2_budgets.count(), 1)
        self.assertEqual(user1_budgets.first().amount, Decimal('10000.00'))
        self.assertEqual(user2_budgets.first().amount, Decimal('20000.00'))
