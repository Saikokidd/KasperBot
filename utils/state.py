"""
utils/state.py - КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ
Роль НЕ должна сбрасываться при clear_all_states

ИЗМЕНЕНИЯ:
✅ clear_all_states() НЕ трогает роль
✅ Роль живёт весь сеанс (с момента /start)
✅ Только телефония и режимы очищаются
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
from telegram.ext import ContextTypes
from config.constants import TEL_CHOICE_TIMEOUT


def is_tel_choice_expired(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет, истёк ли timeout выбора телефонии"""
    chosen_at = context.user_data.get("tel_chosen_at")
    if not chosen_at:
        return True
    return datetime.now() - chosen_at > timedelta(minutes=TEL_CHOICE_TIMEOUT)


def clear_tel_choice(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Очищает данные выбора телефонии"""
    context.user_data.pop("chosen_tel", None)
    context.user_data.pop("chosen_tel_code", None)
    context.user_data.pop("tel_chosen_at", None)


def clear_all_states(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Очищает все ВРЕМЕННЫЕ состояния пользователя
    
    ✅ КРИТИЧНО: НЕ очищает роль (она живёт весь сеанс)
    """
    clear_tel_choice(context)
    context.user_data.pop("support_mode", None)
    # ✅ КРИТИЧНО: role НЕ очищается!
    # Роль устанавливается при /start и живёт весь сеанс


def get_user_role(context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Получает роль пользователя из контекста
    
    Returns:
        Роль пользователя ("manager", "admin" или "pult")
    """
    return context.user_data.get("role", "manager")


def set_user_role(context: ContextTypes.DEFAULT_TYPE, role: str) -> None:
    """
    Устанавливает роль пользователя
    
    Args:
        role: Роль ("manager", "admin" или "pult")
        
    Raises:
        ValueError: Если роль неизвестна
    """
    valid_roles = {"manager", "admin", "pult"}
    if role not in valid_roles:
        raise ValueError(f"Неизвестная роль: {role}. Допустимые: {valid_roles}")
    
    context.user_data["role"] = role


def set_support_mode(context: ContextTypes.DEFAULT_TYPE, enabled: bool) -> None:
    """Включает/выключает режим поддержки"""
    if enabled:
        context.user_data["support_mode"] = True
    else:
        context.user_data.pop("support_mode", None)


def is_support_mode(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет, активен ли режим поддержки"""
    return context.user_data.get("support_mode", False)


def set_tel_choice(
    context: ContextTypes.DEFAULT_TYPE, 
    tel_name: str, 
    tel_code: str
) -> None:
    """
    Сохраняет выбор телефонии
    
    Args:
        tel_name: Название телефонии (BMW, Звонари)
        tel_code: Код телефонии (bmw, zvon)
        
    Raises:
        ValueError: Если tel_name или tel_code пустые
    """
    if not tel_name or not tel_name.strip():
        raise ValueError("tel_name не может быть пустым")
    
    if not tel_code or not tel_code.strip():
        raise ValueError("tel_code не может быть пустым")
    
    context.user_data["chosen_tel"] = tel_name.strip()
    context.user_data["chosen_tel_code"] = tel_code.strip()
    context.user_data["tel_chosen_at"] = datetime.now()


def get_tel_choice(context: ContextTypes.DEFAULT_TYPE) -> Tuple[Optional[str], Optional[str]]:
    """
    Получает текущий выбор телефонии
    
    Returns:
        Кортеж (tel_name, tel_code) или (None, None) если не выбрано
    """
    tel = context.user_data.get("chosen_tel")
    tel_code = context.user_data.get("chosen_tel_code")
    return tel, tel_code