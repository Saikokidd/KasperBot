"""
Fixtures для всех тестов
"""
import pytest
from unittest.mock import MagicMock


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
