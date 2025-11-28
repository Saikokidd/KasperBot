#!/usr/bin/env python3
"""
Миграция БД: добавление индексов для ускорения аналитики
"""
import sqlite3
import sys
import os

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import logger


def add_indexes():
    """Добавляет индексы в таблицы для ускорения запросов"""
    
    logger.info("🔄 Начало добавления индексов в БД...")
    
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    
    # Индексы для таблицы error_reports
    indexes_to_create = [
        # Для фильтрации по дате создания (используется везде в аналитике)
        ("idx_error_reports_created_at", "error_reports", "created_at"),
        
        # Для фильтрации по дате решения
        ("idx_error_reports_resolved_at", "error_reports", "resolved_at"),
        
        # Для группировки по телефонии
        ("idx_error_reports_telephony", "error_reports", "telephony_code"),
        
        # Для группировки по менеджерам
        ("idx_error_reports_user", "error_reports", "user_id"),
        
        # Для группировки по саппорту
        ("idx_error_reports_support", "error_reports", "support_user_id"),
        
        # Для фильтрации по статусу
        ("idx_error_reports_status", "error_reports", "status"),
        
        # Составной индекс для частых запросов (дата + статус)
        ("idx_error_reports_date_status", "error_reports", "created_at, status"),
        
        # Составной индекс (дата решения + время ответа) для статистики времени
        ("idx_error_reports_resolved_time", "error_reports", "resolved_at, response_time_seconds"),
    ]
    
    # Индексы для таблицы manager_daily_stats
    indexes_to_create.extend([
        # Для поиска по дате
        ("idx_manager_stats_date", "manager_daily_stats", "date"),
        
        # Для поиска по менеджеру
        ("idx_manager_stats_user", "manager_daily_stats", "user_id"),
        
        # Составной индекс (user + date) — используется в UNIQUE constraint, но явный индекс быстрее
        ("idx_manager_stats_user_date", "manager_daily_stats", "user_id, date"),
    ])
    
    # Индексы для таблицы manager_sips
    indexes_to_create.extend([
        # Для проверки актуальности SIP
        ("idx_manager_sips_updated", "manager_sips", "last_updated"),
    ])
    
    created = 0
    skipped = 0
    
    for index_name, table_name, columns in indexes_to_create:
        try:
            # Проверяем существование индекса
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                (index_name,)
            )
            
            if cursor.fetchone():
                logger.info(f"⏭ Индекс {index_name} уже существует")
                skipped += 1
                continue
            
            # Создаём индекс
            cursor.execute(f"CREATE INDEX {index_name} ON {table_name}({columns})")
            logger.info(f"✅ Создан индекс: {index_name} на {table_name}({columns})")
            created += 1
            
        except sqlite3.Error as e:
            logger.error(f"❌ Ошибка создания индекса {index_name}: {e}")
    
    conn.commit()
    
    # Анализируем таблицы для обновления статистики
    logger.info("📊 Анализ таблиц...")
    for table in ["error_reports", "manager_daily_stats", "manager_sips"]:
        try:
            cursor.execute(f"ANALYZE {table}")
            logger.info(f"✅ Анализ таблицы {table} завершён")
        except sqlite3.Error as e:
            logger.error(f"❌ Ошибка анализа {table}: {e}")
    
    conn.commit()
    conn.close()
    
    logger.info("=" * 60)
    logger.info(f"✅ Миграция завершена!")
    logger.info(f"📊 Создано индексов: {created}")
    logger.info(f"⏭ Пропущено (уже существуют): {skipped}")
    logger.info(f"📈 Аналитика теперь работает быстрее!")
    logger.info("=" * 60)


if __name__ == "__main__":
    add_indexes()
