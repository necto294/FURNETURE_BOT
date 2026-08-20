import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import DeleteWebhook

from handlers.user import router as user_router
from settings.config import ConfigBot


async def main() -> None:
    bot = Bot(
        token=ConfigBot.TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(user_router)

    await bot(DeleteWebhook(drop_pending_updates=True))
    try:
        await dispatcher.start_polling(bot)
    finally:
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
