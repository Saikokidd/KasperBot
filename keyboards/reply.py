"""
keyboards/reply.py (ОЧИЩЕНО)
Телефонии убраны из Reply меню - они теперь только в Inline кнопках

ИЗМЕНЕНИЯ:
✅ get_telephony_menu() УДАЛЕНА (больше не нужна)
✅ Reply меню теперь только для основных действий
"""
from telegram import ReplyKeyboardMarkup, KeyboardButton
from config.constants import MANAGER_MENU, ADMIN_MENU, PULT_MENU


def get_manager_menu() -> ReplyKeyboardMarkup:
    """Генерирует клавиатуру меню для менеджера"""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(text) for text in row] for row in MANAGER_MENU],
        resize_keyboard=True
    )


def get_admin_menu() -> ReplyKeyboardMarkup:
    """Генерирует клавиатуру меню для администратора"""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(text) for text in row] for row in ADMIN_MENU],
        resize_keyboard=True
    )


def get_pult_menu() -> ReplyKeyboardMarkup:
    """Генерирует клавиатуру меню для пульта"""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(text) for text in row] for row in PULT_MENU],
        resize_keyboard=True
    )


def get_menu_by_role(role: str) -> ReplyKeyboardMarkup:
    """
    Возвращает клавиатуру меню в зависимости от роли
    
    Args:
        role: Роль пользователя ("manager", "admin" или "pult")
        
    Returns:
        ReplyKeyboardMarkup соответствующая роли
    """
    if role == "admin":
        return get_admin_menu()
    elif role == "pult":
        return get_pult_menu()
    return get_manager_menu()