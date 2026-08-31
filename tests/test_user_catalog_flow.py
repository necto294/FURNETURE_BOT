"""Поток покупателя по каталогу и управление подкатегориями («Остальные»)."""
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import helpers

from database import crud
from database.crud_catalog import OTHERS_SUBCATEGORY


def _content(callback) -> str:
    return callback.message.edit_text.await_args.args[0]


def _patch_messages():
    stack = ExitStack()
    stack.enter_context(patch("handlers.backend.user.router.Message", helpers._AnyMessage))
    stack.enter_context(patch("handlers.backend.user.views.Message", helpers._AnyMessage))
    return stack


class CategoryFlowTests(helpers.TempDbMixin, unittest.IsolatedAsyncioTestCase):
    async def test_category_with_subcategories_shows_subcategory_menu(self) -> None:
        from handlers.backend.user.router import category_handler

        category = await crud.create_category("Кухонная мебель")
        await crud.create_subcategory(category.id, "Прямая")
        await crud.create_subcategory(category.id, "Угловая")
        callback = helpers.make_admin_event(f"category:{category.id}")

        with _patch_messages():
            await category_handler(callback)

        markup = callback.message.edit_text.await_args.kwargs["reply_markup"]
        buttons = [b.text for row in markup.inline_keyboard for b in row]
        self.assertIn("📐 Прямая", buttons)
        self.assertIn("📐 Угловая", buttons)

    async def test_category_without_subcategories_shows_country(self) -> None:
        from handlers.backend.user.router import category_handler

        category = await crud.create_category("Матрасы")
        await crud.create_furniture_with_photos(
            name="Матрас",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
            country="Россия",
        )
        callback = helpers.make_admin_event(f"category:{category.id}")

        with _patch_messages():
            await category_handler(callback)

        self.assertIn("Выберите страну производства", _content(callback))
        markup = callback.message.edit_text.await_args.kwargs["reply_markup"]
        buttons = [b.text for row in markup.inline_keyboard for b in row]
        self.assertIn("🇷🇺 Россия", buttons)

    async def test_deleted_subcategory_shows_others_button(self) -> None:
        from handlers.backend.user.router import category_handler

        category = await crud.create_category("Кухонная мебель")
        keep = await crud.create_subcategory(category.id, "Прямая")
        removed = await crud.create_subcategory(category.id, "Угловая")
        await crud.create_furniture_with_photos(
            name="Гарнитур-А",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
            subcategory="Прямая",
            country="Россия",
        )
        await crud.create_furniture_with_photos(
            name="Гарнитур-Б",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
            subcategory="Угловая",
            country="Турция",
        )
        await crud.delete_subcategory(removed.id)

        callback = helpers.make_admin_event(f"category:{category.id}")

        with _patch_messages():
            await category_handler(callback)

        markup = callback.message.edit_text.await_args.kwargs["reply_markup"]
        buttons = [b.text for row in markup.inline_keyboard for b in row]
        # Осталась активная подкатегория, товар удалённой ушёл в «Остальные».
        self.assertIn("📐 Прямая", buttons)
        self.assertNotIn("📐 Угловая", buttons)
        self.assertIn("🗂 Остальные (1)", buttons)


