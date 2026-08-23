"""Нормализация и форматирование телефонов покупателей.

Правила согласованы в ADR 0001: разбор и проверка — через phonenumbers
(Google libphonenumber), хранение — только E.164, номера без «+»
интерпретируются как российские (регион по умолчанию RU).
"""
import phonenumbers
from phonenumbers import PhoneNumberFormat

# Регион для номеров без кода страны; продиктован бизнес-контекстом,
# а не ориентацией бота только на Россию.
DEFAULT_REGION = "RU"


def normalize_phone(raw: str) -> str | None:
    """Проверить телефон и вернуть его в E.164, иначе None.

    Локальные форматы трактуются как российские; международные («+…»)
    проверяются по собственному коду страны.
    """
    try:
        number = phonenumbers.parse(raw.strip(), DEFAULT_REGION)
    except phonenumbers.NumberParseException:
        return None
    # Строгая проверка: цена пропущенного некорректного номера выше
    # редкого ложного отказа из-за метаданных библиотеки.
    if not phonenumbers.is_valid_number(number):
        return None
    return phonenumbers.format_number(number, PhoneNumberFormat.E164)


def pretty_phone(stored: str) -> str | None:
    """Человекочитаемый вид сохранённого номера для показа админу.

    Исторические записи могут не разбираться (до ADR 0001 телефон хранился
    как ввели) — тогда возвращаем None, вызывающий покажет строку как есть.
    """
    try:
        number = phonenumbers.parse(stored.strip(), DEFAULT_REGION)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(number):
        return None
    return phonenumbers.format_number(number, PhoneNumberFormat.INTERNATIONAL)
