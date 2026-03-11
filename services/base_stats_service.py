"""
services/base_stats_service.py
✅ ПЕРЕРАБОТАН: только получение данных по запросу (кнопка в боте)
Убрано автозаполнение Google Sheets — только текстовое сообщение за сегодня
"""

from datetime import datetime
from typing import List, Dict
import pytz
import aiohttp
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from utils.logger import logger
from config.settings import settings


class BaseStatsService:
    """Сервис статистики баз — получение данных по запросу"""

    def __init__(self):
        self.timezone = pytz.timezone("Europe/Kiev")
        self.url = getattr(settings, "GOOGLE_APPS_SCRIPT_URL", None)

        if not self.url:
            logger.warning("⚠️ GOOGLE_APPS_SCRIPT_URL не настроен — статистика баз недоступна")

    # ------------------------------------------------------------------
    # Получение сырых данных из Apps Script
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10),
        retry=retry_if_exception_type(aiohttp.ClientError),
    )
    async def _fetch_providers_raw(self, date_str: str) -> List[Dict]:
        """Запросить сырые данные поставщиков за дату (формат DD.MM)"""
        if not self.url:
            raise Exception("GOOGLE_APPS_SCRIPT_URL не настроен")

        params = {"action": "providers", "date": date_str}

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15)
        ) as session:
            async with session.get(self.url, params=params) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")

                data = await response.json(content_type=None)

                if isinstance(data, dict) and "error" in data:
                    if "не найден" in data["error"]:
                        logger.debug(f"📭 Лист {date_str} не найден в таблице")
                        return []
                    raise Exception(data["error"])

                if not isinstance(data, list):
                    raise ValueError(f"Apps Script вернул неожиданный тип: {type(data)}")

                return data

    # ------------------------------------------------------------------
    # Подсчёт статистики по поставщикам
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_stats(raw_data: List[Dict]) -> Dict[str, Dict[str, int]]:
        """
        Подсчитать по каждому поставщику:
          - calls  — всего трубок
          - bomzh  — розовые (РОЗОВЫЙ)
          - recalls — зелёные (ЗЕЛЕНЫЙ)
        """
        stats: Dict[str, Dict[str, int]] = {}

        for row in raw_data:
            provider = row.get("поставщик", "").strip()
            if not provider:
                continue

            if provider not in stats:
                stats[provider] = {"calls": 0, "bomzh": 0, "recalls": 0}

            stats[provider]["calls"] += 1

            color = row.get("цвет", "").strip().upper()
            if color == "РОЗОВЫЙ":
                stats[provider]["bomzh"] += 1
            elif color == "ЗЕЛЕНЫЙ":
                stats[provider]["recalls"] += 1

        return stats

    # ------------------------------------------------------------------
    # Форматирование текстового сообщения
    # ------------------------------------------------------------------

    @staticmethod
    def _format_message(
        stats: Dict[str, Dict[str, int]], date_str: str
    ) -> str:
        """Сформировать текстовое сообщение — каждый поставщик в отдельном блоке"""
        if not stats:
            return (
                f"<b>Статистика баз — {date_str}</b>\n\n"
                "Данных за сегодня пока нет."
            )

        lines = [f"<b>Статистика баз — {date_str}</b>"]

        total_calls = total_bomzh = total_recalls = 0

        for provider, data in sorted(stats.items()):
            calls   = data["calls"]
            bomzh   = data["bomzh"]
            recalls = data["recalls"]
            pct     = (recalls / calls * 100) if calls > 0 else 0.0

            total_calls   += calls
            total_bomzh   += bomzh
            total_recalls += recalls

            # Используем code-блок чтобы Telegram рендерил рамку корректно
            block = (
                f"┌──────────────────────────┐\n"
                f"│ {provider:<24} │\n"
                f"├──────────────────────────┤\n"
                f"│ Трубок:   {calls:<15}│\n"
                f"│ Бомжи:    {bomzh:<15}│\n"
                f"│ Перезв: {recalls:<6} ({pct:.1f}%)  │\n"
                f"└──────────────────────────┘"
            )
            lines.append(f"\n<code>{block}</code>")

        total_pct = (total_recalls / total_calls * 100) if total_calls > 0 else 0.0
        block = (
            f"┌──────────────────────────┐\n"
            f"│ {'ИТОГО':<24} │\n"
            f"├──────────────────────────┤\n"
            f"│ Трубок:   {total_calls:<15}│\n"
            f"│ Бомжи:    {total_bomzh:<15}│\n"
            f"│ Перезв: {total_recalls:<6} ({total_pct:.1f}%)  │\n"
            f"└──────────────────────────┘"
        )
        lines.append(f"\n<code>{block}</code>")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Публичный метод — вызывается из обработчика кнопки
    # ------------------------------------------------------------------

    async def get_today_stats_text(self) -> str:
        """
        Получить статистику баз за сегодня и вернуть готовый HTML-текст
        для отправки пользователю.
        """
        now = datetime.now(self.timezone)
        date_str = now.strftime("%d.%m")

        logger.info(f"📦 Запрос статистики баз за {date_str}")

        try:
            raw_data = await self._fetch_providers_raw(date_str)
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных баз: {e}")
            return (
                "⚠️ Не удалось получить статистику баз.\n"
                "Проверьте подключение к Google Apps Script или обратитесь к администратору."
            )

        stats = self._calculate_stats(raw_data)
        return self._format_message(stats, date_str)


# Глобальный экземпляр
base_stats_service = BaseStatsService()