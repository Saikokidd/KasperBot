"""
config/validators.py - Централизованная валидация входных данных

НАЗНАЧЕНИЕ:
✅ Единая точка валидации для всех user_id, телефоний, SIP и т.д.
✅ Переиспользование во всех handlers
✅ Защита от некорректных данных
"""
import re
from typing import Tuple, Optional
from config.constants import SIP_PATTERN, MAX_SIP_LENGTH, MAX_CUSTOM_ERROR_LENGTH
from utils.logger import logger


class InputValidator:
    """Класс для валидации входных данных"""
    
    # Диапазоны для Telegram user_id
    MIN_USER_ID = 1000
    MAX_USER_ID = 2**31 - 1
    
    @staticmethod
    def validate_user_id(user_id: any) -> Tuple[bool, Optional[str]]:
        """
        Валидирует user_id пользователя
        
        Args:
            user_id: ID пользователя (может быть str, int)
            
        Returns:
            (is_valid, error_message)
        """
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return False, f"❌ ID пользователя должен быть числом, получено: {user_id}"
        
        if user_id <= 0:
            return False, f"❌ ID пользователя должен быть положительным числом (получено: {user_id})"
        
        if user_id < InputValidator.MIN_USER_ID or user_id > InputValidator.MAX_USER_ID:
            return False, f"❌ ID пользователя вне допустимого диапазона ({InputValidator.MIN_USER_ID}-{InputValidator.MAX_USER_ID})"
        
        return True, None
    
    @staticmethod
    def validate_telephony_code(code: str) -> Tuple[bool, Optional[str]]:
        """
        Валидирует код телефонии
        
        Args:
            code: Код телефонии (должен быть буквы/цифры, 1-10 символов)
            
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(code, str):
            return False, f"❌ Код телефонии должен быть строкой"
        
        code = code.strip()
        
        if not code:
            return False, f"❌ Код телефонии не может быть пустым"
        
        if len(code) > 50:
            return False, f"❌ Код телефонии слишком длинный (макс 50 символов)"
        
        # Только буквы, цифры, подчёркивание, дефис
        if not re.match(r'^[a-zA-Z0-9_-]+$', code):
            return False, f"❌ Код содержит недопустимые символы: {code}"
        
        return True, None
    
    @staticmethod
    def validate_sip_number(sip: str) -> Tuple[bool, Optional[str]]:
        """
        Валидирует SIP номер
        
        Args:
            sip: SIP номер (только цифры)
            
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(sip, str):
            return False, f"❌ SIP должен быть строкой"
        
        sip = sip.strip()
        
        if not sip:
            return False, f"❌ SIP не может быть пустым"
        
        if len(sip) > MAX_SIP_LENGTH:
            return False, f"❌ SIP слишком длинный (макс {MAX_SIP_LENGTH} символов, получено {len(sip)})"
        
        if not SIP_PATTERN.match(sip):
            return False, f"❌ SIP должен содержать только цифры (получено: {sip})"
        
        return True, None
    
    @staticmethod
    def validate_telephony_name(name: str) -> Tuple[bool, Optional[str]]:
        """
        Валидирует имя телефонии
        
        Args:
            name: Имя телефонии
            
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(name, str):
            return False, f"❌ Имя телефонии должно быть строкой"
        
        name = name.strip()
        
        if not name:
            return False, f"❌ Имя телефонии не может быть пустым"
        
        if len(name) > 100:
            return False, f"❌ Имя телефонии слишком длинное (макс 100 символов)"
        
        # Допускаем кириллицу, латиницу, пробелы, цифры
        if not re.match(r'^[\w\s\u0400-\u04FF-]+$', name):
            return False, f"❌ Имя содержит недопустимые символы: {name}"
        
        return True, None
    
    @staticmethod
    def validate_error_description(description: str) -> Tuple[bool, Optional[str]]:
        """
        Валидирует описание ошибки
        
        Args:
            description: Описание ошибки от пользователя
            
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(description, str):
            return False, f"❌ Описание должно быть строкой"
        
        description = description.strip()
        
        if not description:
            return False, f"❌ Описание ошибки не может быть пустым"
        
        if len(description) > MAX_CUSTOM_ERROR_LENGTH:
            return False, f"❌ Описание слишком длинное (макс {MAX_CUSTOM_ERROR_LENGTH} символов, получено {len(description)})"
        
        return True, None
    
    @staticmethod
    def validate_group_id(group_id: any) -> Tuple[bool, Optional[str]]:
        """
        Валидирует ID группы Telegram
        
        Args:
            group_id: ID группы (должен начинаться с "-")
            
        Returns:
            (is_valid, error_message)
        """
        try:
            group_id = int(group_id)
        except (ValueError, TypeError):
            return False, f"❌ ID группы должен быть числом, получено: {group_id}"
        
        if group_id > 0:
            return False, f"❌ ID группы должен быть отрицательным (начинаться с '-')"
        
        return True, None
    
    @staticmethod
    def validate_username(username: str) -> Tuple[bool, Optional[str]]:
        """
        Валидирует username Telegram
        
        Args:
            username: Username (может быть пустым в Telegram)
            
        Returns:
            (is_valid, error_message)
        """
        if username is None:
            return True, None  # Username может быть None
        
        if not isinstance(username, str):
            return False, f"❌ Username должен быть строкой"
        
        username = username.strip()
        
        if username and len(username) > 32:
            return False, f"❌ Username слишком длинный (макс 32 символа)"
        
        if username and not re.match(r'^[a-zA-Z0-9_]+$', username):
            return False, f"❌ Username содержит недопустимые символы: {username}"
        
        return True, None
    
    @staticmethod
    def log_validation_error(field: str, value: any, reason: str) -> None:
        """
        Логирует ошибку валидации для отладки
        
        Args:
            field: Название поля
            value: Полученное значение
            reason: Причина ошибки
        """
        logger.warning(f"⚠️ Валидация {field} провалена: {reason} (значение: {value})")
