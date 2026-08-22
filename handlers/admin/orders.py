from html import escape

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from database.crud import (
    get_order_by_id_full,
    get_orders_page,
    update_order_status,
)
from handlers.backend.user.texts import HTML_SEPARATOR
from keyboard.admin_keyboards import (
    ADMIN_PAGE_SIZE,
    ORDER_STATUS_LABELS,
    order_card_menu,
    orders_list_menu,
)

from .router import _is_admin

router = Router(name="admin_orders")

# Статусы, которые админ может выставить кнопками в карточке.
VALID_STATUSES = ("new", "processing", "completed", "cancelled")


def _format_datetime(value) -> str:
    return value.strftime("%d.%m.%Y %H:%M") if value else "не указана"


def _customer_line(order) -> str:
    """Имя из формы заявки; для старых заявок — профиль Telegram."""
    if order.customer_name:
        return escape(order.customer_name)
    user = order.user
    if user is not None and (user.first_name or user.last_name):
        parts = [str(user.first_name or ""), str(user.last_name or "")]
        return escape(" ".join(part for part in parts if part))
    return "не указано"


def _order_card_text(order) -> str:
    """Собрать карточку заявки для администратора."""
    status = ORDER_STATUS_LABELS.get(order.status, order.status)
    product = (
        f"<b>{escape(str(order.furniture.name))}</b>"
        if order.furniture is not None
        else "<i>товар удалён</i>"
    )
    username = "нет"
    if order.user is not None and order.user.username:
        username = f"@{escape(order.user.username)}"

    return (
        f"🧾 <b>Заявка №{order.id}</b>\n"
        f"{HTML_SEPARATOR}\n\n"
        f"🪑 Товар: {product}\n"
        f"👤 Имя: {_customer_line(order)}\n"
        f"📱 Телефон: {escape(str(order.customer_phone or 'не указан'))}\n"
        f"💬 Telegram: {username}\n"
        f"📆 Создана: {_format_datetime(order.created_at)}\n"
        f"{HTML_SEPARATOR}\n"
        f"Статус: <b>{status}</b>\n\n"
        "Смените статус кнопкой ниже 👇"
    )


async def _show_orders_list(callback: CallbackQuery, page: int) -> None:
    """Отрисовать постраничный список последних заявок."""
    if not isinstance(callback.message, Message):
        return

    orders, total = await get_orders_page(page=page, page_size=ADMIN_PAGE_SIZE)
    total_pages = max((total + ADMIN_PAGE_SIZE - 1) // ADMIN_PAGE_SIZE, 1)
    safe_page = min(max(page, 0), total_pages - 1)

    text = (
        f"📨 <b>Заявки покупателей</b>\nВсего: <b>{total}</b>.\n\nВыберите заявку:"
        if orders
        else "📭 Заявок пока нет.\n\nЗдесь появятся заказы после подтверждения покупателем."
    )
    await callback.message.edit_text(
        text,
        reply_markup=orders_list_menu(orders, safe_page, total_pages),
    )
    await callback.answer()


async def _show_order_card(callback: CallbackQuery, order_id: int, page: int) -> None:
    """Отрисовать карточку заявки с кнопками смены статуса."""
    if not isinstance(callback.message, Message):
        return

    order = await get_order_by_id_full(order_id)
    if order is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    await callback.message.edit_text(
        _order_card_text(order),
        reply_markup=order_card_menu(order.id, order.status, page),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:orders")
async def orders_start_handler(callback: CallbackQuery) -> None:
    if not await _is_admin(callback):
        await callback.answer("⛔ Раздел доступен только администраторам.", show_alert=True)
        return
    await _show_orders_list(callback, page=0)


@router.callback_query(F.data.startswith("adm:orders:"))
async def orders_page_handler(callback: CallbackQuery) -> None:
    if not await _is_admin(callback):
        await callback.answer("⛔ Раздел доступен только администраторам.", show_alert=True)
        return
    # callback_data вида adm:orders:<страница>.
    await _show_orders_list(callback, page=int(callback.data.split(":")[2]))


@router.callback_query(F.data.startswith("adm:order:"))
async def order_card_handler(callback: CallbackQuery) -> None:
    if not await _is_admin(callback):
        await callback.answer("⛔ Раздел доступен только администраторам.", show_alert=True)
        return
    # callback_data вида adm:order:<id>:<страница>.
    _, _, order_id, page = callback.data.split(":")
    await _show_order_card(callback, int(order_id), int(page))


@router.callback_query(F.data.startswith("adm:ost:"))
async def order_status_handler(callback: CallbackQuery) -> None:
    if not await _is_admin(callback):
        await callback.answer("⛔ Раздел доступен только администраторам.", show_alert=True)
        return
    # callback_data вида adm:ost:<id>:<статус>:<страница>.
    _, _, order_id, new_status, page = callback.data.split(":")
    if new_status not in VALID_STATUSES:
        await callback.answer("Неизвестный статус", show_alert=True)
        return

    updated = await update_order_status(int(order_id), new_status)
    await callback.answer(
        "Статус обновлён" if updated else "Заявка не найдена",
        show_alert=updated is None,
    )
    if updated is not None:
        await _show_order_card(callback, int(order_id), int(page))
