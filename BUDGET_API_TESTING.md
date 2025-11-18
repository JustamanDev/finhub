# 💰 Budget API Testing Guide

## 📊 План-факт анализ готов!

### 🔑 API Token (тот же)
```
Token: f351e5df40d9bbe6c39ce6d7769060ba72e81b91
```

## 🆕 Новые Budget API Endpoints

### 💳 Основные операции с бюджетами

#### Получить все бюджеты
```bash
curl -H "Authorization: Token f351e5df40d9bbe6c39ce6d7769060ba72e81b91" \
     http://localhost:8000/api/v1/budgets/
```

#### Создать бюджет
```bash
curl -X POST \
     -H "Authorization: Token f351e5df40d9bbe6c39ce6d7769060ba72e81b91" \
     -H "Content-Type: application/json" \
     -d '{
       "category": 1,
       "amount": "25000.00",
       "period_type": "monthly",
       "start_date": "2025-08-01"
     }' \
     http://localhost:8000/api/v1/budgets/
```

#### Быстрое создание месячного бюджета
```bash
curl -X POST \
     -H "Authorization: Token f351e5df40d9bbe6c39ce6d7769060ba72e81b91" \
     -H "Content-Type: application/json" \
     -d '{
       "category": 2,
       "amount": "15000.00",
       "start_date": "2025-07-01"
     }' \
     http://localhost:8000/api/v1/budgets/quick_create/
```

### 📊 Аналитические endpoints

#### Текущие активные бюджеты
```bash
curl -H "Authorization: Token f351e5df40d9bbe6c39ce6d7769060ba72e81b91" \
     http://localhost:8000/api/v1/budgets/current/
```

#### Превышенные бюджеты
```bash
curl -H "Authorization: Token f351e5df40d9bbe6c39ce6d7769060ba72e81b91" \
     http://localhost:8000/api/v1/budgets/overspent/
```

#### Обзор всех категорий с бюджетами (⭐ ГЛАВНАЯ ФИЧА)
```bash
curl -H "Authorization: Token f351e5df40d9bbe6c39ce6d7769060ba72e81b91" \
     http://localhost:8000/api/v1/budgets/categories_overview/
```

#### Месячная сводка бюджетов
```bash
curl -H "Authorization: Token f351e5df40d9bbe6c39ce6d7769060ba72e81b91" \
     "http://localhost:8000/api/v1/budgets/monthly_summary/?year=2025&month=7"
```

### 🏷️ Обновленные Category endpoints

#### Категории теперь включают budget_info
```bash
curl -H "Authorization: Token f351e5df40d9bbe6c39ce6d7769060ba72e81b91" \
     http://localhost:8000/api/v1/categories/expense/
```

### 📈 Пример ответа categories_overview
```json
[
  {
    "category_id": 1,
    "category_name": "Продукты",
    "category_icon": "🛒",
    "category_color": "#FF6B6B",
    "has_budget": true,
    "budget_amount": "30000.00",
    "spent_amount": "12000.00",
    "remaining_amount": "18000.00",
    "spent_percentage": 40.0,
    "remaining_percentage": 60.0,
    "is_overspent": false,
    "days_remaining": 10,
    "daily_budget_remaining": "1800.00",
    "period_type": "Месячный"
  },
  {
    "category_id": 2,
    "category_name": "Транспорт",
    "category_icon": "🚗",
    "category_color": "#4ECDC4",
    "has_budget": false,
    "budget_amount": null,
    "spent_amount": null,
    // ... все остальные поля null
  }
]
```

## 🖥️ Обновленная Admin Panel

**URL:** http://localhost:8000/admin/budgets/budget/

### Новые возможности:
- ✅ **Цветовые индикаторы:** Зеленый/оранжевый/красный по % потрат
- ✅ **План-факт в реальном времени:** Потрачено, остаток, проценты
- ✅ **Статус превышения:** Визуальные индикаторы ❌/✅  
- ✅ **Дневной лимит:** Рекомендуемые траты на день
- ✅ **Только расходные категории:** Автофильтр

## 🎯 Готовые сценарии использования

### 1. Просмотр всех категорий с бюджетами (для Telegram бота)
```bash
curl -H "Authorization: Token f351e5df40d9bbe6c39ce6d7769060ba72e81b91" \
     http://localhost:8000/api/v1/budgets/categories_overview/
```

### 2. Проверка превышений
```bash
curl -H "Authorization: Token f351e5df40d9bbe6c39ce6d7769060ba72e81b91" \
     http://localhost:8000/api/v1/budgets/overspent/
```

### 3. Месячный отчет по бюджетам
```bash
curl -H "Authorization: Token f351e5df40d9bbe6c39ce6d7769060ba72e81b91" \
     "http://localhost:8000/api/v1/budgets/monthly_summary/?year=2025&month=7"
```

## 🚀 Что изменилось в проекте

### ✅ Новые модели:
- **Budget** - гибкая система бюджетов с автоматическими расчетами

### ✅ Расширенная функциональность:
- **Plan-Fact анализ** в реальном времени
- **Процентные индикаторы** потраченного бюджета  
- **Дневные лимиты** на оставшиеся дни
- **Визуальные статусы** превышения

### ✅ API endpoints:
- 12+ новых endpoints для управления бюджетами
- Интеграция с существующими Category API

**Теперь ваше приложение готово к продвинутому бюджетированию! 🎉** 