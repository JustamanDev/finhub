from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('transactions', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Goal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('title', models.CharField(max_length=120, verbose_name='Название цели')),
                ('target_amount', models.DecimalField(decimal_places=2, max_digits=14, verbose_name='Целевая сумма')),
                ('deadline', models.DateField(blank=True, null=True, verbose_name='Дедлайн')),
                ('status', models.CharField(choices=[('active', 'Активна'), ('paused', 'Пауза'), ('completed', 'Завершена'), ('cancelled', 'Отменена')], default='active', max_length=16, verbose_name='Статус')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='goals', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Цель',
                'verbose_name_plural': 'Цели',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='GoalLedgerEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('occurred_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Дата операции')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14, verbose_name='Сумма')),
                ('entry_type', models.CharField(choices=[('deposit', 'Пополнение'), ('withdraw', 'Снятие'), ('spend', 'Покупка/трата из цели')], max_length=16, verbose_name='Тип')),
                ('comment', models.TextField(blank=True, verbose_name='Комментарий')),
                ('goal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='entries', to='goals.goal', verbose_name='Цель')),
                ('linked_transaction', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='goal_entries', to='transactions.transaction', verbose_name='Связанная транзакция')),
            ],
            options={
                'verbose_name': 'Операция по цели',
                'verbose_name_plural': 'Операции по целям',
                'ordering': ['-occurred_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='goalledgerentry',
            index=models.Index(fields=['goal', 'occurred_at'], name='goals_goall_goal_id_b2f0f5_idx'),
        ),
        migrations.AddConstraint(
            model_name='goal',
            constraint=models.UniqueConstraint(fields=('user', 'title'), name='unique_goal_title_per_user'),
        ),
    ]

