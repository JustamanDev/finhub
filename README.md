# FinHub

Django проект для финансового хаба.

## Установка

1. Клонировать репозиторий
2. Установить зависимости: `poetry install`
3. Активировать окружение: `poetry shell`
4. Запустить сервер: `python manage.py runserver`

## Настройка

Создайте файл `.env` с необходимыми переменными окружения:

```env
SECRET_KEY=your-secret-key
DEBUG=True
DB_NAME=finhub_db
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432
ALLOWED_HOSTS=localhost,127.0.0.1
``` 