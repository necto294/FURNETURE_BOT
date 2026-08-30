"""Товары в админ-панели: пошаговый мастер добавления.

Потоки удаления товара вынесены в furniture_delete.py.
"""
import asyncio
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.crud import (
    create_furniture_with_photos,
    create_subcategory,
    get_active_subcategory_names,
    get_categories_with_counts,
    get_category_by_id,
)
from handlers.backend.user.formatters import format_price
from keyboard.admin_keyboards import (
    back_to_admin_menu,
    categories_menu,
    countries_menu,
    kitchen_types_menu,
    photos_menu,
)
from states.states import NewFurnitureStates
from utils.phone import normalize_phone

from .router import (
    _category_key,
)

router = Router(name="admin_furniture")

# Максимум фотографий у товара. Превышение не принимается.
MAX_FURNITURE_PHOTOS = 10

# Кэш собираемых альбомов фото: media_group_id -> {task, message, photos}.
# Позволяет принять весь альбом разом и ответить одним подтверждением.
_ALBUM_TIMER_DELAY = 0.6
_ALBUM_CACHE: dict[str, dict] = {}


# --- Добавление товара ---

async def _start_photos_step(target: Message, state: FSMContext) -> None:
    await state.set_state(NewFurnitureStates.photos)
    await target.answer(
        f"📸 Прикрепите фотографии товара.\n"
        f"Можно отправить несколько фото за раз (до {MAX_FURNITURE_PHOTOS} всего, "
        "одиночные фото и целыми альбомами).\n"
        "Когда закончите — нажмите «Готово, сохранить».",
        reply_markup=photos_menu(),
    )


async def _ask_whatsapp(target: Message, state: FSMContext) -> None:
    await state.set_state(NewFurnitureStates.whatsapp_contact)
    await target.answer(
        "📱 Введите номер WhatsApp для карточки этого товара\n"
        "(например <code>+7 900 123 45 67</code>; <code>-</code> — пропустить):",
    )


async def _ask_country(target: Message, state: FSMContext) -> None:
    await state.set_state(NewFurnitureStates.country)
    await target.answer(
        "🌍 Выберите страну производства:",
        reply_markup=countries_menu(),
    )


async def _ask_telegram(target: Message, state: FSMContext) -> None:
    await state.set_state(NewFurnitureStates.telegram_contact)
    await target.answer(
        "📱 Введите Telegram-контакт для карточки товара\n"
        "(например @username или ссылку; <code>-</code> — пропустить):",
    )


@router.callback_query(F.data == "adm:addfurn")
async def add_furniture_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message):
        return

    await callback.message.edit_text("🪑 Введите название товара:")
    await state.set_state(NewFurnitureStates.name)
    await callback.answer()


@router.message(StateFilter(NewFurnitureStates.name), F.text)
async def add_furniture_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым. Попробуйте ещё раз:")
        return

    await state.update_data(name=name)
    await state.set_state(NewFurnitureStates.description)
    await message.answer(
        "📝 Введите описание товара (или <code>-</code>, чтобы пропустить):"
    )


