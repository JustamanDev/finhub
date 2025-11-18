from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from decimal import Decimal
from datetime import date, timedelta
from transactions.models import Transaction
from categories.models import Category


class TransactionModelTestCase(TestCase):
    """
    Comprehensive unit tests for Transaction model.
    
    Tests cover:
    - Model creation and validation
    - Property methods
    - String representation
    - Ordering
    - Edge cases with decimal amounts
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
        
        # Create test categories
        self.income_category = Category.objects.create(
            name='Зарплата',
            type=Category.INCOME,
            user=self.user,
        )
        self.expense_category = Category.objects.create(
            name='Продукты',
            type=Category.EXPENSE,
            user=self.user,
        )
        
    def test_transaction_creation_income(self):
        """Test creating income transaction with valid data."""
        transaction = Transaction.objects.create(
            amount=Decimal('50000.00'),
            description='Зарплата за декабрь',
            category=self.income_category,
            date=date.today(),
            user=self.user,
        )
        
        self.assertEqual(transaction.amount, Decimal('50000.00'))
        self.assertEqual(transaction.description, 'Зарплата за декабрь')
        self.assertEqual(transaction.category, self.income_category)
        self.assertEqual(transaction.date, date.today())
        self.assertEqual(transaction.user, self.user)
        self.assertIsNotNone(transaction.created_at)
        self.assertIsNotNone(transaction.updated_at)
        
    def test_transaction_creation_expense(self):
        """Test creating expense transaction with valid data."""
        transaction = Transaction.objects.create(
            amount=Decimal('1500.50'),
            description='Покупка продуктов',
            category=self.expense_category,
            date=date.today(),
            user=self.user,
        )
        
        self.assertEqual(transaction.amount, Decimal('1500.50'))
        self.assertEqual(transaction.category, self.expense_category)
        
    def test_transaction_str_representation(self):
        """Test string representation of transaction."""
        transaction = Transaction.objects.create(
            amount=Decimal('2500.75'),
            description='Тестовая транзакция',
            category=self.expense_category,
            date=date(2024, 12, 28),
            user=self.user,
        )
        
        expected = "2500.75 руб. - Продукты (2024-12-28)"
        self.assertEqual(str(transaction), expected)
        
    def test_transaction_empty_description(self):
        """Test transaction can be created with empty description."""
        transaction = Transaction.objects.create(
            amount=Decimal('100.00'),
            description='',
            category=self.income_category,
            date=date.today(),
            user=self.user,
        )
        
        self.assertEqual(transaction.description, '')
        
    def test_is_income_property_true(self):
        """Test is_income property returns True for income transaction."""
        transaction = Transaction.objects.create(
            amount=Decimal('5000.00'),
            category=self.income_category,
            date=date.today(),
            user=self.user,
        )
        
        self.assertTrue(transaction.is_income)
        self.assertFalse(transaction.is_expense)
        
    def test_is_expense_property_true(self):
        """Test is_expense property returns True for expense transaction."""
        transaction = Transaction.objects.create(
            amount=Decimal('1000.00'),
            category=self.expense_category,
            date=date.today(),
            user=self.user,
        )
        
        self.assertTrue(transaction.is_expense)
        self.assertFalse(transaction.is_income)
        
    def test_transaction_ordering(self):
        """Test transactions are ordered by date desc, then created_at desc."""
        # Create transactions in different order
        old_transaction = Transaction.objects.create(
            amount=Decimal('100.00'),
            category=self.expense_category,
            date=date.today() - timedelta(days=5),
            user=self.user,
        )
        
        recent_transaction = Transaction.objects.create(
            amount=Decimal('200.00'),
            category=self.income_category,
            date=date.today(),
            user=self.user,
        )
        
        middle_transaction = Transaction.objects.create(
            amount=Decimal('150.00'),
            category=self.expense_category,
            date=date.today() - timedelta(days=2),
            user=self.user,
        )
        
        # Get ordered queryset
        transactions = list(Transaction.objects.filter(user=self.user))
        
        # Should be ordered by date desc, then created_at desc
        self.assertEqual(transactions[0], recent_transaction)
        self.assertEqual(transactions[1], middle_transaction)
        self.assertEqual(transactions[2], old_transaction)
        
    def test_transaction_decimal_precision(self):
        """Test transaction handles decimal amounts correctly."""
        transaction = Transaction.objects.create(
            amount=Decimal('123.45'),
            category=self.expense_category,
            date=date.today(),
            user=self.user,
        )
        
        # Verify precision is maintained
        self.assertEqual(transaction.amount, Decimal('123.45'))
        self.assertEqual(str(transaction.amount), '123.45')
        
    def test_transaction_large_amount(self):
        """Test transaction can handle large amounts."""
        large_amount = Decimal('9999999999.99')  # Max for 12 digits, 2 decimal places
        
        transaction = Transaction.objects.create(
            amount=large_amount,
            category=self.income_category,
            date=date.today(),
            user=self.user,
        )
        
        self.assertEqual(transaction.amount, large_amount)
        
    def test_transaction_small_amount(self):
        """Test transaction can handle small amounts."""
        small_amount = Decimal('0.01')
        
        transaction = Transaction.objects.create(
            amount=small_amount,
            category=self.expense_category,
            date=date.today(),
            user=self.user,
        )
        
        self.assertEqual(transaction.amount, small_amount)
        
    def test_transaction_zero_amount(self):
        """Test transaction can be created with zero amount."""
        transaction = Transaction.objects.create(
            amount=Decimal('0.00'),
            category=self.expense_category,
            date=date.today(),
            user=self.user,
        )
        
        self.assertEqual(transaction.amount, Decimal('0.00'))
        
    def test_transaction_future_date(self):
        """Test transaction can be created with future date."""
        future_date = date.today() + timedelta(days=30)
        
        transaction = Transaction.objects.create(
            amount=Decimal('500.00'),
            category=self.income_category,
            date=future_date,
            user=self.user,
        )
        
        self.assertEqual(transaction.date, future_date)
        
    def test_transaction_old_date(self):
        """Test transaction can be created with old date."""
        old_date = date(2020, 1, 1)
        
        transaction = Transaction.objects.create(
            amount=Decimal('300.00'),
            category=self.expense_category,
            date=old_date,
            user=self.user,
        )
        
        self.assertEqual(transaction.date, old_date)
        
    def test_transaction_different_users_isolation(self):
        """Test transactions are isolated between users."""
        # Create transaction for first user
        Transaction.objects.create(
            amount=Decimal('1000.00'),
            category=self.expense_category,
            date=date.today(),
            user=self.user,
        )
        
        # Create category and transaction for second user
        other_category = Category.objects.create(
            name='Другая категория',
            type=Category.EXPENSE,
            user=self.other_user,
        )
        
        Transaction.objects.create(
            amount=Decimal('2000.00'),
            category=other_category,
            date=date.today(),
            user=self.other_user,
        )
        
        # Verify isolation
        user1_transactions = Transaction.objects.filter(user=self.user)
        user2_transactions = Transaction.objects.filter(user=self.other_user)
        
        self.assertEqual(user1_transactions.count(), 1)
        self.assertEqual(user2_transactions.count(), 1)
        self.assertEqual(user1_transactions.first().amount, Decimal('1000.00'))
        self.assertEqual(user2_transactions.first().amount, Decimal('2000.00'))
        
    def test_transaction_category_relationship(self):
        """Test transaction properly relates to category."""
        transaction = Transaction.objects.create(
            amount=Decimal('750.00'),
            category=self.income_category,
            date=date.today(),
            user=self.user,
        )
        
        # Test forward relationship
        self.assertEqual(transaction.category, self.income_category)
        self.assertEqual(transaction.category.name, 'Зарплата')
        self.assertEqual(transaction.category.type, Category.INCOME)
        
        # Test reverse relationship
        category_transactions = self.income_category.transactions.all()
        self.assertIn(transaction, category_transactions)
        
    def test_transaction_long_description(self):
        """Test transaction with very long description."""
        long_description = 'A' * 1000  # Very long description
        
        transaction = Transaction.objects.create(
            amount=Decimal('100.00'),
            description=long_description,
            category=self.expense_category,
            date=date.today(),
            user=self.user,
        )
        
        self.assertEqual(transaction.description, long_description)
