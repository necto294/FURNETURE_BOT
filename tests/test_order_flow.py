import os
import sys
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("BOT_TOKEN", "test-token")

from handlers.backend.order import (
    order_cancel_handler,
    order_confirm_handler,
    order_name_handler,
    order_phone_handler,
    order_start_handler,
)
from states.states import OrderStates


def make_state(data: dict | None = None) -> AsyncMock:
    # Заглушка FSMContext с готовыми данными для сценариев заявки.
    state = AsyncMock()
    state.get_data = AsyncMock(return_value=data or {})
    return state


class _AnyMessageMeta(type):
    # Заставляем isinstance(x, _AnyMessage) всегда возвращать True.
    def __instancecheck__(cls, instance) -> bool:
        return True


class _AnyMessage(metaclass=_AnyMessageMeta):
    """Заменяет Message в isinstance-проверках обработчиков."""


def patch_message() -> Any:
    # Подменяем Message в обработчике, чтобы пройти isinstance-проверку.
    return patch("handlers.backend.order.Message", _AnyMessage)


class OrderFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_asks_for_name(self) -> None:
        message = SimpleNamespace(answer=AsyncMock())
        callback = SimpleNamespace(
            message=message,
            data="order:42",
            answer=AsyncMock(),
        )
        state = make_state()

        with (
            patch_message(),
            patch(
                "handlers.backend.order.get_furniture_by_id", new_callable=AsyncMock
            ) as furniture,
        ):
            furniture.return_value = SimpleNamespace(id=42, name="Диван")
            await order_start_handler(callback, state)

        state.set_state.assert_awaited_once_with(OrderStates.name)
        message.answer.assert_awaited_once()

    async def test_start_ignores_unknown_product(self) -> None:
        message = SimpleNamespace(answer=AsyncMock())
        callback = SimpleNamespace(
            message=message,
            data="order:999",
            answer=AsyncMock(),
        )
        state = make_state()

        with (
            patch_message(),
            patch(
                "handlers.backend.order.get_furniture_by_id", new_callable=AsyncMock
            ) as furniture,
        ):
            furniture.return_value = None
            await order_start_handler(callback, state)

        state.set_state.assert_not_awaited()
        callback.answer.assert_awaited_once_with("Товар не найден", show_alert=True)

    async def test_name_moves_to_phone(self) -> None:
        message = SimpleNamespace(text="  Иван  ", answer=AsyncMock())
        state = make_state()

        await order_name_handler(message, state)

        state.update_data.assert_awaited_once_with(name="Иван")
        state.set_state.assert_awaited_once_with(OrderStates.phone)

    async def test_phone_shows_confirmation(self) -> None:
        message = SimpleNamespace(text="+7 900 123-45-67", answer=AsyncMock())
        state = make_state(
            {"product_id": 42, "product_name": "Диван", "name": "Иван"}
        )

        await order_phone_handler(message, state)

        state.update_data.assert_awaited_once_with(phone="+7 900 123-45-67")
        state.set_state.assert_awaited_once_with(OrderStates.confirm)
        confirmation = message.answer.await_args.args[0]
        self.assertIn("Диван", confirmation)
        self.assertIn("Иван", confirmation)

    async def test_confirm_creates_order(self) -> None:
        callback = SimpleNamespace(
            from_user=SimpleNamespace(
                id=777, username="u", first_name="И", last_name="Т"
            ),
            message=SimpleNamespace(edit_text=AsyncMock()),
            answer=AsyncMock(),
        )
        state = make_state(
            {"product_id": 42, "product_name": "Диван", "name": "Иван", "phone": "+7000"}
        )

        with (
            patch_message(),
            patch("handlers.backend.order.upsert_user", new_callable=AsyncMock) as user,
            patch("handlers.backend.order.create_order", new_callable=AsyncMock) as order,
            patch("handlers.backend.order.get_categories", new_callable=AsyncMock),
            patch("handlers.backend.order.main_menu", return_value="menu"),
        ):
            user.return_value = SimpleNamespace(id="user-1")
            await order_confirm_handler(callback, state)

        order.assert_awaited_once_with(
            user_id="user-1",
            furniture_id=42,
            customer_name="Иван",
            customer_phone="+7000",
        )
        state.clear.assert_awaited_once()
        callback.message.edit_text.assert_awaited_once()

    async def test_cancel_clears_state(self) -> None:
        callback = SimpleNamespace(
            message=SimpleNamespace(edit_text=AsyncMock()),
            answer=AsyncMock(),
        )
        state = make_state()

        with (
            patch_message(),
            patch("handlers.backend.order.back_to_main_menu", return_value="menu"),
        ):
            await order_cancel_handler(callback, state)

        state.clear.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()