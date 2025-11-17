#!/usr/bin/env python3
"""
Скрипт миграции существующих телефоний в БД
Запустить один раз после обновления
"""
from database.models import db
from config.settings import settings
from utils.logger import logger


def migrate_telephonies():
    """Мигрирует телефонии из settings в БД"""
    
    logger.info("🔄 Начало миграции телефоний...")
    
    # BMW - белая телефония (с кнопками)
    success = db.add_telephony(
        name="BMW",
        code="bmw",
        tel_type="white",
        group_id=settings.BMW_GROUP_ID,
        created_by=settings.ADMIN_ID
    )
    
    if success:
        logger.info("✅ BMW добавлена")
    else:
        logger.info("⚠️ BMW уже существует")
    
    # Звонари - чёрная телефония (без кнопок)
    success = db.add_telephony(
        name="Звонари",
        code="zvon",
        tel_type="black",
        group_id=settings.ZVONARI_GROUP_ID,
        created_by=settings.ADMIN_ID
    )
    
    if success:
        logger.info("✅ Звонари добавлены")
    else:
        logger.info("⚠️ Звонари уже существуют")
    
    logger.info("✅ Миграция завершена!")
    
    # Показываем текущий список
    telephonies = db.get_all_telephonies()
    logger.info(f"�� Телефоний в БД: {len(telephonies)}")
    for tel in telephonies:
        logger.info(f"  - {tel['name']} ({tel['code']}) - {tel['type']}")


if __name__ == "__main__":
    migrate_telephonies()
