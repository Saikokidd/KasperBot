"""
Утилиты для управления состоянием пользователя
"""
from datetime import datetime, timedelta
from telegram.ext import ContextTypes
from config.constants import TEL_CHOICE_TIMEOUT


def is_tel_choice_expired(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Проверяет, истёк ли timeout выбора телефонии
    
    Args:
        context: Контекст пользователя
        
    Returns:
        True если выбор истёк, False если ещё активен
    """
    chosen_at = context.user_data.get("tel_chosen_at")
    if not chosen_at:
        return True
    return datetime.now() - chosen_at > timedelta(minutes=TEL_CHOICE_TIMEOUT)


def clear_tel_choice(context: ContextTypes.DEFAULT_TYPE):
    """
    Очищает данные выбора телефонии
    
    Args:
        context: Контекст пользователя
    """
    context.user_data.pop("chosen_tel", None)
    context.user_data.pop("chosen_tel_code", None)
    context.user_data.pop("tel_chosen_at", None)


def clear_all_states(context: ContextTypes.DEFAULT_TYPE):
    """
    Очищает все состояния пользователя
    
    Args:
        context: Контекст пользователя
    """
    clear_tel_choice(context)
    context.user_data.pop("support_mode", None)
    context.user_data.pop("role", None)


def get_user_role(context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Получает роль пользователя из контекста
    
    Args:
        context: Контекст пользователя
        
    Returns:
        Роль пользователя ("manager" или "admin")
    """
    return context.user_data.get("role", "manager")


def set_user_role(context: ContextTypes.DEFAULT_TYPE, role: str):
    """
    Устанавливает роль пользователя
    
    Args:
        context: Контекст пользователя
        role: Роль ("manager" или "admin")
    """
    context.user_data["role"] = role


def set_support_mode(context: ContextTypes.DEFAULT_TYPE, enabled: bool):
    """
    Включает/выключает режим поддержки
    
    Args:
        context: Контекст пользователя
        enabled: True для включения, False для выключения
    """
    if enabled:
        context.user_data["support_mode"] = True
    else:
        context.user_data.pop("support_mode", None)


def is_support_mode(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Проверяет, активен ли режим поддержки
    
    Args:
        context: Контекст пользователя
        
    Returns:
        True если режим поддержки активен
    """
    return context.user_data.get("support_mode", False)


def set_tel_choice(context: ContextTypes.DEFAULT_TYPE, tel_name: str, tel_code: str):
    """
    Сохраняет выбор телефонии
    
    Args:
        context: Контекст пользователя
        tel_name: Название телефонии (BMW, Звонари)
        tel_code: Код телефонии (bmw, zvon)
    """
    context.user_data["chosen_tel"] = tel_name
    context.user_data["chosen_tel_code"] = tel_code
    context.user_data["tel_chosen_at"] = datetime.now()


def get_tel_choice(context: ContextTypes.DEFAULT_TYPE) -> tuple:
    """
    Получает текущий выбор телефонии
    
    Args:
        context: Контекст пользователя
        
    Returns:
        Кортеж (tel_name, tel_code) или (None, None)
    """
    tel = context.user_data.get("chosen_tel")
    tel_code = context.user_data.get("chosen_tel_code")
    return tel, tel_code
