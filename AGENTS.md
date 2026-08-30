# AGENTS.md

Мебельный Telegram-бот на aiogram 3 + SQLAlchemy 2 (async SQLite/aiosqlite;
детали — ADR 0004). Подробный обзор возможностей — в `README.md`.

## Команды

Локальный venv `./venv` (Python 3.12), глобального окружения нет:

```bash
./venv/bin/python main.py                  # запуск бота (long polling)
./venv/bin/python -m unittest discover -s tests   # тесты (stdlib unittest, не pytest)
./venv/bin/ruff check .                    # линтер (конфига нет — дефолты ruff)
./venv/bin/alembic upgrade head            # миграции (SQLite из DATABASE_PATH в .env)
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
  Актуальная цепочка: начальная `d86de4abbf3e` (вся схема из `models.py` +
  сид категорий; ADR 0004) → `9c6920cb0ae6` (таблица `subcategories` +
  сид кухонных типов) → `9e046db1dbeb` (полное удаление подкатегорий:
  drop `is_deleted`, legacy-удалённые перенесены в «Остальные»).
- **БД — SQLite-файл** из `DATABASE_PATH` в `.env` (`settings/config.py`):
  async-URL (`sqlite+aiosqlite://`) для бота, sync-URL (`sqlite://`) для
  Alembic (`ConfigBot.SYNC_DATABASE_URL`; aiosqlite не годится для sync-
  движка миграций). Файл автоматически создаётся при первом подключении,
  ожидание готовности не нужно.
- **CRUD возвращает отсоединённые объекты**: сессия закрывается на выходе,
  поэтому связи нужно грузить сразу (`selectinload`) внутри функции — ленивая
  загрузка после возврата падает с `DetachedInstanceError`. `refresh()` связи
  не грузит.

## Архитектура

- Роутеры в `main.py` (порядок важен; каталог идёт ПЕРВЫМ, чтобы `/start`
  всегда обрабатывался для всех и не перехватывался незавершёнными админскими
  FSM-сценариями — `start_handler` сбрасывает state):
  `handlers/backend/user/router.py` (каталог),
  `handlers/admin` (сборка в `__init__.py`: меню в `router.py`, потоки в
  `categories.py` / `furniture.py` (добавление) / `furniture_delete.py`
  (удаление) / `subcategories.py` / `orders.py`; доступ — один middleware
  `access.setup_admin_access` на родительском роутере, хендлеры прав НЕ
  проверяют),
  `handlers/backend/order.py` (FSM-заявка: имя → телефон → подтверждение).
- Fallback «отправьте текстом» для админских FSM живёт ВНУТРИ своего модуля
  (`categories.py`, `furniture.py`) и регистрируется после текстовых
  хендлеров этого модуля.
- Навигация на строках callback_data: `category:<id>` →
  `filtersub:<key>:<подкатегория|__others__>` → `country:<key>:<подкатегория>:<страна>`
  → `page:<key>:<стр>:<подкатегория>:<страна>` → `product:<id>:<key>:<подкатегория>:<страна>:<стр>`,
  возврат `back:sub:<key>` / `back:main`, заявка `order:<id>` / `order:confirm|cancel`.
  Контекст возврата зашит в кнопки. Подкатегория в этих данных — имя активной
  подкатегории либо синтаксическое `__others__` (раздел «Остальные»;
  `database/crud_catalog.OTHERS_SUBCATEGORY`).
  Админские колбэки — префикс `adm:`: меню `adm:menu`, категории
  `adm:delcat[:ok]:<id>`, товары `adm:delfurn[:<id>][:<стр>]` /
  `adm:delp|delok:<pid>:<cid>:<стр>`, подкатегории `adm:subcat:<id>` /
  `adm:scadd:<cid>` (FSM-имя) / `adm:scdel[ok]:<sid>`, заявки `adm:orders[:стр]` /
  `adm:order:<id>:<стр>` / `adm:ost:<id>:<статус>:<стр>`; статистика заявок
  `adm:ostats` (без двоеточия после ost — не путать с `adm:ost:`), экспорт
  CSV `adm:oexport`.
  При добавлении нового формата сверяй «кнопка ↔ парсер»: разбор падает молча
  в рантайме (см. историю с `adm:delfurn` без страницы).
- `CATEGORY_CONFIG` (`keyboard/user_keyboards.py`): короткий ключ категории →
  (имя из БД, тип фильтра). Категория без ключа работает: имя = ключ.
- **Подкатегории — отдельная таблица `subcategories`** (`models.Subcategory`,
  миграция `9c6920cb0ae6`): `category_id`, `name`, `created_at` (`is_deleted`
  убран миграцией `9e046db1dbeb`). Товар ссылается на неё по имени через
  `furniture.subcategory`. Удаление (`delete_subcategory`) стирает метку у
  товаров подкатегории (они уходят в раздел «Остальные», `подкатегория=__others__`)
  и полностью удаляет запись. «Остальные» показываются только если у категории
  есть записи подкатегорий (тогда это дополнение к ним); у категории без
  подкатегорий все товары видны по стране напрямую. `get_subcategories_with_counts`
  объединяет таблицу с метками товаров (легаси), возвращает
  `(id, имя, счётчик)`. `REQUIRED_KITCHEN_TYPES` гарантируют
  «Прямая»/«Угловая» для кухни в сид миграции.
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
- CRUD разнесён на `database/crud_catalog.py` (категории, товары,
  подкатегории, пользователи) и `database/crud_orders.py` (заявки);
  `database/crud.py` — фасад-реэкспорт, внешние импорты идут через него.
  Обе половины берут сессию как `engine.AsyncSessionLocal()` в момент
  вызова — тесты подменяют именно `engine.AsyncSessionLocal` временной
  SQLite-базой (aiosqlite — только тесты; единая точка патча
  для обеих половин).
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
- Статистика заявок — только снимок текущих статусов (истории переходов
  в схеме нет); уведомление покупателю шлётся при переходе в «В работе» /
  «Выполнена» / «Отменена» и глушит только `TelegramForbiddenError`.
- Нет рассылки по пользователям и блокировки спамеров.
- Поддерживаются long polling и webhook через `WEBHOOK_BASE_URL`; нет CI
  (ruff+unittest в GitHub Actions), Dockerfile и стратегии бэкапов.
  Бэкап БД сводится к копированию SQLite-файла (ADR 0004).

## Инструкция для агентов

`.github/agents/russian-code-commenter.agent.md` — добавление русских
комментариев (не менять логику кода).
