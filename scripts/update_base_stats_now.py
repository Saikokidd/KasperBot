"""
scripts/update_base_stats_now.py
✅ ОБНОВЛЁН: теперь выводит статистику баз за сегодня в консоль (без записи в Google Sheets)
Запуск: python scripts/update_base_stats_now.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import logger


async def main():
    from services.base_stats_service import base_stats_service

    logger.info("🔄 Запрос статистики баз за сегодня...")

    text = await base_stats_service.get_today_stats_text()

    # Выводим результат (убираем HTML-теги для читаемости в консоли)
    import re
    clean = re.sub(r'<[^>]+>', '', text)
    print("\n" + clean)

    logger.info("✅ Готово")


if __name__ == "__main__":
    asyncio.run(main())