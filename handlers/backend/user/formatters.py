from html import escape

from database.models import Furniture
from keyboard.user_keyboards import CATEGORY_CONFIG, CATEGORY_ICONS
from settings.config import ConfigBot

from .texts import HTML_SEPARATOR, INSTAGRAM_URL


def format_date(value) -> str:
    """Показать дату добавления в формате день.месяц.год."""
    return value.strftime("%d.%m.%Y") if value else "не указана"


def country_label(country: str) -> str:
    """Добавить флаг к стране, сохранённой в карточке товара."""
    flags = {"Россия": "🇷🇺", "Турция": "🇹🇷"}
    return f"{flags.get(country, '🌍')} {escape(country)}"


def build_product_card(product: Furniture, category_key: str) -> str:
    """Собрать HTML-карточку товара с контактами для заказа."""
    category_name, _ = CATEGORY_CONFIG.get(category_key, (category_key, None))
    category_icon = CATEGORY_ICONS.get(category_key, "🪑")
    description = escape(
        str(product.description)
        if product.description is not None
        else "Описание пока не добавлено."
    )
    details = (
        f"<b>{category_icon} {escape(category_name)}</b>\n"
        f"{HTML_SEPARATOR}\n"
        f"<b>{escape(str(product.name))}</b>\n\n"
        f"{description}\n\n"
    )
    if product.subcategory is not None:
        details += f"📐 Тип мебели: {escape(str(product.subcategory))}\n"
    if product.country is not None:
        details += f"🌍 Страна производства: {country_label(str(product.country))}\n"
    # Контакты берутся из настроек, чтобы администратор мог менять их без кода.
    details += (
        f"📆 Дата добавления: {format_date(product.created_at)}\n"
        f"{HTML_SEPARATOR}\n\n"
        f"📱 WhatsApp: {escape(ConfigBot.WHATSAPP)}\n"
        f"📱 Telegram: {escape(ConfigBot.TELEGRAM)}\n\n"
        "<b>✨ Подписывайтесь на нас в Instagram</b> и будьте в курсе "
        "новинок и акций:\n"
        f"📸 <b>Instagram:</b> <a href=\"{INSTAGRAM_URL}\">{INSTAGRAM_URL}</a>"
    )
    return details
