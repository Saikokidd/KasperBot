"""
Сервис для работы со статистикой из Google Sheets через Apps Script
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import aiohttp
from config.settings import settings
from utils.logger import logger


class StatsService:
    """Сервис для получения статистики перезвонов из Google Sheets"""

    async def get_perezvoni_stats(self) -> str:
        """
        Получает статистику перезвонов за сегодня из Google Sheets

        Returns:
            Форматированная строка со статистикой
        """
        try:
            # Получаем данные из таблицы
            data = await self._fetch_sheet_data()

            # Группируем по городам
            stats_by_city = self._group_by_city(data)

            # Форматируем результат
            result = self._format_stats(stats_by_city)

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}", exc_info=True)
            return "⚠️ Ошибка получения статистики из Google Sheets"

    async def _fetch_sheet_data(self) -> List[Dict]:
        """
        Получает данные из Google Sheets через Apps Script

        Returns:
            Список словарей с данными строк
        """
        url = settings.GOOGLE_APPS_SCRIPT_URL

        if not url:
            logger.error("❌ GOOGLE_APPS_SCRIPT_URL не установлен в .env")
            raise ValueError("GOOGLE_APPS_SCRIPT_URL не настроен")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        logger.error(f"❌ HTTP ошибка: {response.status}")
                        raise Exception(f"HTTP {response.status}")

                    data = await response.json()

                    # Проверка на ошибку от скрипта
                    if isinstance(data, dict) and "error" in data:
                        logger.error(f"❌ Ошибка от скрипта: {data['error']}")
                        raise Exception(data["error"])

                    logger.info(f"✅ Получено {len(data)} записей из Google Sheets")
                    return data

        except aiohttp.ClientError as e:
            logger.error(f"❌ Ошибка HTTP запроса: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных: {e}", exc_info=True)
            raise

    def _group_by_city(self, data: List[Dict]) -> Dict[str, Dict[str, int]]:
        """
        Группирует данные по городам и цветам

        Args:
            data: Данные из Google Sheets

        Returns:
            Словарь {город: {цвет: количество}}
        """
        stats = {}

        for row in data:
            city = row.get("город", "").strip()
            color = row.get("цвет", "").strip()

            if not city or not color:
                continue

            # Нормализуем название города
            if city not in stats:
                stats[city] = {"ЖЕЛТЫЙ": 0, "ЗЕЛЕНЫЙ": 0, "ФИОЛЕТОВЫЙ": 0}

            if color in stats[city]:
                stats[city][color] += 1

        return stats

    def _format_stats(self, stats: Dict[str, Dict[str, int]]) -> str:
        """
        Форматирует статистику в красивый текст

        Args:
            stats: Статистика по городам

        Returns:
            Форматированная строка
        """
        # Киевское время (UTC+2 зимой)
        kiev_tz = timezone(timedelta(hours=2))
        current_time = datetime.now(kiev_tz).strftime("%H:%M")

        # Эмодзи для цветов
        COLOR_EMOJI = {"ЖЕЛТЫЙ": "🟨", "ЗЕЛЕНЫЙ": "🟩", "ФИОЛЕТОВЫЙ": "🟪"}

        # Порядок городов
        city_order = ["Павлоград", "Харьков", "Днепр"]

        result = f"📊 <b>Статистика трубок на {current_time}</b>\n"
        result += "━━━━━━━━━━━━━━━━━━━━━━━━\n"

        for city in city_order:
            if city not in stats:
                continue

            city_stats = stats[city]
            total = sum(city_stats.values())

            if total == 0:
                continue

            green = city_stats["ЗЕЛЕНЫЙ"]
            yellow = city_stats["ЖЕЛТЫЙ"]
            purple = city_stats["ФИОЛЕТОВЫЙ"]

            green_pct = int((green / total) * 100) if total > 0 else 0
            yellow_pct = int((yellow / total) * 100) if total > 0 else 0
            purple_pct = int((purple / total) * 100) if total > 0 else 0

            result += f"<b>{city}:</b> {total}\n"

            # Показываем только цвета которые есть (больше 0)
            colors_to_show = []
            if green > 0:
                colors_to_show.append(f"{green}{COLOR_EMOJI['ЗЕЛЕНЫЙ']}({green_pct}%)")
            if yellow > 0:
                colors_to_show.append(f"{yellow}{COLOR_EMOJI['ЖЕЛТЫЙ']}({yellow_pct}%)")
            if purple > 0:
                colors_to_show.append(
                    f"{purple}{COLOR_EMOJI['ФИОЛЕТОВЫЙ']}({purple_pct}%)"
                )

            result += " ".join(colors_to_show) + "\n"
            result += "━━━━━━━━━━━━━━━━━━━━━━━━\n"

        return result


# Глобальный экземпляр сервиса
stats_service = StatsService()
