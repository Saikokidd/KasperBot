#!/usr/bin/env python3
"""
Миграция БД: добавление полей для аналитики
"""
import sqlite3
from utils.logger import logger


def migrate_analytics_fields():
    """Добавляет поля для аналитики в таблицу error_reports"""

    logger.info("🔄 Начало миграции: добавление полей аналитики...")

    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()

    # Проверяем какие поля уже есть
    cursor.execute("PRAGMA table_info(error_reports)")
    existing_columns = [row[1] for row in cursor.fetchall()]

    # Добавляем недостающие поля
    fields_to_add = {"support_username": "TEXT", "response_time_seconds": "INTEGER"}

    for field, field_type in fields_to_add.items():
        if field not in existing_columns:
            try:
                cursor.execute(
                    f"ALTER TABLE error_reports ADD COLUMN {field} {field_type}"
                )
                logger.info(f"✅ Добавлено поле: {field}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    logger.info(f"⏭ Поле {field} уже существует")
                else:
                    logger.error(f"❌ Ошибка добавления поля {field}: {e}")
        else:
            logger.info(f"⏭ Поле {field} уже существует")

    conn.commit()
    conn.close()

    logger.info("✅ Миграция завершена!")


if __name__ == "__main__":
    migrate_analytics_fields()
