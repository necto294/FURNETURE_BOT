"""Поток покупателя по каталогу и управление подкатегориями («Остальные»)."""
import unittest
from contextlib import ExitStack
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
