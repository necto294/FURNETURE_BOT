import os

from dotenv import load_dotenv

# Загружаем токен из локального .env, который не попадает в Git.
load_dotenv()


# Проверка выполняется при старте, чтобы бот не запускался без токена.
token = os.getenv("BOT_TOKEN")
if not token:
    raise ValueError("BOT_TOKEN не найден в .env файле!")


# Администраторы из .env: один telegram_id или список через запятую.
admin_ids_raw = os.getenv("ADMIN_ID", "")
try:
    admin_ids = tuple(
        int(item) for item in admin_ids_raw.replace(" ", "").split(",") if item
    )
except ValueError:
    raise ValueError(
        "ADMIN_ID должен быть telegram_id или списком id через запятую!"
    ) from None


class ConfigBot:
    TOKEN: str = token
    # Флаг is_admin в базе тоже продолжает работать.
    ADMIN_IDS: tuple[int, ...] = admin_ids
    WEBHOOK_BASE_URL: str = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")
    WEBHOOK_PATH: str = os.getenv("WEBHOOK_PATH", "/webhook")
    WEBHOOK_SECRET_TOKEN: str = os.getenv("WEBHOOK_SECRET_TOKEN", "")
    WEB_SERVER_HOST: str = os.getenv("WEB_SERVER_HOST", "0.0.0.0")
    WEB_SERVER_PORT: int = int(os.getenv("WEB_SERVER_PORT", "8080"))


BOT_TOKEN = ConfigBot.TOKEN