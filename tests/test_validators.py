"""
Тесты для config/validators.py - Input Validation
"""
from config.validators import InputValidator


class TestInputValidator:
    """Тесты валидации входных данных"""

    def test_validate_user_id_valid(self):
        """Тест валидного user_id"""
        is_valid, error = InputValidator.validate_user_id(123456789)
        assert is_valid is True
        assert error is None

    def test_validate_user_id_string(self):
        """Тест user_id как строка"""
        is_valid, error = InputValidator.validate_user_id("123456789")
        assert is_valid is True
        assert error is None

    def test_validate_user_id_negative(self):
        """Тест отрицательного user_id"""
        is_valid, error = InputValidator.validate_user_id(-123)
        assert is_valid is False
        assert "положительным" in error

    def test_validate_user_id_zero(self):
        """Тест нулевого user_id"""
        is_valid, error = InputValidator.validate_user_id(0)
        assert is_valid is False
        assert "положительным" in error

    def test_validate_user_id_too_small(self):
        """Тест user_id меньше минимума"""
        is_valid, error = InputValidator.validate_user_id(100)
        assert is_valid is False
        assert "диапазон" in error

    def test_validate_user_id_invalid_string(self):
        """Тест невалидной строки как user_id"""
        is_valid, error = InputValidator.validate_user_id("abc")
        assert is_valid is False
        assert "число" in error

    def test_validate_sip_valid(self):
        """Тест валидного SIP"""
        is_valid, error = InputValidator.validate_sip_number("1234567890")
        assert is_valid is True
        assert error is None

    def test_validate_sip_empty(self):
        """Тест пустого SIP"""
        is_valid, error = InputValidator.validate_sip_number("")
        assert is_valid is False
        assert "пустым" in error

    def test_validate_sip_with_letters(self):
        """Тест SIP с буквами (недопустимо)"""
        is_valid, error = InputValidator.validate_sip_number("123abc456")
        assert is_valid is False
        assert "цифр" in error

    def test_validate_sip_too_long(self):
        """Тест слишком длинного SIP"""
        long_sip = "1" * 100
        is_valid, error = InputValidator.validate_sip_number(long_sip)
        assert is_valid is False
        assert "длинный" in error

    def test_validate_telephony_code_valid(self):
        """Тест валидного кода телефонии"""
        is_valid, error = InputValidator.validate_telephony_code("bmw")
        assert is_valid is True
        assert error is None

    def test_validate_telephony_code_with_numbers(self):
        """Тест кода с цифрами"""
        is_valid, error = InputValidator.validate_telephony_code("tel_123")
        assert is_valid is True
        assert error is None

    def test_validate_telephony_code_empty(self):
        """Тест пустого кода"""
        is_valid, error = InputValidator.validate_telephony_code("")
        assert is_valid is False
        assert "пустым" in error

    def test_validate_telephony_code_special_chars(self):
        """Тест кода со спец символами"""
        is_valid, error = InputValidator.validate_telephony_code("tel!@#")
        assert is_valid is False
        assert "недопустимые" in error

    def test_validate_error_description_valid(self):
        """Тест валидного описания ошибки"""
        description = "Это описание ошибки телефонии"
        is_valid, error = InputValidator.validate_error_description(description)
        assert is_valid is True
        assert error is None

    def test_validate_error_description_empty(self):
        """Тест пустого описания"""
        is_valid, error = InputValidator.validate_error_description("")
        assert is_valid is False
        assert "пустым" in error

    def test_validate_error_description_too_long(self):
        """Тест слишком длинного описания"""
        long_desc = "х" * 1000
        is_valid, error = InputValidator.validate_error_description(long_desc)
        assert is_valid is False
        assert "длинное" in error

    def test_validate_group_id_valid(self):
        """Тест валидного ID группы"""
        is_valid, error = InputValidator.validate_group_id(-100123456789)
        assert is_valid is True
        assert error is None

    def test_validate_group_id_positive(self):
        """Тест положительного ID (должно быть отрицательным)"""
        is_valid, error = InputValidator.validate_group_id(100123456789)
        assert is_valid is False
        assert "отрицательным" in error

    def test_validate_group_id_invalid_type(self):
        """Тест невалидного типа ID"""
        is_valid, error = InputValidator.validate_group_id("abc")
        assert is_valid is False
        assert "число" in error

    def test_validate_username_valid(self):
        """Тест валидного username"""
        is_valid, error = InputValidator.validate_username("user_name")
        assert is_valid is True
        assert error is None

    def test_validate_username_none(self):
        """Тест None username (допустимо в Telegram)"""
        is_valid, error = InputValidator.validate_username(None)
        assert is_valid is True
        assert error is None

    def test_validate_username_with_special_chars(self):
        """Тест username со спец символами"""
        is_valid, error = InputValidator.validate_username("user-name")
        assert is_valid is False
        assert "недопустимые" in error

    def test_validate_username_too_long(self):
        """Тест слишком длинного username"""
        long_user = "u" * 50
        is_valid, error = InputValidator.validate_username(long_user)
        assert is_valid is False
        assert "длинный" in error


class TestInputValidatorEdgeCases:
    """Тесты граничных случаев"""

    def test_validate_user_id_max_value(self):
        """Тест максимального значения user_id"""
        is_valid, error = InputValidator.validate_user_id(InputValidator.MAX_USER_ID)
        assert is_valid is True

    def test_validate_user_id_min_value(self):
        """Тест минимального значения user_id"""
        is_valid, error = InputValidator.validate_user_id(InputValidator.MIN_USER_ID)
        assert is_valid is True

    def test_validate_user_id_with_whitespace(self):
        """Тест user_id со скрытыми пробелами"""
        is_valid, error = InputValidator.validate_user_id("  123456789  ")
        assert is_valid is True

    def test_validate_sip_with_spaces(self):
        """Тест SIP с пробелами - должны быть обрезаны"""
        is_valid, error = InputValidator.validate_sip_number("  123456  ")
        assert is_valid is True

    def test_validate_telephony_code_case_sensitive(self):
        """Тест чувствительности к регистру"""
        is_valid1, _ = InputValidator.validate_telephony_code("BMW")
        is_valid2, _ = InputValidator.validate_telephony_code("bmw")
        assert is_valid1 is True
        assert is_valid2 is True
