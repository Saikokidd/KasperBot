"""
Миграция БД: добавление поля quick_errors_enabled
Запустить ОДИН РАЗ перед обновлением бота

Использование:
    python3 scripts/add_quick_errors_column.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "bot_data.db"


def add_quick_errors_column():
    """Добавляет колонку quick_errors_enabled в таблицу telephonies"""

    print("🔄 Начало миграции: добавление поля quick_errors_enabled...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Проверяем существование колонки
        cursor.execute("PRAGMA table_info(telephonies)")
        columns = [row[1] for row in cursor.fetchall()]

        if "quick_errors_enabled" in columns:
            print("⏭  Колонка quick_errors_enabled уже существует")
        else:
            # Добавляем колонку
            cursor.execute(
                """
                ALTER TABLE telephonies 
                ADD COLUMN quick_errors_enabled INTEGER DEFAULT 0
            """
            )
            print("✅ Колонка quick_errors_enabled добавлена")

        # По умолчанию включаем быстрые ошибки для BMW (если есть)
        cursor.execute(
            """
            UPDATE telephonies 
            SET quick_errors_enabled = 1 
            WHERE code = 'bmw' AND type = 'white'
        """
        )

        updated = cursor.rowcount
        if updated > 0:
            print(f"✅ Быстрые ошибки включены для BMW")

        conn.commit()

        # Показываем текущее состояние
        cursor.execute(
            """
            SELECT name, code, type, quick_errors_enabled 
            FROM telephonies 
            WHERE type = 'white'
            ORDER BY name
        """
        )

        white_tels = cursor.fetchall()

        if white_tels:
            print("\n📊 Белые телефонии:")
            for name, code, tel_type, qe_enabled in white_tels:
                status = "✅ Включены" if qe_enabled else "❌ Выключены"
                print(f"  • {name} ({code}): {status}")
        else:
            print("\n⚠️  Белых телефоний не найдено")

        print("\n✅ Миграция завершена успешно!")

    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    add_quick_errors_column()
