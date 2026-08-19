from typing import List, Tuple
from aiogram.types import (ReplyKeyboardMarkup,
                        KeyboardButton,
                        InlineKeyboardMarkup,
                        InlineKeyboardButton)


def make_row_keyboards(items: List[str]) -> ReplyKeyboardMarkup:
    """
    Create a list of rows of KeyboardButtons from a list of strings.

    :param items: List of strings to create buttons from.
    :return: List of lists, where each inner list represents a row of buttons.
    """

    keyboard = [[KeyboardButton(text=item) for item in items]]

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def make_inline_row_keyboards(items: List[Tuple[str, str]]) -> InlineKeyboardMarkup:
    """
    Create a list of rows of InlineKeyboardButtons from a list of tuples.

    :param items: List of tuples where each tuple contains (text, callback_data).
    :return: InlineKeyboardMarkup object with buttons arranged in rows.
    """

    keyboard = []

    for text, callback_data in items:
        button = InlineKeyboardButton(text=text, callback_data=callback_data)
        keyboard.append([button])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
