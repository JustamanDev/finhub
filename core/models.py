from django.db import models

# Create your models here.


class TimestampedModel(models.Model):
    """Базовая модель с временными метками"""
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    
    class Meta:
        abstract = True
