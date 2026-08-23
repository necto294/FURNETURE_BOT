"""Шов авторизации админ-панели.

Вся проверка прав живёт здесь: хендлеры панельных роутеров не знают о ней
и не дублируют проверки. setup_admin_access навешивает middleware на
родительский роутер, admin_guard доступен напрямую для тестов.
"""
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Router
from aiogram.types import CallbackQuery, Message

from database.crud import get_user_by_telegram_id
from settings.config import ConfigBot

ADMIN_ONLY_TEXT = "⛔ Раздел доступен только администраторам."


async def _is_admin(event: CallbackQuery | Message) -> bool:
    """Админ — если telegram_id из .env или флаг is_admin в базе."""
    from_user = event.from_user
    if from_user is None:
        return False
    if from_user.id in ConfigBot.ADMIN_IDS:
        return True
    user = await get_user_by_telegram_id(from_user.id)
    return user is not None and user.is_admin


async def admin_guard(
    handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
    event: CallbackQuery | Message,
    data: dict[str, Any],
) -> Any:
    """Пропустить событие дальше только администратору."""
    if await _is_admin(event):
        return await handler(event, data)
    if isinstance(event, CallbackQuery):
        await event.answer(ADMIN_ONLY_TEXT, show_alert=True)
    else:
        await event.answer(ADMIN_ONLY_TEXT)
    return None


def setup_admin_access(router: Router) -> None:
    """Защитить все хендлеры роутера и его вложенных роутеров."""
    router.message.outer_middleware(admin_guard)
    router.callback_query.outer_middleware(admin_guard)
