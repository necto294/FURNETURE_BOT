import os
import sys
import tempfile
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("BOT_TOKEN", "test-token")

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from database import crud
from database.engine import Base
from database.models import FurniturePhoto
from handlers.admin.furniture import add_furniture_name, add_furniture_save
from handlers.admin.router import admin_menu_command
from states.states import NewFurnitureStates

ADMIN_USER = SimpleNamespace(id="uuid-1", telegram_id=777, is_admin=True)
REGULAR_USER = None


def make_state(data: dict | None = None) -> AsyncMock:
    # Заглушка FSMContext с готовыми данными для сценариев админки.
    state = AsyncMock()
    state.get_data = AsyncMock(return_value=data or {})
    return state


class _AnyMessageMeta(type):
    # Заставляем isinstance(x, _AnyMessage) всегда возвращать True.
    def __instancecheck__(cls, instance) -> bool:
        return True


class _AnyMessage(metaclass=_AnyMessageMeta):
    """Заменяет Message в isinstance-проверках обработчиков."""


class _AnyCallbackQueryMeta(type):
    # Аналог _AnyMessage для CallbackQuery.
    def __instancecheck__(cls, instance) -> bool:
        return True


class _AnyCallbackQuery(metaclass=_AnyCallbackQueryMeta):
    """Заменяет CallbackQuery в isinstance-проверках."""


def patch_admin_message() -> Any:
    # Хендлеры разнесены по модулям, каждый импортирует Message отдельно.
    stack = ExitStack()
    for module in ("router", "categories", "furniture", "subcategories"):
        stack.enter_context(patch(f"handlers.admin.{module}.Message", _AnyMessage))
    return stack


def make_admin_event(data: str = "adm:menu", with_bot: bool = False) -> SimpleNamespace:
    message = SimpleNamespace(
        edit_text=AsyncMock(),
        answer=AsyncMock(),
        delete=AsyncMock(),
    )
    if with_bot:
        message.bot = SimpleNamespace(send_message=AsyncMock())
    return SimpleNamespace(
        message=message,
        data=data,
        from_user=SimpleNamespace(
            id=777,
            username="boss",
            first_name="Ольга",
            last_name="Админова",
        ),
        answer=AsyncMock(),
    )


class AdminCrudTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # mkstemp не открывает файловый объект, поэтому контекст-менеджер не нужен.
        descriptor, path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self._tmp_path = path
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self._tmp_path}")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(
            bind=self.engine, expire_on_commit=False
        )
        self._original_session = crud.AsyncSessionLocal
        crud.AsyncSessionLocal = self.session_factory

    async def asyncTearDown(self) -> None:
        crud.AsyncSessionLocal = self._original_session
        await self.engine.dispose()
        os.unlink(self._tmp_path)

    async def test_create_and_find_category(self) -> None:
        created = await crud.create_category("Шкафы", description="Корпусная мебель")
        found = await crud.get_category_by_name("Шкафы")
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found.id, created.id)
        self.assertIsNone(await crud.get_category_by_name("Кровати"))

    async def test_delete_category_removes_products_and_photos(self) -> None:
        category = await crud.create_category("Спальная мебель")
        await crud.create_furniture_with_photos(
            name="Кровать",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
            country="Россия",
            photos=[("file-1", "photos/file_1.jpg")],
        )

        self.assertTrue(await crud.delete_category(category.id))

        products = await crud.get_furniture_list(str(category.name))
        self.assertEqual(products, [])
        async with self.session_factory() as session:
            remaining = await session.scalar(
                select(func.count()).select_from(FurniturePhoto)
            )
        self.assertEqual(remaining, 0)

    async def test_subcategory_clear_keeps_products(self) -> None:
        category = await crud.create_category("Кухонная мебель")
        for _ in range(2):
            await crud.create_furniture_with_photos(
                name="Гарнитур",
                description=None,
                category_name=str(category.name),
                category_id=category.id,
                subcategory="Прямая",
            )

        items = await crud.get_subcategories_with_counts(str(category.name))
        self.assertEqual(items, [("Прямая", 2)])

        updated = await crud.clear_subcategory(str(category.name), "Прямая")
        self.assertEqual(updated, 2)
        products = await crud.get_furniture_list(str(category.name))
        self.assertEqual(len(products), 2)
        for product in products:
            self.assertIsNone(product.subcategory)

    async def test_delete_furniture_with_photos(self) -> None:
        category = await crud.create_category("Матрасы")
        product = await crud.create_furniture_with_photos(
            name="Матрас Ортопедик",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
            photos=[("file-9", "photos/file_9.jpg")],
        )

        self.assertTrue(await crud.delete_furniture(product.id))
        self.assertIsNone(await crud.get_furniture_by_id(product.id))
        async with self.session_factory() as session:
            remaining = await session.scalar(
                select(func.count()).select_from(FurniturePhoto)
            )
        self.assertEqual(remaining, 0)

    async def test_created_product_photos_available_after_session(self) -> None:
        # Регрессия: после commit сессия закрывается, и ленивая загрузка
        # photos на отсоединённом объекте падала с DetachedInstanceError.
        category = await crud.create_category("Матрасы")
        product = await crud.create_furniture_with_photos(
            name="Матрас Ортопедик",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
            photos=[("file-1", "photos/file_1.jpg"), ("file-2", "photos/file_2.jpg")],
        )

        self.assertEqual(len(product.photos), 2)
        self.assertEqual([photo.file_id for photo in product.photos], ["file-1", "file-2"])


