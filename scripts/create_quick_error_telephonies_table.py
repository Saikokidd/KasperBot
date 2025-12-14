#!/usr/bin/env python3
"""
Создание таблицы quick_error_telephonies

Запуск: python3 scripts/create_quick_error_telephonies_table.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "bot_data.db"


def create_table():
    """Создаёт таблицу quick_error_telephonies"""
    
    print("🔄 Создание таблицы quick_error_telephonies...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Создаём таблицу
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quick_error_telephonies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telephony_code TEXT UNIQUE NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telephony_code) REFERENCES telephonies(code)
            )
        """)
        
        print("✅ Таблица quick_error_telephonies создана")
        
        # Проверяем существующие записи
        cursor.execute("SELECT COUNT(*) FROM quick_error_telephonies")
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"ℹ️  В таблице уже есть {count} записей")
            
            cursor.execute("""
                SELECT qe.telephony_code, t.name
                FROM quick_error_telephonies qe
                LEFT JOIN telephonies t ON qe.telephony_code = t.code
            """)
            
            for code, name in cursor.fetchall():
                print(f"   • {name or 'УДАЛЕНА'} ({code})")
        else:
            print("ℹ️  Таблица пуста")
            print("\nДобавьте телефонии через:")
            print("  Управление ботом → Быстрые ошибки → Добавить")
        
        conn.commit()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
    
    print("\n✅ Миграция завершена успешно!")


if __name__ == "__main__":
    create_table()
