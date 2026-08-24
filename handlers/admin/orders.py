import csv
from datetime import datetime, timezone
from html import escape
from io import StringIO

from aiogram import F, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from database.crud import (
    get_all_orders_full,
    get_order_by_id_full,
    get_order_status_counts,
    get_orders_page,
    update_order_status,
)
from handlers.backend.user.formatters import format_price
from handlers.backend.user.texts import HTML_SEPARATOR
from keyboard.admin_keyboards import (
    ADMIN_PAGE_SIZE,
    ORDER_STATUS_CSV_LABELS,
    ORDER_STATUS_LABELS,
    order_card_menu,
    orders_list_menu,
    orders_stats_menu,
)
from utils.phone import pretty_phone

router = Router(name="admin_orders")

# Статусы, которые админ может выставить кнопками в карточке.
VALID_STATUSES = ("new", "processing", "completed", "cancelled")

CSV_HEADERS = ("№", "Дата", "Товар", "Цена", "Имя", "Телефон", "Статус")


def _format_datetime(value) -> str:
    return value.strftime("%d.%m.%Y %H:%M") if value else "не указана"


def _csv_datetime(value) -> str:
    """Дата для колонки «Дата» в CSV; пустая ячейка вместо заглушки."""
    return value.strftime("%d.%m.%Y %H:%M") if value else ""


