import os
from urllib.parse import quote_plus

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


# Реквизиты PostgreSQL из .env — единый источник и для бота, и для compose,
# и для Alembic (ADR 0002). Готовый DATABASE_URL отдельно не заводится.
postgres_user = os.getenv("POSTGRES_USER", "furniture")
postgres_password = os.getenv("POSTGRES_PASSWORD", "furniture")
postgres_db = os.getenv("POSTGRES_DB", "furniture")
postgres_host = os.getenv("POSTGRES_HOST", "localhost")
try:
    postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
except ValueError:
    raise ValueError("POSTGRES_PORT должен быть целым числом!") from None

# Логин и пароль экранируем: в них могут быть символы URL (@, :, /).
_database_url = (
    "postgresql+psycopg://"
    f"{quote_plus(postgres_user)}:{quote_plus(postgres_password)}"
    f"@{postgres_host}:{postgres_port}/{quote_plus(postgres_db)}"
)


class ConfigBot:
    TOKEN: str = token
    # Флаг is_admin в базе тоже продолжает работать.
    ADMIN_IDS: tuple[int, ...] = admin_ids
    POSTGRES_USER: str = postgres_user
    POSTGRES_DB: str = postgres_db
    POSTGRES_HOST: str = postgres_host
    POSTGRES_PORT: int = postgres_port
    # Единый URL для async-движка бота и синхронного движка Alembic.
    DATABASE_URL: str = _database_url
    # Webhook-режим включается только при заданном WEBHOOK_BASE_URL,
    # иначе бот работает через long polling.
    WEBHOOK_BASE_URL: str = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")
    WEBHOOK_PATH: str = os.getenv("WEBHOOK_PATH", "/webhook")
    WEBHOOK_SECRET_TOKEN: str = os.getenv("WEBHOOK_SECRET_TOKEN", "")
    WEB_SERVER_HOST: str = os.getenv("WEB_SERVER_HOST", "0.0.0.0")
    WEB_SERVER_PORT: int = int(os.getenv("WEB_SERVER_PORT", "8080"))


BOT_TOKEN = ConfigBot.TOKEN