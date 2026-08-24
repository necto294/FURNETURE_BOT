"""Тесты уведомления покупателя о смене статуса заявки.

Матрица переходов (CONTEXT.md «Уведомление покупателя»): пишем при
переходе в «В работе»/«Выполнена»/«Отменена», молча — при повторе того
же статуса и возврате в «Новую». Заблокированный бот — не ошибка.
"""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("BOT_TOKEN", "test-token")

from aiogram.exceptions import TelegramForbiddenError

from handlers.admin.orders import order_status_handler


class _AnyMessageMeta(type):
    # Заставляем isinstance(x, _AnyMessage) всегда возвращать True.
    def __instancecheck__(cls, instance) -> bool:
        return True


class _AnyMessage(metaclass=_AnyMessageMeta):
    """Заменяет Message в isinstance-проверках обработчиков."""


def make_callback(data: str) -> SimpleNamespace:
    message = SimpleNamespace(
        edit_text=AsyncMock(),
        answer_document=AsyncMock(),
        bot=SimpleNamespace(send_message=AsyncMock()),
    )
    return SimpleNamespace(
        message=message,
        data=data,
        from_user=SimpleNamespace(id=777),
        answer=AsyncMock(),
    )


def make_order(status: str = "new") -> SimpleNamespace:
    """Заявка до обновления: прежний статус + покупатель + товар."""
    return SimpleNamespace(
        id=7,
        status=status,
        user=SimpleNamespace(telegram_id=3001, username="buyer"),
        furniture=SimpleNamespace(name="<Диван>", price=24990),
        customer_name="Иван",
        customer_phone="+70000000000",
        created_at=None,
    )


def patch_orders(full_return, update_return=None):
    return (
        patch("handlers.admin.orders.Message", _AnyMessage),
        patch(
            "handlers.admin.orders.get_order_by_id_full",
            new_callable=AsyncMock,
            return_value=full_return,
        ),
        patch(
            "handlers.admin.orders.update_order_status",
            new_callable=AsyncMock,
            return_value=(
                update_return if update_return is not None else full_return
            ),
        ),
    )


class BuyerNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_transition_to_target_statuses_notifies(self) -> None:
        expected_fragments = {
            "processing": ("🔧", "принята в работу"),
            "completed": ("✅", "выполнена"),
            "cancelled": ("🚫", "отменена"),
        }
        for new_status, (emoji, phrase) in expected_fragments.items():
            with self.subTest(new_status=new_status):
                callback = make_callback(f"adm:ost:7:{new_status}:0")
                patches = patch_orders(make_order(status="new"))
                with patches[0], patches[1], patches[2]:
                    await order_status_handler(callback)

                callback.message.bot.send_message.assert_awaited_once()
                args = callback.message.bot.send_message.await_args.args
                self.assertEqual(args[0], 3001)
                self.assertIn("№7", args[1])
                self.assertIn(emoji, args[1])
                self.assertIn(phrase, args[1])

    async def test_same_status_and_reset_to_new_stay_silent(self) -> None:
        for old_status in ("processing", "completed", "cancelled"):
            with self.subTest(old_status=old_status):
                callback = make_callback(f"adm:ost:7:{old_status}:0")
                patches = patch_orders(make_order(status=old_status))
                with patches[0], patches[1], patches[2]:
                    await order_status_handler(callback)
                callback.message.bot.send_message.assert_not_awaited()

        callback = make_callback("adm:ost:7:new:0")
        patches = patch_orders(make_order(status="completed"))
        with patches[0], patches[1], patches[2]:
            await order_status_handler(callback)
        callback.message.bot.send_message.assert_not_awaited()

    async def test_product_name_is_html_escaped(self) -> None:
        callback = make_callback("adm:ost:7:processing:0")
        patches = patch_orders(make_order(status="new"))
        with patches[0], patches[1], patches[2]:
            await order_status_handler(callback)

        text = callback.message.bot.send_message.await_args.args[1]
        self.assertNotIn("<Диван>", text)
        self.assertIn("&lt;Диван&gt;", text)

    async def test_forbidden_error_is_swallowed(self) -> None:
        # Покупатель заблокировал бота — смена статуса не должна ломаться.
        callback = make_callback("adm:ost:7:completed:0")
        callback.message.bot.send_message = AsyncMock(
            side_effect=TelegramForbiddenError(
                method=SimpleNamespace(), message="bot was blocked by the user"
            )
        )
        patches = patch_orders(make_order(status="new"))
        with patches[0], patches[1], patches[2]:
            await order_status_handler(callback)

        # Карточка всё равно перерисована, статус админу подтверждён.
        callback.message.edit_text.assert_awaited()
        callback.answer.assert_awaited()

    async def test_missing_bot_or_user_does_nothing(self) -> None:
        # У сообщения нет бота (юнит-окружение) — уведомление пропускается.
        callback = make_callback("adm:ost:7:processing:0")
        del callback.message.bot
        patches = patch_orders(make_order(status="new"))
        with patches[0], patches[1], patches[2]:
            await order_status_handler(callback)
        callback.answer.assert_awaited()

        # Заявка без покупателя — отправлять некому.
        callback = make_callback("adm:ost:8:processing:0")
        orphan = make_order()
        orphan.user = None
        orphan.id = 8
        patches = patch_orders(orphan)
        with patches[0], patches[1], patches[2]:
            await order_status_handler(callback)
        callback.message.bot.send_message.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
