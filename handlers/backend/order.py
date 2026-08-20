from html import escape

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import CallbackQuery, Message

from database.crud import create_order, get_categories, get_furniture_by_id, upsert_user
from keyboard.user_keyboards import (
    back_to_main_menu,
    cancel_order_menu,
    main_menu,
    order_confirmation_menu,
)
from states.states import OrderStates

router = Router(name="user_order")

# Регистрация заявки из карточки товара: id товара берётся из callback-кнопки.
@router.callback_query(F.data.regexp(r"^order:\d+$"), StateFilter(default_state))
async def order_start_handler(callback: CallbackQuery, state: FSMContext) -> None:
    # Кнопка заявки есть в карточке товара; сохраняем товар для подтверждения.
    if not isinstance(callback.message, Message) or callback.data is None:
        return

    product_id = int(callback.data.split(":", 1)[1])
    product = await get_furniture_by_id(product_id)
    if product is None:
        await callback.answer("Товар не найден", show_alert=True)
        return

    # Товар храним в FSM-контексте, чтобы показать его в подтверждении.
    await state.update_data(product_id=product.id, product_name=product.name)
    await state.set_state(OrderStates.name)
    await callback.message.answer(
        "📝 <b>Оформление заявки</b>\n\n"
        "Пожалуйста, введите ваше имя:",
        reply_markup=cancel_order_menu(),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^order:\d+$"))
async def order_already_started_handler(callback: CallbackQuery) -> None:
    # Повторный клик по заявке, пока старая ещё не завершена.
    await callback.answer("Сначала завершите текущую заявку", show_alert=True)


# Обработчик отрабатывает только в состоянии ввода имени.
@router.message(StateFilter(OrderStates.name), F.text)
async def order_name_handler(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await message.answer(
            "Имя не может быть пустым. Пожалуйста, введите ваше имя:",
            reply_markup=cancel_order_menu(),
        )
        return

    await state.update_data(name=name)
    await state.set_state(OrderStates.phone)
    await message.answer(
        "📱 Теперь введите ваш номер телефона:",
        reply_markup=cancel_order_menu(),
    )


# После телефона показываем сводку заявки и просим подтвердить.
@router.message(StateFilter(OrderStates.phone), F.text)
async def order_phone_handler(message: Message, state: FSMContext) -> None:
    phone = message.text.strip()
    if not phone:
        await message.answer(
            "Номер не может быть пустым. Пожалуйста, введите ваш номер телефона:",
            reply_markup=cancel_order_menu(),
        )
        return

    data = await state.get_data()
    await state.update_data(phone=phone)
    await state.set_state(OrderStates.confirm)
    await message.answer(
        f"<b>Проверьте данные заявки:</b>\n\n"
        f"🪑 Товар: <b>{escape(str(data['product_name']))}</b>\n"
        f"👤 Имя: {escape(data['name'])}\n"
        f"📱 Телефон: {escape(phone)}\n\n"
        "Всё верно?",
        reply_markup=order_confirmation_menu(),
    )


@router.message(StateFilter(OrderStates.name, OrderStates.phone))
async def order_wrong_input_handler(message: Message) -> None:
    await message.answer(
        "Пожалуйста, отправьте ответ текстом.",
        reply_markup=cancel_order_menu(),
    )


# Подтверждение создаёт запись в orders и сбрасывает FSM.
@router.callback_query(F.data == "order:confirm", StateFilter(OrderStates.confirm))
async def order_confirm_handler(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message):
        return

    data = await state.get_data()
    # Гарантируем, что у посетителя есть запись в users для внешнего ключа заявки.
    user = await upsert_user(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
    )
    await create_order(user_id=user.id, furniture_id=int(data["product_id"]))

    await state.clear()
    await callback.message.edit_text(
        "✅ <b>Заявка успешно отправлена!</b>\n\n"
        f"🪑 Товар: <b>{escape(str(data['product_name']))}</b>\n"
        f"👤 Имя: {escape(data['name'])}\n"
        f"📱 Телефон: {escape(data['phone'])}\n\n"
        "Мы свяжемся с вами в ближайшее время.",
        reply_markup=main_menu(await get_categories()),
    )
    await callback.answer()


# Отмена доступна в любом состоянии заявки и очищает контекст.
@router.callback_query(F.data == "order:cancel")
async def order_cancel_handler(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message):
        return

    await state.clear()
    await callback.message.edit_text(
        "❌ Оформление заявки отменено.\n"
        "Если передумаете — вы всегда можете вернуться в каталог.",
        reply_markup=back_to_main_menu(),
    )
    await callback.answer()