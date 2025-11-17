"""
Inline клавиатуры (кнопки в сообщениях)
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database.models import db


def get_telephony_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру выбора телефонии (динамическая из БД)
    
    Returns:
        InlineKeyboardMarkup с кнопками телефоний
    """
    telephonies = db.get_all_telephonies()
    
    # Если нет телефоний в БД, показываем старые (совместимость)
    if not telephonies:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("BMW", callback_data="tel_bmw")],
            [InlineKeyboardButton("Звонари", callback_data="tel_zvon")]
        ])
    
    # Создаём кнопки из БД
    buttons = []
    for tel in telephonies:
        buttons.append([
            InlineKeyboardButton(tel['name'], callback_data=f"tel_{tel['code']}")
        ])
    
    return InlineKeyboardMarkup(buttons)


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
    Возвращает клавиатуру с кнопками для саппорта (только для белых телефоний)
    
    Args:
        user_id: ID пользователя
        tel_code: Код телефонии
        
    Returns:
        InlineKeyboardMarkup с кнопками саппорта или None для чёрных
    """
    # Проверяем тип телефонии из БД
    tel = db.get_telephony_by_code(tel_code)
    
    # Если нет в БД, проверяем старые
    if not tel:
        if tel_code != "bmw":
            return None
    else:
        # Если чёрная телефония - без кнопок
        if tel['type'] == 'black':
            return None
    
    # Белая телефония - показываем кнопки
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


# ===== НОВЫЕ КЛАВИАТУРЫ ДЛЯ УПРАВЛЕНИЯ =====

def get_management_menu() -> InlineKeyboardMarkup:
    """Главное меню управления ботом"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Менеджеры", callback_data="mgmt_managers")],
        [InlineKeyboardButton("📞 Телефонии", callback_data="mgmt_telephonies")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="mgmt_broadcast")],
    ])


def get_telephony_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа телефонии"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚪️ Белая (с кнопками саппорта)", callback_data="tel_type_white")],
        [InlineKeyboardButton("⚫️ Чёрная (без кнопок)", callback_data="tel_type_black")]
    ])