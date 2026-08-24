import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import DeleteWebhook
from aiogram.types import BotCommand, BotCommandScopeChat
from sqlalchemy import text

from database.engine import async_engine as engine
from handlers.admin import router as admin_router
from handlers.backend.order import router as order_router
from handlers.backend.user import router as user_router
from settings.config import ConfigBot

logger = logging.getLogger(__name__)

# Обычным пользователям показываем только каталог.
USER_COMMANDS = [BotCommand(command="start", description="🏠 Открыть каталог мебели")]
# Админам дополнительно видна команда входа в панель.
ADMIN_COMMANDS = USER_COMMANDS + [
    BotCommand(command="admin", description="🛠 Админ-панель"),
]


async def setup_commands(bot: Bot) -> None:
    """Зарегистрировать меню команд в интерфейсе Telegram."""
    await bot.set_my_commands(USER_COMMANDS)
    # Отдельный список команд для каждого админа из .env.
    for admin_id in ConfigBot.ADMIN_IDS:
        try:
            await bot.set_my_commands(
                ADMIN_COMMANDS,
                # type="chat" подставляется по умолчанию для этого скоупа.
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
        except TelegramBadRequest:
            # Админ ещё не написал боту — меню команд появится позже.
            continue


async def wait_for_database(
    attempts: int = 30, delay: float = 1.0
) -> None:
    """Дождаться готовности PostgreSQL перед запуском polling (ADR 0002).

    Контейнер БД может подниматься дольше бота; ограниченный retry
    переживает это, но не маскирует ошибки конфигурации — после
    исчерпания попыток падаем с понятной ошибкой.
    """
    for attempt in range(1, attempts + 1):
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return
        except Exception as error:
            if attempt == attempts:
                raise SystemExit(
                    f"PostgreSQL недоступен после {attempts} попыток "
                    f"({error}). Проверьте: docker-compose up -d, "
                    "реквизиты POSTGRES_* в .env."
                ) from error
            logger.info(
                "База ещё не готова (попытка %d/%d), ждём...", attempt, attempts
            )
            await asyncio.sleep(delay)


async def main() -> None:
    # Настраиваем базовое логирование приложения.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    # Настраиваем HTML-форматирование сообщений и подключаем каталог.
    bot = Bot(
        token=ConfigBot.TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    logger.info("Администраторы из ADMIN_ID: %s", ConfigBot.ADMIN_IDS or "не заданы")
    dispatcher = Dispatcher()
    # Каталог, заявки и админ-панель — роутеры одного диспетчера.
    dispatcher.include_router(admin_router)
    dispatcher.include_router(user_router)
    dispatcher.include_router(order_router)

    # Регистрируем команды, чтобы /start и /admin были видны в меню Telegram.
    await setup_commands(bot)

    # Не выходим в polling, пока БД не примет соединения.
    await wait_for_database()

    # Удаляем старый webhook перед запуском long polling.
    await bot(DeleteWebhook(drop_pending_updates=True))
    try:
        await dispatcher.start_polling(bot)
    finally:
        # Закрываем HTTP-сессию даже при остановке бота с ошибкой.
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except TelegramBadRequest as error:
        logger.error("Telegram API error: %s", error)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception:
        logger.critical("Critical bot error", exc_info=True)
