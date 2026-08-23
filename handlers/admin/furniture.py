"""Товары в админ-панели: пошаговое добавление и удаление."""
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.crud import (
    create_furniture_with_photos,
    delete_furniture,
    get_categories_with_counts,
    get_category_by_id,
    get_filter_values,
    get_furniture_by_id,
    get_furniture_page,
)
from handlers.backend.user.formatters import format_price
from keyboard.admin_keyboards import (
    ADMIN_PAGE_SIZE,
    admin_main_menu,
    back_to_admin_menu,
    categories_menu,
    confirm_menu,
    countries_menu,
    furniture_list_menu,
    kitchen_types_menu,
    photos_menu,
)
from states.states import NewFurnitureStates
from utils.phone import normalize_phone

from .router import (
    _admin_welcome_text,
    _category_key,
    _filter_type,
    _show_categories_for,
)

router = Router(name="admin_furniture")


# --- Добавление товара ---

async def _start_photos_step(target: Message, state: FSMContext) -> None:
    await state.set_state(NewFurnitureStates.photos)
    await target.answer(
        "📸 Прикрепите фотографии товара.\n"
        "Можно отправить несколько сообщений с фото.\n"
        "Когда закончите — нажмите «Готово, сохранить».",
        reply_markup=photos_menu(),
    )


async def _ask_whatsapp(target: Message, state: FSMContext) -> None:
    await state.set_state(NewFurnitureStates.whatsapp_contact)
    await target.answer(
        "📱 Введите номер WhatsApp для карточки этого товара\n"
        "(например <code>+7 900 123 45 67</code>; <code>-</code> — пропустить):",
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
    filter_type = _filter_type(category_name)
    await state.update_data(
        category_id=category.id,
        category_name=category_name,
        category_key=_category_key(category_name),
    )

    if filter_type == "subcategory":
        types = await get_filter_values(category_name, "subcategory")
        await state.set_state(NewFurnitureStates.kitchen_type)
        await callback.message.edit_text(
            "📐 Выберите тип кухни или отправьте свой вариант текстом:",
            reply_markup=kitchen_types_menu(types),
        )
    elif filter_type == "country":
        await state.set_state(NewFurnitureStates.country)
        await callback.message.edit_text(
            "🌍 Выберите страну производства:",
            reply_markup=countries_menu(),
        )
    else:
        await callback.message.delete()
        await _ask_whatsapp(callback.message, state)
    await callback.answer()


@router.callback_query(StateFilter(NewFurnitureStates.kitchen_type), F.data.startswith("adm:ktype:"))
async def add_furniture_kitchen_type(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message):
        return

    value = callback.data.split(":", 2)[2]
    await state.update_data(subcategory=value)
    await _ask_whatsapp(callback.message, state)
    await callback.answer()


@router.message(StateFilter(NewFurnitureStates.kitchen_type), F.text)
async def add_furniture_kitchen_custom(message: Message, state: FSMContext) -> None:
    # Свой вариант подкатегории появится в фильтрах автоматически.
    value = message.text.strip()
    if not value:
        await message.answer("Тип не может быть пустым. Попробуйте ещё раз:")
        return

    await state.update_data(subcategory=value)
    await _ask_whatsapp(message, state)


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
    # Для показа в каталоге достаточно file_id, путь сохраняем на всякий случай.
    photo = message.photo[-1]
    file_path = None
    try:
        file = await message.bot.get_file(photo.file_id)
        file_path = file.file_path
    except TelegramBadRequest:
        file_path = ""
    if file_path is None:
        file_path = ""

    data = await state.get_data()
    photos = list(data.get("photos", []))
    photos.append((photo.file_id, str(file_path)))
    await state.update_data(photos=photos)

    await message.answer(
        f"✅ Фото добавлено ({len(photos)}). "
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


# --- Удаление товара ---

@router.callback_query(F.data == "adm:delfurn")
async def delete_furniture_start(callback: CallbackQuery) -> None:
    await _show_categories_for(callback, "adm:delfurn")


@router.callback_query(F.data.startswith("adm:delfurn:"))
async def delete_furniture_list(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message):
        return

    # Вход из списка категорий: adm:delfurn:<id>; пагинация:
    # adm:delfurn:<id>:<страница>. Без страницы начинаем с первой.
    parts = callback.data.split(":")
    category_id = parts[2]
    page = max(int(parts[3]), 0) if len(parts) > 3 else 0
    category = await get_category_by_id(int(category_id))
    if category is None:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    products, total = await get_furniture_page(
        category_name=str(category.name),
        page=page,
        page_size=ADMIN_PAGE_SIZE,
    )
    if not products:
        await callback.message.edit_text(
            f"В категории «{escape(str(category.name))}» пока нет товаров.",
            reply_markup=back_to_admin_menu(),
        )
        await callback.answer()
        return

    total_pages = max((total + ADMIN_PAGE_SIZE - 1) // ADMIN_PAGE_SIZE, 1)
    await callback.message.edit_text(
        f"🗑 Товары категории «{escape(str(category.name))}»:\n"
        "Нажмите на товар, чтобы удалить его.",
        reply_markup=furniture_list_menu(products, category.id, page, total_pages),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:delp:"))
async def delete_furniture_confirm(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message):
        return

    _, _, product_id, category_id, page = callback.data.split(":")
    product = await get_furniture_by_id(int(product_id))
    if product is None:
        await callback.answer("Товар не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"❌ Удалить товар <b>{escape(str(product.name))}</b>?\n"
        f"Категория: {escape(str(product.category_name))}.",
        reply_markup=confirm_menu(f"adm:delok:{product.id}:{category_id}:{page}"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:delok:"))
async def delete_furniture_apply(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message):
        return

    _, _, product_id, category_id, page = callback.data.split(":")
    deleted = await delete_furniture(int(product_id))
    await callback.answer(
        "Товар удалён" if deleted else "Товар не найден",
        show_alert=not deleted,
    )
    if not deleted:
        return

    # После удаления возвращаем админа в список той же категории.
    category = await get_category_by_id(int(category_id))
    if category is None:
        await callback.message.edit_text(
            _admin_welcome_text(callback.from_user.first_name),
            reply_markup=admin_main_menu(),
        )
        return
    products, total = await get_furniture_page(
        category_name=str(category.name),
        page=int(page),
        page_size=ADMIN_PAGE_SIZE,
    )
    if not products:
        await callback.message.edit_text(
            f"В категории «{escape(str(category.name))}» больше нет товаров.",
            reply_markup=back_to_admin_menu(),
        )
        return
    total_pages = max((total + ADMIN_PAGE_SIZE - 1) // ADMIN_PAGE_SIZE, 1)
    safe_page = min(int(page), total_pages - 1)
    await callback.message.edit_text(
        f"🗑 Товары категории «{escape(str(category.name))}»:\n"
        "Нажмите на товар, чтобы удалить его.",
        reply_markup=furniture_list_menu(products, category.id, safe_page, total_pages),
    )
