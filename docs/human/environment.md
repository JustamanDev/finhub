# Переменные окружения

Единый `.env` в корне проекта. Используется и локально, и на production (на сервере: `/srv/www/finhub/.env`).

## Обязательные

| Переменная | Описание |
|------------|----------|
| `SECRET_KEY` | Django secret key |
| `DJANGO_ENVIRONMENT` | `development` или `production` |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL |
| `TELEGRAM_BOT_TOKEN` | Токен от @BotFather |

## Django

| Переменная | Default | Описание |
|------------|---------|----------|
| `DEBUG` | `True` (dev) | `False` на prod |
| `ALLOWED_HOSTS` | — | Через запятую |

## Redis (production)

| Переменная | Default |
|------------|---------|
| `REDIS_URL` | `redis://127.0.0.1:6379/1` |

## PostgreSQL SSL (production)

| Переменная | Default | Описание |
|------------|---------|----------|
| `DB_SSLMODE` | `disable` | `require` для managed Postgres с TLS |

## Telegram — сеть и устойчивость

| Переменная | Default | Описание |
|------------|---------|----------|
| `TELEGRAM_PROXY_URL` | — | `socks5://user:pass@host:1080` |
| `TELEGRAM_CONNECT_TIMEOUT` | 10 | TCP connect |
| `TELEGRAM_READ_TIMEOUT` | 30 | Read timeout API |
| `TELEGRAM_WRITE_TIMEOUT` | 30 | Write timeout |
| `TELEGRAM_POOL_TIMEOUT` | 10 | Pool wait |
| `TELEGRAM_GET_UPDATES_READ_TIMEOUT` | 45 | Long polling |
| `TELEGRAM_POLLING_TIMEOUT` | 30 | Polling cycle |

При нестабильной сети увеличь timeouts (см. README в корне).

## Telegram — алерты

| Переменная | Описание |
|------------|----------|
| `TELEGRAM_ADMIN_CHAT_IDS` | Chat ID через запятую для error alerts |

## CORS (production)

| Переменная | Описание |
|------------|----------|
| `CORS_ALLOWED_ORIGINS` | `https://yourdomain.com` |

## Voice input

| Переменная | Default | Описание |
|------------|---------|----------|
| `VOICE_ENABLED` | `False` | Включить обработку голосовых сообщений |
| `OPENAI_API_KEY` | — | Whisper + LLM (обязательно при `VOICE_ENABLED=True`) |
| `OPENAI_PROXY_URL` | `TELEGRAM_PROXY_URL` | HTTP/SOCKS proxy для OpenAI (`socks5h://…`); нужен выход в поддерживаемой стране |
| `TRANSCRIPTION_MODEL` | `whisper-1` | Модель Whisper |
| `VOICE_LLM_MODEL` | `gpt-4o-mini` | Модель для разбора естественной речи |
| `WHISPER_PROMPT` | — | Подсказка Whisper (фин. термины RU/EN) |
| `WHISPER_LANGUAGE` | — | ISO-код языка (`ru`), пусто = auto |

## Пример `.env` для development

```env
SECRET_KEY=dev-secret-change-me
DJANGO_ENVIRONMENT=development
DEBUG=True

DB_NAME=finhub_db
DB_USER=finhub_user
DB_PASSWORD=finhub_password
DB_HOST=db
DB_PORT=5432

ALLOWED_HOSTS=localhost,127.0.0.1
TELEGRAM_BOT_TOKEN=123456:ABC...
REDIS_URL=redis://redis:6379/1
```

## Пример `.env` для production

```env
DJANGO_ENVIRONMENT=production
DEBUG=False
SECRET_KEY=strong-random-key

DB_NAME=finhub
DB_USER=finhub_user
DB_PASSWORD=very-strong-password
DB_HOST=db

ALLOWED_HOSTS=your.domain,localhost
REDIS_URL=redis://redis:6379/1
TELEGRAM_BOT_TOKEN=...
DB_SSLMODE=disable
```

## Переключение окружения

- `manage.py` → development по умолчанию
- `wsgi.py` / gunicorn → production
- Переменная `DJANGO_ENVIRONMENT` переопределяет defaults
