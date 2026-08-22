# AGENTS.md

Мебельный Telegram-бот на aiogram 3 + SQLAlchemy 2 (async SQLite). Подробный
обзор возможностей и схемы — в `README.md`.

## Команды

Проект использует локальный venv в `./venv` (Python 3.12), глобального
окружения нет:

```bash
./venv/bin/python main.py                  # запуск бота (long polling)
./venv/bin/python -m unittest discover -s tests   # тесты (stdlib unittest, не pytest)
./venv/bin/ruff check .                    # линтер (конфига нет — дефолты ruff)
./venv/bin/alembic upgrade head            # миграции
```

Проверка перед коммитом: `python -m compileall -q main.py database handlers keyboard settings states utils alembic`, затем `pip check` и тесты.

## Критичные особенности

- **`BOT_TOKEN` нужен при импорте.** `settings/config.py` бросает
  `ValueError` без `.env`. Любой импорт хендлеров или CRUD тянет конфиг, поэтому
  тесты ставят `os.environ.setdefault("BOT_TOKEN", "test-token")` до импорта
  пакетов проекта.
- **Один процесс — один токен.** Все роутеры включаются в один Dispatcher в
  `main.py`. Второй процесс с polling конфликтует с первым.
- Сообщения отправляются с глобальным `ParseMode.HTML`: экранируй
  пользовательский ввод через `html.escape` (как в `handlers/backend/order.py`).
- Миграции не редактировать после применения — новая схема = новая ревизия.
  Ревизия `9c3e2a1b7d4f` сеет стандартные категории, `f8b2d4c6a9e1` добавляет
  контакты товара (`whatsapp_contact`, `telegram_contact`), а `c4d9e7f2a8b3`
  — имя и телефон покупателя в `orders`. Внимание: таблицу `orders` создаёт
  именно `c4d9e7f2a8b3` (устойчиво к её отсутствию) — в старых ревизиях её
  не было.

## Архитектура

- Точки входа роутеров в `main.py`: `handlers/admin/router.py` (`/admin`),
  `handlers/backend/user/router.py` (каталог) и `handlers/backend/order.py`
  (FSM-заявка: имя → телефон → подтверждение). Порядок подключения важен.
- Вся навигация построена на строках callback_data:
  `category:<id>`, `filter:<key>:<тип>:<значение>`,
  `page:<key>:<стр>:<тип>:<значение>`,
  `product:<id>:<key>:<тип>:<значение>:<стр>`, `order:<id>`,
  `order:confirm|cancel`, `back:main`. Контекст возврата (категория, фильтр,
  страница) зашивается в сами кнопки. Админские колбэки имеют префикс `adm:`.
- `CATEGORY_CONFIG` в `keyboard/user_keyboards.py` сопоставляет короткие ключи
  категорий (`sleep`, `kitchen`, …) именам из таблицы `categories` и типу
  фильтра. Новая категория из БД без ключа работает: имя используется как ключ,
  иконка берётся дефолтная.
- Фильтры динамические: уникальные значения колонок `country` и `subcategory`
  таблицы `furniture`. Подкатегорий как отдельной таблицы НЕТ — это строковая
  колонка (используется только кухонной мебелью). Константы
  `REQUIRED_COUNTRIES` / `REQUIRED_KITCHEN_TYPES` в `database/crud.py`
  гарантируют наличие «Россия», «Турция», «Прямая», «Угловая» даже при пустой
  базе товаров.
- Фото товара хранятся в `furniture_photos` по Telegram `file_id` (плюс
  локальный путь) и отправляются альбомом через `answer_media_group`.
- Контакты карточки (`whatsapp_contact`, `telegram_contact`) — колонки таблицы
  `furniture`; админ вводит их при добавлении товара, констант из `.env`
  больше нет. Пустое поле показывается как «не указан».
- Админский доступ двойной: telegram_id из `ADMIN_ID` в `.env` (можно список
  через запятую, `ConfigBot.ADMIN_IDS`) **или** флаг `is_admin` в БД.
- `Order.user_id` — FK на `users.id` (UUID-строка), а не telegram_id. Перед
  `create_order` обязательно вызвать `upsert_user`. Имя и телефон из формы
  сохраняются в `orders.customer_name` / `customer_phone`.
- Уведомление админов: `notify_admins` из `handlers/backend/order.py` шлёт
  заявку объединению получателей из `ADMIN_IDS` и БД (`get_admin_ids`),
  глушит только `TelegramForbiddenError`. Без `.bot` у сообщения (тесты) —
  пропускается.

## Админ-панель

Вход — команда `/admin`, доступ по `ADMIN_ID` из `.env` или по `User.is_admin`
(ставится вручную в БД). При входе админ получает отдельное сообщение с
приветствием и инструкцией (`_admin_welcome_text`). Меню команд Telegram
регистрируется при старте в `setup_commands` (`main.py`): всем — `/start`,
админам из `ADMIN_IDS` дополнительно `/admin`.
Умения: добавление/удаление категорий (каскадно с товарами), добавление товара
(название → описание → категория → тип кухни или страна → WhatsApp → Telegram
→ фото), удаление товара списком с пагинацией, просмотр/удаление подкатегорий
(снимает метку у товаров, товары остаются), раздел «Заявки»
(`handlers/admin/orders.py`, отдельный роутер в пакете): список заявок
`adm:orders[:стр]`, карточка `adm:order:<id>:<стр>`, смена статуса
`adm:ost:<id>:<статус>:<стр>` (new/processing/completed/cancelled,
метки — `ORDER_STATUS_LABELS`). FSM-состояния — в `states/states.py`. Новая
подкатегория создаётся сама при вводе своего типа текстом во время добавления
товара.

## Соглашения

- Комментарии, доки и тексты бота — на русском языке.
- Тесты подменяют `crud.AsyncSessionLocal` временной SQLite-базой и используют
  `SimpleNamespace` + `AsyncMock` вместо реальных aiogram-объектов; для обхода
  `isinstance(callback.message, Message)` есть трюк `_AnyMessage` в
  `tests/test_order_flow.py` — повторяй этот паттерн для новых хендлеров.

## Инструкция для агентов

В `.github/agents/russian-code-commenter.agent.md` — агент для добавления
русских комментариев (не менять логику кода).
