"""
utils/state.py - КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ
Роль НЕ должна сбрасываться при clear_all_states

ИЗМЕНЕНИЯ:
✅ clear_all_states() НЕ трогает роль
✅ Роль живёт весь сеанс (с момента /start)
✅ Только телефония и режимы очищаются
✅ ДОБАВЛЕНО: Timeout для быстрых ошибок (SIP)
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
from telegram.ext import ContextTypes
from config.constants import TEL_CHOICE_TIMEOUT
from utils.logger import logger

# Константы для timeout'ов
QUICK_ERROR_SIP_TIMEOUT_MINUTES = 10
QUICK_ERROR_CODE_TIMEOUT_MINUTES = 10


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
    # ✅ НОВОЕ: Очищаем timeout'ы для быстрых ошибок
    clear_quick_error_state(context)


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


# ✅ НОВОЕ: Управление состоянием быстрых ошибок

def set_quick_error_sip(context: ContextTypes.DEFAULT_TYPE, sip: str) -> None:
    """
    Сохраняет SIP номер для быстрой ошибки с timestamp
    
    Args:
        sip: SIP номер
    """
    if not sip or not sip.strip():
        raise ValueError("SIP не может быть пустым")
    
    context.user_data["quick_error_sip"] = sip.strip()
    context.user_data["quick_error_sip_set_at"] = datetime.now()
    logger.debug(f"💾 SIP для быстрой ошибки сохранён: {sip}")


def get_quick_error_sip(context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
    """
    Получает SIP номер, если он ещё не истёк по времени
    
    Returns:
        SIP номер или None если истёк timeout
    """
    sip = context.user_data.get("quick_error_sip")
    sip_set_at = context.user_data.get("quick_error_sip_set_at")
    
    if not sip or not sip_set_at:
        return None
    
    # Проверяем timeout
    if is_quick_error_sip_expired(context):
        logger.warning("⚠️ Timeout SIP быстрой ошибки истёк, очищаем")
        clear_quick_error_state(context)
        return None
    
    return sip


def is_quick_error_sip_expired(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Проверяет, истёк ли timeout для SIP быстрой ошибки
    
    Returns:
        True если истёк, False если ещё актуален
    """
    sip_set_at = context.user_data.get("quick_error_sip_set_at")
    
    if not sip_set_at:
        return True
    
    elapsed = datetime.now() - sip_set_at
    expired = elapsed > timedelta(minutes=QUICK_ERROR_SIP_TIMEOUT_MINUTES)
    
    if expired:
        logger.debug(f"⏰ SIP timeout истёк ({QUICK_ERROR_SIP_TIMEOUT_MINUTES} минут)")
    
    return expired


def set_quick_error_code(context: ContextTypes.DEFAULT_TYPE, code: str) -> None:
    """
    Сохраняет код быстрой ошибки с timestamp
    
    Args:
        code: Код ошибки (1-10 или "custom")
    """
    if not code or not code.strip():
        raise ValueError("Код ошибки не может быть пустым")
    
    context.user_data["quick_error_code"] = code.strip()
    context.user_data["quick_error_code_set_at"] = datetime.now()
    logger.debug(f"💾 Код быстрой ошибки сохранён: {code}")


def get_quick_error_code(context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
    """
    Получает код быстрой ошибки, если он ещё не истёк по времени
    
    Returns:
        Код ошибки или None если истёк timeout
    """
    code = context.user_data.get("quick_error_code")
    code_set_at = context.user_data.get("quick_error_code_set_at")
    
    if not code or not code_set_at:
        return None
    
    # Проверяем timeout
    if is_quick_error_code_expired(context):
        logger.warning("⚠️ Timeout кода быстрой ошибки истёк, очищаем")
        clear_quick_error_state(context)
        return None
    
    return code


def is_quick_error_code_expired(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Проверяет, истёк ли timeout для кода быстрой ошибки
    
    Returns:
        True если истёк, False если ещё актуален
    """
    code_set_at = context.user_data.get("quick_error_code_set_at")
    
    if not code_set_at:
        return True
    
    elapsed = datetime.now() - code_set_at
    expired = elapsed > timedelta(minutes=QUICK_ERROR_CODE_TIMEOUT_MINUTES)
    
    if expired:
        logger.debug(f"⏰ Код быстрой ошибки timeout истёк ({QUICK_ERROR_CODE_TIMEOUT_MINUTES} минут)")
    
    return expired


def clear_quick_error_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Полностью очищает состояние быстрой ошибки"""
    context.user_data.pop("quick_error_sip", None)
    context.user_data.pop("quick_error_sip_set_at", None)
    context.user_data.pop("quick_error_code", None)
    context.user_data.pop("quick_error_code_set_at", None)
    logger.debug("🧹 Состояние быстрой ошибки очищено")