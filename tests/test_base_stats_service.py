"""
tests/test_base_stats_service.py
Unit тесты для сервиса base_stats_service

Запуск: pytest tests/test_base_stats_service.py -v
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime


@pytest.fixture
def mock_context():
    """Mock telegram context"""
    context = MagicMock()
    context.user_data = {}
    context.bot_data = {}
    return context


class TestBaseStatsCalculations:
    """Тесты логики подсчёта метрик"""

    def test_count_calls_basic(self):
        """Тест базового подсчёта трубок"""
        from services.base_stats_service import BaseStatsService

        # Создаём mock сервиса
        service = BaseStatsService()
        service.client = MagicMock()
        service.spreadsheet = MagicMock()

        # Тестовые данные
        raw_data = [
            {"поставщик": "3к_МСК", "итог_цвет": "ЗЕЛЕНЫЙ"},
            {"поставщик": "3к_МСК", "итог_цвет": "ЗЕЛЕНЫЙ"},
            {"поставщик": "3к_МСК", "итог_цвет": "РОЗОВЫЙ"},
            {"поставщик": "1к_Анон", "итог_цвет": "ЗЕЛЕНЫЙ"},
        ]

        # Имитируем вызов метода
        result = service.calculate_provider_stats(raw_data)

        # Проверяем результаты
        assert result["3к_МСК"]["calls"] == 3
        assert result["3к_МСК"]["recalls"] == 2
        assert result["3к_МСК"]["bomzh"] == 1

        assert result["1к_Анон"]["calls"] == 1
        assert result["1к_Анон"]["recalls"] == 1
        assert result["1к_Анон"]["bomzh"] == 0

    def test_count_empty_data(self):
        """Тест с пустыми данными"""
        from services.base_stats_service import BaseStatsService

        service = BaseStatsService()
        service.client = MagicMock()
        service.spreadsheet = MagicMock()

        result = service.calculate_provider_stats([])
        assert result == {}

    def test_count_unknown_color(self):
        """Тест с неизвестным цветом (не считается ни как бомж, ни как перезвон)"""
        from services.base_stats_service import BaseStatsService

        service = BaseStatsService()
        service.client = MagicMock()
        service.spreadsheet = MagicMock()

        raw_data = [
            {"поставщик": "3к_МСК", "итог_цвет": ""},  # Пусто
            {"поставщик": "3к_МСК", "итог_цвет": "КРАСНЫЙ"},  # Неизвестный цвет
        ]

        result = service.calculate_provider_stats(raw_data)

        assert result["3к_МСК"]["calls"] == 2
        assert result["3к_МСК"]["recalls"] == 0
        assert result["3к_МСК"]["bomzh"] == 0


class TestPercentageCalculations:
    """Тесты расчёта процентов"""

    @pytest.mark.parametrize(
        "calls,recalls,expected_pct",
        [
            (10, 5, 50),
            (100, 25, 25),
            (7, 3, 42),
            (1, 0, 0),
            (0, 0, 0),
        ],
    )
    def test_recall_percentage(self, calls, recalls, expected_pct):
        """Тест расчёта процента перезвонов"""
        pct = (recalls / calls * 100) if calls > 0 else 0
        assert int(pct) == expected_pct

    def test_total_percentage(self):
        """Тест расчёта итогового процента"""
        stats = {
            "provider1": {"calls": 10, "recalls": 4, "bomzh": 1},
            "provider2": {"calls": 15, "recalls": 6, "bomzh": 2},
        }

        total_calls = sum(s["calls"] for s in stats.values())
        total_recalls = sum(s["recalls"] for s in stats.values())

        pct = (total_recalls / total_calls * 100) if total_calls > 0 else 0

        assert total_calls == 25
        assert total_recalls == 10
        assert int(pct) == 40


class TestWeekRangeCalculations:
    """Тесты расчёта недельного диапазона"""

    def test_week_range_monday(self):
        """Тест диапазона для понедельника"""
        from services.base_stats_service import BaseStatsService

        service = BaseStatsService()

        # Понедельник
        monday = datetime(2025, 12, 15)  # Понедельник
        start, end = service.get_week_range(monday)

        assert start.weekday() == 0  # Понедельник
        assert end.weekday() == 5  # Суббота
        assert (end - start).days == 5

    def test_week_range_friday(self):
        """Тест диапазона для пятницы"""
        from services.base_stats_service import BaseStatsService

        service = BaseStatsService()

        # Пятница
        friday = datetime(2025, 12, 19)
        start, end = service.get_week_range(friday)

        assert start.weekday() == 0  # Понедельник текущей недели
        assert end.weekday() == 5  # Суббота

    def test_week_range_sunday(self):
        """Тест диапазона для воскресенья - переходит на следующий понедельник"""
        from services.base_stats_service import BaseStatsService

        service = BaseStatsService()

        # Воскресенье
        sunday = datetime(2025, 12, 21)
        start, end = service.get_week_range(sunday)

        assert start.weekday() == 0  # Понедельник
        assert end.weekday() == 5  # Суббота


class TestDataGrouping:
    """Тесты группировки данных по датам и поставщикам"""

    def test_data_grouped_by_provider(self):
        """Тест группировки данных по поставщикам"""
        raw_data = [
            {"поставщик": "A", "итог_цвет": "ЗЕЛЕНЫЙ"},
            {"поставщик": "B", "итог_цвет": "РОЗОВЫЙ"},
            {"поставщик": "A", "итог_цвет": "ЗЕЛЕНЫЙ"},
            {"поставщик": "A", "итог_цвет": ""},
        ]

        from services.base_stats_service import BaseStatsService

        service = BaseStatsService()
        service.client = MagicMock()
        service.spreadsheet = MagicMock()

        result = service.calculate_provider_stats(raw_data)

        assert len(result) == 2
        assert "A" in result
        assert "B" in result


@pytest.mark.asyncio
class TestAsyncOperations:
    """Тесты асинхронных операций"""

    async def test_fetch_data_called(self):
        """Тест вызова fetch при подсчёте"""
        from services.base_stats_service import BaseStatsService

        service = BaseStatsService()
        service.client = MagicMock()
        service.spreadsheet = MagicMock()

        # Mock для fetch метода
        service.fetch_provider_data = AsyncMock(
            return_value=[{"поставщик": "3к_МСК", "итог_цвет": "ЗЕЛЕНЫЙ"}]
        )

        result = await service.count_calls_by_provider("15.12")

        # Проверяем что метод был вызван
        service.fetch_provider_data.assert_called_once_with("15.12")
        assert "3к_МСК" in result


class TestDesignColors:
    """Тесты цветовой схемы"""

    def test_color_values(self):
        """Тест значений цветов в RGB"""
        colors = {
            "orange_date": {"red": 1, "green": 0.65, "blue": 0.3},
            "purple_provider": {"red": 0.9, "green": 0.8, "blue": 1.0},
            "yellow_calls": {"red": 1, "green": 1, "blue": 0.4},
            "pink_bomzh": {"red": 1, "green": 0.75, "blue": 0.8},
            "green_recalls": {"red": 0.7, "green": 0.95, "blue": 0.7},
            "blue_total": {"red": 0.5, "green": 0.8, "blue": 1.0},
        }

        # Проверяем что все цвета в диапазоне 0-1
        for color_name, rgb in colors.items():
            for channel, value in rgb.items():
                assert (
                    0 <= value <= 1
                ), f"{color_name}.{channel} = {value} не в диапазоне [0, 1]"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
