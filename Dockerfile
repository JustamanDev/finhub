FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Системные зависимости
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Копируем весь проект внутрь контейнера
COPY . /app/

# Ставим только зависимости проекта (из pyproject.toml)
RUN pip install --upgrade pip && \
    pip install --no-cache-dir \
        "django==4.2" \
        "psycopg2-binary>=2.9.10,<3.0.0" \
        "python-decouple>=3.8,<4.0" \
        "djangorestframework>=3.16.0,<4.0.0" \
        "django-environ>=0.12.0,<0.13.0" \
        "django-cors-headers>=4.7.0,<5.0.0" \
        "django-filter>=25.1,<26.0" \
        "djoser>=2.3.3,<3.0.0" \
        "django-ratelimit>=4.1.0,<5.0.0" \
        "drf-spectacular>=0.28.0,<0.29.0" \
        "python-telegram-bot>=22.3,<23.0" \
        "django-redis>=5.4.0,<6.0.0" \
        "xlsxwriter>=3.2.0,<4.0.0" \
        "gunicorn>=22.0.0,<23.0.0"

# Дефолтная команда (в docker-compose переопределяется)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]