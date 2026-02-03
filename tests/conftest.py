"""
Fixtures для всех тестов

ВАЖНО: загрузка .env.test должна быть ПЕРВОЙ операцией,
до любого импорта модулей проекта (config, services и т.д.)
"""
import os
import pytest
from unittest.mock import MagicMock
from dotenv import load_dotenv

# Загружаем тестовые переменные окружения ДО любого импорта проекта
# Путь: tests/../.env.test = корень проекта
_test_env_path = os.path.join(os.path.dirname(__file__), "..", ".env.test")
load_dotenv(dotenv_path=os.path.abspath(_test_env_path), override=True)


@pytest.fixture
def mock_context():
    """Mock telegram.ext.ContextTypes"""
    context = MagicMock()
    context.user_data = {}
    context.bot_data = {}
    return context


@pytest.fixture
def mock_update():
    """Mock telegram Update"""
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123456789
    update.effective_user.username = "test_user"
    update.effective_user.first_name = "Test"
    return update
