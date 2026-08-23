"""Регрессионный тест: WhatsApp-контакт товара нормализуется как телефон.

Дефект: при добавлении товара шаг WhatsApp принимал любую строку и
сохранял её как есть (товар №2 получил «89288863575» вместо E.164).
Правила телефонов — в ADR 0001.
"""
import os
import sys
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("BOT_TOKEN", "test-token")

from handlers.admin.furniture import add_furniture_whatsapp
from states.states import NewFurnitureStates


def make_state(data: dict | None = None) -> AsyncMock:
    state = AsyncMock()
    state.get_data = AsyncMock(return_value=data or {})
    return state


class _AnyMessageMeta(type):
    def __instancecheck__(cls, instance) -> bool:
        return True


class _AnyMessage(metaclass=_AnyMessageMeta):
    """Заменяет Message в isinstance-проверках обработчиков."""


def patch_message() -> Any:
    # Патчим Message в том модуле, где хендлер его импортировал.
    from unittest import mock

    return mock.patch("handlers.admin.furniture.Message", _AnyMessage)


class WhatsappContactStepTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_number_normalized_to_e164(self) -> None:
        message = SimpleNamespace(text="89288863575", answer=AsyncMock())
        state = make_state()

        with patch_message():
            await add_furniture_whatsapp(message, state)

        state.update_data.assert_awaited_once_with(whatsapp_contact="+79288863575")
        state.set_state.assert_awaited_once_with(NewFurnitureStates.telegram_contact)

    async def test_garbage_reprompts_and_stays_in_state(self) -> None:
        message = SimpleNamespace(text="наберите на городской", answer=AsyncMock())
        state = make_state()

        with patch_message():
            await add_furniture_whatsapp(message, state)

        state.update_data.assert_not_awaited()
        state.set_state.assert_not_awaited()
        self.assertIn("Не удалось распознать", message.answer.await_args.args[0])

    async def test_dash_skips_contact(self) -> None:
        message = SimpleNamespace(text="-", answer=AsyncMock())
        state = make_state()

        with patch_message():
            await add_furniture_whatsapp(message, state)

        state.update_data.assert_awaited_once_with(whatsapp_contact=None)
        state.set_state.assert_awaited_once_with(NewFurnitureStates.telegram_contact)


if __name__ == "__main__":
    unittest.main()
