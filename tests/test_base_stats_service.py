"""
tests/test_base_stats_service.py
Unit тесты для сервиса base_stats_service (новая версия)
Запуск: pytest tests/test_base_stats_service.py -v
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
import pytz


# ===================================================================
# Тесты _calculate_stats
# ===================================================================

class TestCalculateStats:
    """Тесты подсчёта статистики по поставщикам"""

    def _calc(self, raw):
        from services.base_stats_service import BaseStatsService
        return BaseStatsService._calculate_stats(raw)

    def test_empty_data(self):
        result = self._calc([])
        assert result == {}

    def test_single_provider_yellow(self):
        raw = [{"поставщик": "Поставщик А", "цвет": "ЖЕЛТЫЙ"}]
        result = self._calc(raw)
        assert result["Поставщик А"]["calls"] == 1
        assert result["Поставщик А"]["bomzh"] == 0
        assert result["Поставщик А"]["recalls"] == 0

    def test_single_provider_green(self):
        raw = [{"поставщик": "Поставщик А", "цвет": "ЗЕЛЕНЫЙ"}]
        result = self._calc(raw)
        assert result["Поставщик А"]["recalls"] == 1
        assert result["Поставщик А"]["bomzh"] == 0

    def test_single_provider_pink(self):
        raw = [{"поставщик": "Поставщик А", "цвет": "РОЗОВЫЙ"}]
        result = self._calc(raw)
        assert result["Поставщик А"]["bomzh"] == 1
        assert result["Поставщик А"]["recalls"] == 0

    def test_multiple_providers(self):
        raw = [
            {"поставщик": "А", "цвет": "ЗЕЛЕНЫЙ"},
            {"поставщик": "А", "цвет": "ЖЕЛТЫЙ"},
            {"поставщик": "А", "цвет": "РОЗОВЫЙ"},
            {"поставщик": "Б", "цвет": "ЗЕЛЕНЫЙ"},
            {"поставщик": "Б", "цвет": "ЗЕЛЕНЫЙ"},
        ]
        result = self._calc(raw)

        assert result["А"]["calls"] == 3
        assert result["А"]["recalls"] == 1
        assert result["А"]["bomzh"] == 1

        assert result["Б"]["calls"] == 2
        assert result["Б"]["recalls"] == 2
        assert result["Б"]["bomzh"] == 0

    def test_skips_empty_provider(self):
        raw = [
            {"поставщик": "", "цвет": "ЗЕЛЕНЫЙ"},
            {"поставщик": "   ", "цвет": "ЖЕЛТЫЙ"},
            {"поставщик": "Нормальный", "цвет": "ЖЕЛТЫЙ"},
        ]
        result = self._calc(raw)
        assert len(result) == 1
        assert "Нормальный" in result

    def test_missing_provider_key(self):
        raw = [{"цвет": "ЗЕЛЕНЫЙ"}, {"поставщик": "А", "цвет": "ЖЕЛТЫЙ"}]
        result = self._calc(raw)
        assert len(result) == 1
        assert "А" in result

    def test_missing_color_key(self):
        """Нет ключа 'цвет' — не должно падать"""
        raw = [{"поставщик": "А"}]
        result = self._calc(raw)
        assert result["А"]["calls"] == 1
        assert result["А"]["bomzh"] == 0
        assert result["А"]["recalls"] == 0

    def test_case_insensitive_color(self):
        """Цвет в нижнем регистре — не должен засчитываться как ЗЕЛЕНЫЙ/РОЗОВЫЙ"""
        raw = [
            {"поставщик": "А", "цвет": "зеленый"},   # не верхний регистр
            {"поставщик": "А", "цвет": "ЗЕЛЕНЫЙ"},   # верхний — засчитывается
        ]
        result = self._calc(raw)
        # Только одна зелёная (верхний регистр)
        assert result["А"]["recalls"] == 1
        assert result["А"]["calls"] == 2


# ===================================================================
# Тесты _format_message
# ===================================================================

class TestFormatMessage:
    """Тесты форматирования текстового сообщения"""

    def _fmt(self, stats, date_str="11.03"):
        from services.base_stats_service import BaseStatsService
        return BaseStatsService._format_message(stats, date_str)

    def test_empty_stats(self):
        msg = self._fmt({})
        assert "пока нет" in msg
        assert "11.03" in msg

    def test_contains_provider_name(self):
        stats = {"Поставщик А": {"calls": 10, "bomzh": 2, "recalls": 3}}
        msg = self._fmt(stats)
        assert "Поставщик А" in msg

    def test_contains_numbers(self):
        stats = {"А": {"calls": 5, "bomzh": 1, "recalls": 2}}
        msg = self._fmt(stats)
        assert "5" in msg
        assert "1" in msg
        assert "2" in msg

    def test_percent_calculation(self):
        stats = {"А": {"calls": 10, "bomzh": 0, "recalls": 5}}
        msg = self._fmt(stats)
        assert "50.0%" in msg

    def test_total_line_present(self):
        stats = {
            "А": {"calls": 3, "bomzh": 0, "recalls": 1},
            "Б": {"calls": 7, "bomzh": 2, "recalls": 3},
        }
        msg = self._fmt(stats)
        assert "ИТОГО" in msg
        # Итого звонков = 10
        assert "10" in msg

    def test_zero_calls_no_division_error(self):
        """calls=0 не должно вызывать ZeroDivisionError"""
        stats = {"А": {"calls": 0, "bomzh": 0, "recalls": 0}}
        msg = self._fmt(stats)
        assert "0.0%" in msg

    def test_html_tags_present(self):
        stats = {"А": {"calls": 1, "bomzh": 0, "recalls": 0}}
        msg = self._fmt(stats)
        assert "<b>" in msg


# ===================================================================
# Тесты get_today_stats_text (интеграционный, с мокингом)
# ===================================================================

class TestGetTodayStatsText:
    """Интеграционные тесты публичного метода"""

    @pytest.mark.asyncio
    async def test_returns_text_on_success(self):
        from services.base_stats_service import BaseStatsService

        service = BaseStatsService.__new__(BaseStatsService)
        service.timezone = pytz.timezone("Europe/Kiev")
        service.url = "http://fake-url"

        raw = [
            {"поставщик": "Тест", "цвет": "ЗЕЛЕНЫЙ"},
            {"поставщик": "Тест", "цвет": "ЖЕЛТЫЙ"},
        ]

        with patch.object(service, "_fetch_providers_raw", new=AsyncMock(return_value=raw)):
            result = await service.get_today_stats_text()

        assert "Тест" in result
        assert "Трубок" in result

    @pytest.mark.asyncio
    async def test_returns_error_text_on_exception(self):
        from services.base_stats_service import BaseStatsService

        service = BaseStatsService.__new__(BaseStatsService)
        service.timezone = pytz.timezone("Europe/Kiev")
        service.url = "http://fake-url"

        with patch.object(
            service,
            "_fetch_providers_raw",
            new=AsyncMock(side_effect=Exception("Network error")),
        ):
            result = await service.get_today_stats_text()

        assert "⚠️" in result
        assert "ошибка" in result.lower() or "удалось" in result.lower()

    @pytest.mark.asyncio
    async def test_empty_data_returns_no_data_message(self):
        from services.base_stats_service import BaseStatsService

        service = BaseStatsService.__new__(BaseStatsService)
        service.timezone = pytz.timezone("Europe/Kiev")
        service.url = "http://fake-url"

        with patch.object(service, "_fetch_providers_raw", new=AsyncMock(return_value=[])):
            result = await service.get_today_stats_text()

        assert "пока нет" in result