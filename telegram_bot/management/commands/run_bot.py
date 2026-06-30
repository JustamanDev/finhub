import logging
import asyncio
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from telegram import BotCommand
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
)

from telegram_bot.handlers.text_handler import TextHandler
from telegram_bot.handlers.voice_handler import VoiceHandler
from telegram_bot.handlers.callback_handler import CallbackHandler
from telegram_bot.handlers.command_handler import CommandHandler as BotCommandHandler
from telegram_bot.utils.admin_alerts import notify_admins_about_exception
from telegram_bot.utils.telegram_resilience import retry_telegram_call

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid %s=%r, fallback to %s", name, raw, default)
        return default


def _get_proxy_url() -> str | None:
    raw = os.getenv("TELEGRAM_PROXY_URL", "").strip()
    return raw or None


def _build_httpx_request(
    *,
    connect_timeout: int,
    read_timeout: int,
    write_timeout: int,
    pool_timeout: int,
    proxy_url: str | None,
) -> HTTPXRequest:
    kwargs = {
        "connect_timeout": connect_timeout,
        "read_timeout": read_timeout,
        "write_timeout": write_timeout,
        "pool_timeout": pool_timeout,
    }
    if not proxy_url:
        return HTTPXRequest(**kwargs)

    try:
        return HTTPXRequest(proxy=proxy_url, **kwargs)
    except TypeError:
        # Compatibility for PTB versions that still use `proxy_url`.
        return HTTPXRequest(proxy_url=proxy_url, **kwargs)


class Command(BaseCommand):
    """Команда для запуска Telegram бота"""
    
    help = 'Запускает Telegram бота FinHub'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--token',
            type=str,
            help='Токен Telegram бота (по умолчанию из .env)',
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Включить debug режим',
        )
    
    def handle(self, *args, **options):
        """Запускает бота"""
        # Настройка логирования
        if options['debug']:
            logging.basicConfig(
                level=logging.DEBUG,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            )
        
        # Получаем токен из .env файла
        token = options['token'] or os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            self.stdout.write(
                self.style.ERROR(
                    '❌ Токен бота не найден!\n'
                    'Добавьте TELEGRAM_BOT_TOKEN в .env файл или используйте --token'
                )
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS('🚀 Запуск Telegram бота FinHub...')
        )
        
        # Запускаем бота
        try:
            # Используем новый event loop для избежания конфликтов
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_bot(token))
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.SUCCESS('🛑 Бот остановлен пользователем')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка: {e}')
            )
        finally:
            try:
                loop.close()
            except Exception:
                pass
    
    async def _run_bot(self, token: str):
        """
        Настраивает и запускает бота
        
        Args:
            token: Токен Telegram бота
        """
        try:
            proxy_url = _get_proxy_url()
            if proxy_url:
                logger.info("Telegram proxy is enabled: %s", proxy_url)

            request = _build_httpx_request(
                connect_timeout=_env_int("TELEGRAM_CONNECT_TIMEOUT", 10),
                read_timeout=_env_int("TELEGRAM_READ_TIMEOUT", 30),
                write_timeout=_env_int("TELEGRAM_WRITE_TIMEOUT", 30),
                pool_timeout=_env_int("TELEGRAM_POOL_TIMEOUT", 10),
                proxy_url=proxy_url,
            )

            get_updates_request = _build_httpx_request(
                connect_timeout=_env_int("TELEGRAM_CONNECT_TIMEOUT", 10),
                read_timeout=_env_int("TELEGRAM_GET_UPDATES_READ_TIMEOUT", 45),
                write_timeout=_env_int("TELEGRAM_WRITE_TIMEOUT", 30),
                pool_timeout=_env_int("TELEGRAM_POOL_TIMEOUT", 10),
                proxy_url=proxy_url,
            )

            # Создаем приложение
            application = (
                Application.builder()
                .token(token)
                .request(request)
                .get_updates_request(get_updates_request)
                .build()
            )
            
            # Создаем обработчики
            text_handler = TextHandler()
            voice_handler = VoiceHandler()
            callback_handler = CallbackHandler()
            command_handler = BotCommandHandler()
            
            # Регистрируем обработчики команд
            application.add_handler(
                CommandHandler(
                    'start',
                    command_handler.start_command,
                )
            )
            application.add_handler(
                CommandHandler(
                    'help',
                    command_handler.help_command,
                )
            )
            application.add_handler(
                CommandHandler(
                    'stats',
                    command_handler.stats_command,
                )
            )
            
            # Регистрируем обработчик текстовых сообщений
            application.add_handler(
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    text_handler.handle_text_message,
                )
            )

            application.add_handler(
                MessageHandler(
                    filters.VOICE | filters.AUDIO,
                    voice_handler.handle_voice_message,
                )
            )
            
            # Регистрируем обработчик callback запросов
            application.add_handler(
                CallbackQueryHandler(
                    callback_handler.handle_callback_query,
                )
            )
            
            # Обработчик ошибок
            async def error_handler(update, context):
                """Обработчик ошибок бота"""
                logger.error(
                    f'Ошибка при обработке обновления {update}: {context.error}',
                    exc_info=context.error,
                )

                try:
                    await notify_admins_about_exception(
                        context.bot,
                        error=context.error,
                        where="run_bot.error_handler",
                        update=update,
                    )
                except Exception:
                    pass
            
            application.add_error_handler(error_handler)

            # Регистрируем команды бота (для кнопки меню Telegram)
            await retry_telegram_call(
                lambda: application.bot.set_my_commands(
                    [
                        BotCommand('start', 'Главное меню'),
                        BotCommand('stats', 'Статистика за сегодня'),
                        BotCommand('help', 'Справка по использованию'),
                    ]
                ),
                operation_name="set_my_commands",
            )
            
            # Запускаем бота
            self.stdout.write(
                self.style.SUCCESS('✅ Бот запущен и готов к работе!')
            )
            self.stdout.write(
                self.style.WARNING('Нажмите Ctrl+C для остановки')
            )
            
            # Инициализируем и запускаем приложение
            await application.initialize()
            await application.start()
            await application.updater.start_polling(
                timeout=_env_int("TELEGRAM_POLLING_TIMEOUT", 30),
            )
            
            # Ждем остановки
            try:
                # Просто ждем бесконечно
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                await application.stop()
                await application.shutdown()
            
        except Exception as e:
            logger.error(f'Ошибка запуска бота: {e}', exc_info=True)
            raise 