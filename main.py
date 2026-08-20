import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import DeleteWebhook

from handlers.backend.user import router as user_router
from settings.config import ConfigBot


async def main() -> None:
    # Настраиваем HTML-форматирование сообщений и подключаем каталог.
    bot = Bot(
        token=ConfigBot.TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(user_router)

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
        logging.error("Telegram API error: %s", error)
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception:
        logging.critical("Critical bot error", exc_info=True)
