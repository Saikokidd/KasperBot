# scripts/add_ruton_tables.py

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "bot_data.db"


def create_ruton_tables():
    """Создаёт таблицы для Ruton интеграции"""

    print("🔄 Создание таблиц для Ruton...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Таблица логов поисков
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ruton_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                manager_id INTEGER NOT NULL,
                manager_name TEXT,
                search_type TEXT NOT NULL,
                search_query TEXT NOT NULL,
                results_count INTEGER DEFAULT 0,
                search_id TEXT,
                response_time_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (manager_id) REFERENCES managers(user_id)
            )
        """
        )

        # Индекс для статистики
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ruton_searches_manager 
            ON ruton_searches(manager_id, created_at)
        """
        )

        conn.commit()

        print("✅ Таблицы Ruton созданы успешно")

        # Проверка
        cursor.execute("SELECT COUNT(*) FROM ruton_searches")
        count = cursor.fetchone()[0]
        print(f"📊 Записей в ruton_searches: {count}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    create_ruton_tables()
