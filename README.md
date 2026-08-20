# FURNETURE_BOT

Пользовательский каталог мебели для Telegram-бота.

## Запуск

1. Установите зависимости:

	```bash
	pip install -r requirements.txt
	```

2. Скопируйте `.env.example` в `.env` и укажите токен бота:

	```env
	BOT_TOKEN=your_telegram_bot_token
	```

3. Примените миграции:

	```bash
	alembic upgrade head
	```

4. Запустите бота:

	```bash
	python main.py
	```

Товары должны содержать название, категорию, описание, а для фильтруемых разделов
также значения `country` (`Россия` или `Турция`) либо `subcategory`
(`Прямая` или `Угловая`).