class OthersCrudTests(helpers.TempDbMixin, unittest.IsolatedAsyncioTestCase):
    async def test_others_contains_deleted_and_unlabeled_products(self) -> None:
        category = await crud.create_category("Кухонная мебель")
        active = await crud.create_subcategory(category.id, "Прямая")
        removed = await crud.create_subcategory(category.id, "Угловая")
        await crud.create_furniture_with_photos(
            name="В активной",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
            subcategory="Прямая",
            country="Россия",
        )
        await crud.create_furniture_with_photos(
            name="В удалённой",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
            subcategory="Угловая",
            country="Россия",
        )
        await crud.create_furniture_with_photos(
            name="Без метки",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
            country="Турция",
        )
        await crud.delete_subcategory(removed.id)

        # «Остальные» — товары удалённой подкатегории и без метки.
        others, total = await crud.get_furniture_page(
            category_name=str(category.name),
            subcategory=OTHERS_SUBCATEGORY,
        )
        names = {p.name for p in others}
        self.assertEqual({"В удалённой", "Без метки"}, names)
        self.assertEqual(total, 2)

        # В активной подкатегории остаётся только свой товар.
        active_products, active_total = await crud.get_furniture_page(
            category_name=str(category.name),
            subcategory="Прямая",
        )
        self.assertEqual([p.name for p in active_products], ["В активной"])
        self.assertEqual(active_total, 1)

    async def test_delete_subcategory_removes_row_and_moves_products(self) -> None:
        category = await crud.create_category("Кухонная мебель")
        sub = await crud.create_subcategory(category.id, "Угловая")
        await crud.create_furniture_with_photos(
            name="Гарнитур",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
            subcategory="Угловая",
        )

        affected = await crud.delete_subcategory(sub.id)
        self.assertEqual(affected, 1)

        # Товар на месте и перенесён в «Остальные» (метка стёрта).
        products = await crud.get_furniture_list(str(category.name))
        self.assertEqual(len(products), 1)
        self.assertIsNone(products[0].subcategory)

        # Сама запись подкатегории полностью удалена из списка.
        items = await crud.get_subcategories_with_counts(str(category.name))
        self.assertEqual(items, [])

        # Раздел «Остальные» теперь содержит перенесённый товар.
        others, total = await crud.get_furniture_page(
            category_name=str(category.name),
            subcategory=OTHERS_SUBCATEGORY,
        )
        self.assertEqual([p.name for p in others], ["Гарнитур"])
        self.assertEqual(total, 1)

    async def test_recreate_subcategory_after_delete_creates_new_row(self) -> None:
        category = await crud.create_category("Кухонная мебель")
        sub = await crud.create_subcategory(category.id, "Угловая")
        await crud.delete_subcategory(sub.id)

        # После полного удаления записи больше нет.
        self.assertIsNone(await crud.get_subcategory_by_id(sub.id))

        # Новое создание даёт активную запись (единственную в категории).
        again = await crud.create_subcategory(category.id, "Угловая")
        self.assertEqual(again.name, "Угловая")
        items = await crud.get_subcategories_with_counts(str(category.name))
        self.assertEqual(items, [(again.id, "Угловая", 0)])

    async def test_country_values_for_others(self) -> None:
        category = await crud.create_category("Кухонная мебель")
        removed = await crud.create_subcategory(category.id, "Угловая")
        await crud.create_furniture_with_photos(
            name="Гарнитур",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
            subcategory="Угловая",
            country="Россия",
        )
        await crud.delete_subcategory(removed.id)

        countries = await crud.get_country_values(str(category.name), OTHERS_SUBCATEGORY)
        self.assertIn("Россия", countries)


