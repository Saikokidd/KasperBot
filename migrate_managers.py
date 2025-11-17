#!/usr/bin/env python3
"""
Скрипт миграции существующих менеджеров из .env в БД
Запустить один раз после обновления
"""
from database.models import db
from config.settings import settings
from utils.logger import logger


def migrate_managers():
    """Мигрирует менеджеров из .env в БД"""
    
    logger.info("🔄 Начало миграции менеджеров...")
    
    # Получаем список менеджеров из .env (исключая админов и пульт)
    managers_to_migrate = []
    
    for user_id in settings.MANAGERS:
        # Пропускаем админов и пульт
        if user_id in settings.ADMINS or user_id in settings.PULT:
            logger.info(f"⏭ Пропускаем админа/пульт: {user_id}")
            continue
        
        managers_to_migrate.append(user_id)
    
    logger.info(f"📊 Найдено менеджеров для миграции: {len(managers_to_migrate)}")
    
    # Добавляем в БД
    migrated = 0
    skipped = 0
    
    for user_id in managers_to_migrate:
        success = db.add_manager(
            user_id=user_id,
            username=None,  # Username неизвестен из .env
            first_name=None,  # Имя неизвестно из .env
            added_by=settings.ADMIN_ID
        )
        
        if success:
            migrated += 1
            logger.info(f"✅ Менеджер {user_id} добавлен в БД")
        else:
            skipped += 1
            logger.info(f"⚠️ Менеджер {user_id} уже существует")
    
    logger.info(f"✅ Миграция завершена!")
    logger.info(f"📊 Добавлено: {migrated}, Пропущено: {skipped}")
    
    # Показываем текущий список
    all_managers = db.get_all_managers()
    logger.info(f"📋 Всего менеджеров в БД: {len(all_managers)}")
    for m in all_managers:
        logger.info(f"  - ID: {m['user_id']}")


if __name__ == "__main__":
    migrate_managers()
