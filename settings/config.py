import os

from dotenv import load_dotenv


# Загружаем токен из локального .env, который не попадает в Git.
load_dotenv()


# Проверка выполняется при старте, чтобы бот не запускался без токена.
token = os.getenv("BOT_TOKEN")
if not token:
    raise ValueError("BOT_TOKEN не найден в .env файле!")


class ConfigBot:
    TOKEN: str = token
    # Контакты необязательны: без них карточка показывает «не указан».
    WHATSAPP = os.getenv("WHATSAPP_CONTACT", "не указан")
    TELEGRAM = os.getenv("TELEGRAM_CONTACT", "не указан")


BOT_TOKEN = ConfigBot.TOKEN