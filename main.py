import asyncio # Для асинхронности
import logging # Для логирования ошибок

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import DeleteWebhook

from settings.config import ConfigBot # Наш токен из .env


async def main():
    # Создаём бота с токеном и HTML-форматированием
    bot = Bot(token=ConfigBot.TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Удаление всехстарых вебхуков
    await bot(DeleteWebhook(drop_pending_updates=True))

    # Запуск бота
    await dp.start_polling(bot, skip_updates=True)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except TelegramBadRequest as e:
        # Ловим ошибки от Telegram API и выводим их в лог
        logging.error(f'Telegram API erro: {e}')
    except KeyboardInterrupt as e:
        logging.info('Bot stopped by user')
    except Exception as e:
        logging.critical(f'Критические ошибки: {e}', exc_info=True)