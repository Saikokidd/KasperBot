#!/usr/bin/env python3
"""
Скрипт для ручного обновления Google Sheets
"""
import asyncio
import sys
import os

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.google_sheets_service import GoogleSheetsService
from utils.logger import logger

async def main():
    try:
        logger.info("🔄 Запуск ручного обновления статистики...")
        
        # Создаём экземпляр сервиса
        service = GoogleSheetsService()
        
        if not service.client or not service.spreadsheet:
            logger.error("❌ Не удалось инициализировать Google Sheets сервис")
            return
        
        # Проверяем и создаём лист если нужно
        logger.info("📋 Проверка наличия листа текущей недели...")
        await service._create_weekly_sheet()
        
        # Обновляем статистику
        logger.info("📊 Обновление статистики...")
        await service.update_stats()
        
        logger.info("✅ Готово!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())