"""
Тесты для utils/state.py - Управление состоянием пользователя
"""
import pytest
from datetime import datetime, timedelta
from utils.state import (
    get_user_role,
    set_user_role,
    set_tel_choice,
    get_tel_choice,
    clear_all_states,
    clear_tel_choice,
    set_quick_error_sip,
    get_quick_error_sip,
    is_quick_error_sip_expired,
    set_quick_error_code,
    get_quick_error_code,
    is_quick_error_code_expired,
    clear_quick_error_state,
)


class TestUserRole:
    """Тесты управления ролью пользователя"""

    def test_set_and_get_role(self, mock_context):
        """Тест установки и получения роли"""
        set_user_role(mock_context, "admin")
        assert get_user_role(mock_context) == "admin"

    def test_set_role_manager(self, mock_context):
        """Тест установки роли менеджера"""
        set_user_role(mock_context, "manager")
        assert get_user_role(mock_context) == "manager"

    def test_set_role_pult(self, mock_context):
        """Тест установки роли пульта"""
        set_user_role(mock_context, "pult")
        assert get_user_role(mock_context) == "pult"

    def test_invalid_role(self, mock_context):
        """Тест установки невалидной роли"""
        with pytest.raises(ValueError):
            set_user_role(mock_context, "invalid_role")

    def test_default_role(self, mock_context):
        """Тест роли по умолчанию"""
        assert get_user_role(mock_context) == "manager"


class TestTelephonyChoice:
    """Тесты выбора телефонии"""

    def test_set_and_get_tel_choice(self, mock_context):
        """Тест установки и получения выбора телефонии"""
        set_tel_choice(mock_context, "BMW", "bmw")
        tel, code = get_tel_choice(mock_context)
        assert tel == "BMW"
        assert code == "bmw"

    def test_tel_choice_empty_name(self, mock_context):
        """Тест пустого имени телефонии"""
        with pytest.raises(ValueError):
            set_tel_choice(mock_context, "", "bmw")

    def test_tel_choice_empty_code(self, mock_context):
        """Тест пустого кода телефонии"""
        with pytest.raises(ValueError):
            set_tel_choice(mock_context, "BMW", "")

    def test_get_tel_choice_default(self, mock_context):
        """Тест получения выбора по умолчанию"""
        tel, code = get_tel_choice(mock_context)
        assert tel is None
        assert code is None

    def test_clear_tel_choice(self, mock_context):
        """Тест очистки выбора телефонии"""
        set_tel_choice(mock_context, "BMW", "bmw")
        clear_tel_choice(mock_context)
        tel, code = get_tel_choice(mock_context)
        assert tel is None
        assert code is None


class TestQuickErrorSIP:
    """Тесты управления SIP быстрой ошибки"""

    def test_set_and_get_quick_error_sip(self, mock_context):
        """Тест установки и получения SIP"""
        set_quick_error_sip(mock_context, "1234567890")
        sip = get_quick_error_sip(mock_context)
        assert sip == "1234567890"

    def test_quick_error_sip_empty(self, mock_context):
        """Тест пустого SIP"""
        with pytest.raises(ValueError):
            set_quick_error_sip(mock_context, "")

    def test_quick_error_sip_get_default(self, mock_context):
        """Тест получения SIP по умолчанию"""
        sip = get_quick_error_sip(mock_context)
        assert sip is None

    def test_quick_error_sip_not_expired(self, mock_context):
        """Тест что SIP ещё не истёк"""
        set_quick_error_sip(mock_context, "1234567890")
        assert is_quick_error_sip_expired(mock_context) is False

    def test_quick_error_sip_expired(self, mock_context):
        """Тест истекшего SIP"""
        set_quick_error_sip(mock_context, "1234567890")
        # Устанавливаем время в прошлое (более 10 минут)
        old_time = datetime.now() - timedelta(minutes=15)
        mock_context.user_data["quick_error_sip_set_at"] = old_time

        assert is_quick_error_sip_expired(mock_context) is True

    def test_quick_error_sip_expires_on_get(self, mock_context):
        """Тест что get возвращает None если истёк"""
        set_quick_error_sip(mock_context, "1234567890")
        old_time = datetime.now() - timedelta(minutes=15)
        mock_context.user_data["quick_error_sip_set_at"] = old_time

        sip = get_quick_error_sip(mock_context)
        assert sip is None


class TestQuickErrorCode:
    """Тесты управления кодом быстрой ошибки"""

    def test_set_and_get_quick_error_code(self, mock_context):
        """Тест установки и получения кода"""
        set_quick_error_code(mock_context, "5")
        code = get_quick_error_code(mock_context)
        assert code == "5"

    def test_quick_error_code_empty(self, mock_context):
        """Тест пустого кода"""
        with pytest.raises(ValueError):
            set_quick_error_code(mock_context, "")

    def test_quick_error_code_get_default(self, mock_context):
        """Тест получения кода по умолчанию"""
        code = get_quick_error_code(mock_context)
        assert code is None

    def test_quick_error_code_not_expired(self, mock_context):
        """Тест что код ещё не истёк"""
        set_quick_error_code(mock_context, "5")
        assert is_quick_error_code_expired(mock_context) is False

    def test_quick_error_code_expired(self, mock_context):
        """Тест истекшего кода"""
        set_quick_error_code(mock_context, "5")
        old_time = datetime.now() - timedelta(minutes=15)
        mock_context.user_data["quick_error_code_set_at"] = old_time

        assert is_quick_error_code_expired(mock_context) is True


class TestClearAllStates:
    """Тесты очистки состояния"""

    def test_clear_all_states_preserves_role(self, mock_context):
        """Тест что clear_all_states сохраняет роль"""
        set_user_role(mock_context, "admin")
        set_tel_choice(mock_context, "BMW", "bmw")
        set_quick_error_sip(mock_context, "1234567890")

        clear_all_states(mock_context)

        # Роль должна остаться
        assert get_user_role(mock_context) == "admin"
        # Остальное должно быть очищено
        tel, code = get_tel_choice(mock_context)
        assert tel is None

    def test_clear_all_states_clears_tel(self, mock_context):
        """Тест что clear_all_states очищает выбор телефонии"""
        set_tel_choice(mock_context, "BMW", "bmw")
        clear_all_states(mock_context)

        tel, code = get_tel_choice(mock_context)
        assert tel is None
        assert code is None

    def test_clear_all_states_clears_quick_error(self, mock_context):
        """Тест что clear_all_states очищает быструю ошибку"""
        set_quick_error_sip(mock_context, "1234567890")
        set_quick_error_code(mock_context, "5")
        clear_all_states(mock_context)

        assert get_quick_error_sip(mock_context) is None
        assert get_quick_error_code(mock_context) is None


class TestClearQuickErrorState:
    """Тесты очистки состояния быстрой ошибки"""

    def test_clear_quick_error_state(self, mock_context):
        """Тест полной очистки быстрой ошибки"""
        set_quick_error_sip(mock_context, "1234567890")
        set_quick_error_code(mock_context, "5")
        set_user_role(mock_context, "admin")

        clear_quick_error_state(mock_context)

        # Быстрая ошибка должна быть очищена
        assert get_quick_error_sip(mock_context) is None
        assert get_quick_error_code(mock_context) is None
        # Роль должна остаться
        assert get_user_role(mock_context) == "admin"
