"""
ИСПРАВЛЕНО: keyboards/reply.py
Динамическое меню телефоний из БД

ИЗМЕНЕНИЯ:
✅ get_telephony_menu() теперь читает из БД
✅ Fallback на хардкод если БД недоступна
✅ Автоматически показывает все активные телефонии
"""
from telegram import ReplyKeyboardMarkup, KeyboardButton
from config.constants import MANAGER_MENU, ADMIN_MENU, PULT_MENU
from database.models import db
from utils.logger import logger


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


def get_telephony_menu() -> ReplyKeyboardMarkup:
    """
    ✅ ИСПРАВЛЕНО: Генерирует клавиатуру выбора телефонии ДИНАМИЧЕСКИ из БД
    
    Returns:
        ReplyKeyboardMarkup с кнопками телефоний + Меню
    """
    try:
        # Получаем все активные телефонии из БД
        telephonies = db.get_all_telephonies()
        
        if not telephonies:
            # Fallback на хардкод если БД пустая
            logger.warning("⚠️ БД телефоний пустая, используем хардкод")
            from config.constants import TELEPHONY_MENU
            return ReplyKeyboardMarkup(
                [[KeyboardButton(text) for text in row] for row in TELEPHONY_MENU],
                resize_keyboard=True
            )
        
        # Формируем кнопки из БД
        buttons = []
        
        # Группируем по 2 кнопки в ряд (или по 3, если много)
        row = []
        for tel in telephonies:
            row.append(KeyboardButton(tel['name']))
            
            # Если накопилось 2 кнопки → добавляем ряд
            if len(row) == 2:
                buttons.append(row)
                row = []
        
        # Добавляем остаток (если нечётное количество)
        if row:
            buttons.append(row)
        
        # Кнопка "Назад"
        buttons.append([KeyboardButton("◀️ Меню")])
        
        logger.debug(f"📞 Сформировано меню телефоний: {[tel['name'] for tel in telephonies]}")
        
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        
    except Exception as e:
        logger.error(f"❌ Ошибка формирования меню телефоний: {e}")
        
        # Fallback на хардкод при ошибке
        from config.constants import TELEPHONY_MENU
        return ReplyKeyboardMarkup(
            [[KeyboardButton(text) for text in row] for row in TELEPHONY_MENU],
            resize_keyboard=True
        )