class ProductCardBackTests(helpers.TempDbMixin, unittest.IsolatedAsyncioTestCase):
    """Карточка товара: альбом+карточка отдельными сообщениями, возврат без дублей."""

    def _patch_messages(self) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(
            patch("handlers.backend.user.router.Message", helpers._AnyMessage)
        )
        stack.enter_context(
            patch("handlers.backend.user.router.CallbackQuery", helpers._AnyCallbackQuery)
        )
        return stack

    async def _make_product(self):
        category = await crud.create_category("Матрасы")
        product = await crud.create_furniture_with_photos(
            name="Матрас",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
            country="Россия",
            photos=[("f1", "p1.jpg"), ("f2", "p2.jpg")],
        )
        return product

    def _state_with_card(self):
        state = AsyncMock()
        state.get_data = AsyncMock(
            return_value={
                "product_list_msg_id": 100,
                "product_photo_msg_ids": [55, 56],
                "product_card_msg_id": 99,
            }
        )
        return state

    async def test_product_card_sends_album_then_card_and_stores_ids(self) -> None:
        from handlers.backend.user.router import product_handler

        product = await self._make_product()
        bot = SimpleNamespace(
            send_media_group=AsyncMock(
                return_value=[
                    SimpleNamespace(message_id=55),
                    SimpleNamespace(message_id=56),
                ]
            ),
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=99)),
        )
        message = SimpleNamespace(chat=SimpleNamespace(id=-100), message_id=100)
        callback = SimpleNamespace(
            message=message,
            data=f"product:{product.id}:mattresses:\u041f\u0440\u044f\u043c\u0430\u044f:\u0420\u043e\u0441\u0441\u0438\u044f:0",
            bot=bot,
            answer=AsyncMock(),
        )
        state = helpers.make_state({})
        with self._patch_messages():
            await product_handler(callback, state)

        # Альбом с фото отправляется первым, карточка — вторым.
        self.assertEqual(bot.send_media_group.await_args.args[0], -100)
        self.assertTrue(bot.send_media_group.await_args.args[1])
        self.assertTrue(bot.send_message.await_args.kwargs["reply_markup"])

        # В state сохранены id всех фото, карточки и списка для удаления при возврате.
        updates = {
            k: v for call in state.update_data.await_args_list for k, v in call.kwargs.items()
        }
        self.assertEqual(updates["product_list_msg_id"], 100)
        self.assertEqual(updates["product_photo_msg_ids"], [55, 56])
        self.assertEqual(updates["product_card_msg_id"], 99)

    async def test_back_to_list_deletes_photo_and_card_without_duplicating(self) -> None:
        from handlers.backend.user.router import page_handler

        bot = SimpleNamespace(delete_message=AsyncMock())
        message = SimpleNamespace(chat=SimpleNamespace(id=-100), edit_text=AsyncMock())
        callback = SimpleNamespace(
            message=message,
            data="page:mattresses:0:\u041f\u0440\u044f\u043c\u0430\u044f:\u0420\u043e\u0441\u0441\u0438\u044f",
            bot=bot,
            answer=AsyncMock(),
        )
        state = self._state_with_card()
        with (
            self._patch_messages(),
            patch(
                "handlers.backend.user.router.show_products",
                new_callable=AsyncMock,
            ) as show,
        ):
            await page_handler(callback, state)

        # Удалены оба фото и карточка; список НЕ пересоздаётся (нет дублей).
        self.assertEqual(bot.delete_message.await_count, 3)
        bot.delete_message.assert_any_await(-100, 55)
        bot.delete_message.assert_any_await(-100, 56)
        bot.delete_message.assert_any_await(-100, 99)
        show.assert_not_awaited()

    async def test_page_flip_keeps_photo_and_shows_products(self) -> None:
        from handlers.backend.user.router import page_handler

        bot = SimpleNamespace(delete_message=AsyncMock())
        message = SimpleNamespace(chat=SimpleNamespace(id=-100), edit_text=AsyncMock())
        callback = SimpleNamespace(
            message=message,
            data="page:mattresses:0:\u041f\u0440\u044f\u043c\u0430\u044f:\u0420\u043e\u0441\u0441\u0438\u044f",
            bot=bot,
            answer=AsyncMock(),
        )
        state = AsyncMock()
        state.get_data = AsyncMock(return_value={})
        with (
            self._patch_messages(),
            patch(
                "handlers.backend.user.router.show_products",
                new_callable=AsyncMock,
            ) as show,
        ):
            await page_handler(callback, state)

        show.assert_awaited_once()
        bot.delete_message.assert_not_awaited()

    async def test_back_to_main_deletes_photo_and_card(self) -> None:
        from handlers.backend.user.router import back_to_main_handler

        bot = SimpleNamespace(delete_message=AsyncMock())
        message = SimpleNamespace(
            chat=SimpleNamespace(id=-100), edit_text=AsyncMock(), answer=AsyncMock()
        )
        callback = SimpleNamespace(
            message=message,
            data="back:main",
            bot=bot,
            answer=AsyncMock(),
        )
        state = self._state_with_card()
        with (
            self._patch_messages(),
            patch("handlers.backend.user.router.main_menu", return_value=[]),
            patch(
                "handlers.backend.user.router.get_categories",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            await back_to_main_handler(callback, state)

        self.assertEqual(bot.delete_message.await_count, 4)
        bot.delete_message.assert_any_await(-100, 55)
        bot.delete_message.assert_any_await(-100, 56)
        bot.delete_message.assert_any_await(-100, 99)
        bot.delete_message.assert_any_await(-100, 100)
        # Меню отправляется новым сообщением, карточка не редактируется.
        message.answer.assert_awaited_once()
        message.edit_text.assert_not_awaited()

    async def test_back_to_main_from_list_edits_message(self) -> None:
        from handlers.backend.user.router import back_to_main_handler

        bot = SimpleNamespace(delete_message=AsyncMock())
        message = SimpleNamespace(
            chat=SimpleNamespace(id=-100), edit_text=AsyncMock(), answer=AsyncMock()
        )
        callback = SimpleNamespace(
            message=message,
            data="back:main",
            bot=bot,
            answer=AsyncMock(),
        )
        state = AsyncMock()
        state.get_data = AsyncMock(return_value={})
        with (
            self._patch_messages(),
            patch("handlers.backend.user.router.main_menu", return_value=[]),
            patch(
                "handlers.backend.user.router.get_categories",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            await back_to_main_handler(callback, state)

        message.edit_text.assert_awaited_once()
        bot.delete_message.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
