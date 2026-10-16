from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('goals', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='goal',
            name='kind',
            field=models.CharField(
                choices=[('savings', 'Цель'), ('envelope', 'Конверт')],
                default='savings',
                max_length=16,
                verbose_name='Тип',
            ),
        ),
        migrations.AlterField(
            model_name='goal',
            name='status',
            field=models.CharField(
                choices=[
                    ('active', 'Активна'),
                    ('paused', 'Пауза'),
                    ('completed', 'Завершена'),
                    ('cancelled', 'Отменена'),
                    ('archived', 'В архиве'),
                ],
                default='active',
                max_length=16,
                verbose_name='Статус',
            ),
        ),
        migrations.AlterField(
            model_name='goal',
            name='target_amount',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=14,
                null=True,
                verbose_name='Целевая сумма',
            ),
        ),
        migrations.AlterField(
            model_name='goal',
            name='title',
            field=models.CharField(max_length=120, verbose_name='Название'),
        ),
        migrations.AlterModelOptions(
            name='goal',
            options={
                'ordering': ['-created_at'],
                'verbose_name': 'Цель или конверт',
                'verbose_name_plural': 'Цели и конверты',
            },
        ),
    ]
