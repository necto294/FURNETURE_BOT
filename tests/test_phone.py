"""Тесты нормализации телефона (правила — в ADR 0001).

Номера взяты из шаблонных тестовых данных libphonenumber, а не реальных
людей.
"""
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("BOT_TOKEN", "test-token")

from utils.phone import normalize_phone, pretty_phone


class NormalizePhoneTests(unittest.TestCase):
    def test_russian_trunk_prefix(self) -> None:
        # 8-ка как транковый префикс РФ.
        self.assertEqual(normalize_phone("89001234567"), "+79001234567")

    def test_bare_local_digits(self) -> None:
        # Голые 10 цифр трактуются через регион по умолчанию RU.
        self.assertEqual(normalize_phone("9001234567"), "+79001234567")

    def test_spaces_and_dashes_stripped(self) -> None:
        self.assertEqual(
            normalize_phone("+7 900 123-45-67"), "+79001234567"
        )

    def test_foreign_international_number(self) -> None:
        # Код страны в номере важнее региона по умолчанию.
        self.assertEqual(normalize_phone("+90 555 123 45 67"), "+905551234567")

    def test_foreign_local_format_rejected(self) -> None:
        # Немецкий локальный номер невалиден для RU — просим повторить ввод.
        self.assertIsNone(normalize_phone("0151 23456789"))

    def test_garbage_text_rejected(self) -> None:
        self.assertIsNone(normalize_phone("позвоните мне позже"))

    def test_strict_pattern_check(self) -> None:
        # Длина корректная, но префикса 111 в плане РФ не существует.
        self.assertIsNone(normalize_phone("+7 111 111 11 11"))


class PrettyPhoneTests(unittest.TestCase):
    def test_e164_shown_pretty(self) -> None:
        self.assertEqual(pretty_phone("+79001234567"), "+7 900 123-45-67")

    def test_legacy_record_unparseable(self) -> None:
        # Исторические записи до ADR 0001 могут не разбираться.
        self.assertIsNone(pretty_phone("наберите на городской"))


if __name__ == "__main__":
    unittest.main()
