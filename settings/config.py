import os
from dotenv import load_dotenv

load_dotenv()

class ConfigBot:
    TOKEN = os.getenv("BOT_TOKEN")  # Берём токен из .env

    if not TOKEN:
        raise ValueError("BOT_TOKEN не найден в .env файле!")