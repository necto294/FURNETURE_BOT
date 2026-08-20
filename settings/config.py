import os

from dotenv import load_dotenv


load_dotenv()


token = os.getenv("BOT_TOKEN")
if not token:
    raise ValueError("BOT_TOKEN не найден в .env файле!")


class ConfigBot:
    TOKEN: str = token


BOT_TOKEN = ConfigBot.TOKEN