class AdminAccessTests(unittest.IsolatedAsyncioTestCase):
    """Проверки шва авторизации: middleware в handlers.admin.access."""

    async def test_message_denied_for_regular_user(self) -> None:
        from handlers.admin.access import admin_guard

        message = SimpleNamespace(
            from_user=SimpleNamespace(id=1111, username="guest"),
            answer=AsyncMock(),
        )
        handler = AsyncMock(return_value="passed")

        with patch(
            "handlers.admin.access.get_user_by_telegram_id",
            new_callable=AsyncMock,
            return_value=REGULAR_USER,
        ):
            result = await admin_guard(handler, message, {})

        self.assertIsNone(result)
        handler.assert_not_awaited()
        message.answer.assert_awaited_once()
        self.assertIn("администратор", message.answer.await_args.args[0])

    async def test_callback_denied_without_admin_flag(self) -> None:
        from handlers.admin.access import admin_guard

        callback = make_admin_event("adm:addcat")
        handler = AsyncMock()

        with (
            patch(
                "handlers.admin.access.get_user_by_telegram_id",
                new_callable=AsyncMock,
                return_value=REGULAR_USER,
            ),
            # SimpleNamespace не проходит isinstance(event, CallbackQuery),
            # поэтому подменяем класс в модуле access (трюк как с Message).
            patch("handlers.admin.access.CallbackQuery", _AnyCallbackQuery),
        ):
            await admin_guard(handler, callback, {})

        handler.assert_not_awaited()
        callback.answer.assert_awaited_once()
        self.assertTrue(callback.answer.await_args.kwargs.get("show_alert"))

    async def test_db_admin_passes_through(self) -> None:
        # Админ по флагу is_admin в базе проходит дальше без ответа.
        from handlers.admin.access import admin_guard

        event = make_admin_event("adm:addcat")
        handler = AsyncMock(return_value="passed")

        with patch(
            "handlers.admin.access.get_user_by_telegram_id",
            new_callable=AsyncMock,
            return_value=ADMIN_USER,
        ):
            result = await admin_guard(handler, event, {})

        self.assertEqual(result, "passed")
        handler.assert_awaited_once_with(event, {})
        event.answer.assert_not_awaited()

    async def test_env_admin_allowed_without_db_record(self) -> None:
        # Админ из .env получает доступ даже без записи в базе
        # и без похода в базу вообще.
        from handlers.admin.access import admin_guard

        event = make_admin_event("adm:addcat")
        event.from_user.id = 555
        handler = AsyncMock(return_value="passed")

        with (
            patch("handlers.admin.access.ConfigBot.ADMIN_IDS", (555,)),
            patch(
                "handlers.admin.access.get_user_by_telegram_id",
                new_callable=AsyncMock,
                return_value=REGULAR_USER,
            ) as lookup,
        ):
            result = await admin_guard(handler, event, {})

        self.assertEqual(result, "passed")
        lookup.assert_not_awaited()

    async def test_setup_attaches_guard_to_router(self) -> None:
        # Сборка в handlers/admin/__init__.py обязана защищать роутер.
        from aiogram import Router

        from handlers.admin.access import admin_guard, setup_admin_access

        checked = Router(name="test")
        setup_admin_access(checked)
        # outer_middleware — MiddlewareManager, он реализует Sequence.
        self.assertIn(admin_guard, checked.message.outer_middleware)
        self.assertIn(admin_guard, checked.callback_query.outer_middleware)

    async def test_command_shows_menu_for_admin(self) -> None:
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=777, username="boss", first_name="Ольга"),
            answer=AsyncMock(),
        )
        state = AsyncMock()

        with patch(
            "handlers.admin.router.admin_main_menu",
            return_value="menu",
        ):
            await admin_menu_command(message, state)

        state.clear.assert_awaited_once()
        message.answer.assert_awaited_once()
        self.assertIn("Панель администратора", message.answer.await_args.args[0])
        # В приветствии есть инструкция по возможностям панели.
        self.assertIn("Добавить товар", message.answer.await_args.args[0])
        self.assertIn("Подкатегории", message.answer.await_args.args[0])


class AddFurnitureFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_name_moves_to_description(self) -> None:
        message = SimpleNamespace(text="  Диван угловой  ", answer=AsyncMock())
        state = make_state()

        await add_furniture_name(message, state)

        state.update_data.assert_awaited_once_with(name="Диван угловой")
        state.set_state.assert_awaited_once_with(NewFurnitureStates.description)

    async def test_save_creates_product_and_clears_state(self) -> None:
        callback = make_admin_event("adm:savefurn")
        state = make_state(
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
            patch_admin_message(),
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


class OrderNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_confirm_sends_order_to_admins(self) -> None:
        os.environ.setdefault("BOT_TOKEN", "test-token")
        from handlers.backend.order import order_confirm_handler

        bot = SimpleNamespace(send_message=AsyncMock())
        callback = SimpleNamespace(
            from_user=SimpleNamespace(
                id=777, username="buyer", first_name="Иван", last_name="Петров"
            ),
            message=SimpleNamespace(edit_text=AsyncMock(), bot=bot),
            answer=AsyncMock(),
        )
        state = make_state(
            {
                "product_id": 42,
                "product_name": "<Диван>",
                "name": "Иван",
                "phone": "+70000000000",
            }
        )

        with (
            patch("handlers.backend.order.Message", _AnyMessage),
            patch(
                "handlers.backend.order.upsert_user", new_callable=AsyncMock
            ) as upsert,
            patch(
                "handlers.backend.order.create_order", new_callable=AsyncMock
            ) as create_order,
            patch(
                "handlers.backend.order.get_categories", new_callable=AsyncMock
            ),
            patch("handlers.backend.order.main_menu", return_value="menu"),
            patch(
                "handlers.backend.order.get_admin_ids", new_callable=AsyncMock
            ) as admins,
        ):
            upsert.return_value = SimpleNamespace(id="user-1")
            create_order.return_value = SimpleNamespace(id=7)
            admins.return_value = [101, 202]
            with patch("handlers.backend.order.ConfigBot.ADMIN_IDS", (999,)):
                await order_confirm_handler(callback, state)

        # Получают и админ из .env, и админы из базы, без дубликатов.
        self.assertEqual(bot.send_message.await_count, 3)
        notified = [call.args[0] for call in bot.send_message.await_args_list]
        self.assertEqual(notified, [999, 101, 202])
        notification = bot.send_message.await_args_list[0].args[1]
        self.assertIn("№7", notification)
        self.assertIn("+70000000000", notification)
        self.assertIn("@buyer", notification)
        # Пользовательский ввод экранируется в уведомлении.
        self.assertNotIn("<Диван>", notification)
        self.assertIn("&lt;Диван&gt;", notification)


class AdminOrdersTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        descriptor, path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self._tmp_path = path
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self._tmp_path}")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(
            bind=self.engine, expire_on_commit=False
        )
        self._original_session = crud.AsyncSessionLocal
        crud.AsyncSessionLocal = self.session_factory

    async def asyncTearDown(self) -> None:
        crud.AsyncSessionLocal = self._original_session
        await self.engine.dispose()
        os.unlink(self._tmp_path)

    async def _make_order(self) -> tuple[object, object]:
        user = await crud.upsert_user(telegram_id=3001, first_name="Иван")
        category = await crud.create_category("Матрасы")
        product = await crud.create_furniture_with_photos(
            name="Матрас Ортопедик",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
        )
        order = await crud.create_order(
            user_id=user.id,
            furniture_id=product.id,
            customer_name="Иван Петров",
            customer_phone="+70000000000",
        )
        return order, product

    async def test_orders_page_loads_relations(self) -> None:
        await self._make_order()

        orders, total = await crud.get_orders_page()

        self.assertEqual(total, 1)
        self.assertEqual(orders[0].customer_name, "Иван Петров")
        self.assertEqual(orders[0].customer_phone, "+70000000000")
        self.assertEqual(orders[0].furniture.name, "Матрас Ортопедик")
        self.assertEqual(orders[0].user.telegram_id, 3001)
        # Свежие заявки идут первыми.
        self.assertEqual(orders[0].status, "new")

    async def test_status_update_via_crud(self) -> None:
        order, _product = await self._make_order()

        updated = await crud.update_order_status(order.id, "processing")

        assert updated is not None
        self.assertEqual(updated.status, "processing")


class DeleteFurnitureListTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        descriptor, path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self._tmp_path = path
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self._tmp_path}")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(
            bind=self.engine, expire_on_commit=False
        )
        self._original_session = crud.AsyncSessionLocal
        crud.AsyncSessionLocal = self.session_factory

    async def asyncTearDown(self) -> None:
        crud.AsyncSessionLocal = self._original_session
        await self.engine.dispose()
        os.unlink(self._tmp_path)

    async def test_entry_callback_without_page_opens_first_page(self) -> None:
        # Регрессия: кнопка категории шлёт adm:delfurn:<id> без страницы,
        # и разбор падал с «not enough values to unpack».
        from handlers.admin.furniture import delete_furniture_list

        category = await crud.create_category("Матрасы")
        await crud.create_furniture_with_photos(
            name="Матрас Ортопедик",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
            photos=[("file-1", "photos/file_1.jpg")],
        )
        callback = make_admin_event(f"adm:delfurn:{category.id}")

        with patch_admin_message():
            await delete_furniture_list(callback)

        callback.answer.assert_awaited_with()
        # Названия товаров выводятся кнопками списка.
        markup = callback.message.edit_text.await_args.kwargs["reply_markup"]
        buttons = [
            button.text for row in markup.inline_keyboard for button in row
        ]
        self.assertIn("Матрас Ортопедик", buttons)


class OrdersSectionHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_status_change_renders_updated_card(self) -> None:
        from handlers.admin.orders import order_status_handler

        callback = make_admin_event("adm:ost:5:processing:0")
        card = SimpleNamespace(
            id=5,
            status="processing",
            customer_name="Иван",
            customer_phone="+7000",
            created_at=None,
            user=SimpleNamespace(username="buyer"),
            furniture=SimpleNamespace(name="Диван", price=None),
        )

        with (
            patch_admin_message(),
            # orders.py импортирует Message отдельно — патчим и его.
            patch("handlers.admin.orders.Message", _AnyMessage),
            patch(
                "handlers.admin.orders.update_order_status",
                new_callable=AsyncMock,
                return_value=SimpleNamespace(status="processing"),
            ),
            patch(
                "handlers.admin.orders.get_order_by_id_full",
                new_callable=AsyncMock,
                return_value=card,
            ),
        ):
            await order_status_handler(callback)

        # Первый ответ — уведомление об успехе; второй лишь закрывает спиннер.
        first_answer = callback.answer.await_args_list[0]
        self.assertEqual(first_answer.args, ("Статус обновлён",))
        self.assertEqual(first_answer.kwargs, {"show_alert": False})
        text = callback.message.edit_text.await_args.args[0]
        self.assertIn("№5", text)
        self.assertIn("+7000", text)


class SubcategoryViewTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        descriptor, path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self._tmp_path = path
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self._tmp_path}")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(
            bind=self.engine, expire_on_commit=False
        )
        self._original_session = crud.AsyncSessionLocal
        crud.AsyncSessionLocal = self.session_factory

    async def asyncTearDown(self) -> None:
        crud.AsyncSessionLocal = self._original_session
        await self.engine.dispose()
        os.unlink(self._tmp_path)

    async def test_kitchen_shows_guaranteed_types_without_products(self) -> None:
        # Регрессия: у пустой кухни должны быть видны «Прямая» и «Угловая».
        from handlers.admin.subcategories import subcategory_list

        category = await crud.create_category("Кухонная мебель")
        callback = make_admin_event(f"adm:subcat:{category.id}")

        with patch_admin_message():
            await subcategory_list(callback)

        markup = callback.message.edit_text.await_args.kwargs["reply_markup"]
        buttons = [
            button.text for row in markup.inline_keyboard for button in row
        ]
        self.assertIn("Прямая (0)", buttons)
        self.assertIn("Угловая (0)", buttons)


class PriceStepTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_price_saved(self) -> None:
        from handlers.admin.furniture import add_furniture_price

        message = SimpleNamespace(text=" 24 990 ", answer=AsyncMock())
        state = make_state()

        await add_furniture_price(message, state)

        state.update_data.assert_awaited_once_with(price=24990)
        state.set_state.assert_awaited_once_with(NewFurnitureStates.photos)

    async def test_dash_skips_price(self) -> None:
        from handlers.admin.furniture import add_furniture_price

        message = SimpleNamespace(text="-", answer=AsyncMock())
        state = make_state()

        await add_furniture_price(message, state)

        state.update_data.assert_awaited_once_with(price=None)
        state.set_state.assert_awaited_once_with(NewFurnitureStates.photos)

    async def test_garbage_reprompts(self) -> None:
        from handlers.admin.furniture import add_furniture_price

        message = SimpleNamespace(text="дорого", answer=AsyncMock())
        state = make_state()

        await add_furniture_price(message, state)

        state.update_data.assert_not_awaited()
        state.set_state.assert_not_awaited()
        self.assertIn("Не понял цену", message.answer.await_args.args[0])

    async def test_format_price(self) -> None:
        from handlers.backend.user.formatters import format_price

        self.assertEqual(format_price(24990), "24 990 ₽")
        self.assertEqual(format_price(1000), "1 000 ₽")
        self.assertEqual(format_price(None), "не указана")


if __name__ == "__main__":
    unittest.main()
