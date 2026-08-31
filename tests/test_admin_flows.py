"""Сценарные тесты админ-потоков: добавление/удаление товара, подкатегории."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import helpers

from database import crud
from handlers.admin.furniture import add_furniture_name, add_furniture_save
from states.states import NewFurnitureStates


class AddFurnitureFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_name_moves_to_description(self) -> None:
        message = SimpleNamespace(text="  Диван угловой  ", answer=AsyncMock())
        state = helpers.make_state()

        await add_furniture_name(message, state)

        state.update_data.assert_awaited_once_with(name="Диван угловой")
        state.set_state.assert_awaited_once_with(NewFurnitureStates.description)

    async def test_save_creates_product_and_clears_state(self) -> None:
        callback = helpers.make_admin_event("adm:savefurn")
        state = helpers.make_state(
            {
                "name": "Диван угловой",
                "description": "Мягкая мебель",
                "category_id": 3,
                "category_name": "Мягкая мебель",
                "country": "Турция",
                "whatsapp_contact": "+79001234567",
                "telegram_contact": "@shop",
                "price": 24990,
                "photos": [("file-1", "photos/file_1.jpg")],
            }
        )
        saved = SimpleNamespace(
            id=12,
            name="Диван угловой",
            category_name="Мягкая мебель",
            subcategory=None,
            country="Турция",
            price=24990,
            photos=[SimpleNamespace(), SimpleNamespace()],
        )

        with (
            helpers.patch_admin_message(),
            patch(
                "handlers.admin.furniture.create_furniture_with_photos",
                new_callable=AsyncMock,
                return_value=saved,
            ) as create,
        ):
            await add_furniture_save(callback, state)

        create.assert_awaited_once_with(
            name="Диван угловой",
            description="Мягкая мебель",
            category_name="Мягкая мебель",
            category_id=3,
            country="Турция",
            subcategory=None,
            whatsapp_contact="+79001234567",
            telegram_contact="@shop",
            price=24990,
            photos=[("file-1", "photos/file_1.jpg")],
        )
        state.clear.assert_awaited_once()
        summary = callback.message.edit_text.await_args.args[0]
        self.assertIn("№12", summary)
        self.assertIn("Диван угловой", summary)
        # Цена выводится в итоговой сводке.
        self.assertIn("24 990 ₽", summary)


class DeleteFurnitureListTests(helpers.TempDbMixin, unittest.IsolatedAsyncioTestCase):
    async def test_entry_callback_without_page_opens_first_page(self) -> None:
        # Регрессия: кнопка категории шлёт adm:delfurn:<id> без страницы,
        # и разбор падал с «not enough values to unpack».
        from handlers.admin.furniture_delete import delete_furniture_list

        category = await crud.create_category("Матрасы")
        await crud.create_furniture_with_photos(
            name="Матрас Ортопедик",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
            photos=[("file-1", "photos/file_1.jpg")],
        )
        callback = helpers.make_admin_event(f"adm:delfurn:{category.id}")

        with helpers.patch_admin_message():
            await delete_furniture_list(callback)

        callback.answer.assert_awaited_with()
        # Названия товаров выводятся кнопками списка.
        markup = callback.message.edit_text.await_args.kwargs["reply_markup"]
        buttons = [
            button.text for row in markup.inline_keyboard for button in row
        ]
        self.assertIn("Матрас Ортопедик", buttons)


class SubcategoryViewTests(helpers.TempDbMixin, unittest.IsolatedAsyncioTestCase):
    async def test_kitchen_shows_subcategories_and_add(self) -> None:
        # Подкатегории кухни видны в списке панели (в проде сидятся миграцией),
        # рядом всегда есть кнопка добавления.
        from handlers.admin.subcategories import subcategory_list

        category = await crud.create_category("Кухонная мебель")
        await crud.create_subcategory(category.id, "Прямая")
        await crud.create_subcategory(category.id, "Угловая")
        callback = helpers.make_admin_event(f"adm:subcat:{category.id}")

        with helpers.patch_admin_message():
            await subcategory_list(callback)

        markup = callback.message.edit_text.await_args.kwargs["reply_markup"]
        buttons = [
            button.text for row in markup.inline_keyboard for button in row
        ]
        self.assertIn("Прямая (0)", buttons)
        self.assertIn("Угловая (0)", buttons)
        self.assertIn("➕ Добавить подкатегорию", buttons)


class PriceStepTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_price_saved(self) -> None:
        from handlers.admin.furniture import add_furniture_price

        message = SimpleNamespace(text=" 24 990 ", answer=AsyncMock())
        state = helpers.make_state()

        await add_furniture_price(message, state)

        state.update_data.assert_awaited_once_with(price=24990)
        state.set_state.assert_awaited_once_with(NewFurnitureStates.photos)

    async def test_dash_skips_price(self) -> None:
        from handlers.admin.furniture import add_furniture_price

        message = SimpleNamespace(text="-", answer=AsyncMock())
        state = helpers.make_state()

        await add_furniture_price(message, state)

        state.update_data.assert_awaited_once_with(price=None)
        state.set_state.assert_awaited_once_with(NewFurnitureStates.photos)

    async def test_garbage_reprompts(self) -> None:
        from handlers.admin.furniture import add_furniture_price

        message = SimpleNamespace(text="дорого", answer=AsyncMock())
        state = helpers.make_state()

        await add_furniture_price(message, state)

        state.update_data.assert_not_awaited()
        state.set_state.assert_not_awaited()
        self.assertIn("Не понял цену", message.answer.await_args.args[0])

    async def test_format_price(self) -> None:
        from handlers.backend.user.formatters import format_price

        self.assertEqual(format_price(24990), "24 990 ₽")
        self.assertEqual(format_price(1000), "1 000 ₽")
        self.assertEqual(format_price(None), "не указана")


class AddFurniturePhotoTests(unittest.IsolatedAsyncioTestCase):
    """Одиночное фото, альбом одним подтверждением и лимит 10."""

    def _photo_message(self, file_id: str = "f1", media_group_id: str | None = None):
        photo = SimpleNamespace(file_id=file_id)
        bot = SimpleNamespace(
            get_file=AsyncMock(return_value=SimpleNamespace(file_path=f"photos/{file_id}.jpg"))
        )
        return SimpleNamespace(
            photo=[photo],
            bot=bot,
            media_group_id=media_group_id,
            answer=AsyncMock(),
        )

    async def test_single_photo_added_with_confirmation(self) -> None:
        from handlers.admin.furniture import add_furniture_photo

        message = self._photo_message("f1")
        state = helpers.make_state()

        await add_furniture_photo(message, state)

        state.update_data.assert_awaited_once_with(
            photos=[("f1", "photos/f1.jpg")]
        )
        text = message.answer.await_args.args[0]
        self.assertIn("Добавлено фото: 1", text)
        self.assertIn("из 10", text)

    async def test_album_stores_all_photos_in_one_confirmation(self) -> None:
        from handlers.admin.furniture import _store_photos

        message = self._photo_message()
        state = helpers.make_state()

        items = [("f1", "p1.jpg"), ("f2", "p2.jpg"), ("f3", "p3.jpg")]
        await _store_photos(message, state, items)

        state.update_data.assert_awaited_once_with(photos=items)
        text = message.answer.await_args.args[0]
        self.assertIn("Добавлено фото: 3", text)

    async def test_photo_limit_enforced(self) -> None:
        from handlers.admin.furniture import _store_photos

        message = self._photo_message()
        state = helpers.make_state(
            {"photos": [(f"x{i}", f"p{i}.jpg") for i in range(9)]}
        )

        # Шлём 3, но влезает только 1 (до лимита 10).
        await _store_photos(message, state, [("a", "a.jpg"), ("b", "b.jpg"), ("c", "c.jpg")])

        photos = state.update_data.await_args.kwargs["photos"]
        self.assertEqual(len(photos), 10)
        text = message.answer.await_args.args[0]
        self.assertIn("Лимит достигнут", text)

    async def test_photo_limit_reached_stops_accepting(self) -> None:
        from handlers.admin.furniture import _store_photos

        message = self._photo_message()
        state = helpers.make_state(
            {"photos": [(f"x{i}", f"p{i}.jpg") for i in range(10)]}
        )

        await _store_photos(message, state, [("a", "a.jpg")])

        photos = state.update_data.await_args.kwargs["photos"]
        self.assertEqual(len(photos), 10)
        text = message.answer.await_args.args[0]
        self.assertIn("не добавлены", text)


if __name__ == "__main__":
    unittest.main()