@router.message(StateFilter(NewFurnitureStates.description), F.text)
async def add_furniture_description(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.update_data(description=message.text.strip())
    await state.set_state(NewFurnitureStates.category)

    items = await get_categories_with_counts()
    await message.answer(
        f"📦 Отлично, «{escape(str(data['name']))}» записан.\n"
        "Теперь выберите категорию товара:",
        reply_markup=categories_menu(items, "adm:fc"),
    )


@router.callback_query(StateFilter(NewFurnitureStates.category), F.data.startswith("adm:fc:"))
async def add_furniture_category(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message):
        return

    category = await get_category_by_id(int(callback.data.split(":")[2]))
    if category is None:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    category_name = str(category.name)
    await state.update_data(
        category_id=category.id,
        category_name=category_name,
        category_key=_category_key(category_name),
    )

    # Шаг «подкатегория» появляется, если у категории есть активные
    # подкатегории; затем всегда следует шаг выбора страны.
    subcategories = await get_active_subcategory_names(category.id)
    if subcategories:
        await state.set_state(NewFurnitureStates.kitchen_type)
        await callback.message.edit_text(
            "📐 Выберите подкатегорию или отправьте свой вариант текстом:",
            reply_markup=kitchen_types_menu(subcategories),
        )
    else:
        await state.set_state(NewFurnitureStates.country)
        await callback.message.edit_text(
            "🌍 Выберите страну производства:",
            reply_markup=countries_menu(),
        )
    await callback.answer()


@router.callback_query(StateFilter(NewFurnitureStates.kitchen_type), F.data.startswith("adm:ktype:"))
async def add_furniture_kitchen_type(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message):
        return

    value = callback.data.split(":", 2)[2]
    await state.update_data(subcategory=value)
    await _ask_country(callback.message, state)
    await callback.answer()


@router.message(StateFilter(NewFurnitureStates.kitchen_type), F.text)
async def add_furniture_kitchen_custom(message: Message, state: FSMContext) -> None:
    # Свой вариант подкатегории регистрируем в таблице — он появится
    # в меню покупателя и в списках подкатегорий.
    value = message.text.strip()
    if not value:
        await message.answer("Тип не может быть пустым. Попробуйте ещё раз:")
        return

    data = await state.get_data()
    if "category_id" in data:
        await create_subcategory(int(data["category_id"]), value)
    await state.update_data(subcategory=value)
    await _ask_country(message, state)


@router.callback_query(StateFilter(NewFurnitureStates.country), F.data.startswith("adm:country:"))
async def add_furniture_country(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message):
        return

    value = callback.data.split(":", 2)[2]
    await state.update_data(country=value)
    await _ask_whatsapp(callback.message, state)
    await callback.answer()


@router.message(StateFilter(NewFurnitureStates.country), F.text)
async def add_furniture_country_wrong(message: Message) -> None:
    await message.answer("Пожалуйста, выберите страну кнопкой выше.")


@router.message(StateFilter(NewFurnitureStates.whatsapp_contact), F.text)
async def add_furniture_whatsapp(message: Message, state: FSMContext) -> None:
    whatsapp = message.text.strip()
    if whatsapp == "-":
        await state.update_data(whatsapp_contact=None)
        await _ask_telegram(message, state)
        return
    # Контакт WhatsApp — телефон: проверяем и нормализуем в E.164
    # по правилам ADR 0001; нераспознанное — повторный ввод.
    normalized = normalize_phone(whatsapp)
    if normalized is None:
        await message.answer(
            "❌ Не удалось распознать номер WhatsApp.\n"
            "Введите его ещё раз — например <code>+7 900 123 45 67</code>;\n"
            "<code>-</code> — оставить карточку без контакта.",
        )
        return
    await state.update_data(whatsapp_contact=normalized)
    await _ask_telegram(message, state)


@router.message(StateFilter(NewFurnitureStates.telegram_contact), F.text)
async def add_furniture_telegram(message: Message, state: FSMContext) -> None:
    telegram = message.text.strip()
    await state.update_data(
        telegram_contact=telegram if telegram != "-" else None,
    )
    await state.set_state(NewFurnitureStates.price)
    await message.answer(
        "💰 Введите цену в рублях целым числом (например 24990;\n"
        "<code>-</code> — оставить без цены):",
    )


@router.message(StateFilter(NewFurnitureStates.price), F.text)
async def add_furniture_price(message: Message, state: FSMContext) -> None:
    raw = message.text.strip().replace(" ", "")
    if raw == "-":
        await state.update_data(price=None)
        await _start_photos_step(message, state)
        return

    try:
        price = int(raw)
    except ValueError:
        await message.answer(
            "Не понял цену. Введите целое число рублей (например 24990) "
            "или <code>-</code>, чтобы пропустить:",
        )
        return
    if price < 0:
        await message.answer("Цена не может быть отрицательной. Попробуйте ещё раз:")
        return

    await state.update_data(price=price)
    await _start_photos_step(message, state)


@router.message(StateFilter(NewFurnitureStates.photos), F.photo)
async def add_furniture_photo(message: Message, state: FSMContext) -> None:
    """Принять одно фото или целый альбом (одним подтверждением, без спама)."""
    photo = message.photo[-1]
    file_path = await _resolve_photo_path(message, photo.file_id)

    media_group_id = getattr(message, "media_group_id", None)
    if media_group_id:
        # Часть альбома: копим и отвечаем один раз по завершении сбора.
        entry = _ALBUM_CACHE.setdefault(
            media_group_id,
            {"task": None, "message": message, "photos": []},
        )
        entry["photos"].append((photo.file_id, file_path))
        if entry["task"] is None:
            entry["task"] = asyncio.create_task(_flush_album(media_group_id, state))
    else:
        # Одиночное фото вне альбома.
        await _store_photos(message, state, [(photo.file_id, file_path)])


async def _resolve_photo_path(message: Message, file_id: str) -> str:
    """Получить путь файла фото в Telegram (не критично, если не удалось)."""
    file_path = None
    try:
        file = await message.bot.get_file(file_id)
        file_path = file.file_path
    except TelegramBadRequest:
        file_path = ""
    return str(file_path or "")


async def _flush_album(media_group_id: str, state: FSMContext) -> None:
    """После короткой паузы обработать собранный альбом одним подтверждением."""
    await asyncio.sleep(_ALBUM_TIMER_DELAY)
    entry = _ALBUM_CACHE.pop(media_group_id, None)
    if entry is None:
        return
    await _store_photos(entry["message"], state, entry["photos"])


async def _store_photos(
    message: Message, state: FSMContext, photo_items: list[tuple[str, str]]
) -> None:
    """Добавить фото в товар с учётом лимита и ответить сводкой."""
    data = await state.get_data()
    photos = list(data.get("photos", []))
    room = MAX_FURNITURE_PHOTOS - len(photos)
    added = photo_items[:room] if room > 0 else []
    photos.extend(added)
    await state.update_data(photos=photos)

    total = len(photos)
    if not added:
        await message.answer(
            f"Фото не добавлены: достигнут лимит {MAX_FURNITURE_PHOTOS}. "
            "Нажмите «Готово, сохранить».",
            reply_markup=photos_menu(),
        )
    elif total >= MAX_FURNITURE_PHOTOS:
        await message.answer(
            f"✅ Добавлено фото: {len(added)} (всего {MAX_FURNITURE_PHOTOS}). "
            "Лимит достигнут. Нажмите «Готово, сохранить».",
            reply_markup=photos_menu(),
        )
    else:
        await message.answer(
            f"✅ Добавлено фото: {len(added)} (всего {total} из {MAX_FURNITURE_PHOTOS}). "
            "Отправьте ещё или нажмите «Готово, сохранить».",
            reply_markup=photos_menu(),
        )


@router.message(StateFilter(NewFurnitureStates.photos))
async def add_furniture_photo_wrong(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте фотографию.")


@router.callback_query(StateFilter(NewFurnitureStates.photos), F.data == "adm:savefurn")
async def add_furniture_save(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message):
        return

    data = await state.get_data()
    product = await create_furniture_with_photos(
        name=str(data["name"]),
        description=data.get("description") or None,
        category_name=str(data["category_name"]),
        category_id=int(data["category_id"]),
        country=data.get("country"),
        subcategory=data.get("subcategory"),
        whatsapp_contact=data.get("whatsapp_contact"),
        telegram_contact=data.get("telegram_contact"),
        price=data.get("price"),
        photos=[(file_id, path) for file_id, path in data.get("photos", [])],
    )

    await state.clear()
    summary = (
        f"✅ <b>Товар №{product.id} сохранён</b>\n\n"
        f"🪑 {escape(str(product.name))}\n"
        f"📦 Категория: {escape(str(product.category_name))}\n"
    )
    if product.subcategory:
        summary += f"📐 Тип: {escape(str(product.subcategory))}\n"
    if product.country:
        summary += f"🌍 Страна: {escape(str(product.country))}\n"
    if product.price is not None:
        summary += f"💰 Цена: {format_price(int(product.price))}\n"
    summary += f"📸 Фотографий: {len(product.photos)}\n\nТовар уже виден покупателям."
    await callback.message.edit_text(summary, reply_markup=back_to_admin_menu())
    await callback.answer()


# Ловим всё, кроме текста, в текстовых состояниях формы товара:
# соответствующие F.text-хендлеры выше уже отработали.
@router.message(
    StateFilter(
        NewFurnitureStates.name,
        NewFurnitureStates.description,
        NewFurnitureStates.whatsapp_contact,
        NewFurnitureStates.telegram_contact,
        NewFurnitureStates.price,
    ),
)
async def furniture_wrong_input_handler(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте ответ текстом.")

