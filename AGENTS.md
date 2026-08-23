# AGENTS.md

Мебельный Telegram-бот на aiogram 3 + SQLAlchemy 2 (async SQLite). Подробный
обзор возможностей — в `README.md`.

## Команды

Локальный venv `./venv` (Python 3.12), глобального окружения нет:

```bash
./venv/bin/python main.py                  # запуск бота (long polling)
./venv/bin/python -m unittest discover -s tests   # тесты (stdlib unittest, не pytest)
./venv/bin/ruff check .                    # линтер (конфига нет — дефолты ruff)
./venv/bin/alembic upgrade head            # миграции
```

Перед коммитом: `compileall` по пакетам, `pip check`, тесты.

## Критичные особенности

- **`BOT_TOKEN` нужен при импорте**: `settings/config.py` бросает `ValueError`
  без `.env`. Любой импорт хендлеров или CRUD тянет конфиг, поэтому тесты
  ставят `os.environ.setdefault("BOT_TOKEN", "test-token")` до импортов.
- **Один процесс — один токен.** Все роутеры включаются в один Dispatcher
  в `main.py`; второй процесс с polling конфликтует с первым.
- Глобальный `ParseMode.HTML`: экранируй пользовательский ввод через
  `html.escape`.
- **Миграции не редактировать после применения** — новая схема = новая ревизия.
  Актуальная цепочка: `9c3e2a1b7d4f` (сид категорий) → `f8b2d4c6a9e1`
  (контакты товара) → `c4d9e7f2a8b3` (имя/телефон покупателя; **эта же ревизия
  создаёт саму таблицу `orders`** — в старых её не было, ревизия устойчива
  к обоим состояниям базы) → `e9f4b8c2d6a7` (цена товара).
- **CRUD возвращает отсоединённые объекты**: сессия закрывается на выходе,
  поэтому связи нужно грузить сразу (`selectinload`) внутри функции — ленивая
  загрузка после возврата падает с `DetachedInstanceError`. `refresh()` связи
  не грузит.

## Архитектура

- Роутеры в `main.py` (порядок важен): `handlers/admin` (сборка в
  `__init__.py`: меню в `router.py`, потоки в `categories.py` /
  `furniture.py` / `subcategories.py` / `orders.py`; доступ — один middleware
  `access.setup_admin_access` на родительском роутере, хендлеры прав НЕ
  проверяют),
  `handlers/backend/user/router.py` (каталог),
  `handlers/backend/order.py` (FSM-заявка: имя → телефон → подтверждение).
- Fallback «отправьте текстом» для админских FSM живёт ВНУТРИ своего модуля
  (`categories.py`, `furniture.py`) и регистрируется после текстовых
  хендлеров этого модуля.
- Навигация на строках callback_data: `category:<id>`,
  `filter:<key>:<тип>:<значение>`, `page:<key>:<стр>:<тип>:<значение>`,
  `product:<id>:<key>:<тип>:<значение>:<стр>`, `order:<id>`,
  `order:confirm|cancel`, `back:main`. Контекст возврата зашит в кнопки.
  Админские колбэки — префикс `adm:`: меню `adm:menu`, категории
  `adm:delcat[:ok]:<id>`, товары `adm:delfurn[:<id>][:<стр>]` /
  `adm:delp|delok:<pid>:<cid>:<стр>`, подкатегории `adm:subcat:<id>` /
  `adm:scdel[ok]:<cid>:<поз>`, заявки `adm:orders[:стр]` /
  `adm:order:<id>:<стр>` / `adm:ost:<id>:<статус>:<стр>`.
  При добавлении нового формата сверяй «кнопка ↔ парсер»: разбор падает молча
  в рантайме (см. историю с `adm:delfurn` без страницы).
- `CATEGORY_CONFIG` (`keyboard/user_keyboards.py`): короткий ключ категории →
  (имя из БД, тип фильтра). Категория без ключа работает: имя = ключ.
- Фильтры динамические — уникальные значения колонок `country`/`subcategory`;
  подкатегорий как таблицы НЕТ. `REQUIRED_COUNTRIES` / `REQUIRED_KITCHEN_TYPES`
  в `database/crud.py` гарантируют варианты фильтра даже при пустой базе;
  админский раздел «Подкатегории» для кухни показывает эти же типы со счётчиком 0.
- Фото — в `furniture_photos` по Telegram `file_id`, отправка альбомом через
  `answer_media_group`.
- Админ — telegram_id из `ADMIN_ID` в `.env` (список через запятую,
  `ConfigBot.ADMIN_IDS`) **или** флаг `is_admin` в БД.
- `Order.user_id` — FK на `users.id` (UUID), перед `create_order` звать
  `upsert_user`; имя/телефон формы хранятся в `customer_name`/`customer_phone`.
- `notify_admins` шлёт заявку объединению `ADMIN_IDS` + `get_admin_ids`,
  глушит только `TelegramForbiddenError`; без `.bot` у сообщения — пропуск.

## Соглашения

- Комментарии, доки и тексты бота — на русском.
- Телефоны покупателя: правила в `docs/adr/0001-phone-normalization.md` и
  `CONTEXT.md`. Хранение только E.164 (`utils/phone.py`: `normalize_phone`,
  `pretty_phone`); номера без «+» трактуются как российские; нераспознанный
  номер — повторный ввод, не отклонение. То же правило действует для
  WhatsApp-контакта товара при добавлении (был баг: номер сохранялся как
  введён). Тесты — шаблонными номерами libphonenumber, не реальными.
- Тесты подменяют `crud.AsyncSessionLocal` временной SQLite-базой;
  aiogram-объекты — `SimpleNamespace` + `AsyncMock`. Для обхода
  `isinstance(message, Message)` — трюк `_AnyMessage` (метакласс); помни,
  что патчить надо `Message` в том модуле, где хендлер его импортировал.
- Fallback-хендлеры FSM («отправьте текстом») регистрировать ПОСЛЕ текстовых
  хендлеров состояния — иначе перехватят ввод (было такое).

## Известные пробелы (кандидаты в roadmap)

- Нет поиска по каталогу; цена не показывается в списках каталога
  (только в карточке).
- Нет редактирования товара/категории — только добавление и удаление;
  отдельное фото нельзя заменить или удалить.
- Смена статуса заявки не уведомляет покупателя; нет экспорта заявок
  и статистики по статусам.
- Нет рассылки по пользователям и блокировки спамеров.
- Только long polling (webhook отсутствует); нет CI (ruff+unittest в GitHub
  Actions), Dockerfile и стратегии бэкапа SQLite.

## Инструкция для агентов

`.github/agents/russian-code-commenter.agent.md` — добавление русских
комментариев (не менять логику кода).
