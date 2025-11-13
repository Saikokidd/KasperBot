"""
Inline клавиатуры (кнопки в сообщениях)
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_telephony_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру выбора телефонии
    
    Returns:
        InlineKeyboardMarkup с кнопками телефоний
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("BMW", callback_data="tel_bmw")],
        [InlineKeyboardButton("Звонари", callback_data="tel_zvon")]
    ])


def get_role_choice_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру выбора роли для админа
    
    Returns:
        InlineKeyboardMarkup с кнопками выбора роли
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👨‍💼 Войти как Менеджер", callback_data="role_manager")],
        [InlineKeyboardButton("👑 Войти как Админ", callback_data="role_admin")]
    ])


def get_support_keyboard(user_id: int, tel_code: str) -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру с кнопками для саппорта (только для BMW)
    
    Args:
        user_id: ID пользователя
        tel_code: Код телефонии
        
    Returns:
        InlineKeyboardMarkup с кнопками саппорта или None для Звонари
    """
    if tel_code != "bmw":
        return None
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Исправлено", callback_data=f"fix_{user_id}_{tel_code}"),
            InlineKeyboardButton("⏱ 2-3 мин", callback_data=f"wait_{user_id}_{tel_code}")
        ],
        [
            InlineKeyboardButton("⚠️ Неверный формат", callback_data=f"wrong_{user_id}_{tel_code}"),
            InlineKeyboardButton("✅ Сим ворк", callback_data=f"sim_{user_id}_{tel_code}")
        ]
    ])
