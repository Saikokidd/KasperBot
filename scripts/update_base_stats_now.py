#!/usr/bin/env python3
"""
Скрипт для ручного обновления статистики баз

Использование:
    python3 scripts/update_base_stats_now.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.base_stats_service import base_stats_service
from utils.logger import logger


async def main():
    try:
        logger.info("🔄 Запуск ручного обновления статистики баз...")
        
        if not base_stats_service.client or not base_stats_service.spreadsheet:
            logger.error("❌ BaseStatsService не инициализирован!")
            logger.error("   Проверьте:")
            logger.error("   1. BASE_STATS_SHEET_ID в .env")
            logger.error("   2. google_credentials.json существует")
            logger.error("   3. Сервис-аккаунт имеет доступ к таблице")
            return
        
        logger.info(f"📋 Таблица: {base_stats_service.spreadsheet.title}")
        
        await base_stats_service.update_stats()
        
        logger.info("✅ Готово!")
        logger.info("   Проверьте таблицу в Google Sheets")
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())
