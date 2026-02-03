"""
utils/validators.py - Централизованная валидация входных данных

ИЗМЕНЕНИЯ:
✅ Валидация user_id (от 1000 до 2^31-1)
✅ Валидация SIP (только цифры, 1-50 символов)
✅ Валидация описания ошибки (1-500 символов, без спецсимволов)
✅ Валидация названия телефонии (1-50 символов)
✅ Валидация кода телефонии (буквы/цифры/underscore, уникален)
"""
import re
from typing import Tuple, Optional
from utils.logger import logger


class InputValidator:
    """Централизованный валидатор входных данных"""
    
    # Регулярные выражения
    SIP_PATTERN = re.compile(r'^\d+$')  # Только цифры
    TELEPHONY_CODE_PATTERN = re.compile(r'^[a-z0-9_]+$')  # Lowercase буквы, цифры, underscore
    TELEPHONY_NAME_PATTERN = re.compile(r'^[а-яА-ЯёЁ\s\-\.a-zA-Z0-9]+$')  # Кириллица, латиница, спецсимволы
    
    # Границы
    USER_ID_MIN = 1000
    USER_ID_MAX = 2**63 - 1  # Максимум 64-битного целого числа (Telegram использует 64-бит)
    SIP_MIN_LEN = 1
    SIP_MAX_LEN = 50
    ERROR_DESC_MIN_LEN = 5
    ERROR_DESC_MAX_LEN = 500
    TEL_NAME_MIN_LEN = 1
    TEL_NAME_MAX_LEN = 50
    TEL_CODE_MIN_LEN = 2
    TEL_CODE_MAX_LEN = 30
    
    @staticmethod
    def validate_user_id(user_id) -> Tuple[bool, Optional[str]]:
        """
        Валидация user_id
        
        Args:
            user_id: ID для проверки
            
        Returns:
            (is_valid, error_message)
        """
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return False, "❌ ID должен быть числом"
        
        if user_id < InputValidator.USER_ID_MIN or user_id > InputValidator.USER_ID_MAX:
            return False, f"❌ ID должен быть между {InputValidator.USER_ID_MIN} и {InputValidator.USER_ID_MAX}"
        
        return True, None
    
    @staticmethod
    def validate_sip(sip: str) -> Tuple[bool, Optional[str]]:
        """
        Валидация SIP номера
        
        Args:
            sip: SIP номер для проверки
            
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(sip, str):
            return False, "❌ SIP должен быть текстом"
        
        sip = sip.strip()
        
        if len(sip) < InputValidator.SIP_MIN_LEN:
            return False, "❌ SIP не может быть пустым"
        
        if len(sip) > InputValidator.SIP_MAX_LEN:
            return False, f"❌ SIP не может быть длиннее {InputValidator.SIP_MAX_LEN} символов"
        
        if not InputValidator.SIP_PATTERN.match(sip):
            return False, "❌ SIP должен содержать только цифры"
        
        return True, None
    
    @staticmethod
    def validate_error_description(description: str) -> Tuple[bool, Optional[str]]:
        """
        Валидация описания ошибки
        
        Args:
            description: Описание для проверки
            
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(description, str):
            return False, "❌ Описание должно быть текстом"
        
        description = description.strip()
        
        if len(description) < InputValidator.ERROR_DESC_MIN_LEN:
            return False, f"❌ Описание должно быть не менее {InputValidator.ERROR_DESC_MIN_LEN} символов"
        
        if len(description) > InputValidator.ERROR_DESC_MAX_LEN:
            return False, f"❌ Описание не может быть длиннее {InputValidator.ERROR_DESC_MAX_LEN} символов"
        
        # Проверка на недопустимые символы (только базовый контроль)
        if any(char in description for char in ['<', '>', '{', '}', '[[', ']]']):
            return False, "❌ Описание содержит недопустимые символы"
        
        return True, None
    
    @staticmethod
    def validate_telephony_name(name: str) -> Tuple[bool, Optional[str]]:
        """
        Валидация названия телефонии
        
        Args:
            name: Название для проверки
            
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(name, str):
            return False, "❌ Название должно быть текстом"
        
        name = name.strip()
        
        if len(name) < InputValidator.TEL_NAME_MIN_LEN:
            return False, "❌ Название не может быть пустым"
        
        if len(name) > InputValidator.TEL_NAME_MAX_LEN:
            return False, f"❌ Название не может быть длиннее {InputValidator.TEL_NAME_MAX_LEN} символов"
        
        if not InputValidator.TELEPHONY_NAME_PATTERN.match(name):
            return False, "❌ Название содержит недопустимые символы (только буквы, цифры, дефис, точка)"
        
        return True, None
    
    @staticmethod
    def validate_telephony_code(code: str) -> Tuple[bool, Optional[str]]:
        """
        Валидация кода телефонии
        
        Args:
            code: Код для проверки
            
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(code, str):
            return False, "❌ Код должен быть текстом"
        
        code = code.strip().lower()
        
        if len(code) < InputValidator.TEL_CODE_MIN_LEN:
            return False, f"❌ Код должен быть не менее {InputValidator.TEL_CODE_MIN_LEN} символов"
        
        if len(code) > InputValidator.TEL_CODE_MAX_LEN:
            return False, f"❌ Код не может быть длиннее {InputValidator.TEL_CODE_MAX_LEN} символов"
        
        if not InputValidator.TELEPHONY_CODE_PATTERN.match(code):
            return False, "❌ Код должен содержать только строчные буквы, цифры и подчеркивание"
        
        return True, None
    
    @staticmethod
    def validate_broadcast_message(message: str) -> Tuple[bool, Optional[str]]:
        """
        Валидация сообщения рассылки
        
        Args:
            message: Сообщение для проверки
            
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(message, str):
            return False, "❌ Сообщение должно быть текстом"
        
        message = message.strip()
        
        if len(message) < 5:
            return False, "❌ Сообщение должно быть не менее 5 символов"
        
        if len(message) > 4000:  # Лимит Telegram
            return False, "❌ Сообщение не может быть длиннее 4000 символов"
        
        return True, None


# Экспортируем валидатор
input_validator = InputValidator()