def _phone_line(order) -> str:
    """Телефон из формы: человекочитаемо + E.164 в <code> для копирования.

    Исторические записи (до нормализации) показываем как есть.
    """
    stored = str(order.customer_phone or "")
    if not stored:
        return "не указан"
    pretty = pretty_phone(stored)
    if pretty is None:
        return escape(stored)
    return f"{escape(pretty)} (<code>{escape(stored)}</code>)"


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
    if order.furniture is not None:
        price = (
            f" (💰 {format_price(order.furniture.price)})"
            if order.furniture.price is not None
            else ""
        )
        product = f"<b>{escape(str(order.furniture.name))}</b>{price}"
    else:
        product = "<i>товар удалён</i>"
    username = "нет"
    if order.user is not None and order.user.username:
        username = f"@{escape(order.user.username)}"

    return (
        f"🧾 <b>Заявка №{order.id}</b>\n"
        f"{HTML_SEPARATOR}\n\n"
        f"🪑 Товар: {product}\n"
        f"👤 Имя: {_customer_line(order)}\n"
        f"📱 Телефон: {_phone_line(order)}\n"
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
    await _show_orders_list(callback, page=0)


@router.callback_query(F.data.startswith("adm:orders:"))
async def orders_page_handler(callback: CallbackQuery) -> None:
    # callback_data вида adm:orders:<страница>.
    await _show_orders_list(callback, page=int(callback.data.split(":")[2]))


@router.callback_query(F.data.startswith("adm:order:"))
async def order_card_handler(callback: CallbackQuery) -> None:
    # callback_data вида adm:order:<id>:<страница>.
    _, _, order_id, page = callback.data.split(":")
    await _show_order_card(callback, int(order_id), int(page))


@router.callback_query(F.data.startswith("adm:ost:"))
async def order_status_handler(callback: CallbackQuery) -> None:
    # callback_data вида adm:ost:<id>:<статус>:<страница>.
    _, _, order_id, new_status, page = callback.data.split(":")
    if new_status not in VALID_STATUSES:
        await callback.answer("Неизвестный статус", show_alert=True)
        return

    # Прежний статус нужен до обновления — по нему решаем, уведомлять ли.
    previous = await get_order_by_id_full(int(order_id))
    updated = await update_order_status(int(order_id), new_status)
    await callback.answer(
        "Статус обновлён" if updated else "Заявка не найдена",
        show_alert=updated is None,
    )
    if updated is None:
        return

    await _show_order_card(callback, int(order_id), int(page))
    # Уведомление — при реальной смене статуса на целевой (CONTEXT.md).
    if (
        previous is not None
        and previous.status != new_status
        and new_status in BUYER_STATUS_MESSAGES
    ):
        bot = getattr(callback.message, "bot", None)
        if bot is not None:
            await _notify_buyer(bot, previous, new_status)


# --- Уведомление покупателя о смене статуса ---

# Покупатель узнаёт о переходе в эти статусы; «Новая» и повтор той же
# метки проходят молча (CONTEXT.md «Уведомление покупателя»).
BUYER_STATUS_MESSAGES = {
    "processing": "🔧 Ваша заявка №{number} «{product}» принята в работу.",
    "completed": "✅ Ваша заявка №{number} «{product}» выполнена.",
    "cancelled": "🚫 Ваша заявка №{number} «{product}» отменена.",
}


async def _notify_buyer(bot, order, new_status: str) -> None:
    """Отправить покупателю одну строку о новом статусе заявки.

    Заблокированный бот — не ошибка: молча пропускаем, как в notify_admins.
    """
    template = BUYER_STATUS_MESSAGES.get(new_status)
    if template is None or order.user is None:
        return
    product = (
        str(order.furniture.name) if order.furniture is not None else "товар удалён"
    )
    text = template.format(number=order.id, product=escape(product))
    try:
        await bot.send_message(order.user.telegram_id, text)
    except TelegramForbiddenError:
        pass


# --- Статистика и экспорт заявок ---

def build_orders_csv(orders: list) -> str:
    """Собрать CSV всей выгрузки: BOM, разделитель «;», CRLF (RFC 4180).

    Телефон уже хранится в E.164 — пишем как есть; статус — русской
    меткой без эмодзи (словарь бота, см. CONTEXT.md).
    """
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(CSV_HEADERS)
    for order in orders:
        furniture_price = (
            int(order.furniture.price)
            if order.furniture is not None and order.furniture.price is not None
            else ""
        )
        writer.writerow(
            [
                order.id,
                _csv_datetime(order.created_at),
                str(order.furniture.name) if order.furniture is not None else "",
                furniture_price,
                str(order.customer_name or ""),
                str(order.customer_phone or ""),
                ORDER_STATUS_CSV_LABELS.get(order.status, order.status),
            ]
        )
    # BOM в начале файла, чтобы Excel распознал UTF-8.
    return "\ufeff" + buffer.getvalue()


def _stats_text(counts: dict[str, int]) -> str:
    """Текст экрана статистики: счётчик на статус плюс итог."""
    total = sum(counts.values())
    lines = "\n".join(
        f"{ORDER_STATUS_LABELS[status]} — <b>{counts.get(status, 0)}</b>"
        for status in VALID_STATUSES
    )
    return (
        f"📊 <b>Статистика заявок</b>\n"
        f"{HTML_SEPARATOR}\n\n"
        f"{lines}\n\n"
        f"Всего: <b>{total}</b>."
    )


@router.callback_query(F.data == "adm:ostats")
async def orders_stats_handler(callback: CallbackQuery) -> None:
    # callback_data вида adm:ostats (без двоеточия — не путается с adm:ost:).
    if not isinstance(callback.message, Message):
        return

    counts = await get_order_status_counts()
    await callback.message.edit_text(
        _stats_text(counts),
        reply_markup=orders_stats_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm:oexport")
async def orders_export_handler(callback: CallbackQuery) -> None:
    # callback_data вида adm:oexport.
    orders = await get_all_orders_full()
    if not orders:
        await callback.answer("Заявок пока нет — экспортировать нечего", show_alert=True)
        return

    content = build_orders_csv(orders)
    filename = f"orders_{datetime.now(tz=timezone.utc).date().isoformat()}.csv"
    document = BufferedInputFile(content.encode("utf-8"), filename=filename)
    if isinstance(callback.message, Message):
        await callback.message.answer_document(
            document,
            caption=f"📨 Выгрузка заявок: <b>{len(orders)}</b>",
        )
    await callback.answer()
