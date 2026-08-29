import os
from pathlib import Path

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


# Путь к файлу SQLite берётся из .env (ADR 0004). Относительный путь
# считается от корня проекта; родительская директория создаётся при первом
# подключении. Единый источник и для бота, и для Alembic.
_raw_db_path = os.getenv("DATABASE_PATH", "database/database.db")
_db_path = Path(_raw_db_path)
if not _db_path.is_absolute():
    _db_path = Path(__file__).resolve().parent.parent / _db_path
_db_path.parent.mkdir(parents=True, exist_ok=True)
_database_path = str(_db_path)
_database_url = f"sqlite+aiosqlite:///{_database_path}"
# Синхронный URL для Alembic: тот же файл, но через стандартный sync-драйвер
# (aiosqlite — только async; sync-движок миграций не умеет в greenlet).
_sync_database_url = f"sqlite:///{_database_path}"


class ConfigBot:
    TOKEN: str = token
    # Флаг is_admin в базе тоже продолжает работать.
    ADMIN_IDS: tuple[int, ...] = admin_ids
    # Путь до SQLite-файла и собранные URL (async-движок бота и sync-Alembic).
    DATABASE_PATH: str = _database_path
    # Единый URL для async-движка бота и синхронного движка Alembic.
    DATABASE_URL: str = _database_url
    # Синхронный URL (sqlite://) — только для Alembic, см. env.py.
    SYNC_DATABASE_URL: str = _sync_database_url
    # Webhook-режим включается только при заданном WEBHOOK_BASE_URL,
    # иначе бот работает через long polling.
    WEBHOOK_BASE_URL: str = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")
    WEBHOOK_PATH: str = os.getenv("WEBHOOK_PATH", "/webhook")
    WEBHOOK_SECRET_TOKEN: str = os.getenv("WEBHOOK_SECRET_TOKEN", "")
    WEB_SERVER_HOST: str = os.getenv("WEB_SERVER_HOST", "0.0.0.0")
    WEB_SERVER_PORT: int = int(os.getenv("WEB_SERVER_PORT", "8080"))


BOT_TOKEN = ConfigBot.TOKEN