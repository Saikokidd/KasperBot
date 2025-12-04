"""
УЛУЧШЕНО: scripts/add_db_indexes.py
Добавляет индексы для оптимизации запросов

ИЗМЕНЕНИЯ:
✅ Индексы для error_reports
✅ Индексы для manager_sips
✅ Проверка существующих индексов
✅ Измерение улучшения производительности
"""
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "bot_data.db"


def check_index_exists(cursor, index_name: str) -> bool:
    """Проверяет существование индекса"""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        (index_name,)
    )
    return cursor.fetchone() is not None


def measure_query_time(cursor, query: str, params: tuple = ()) -> float:
    """Измеряет время выполнения запроса"""
    start = time.time()
    cursor.execute(query, params)
    cursor.fetchall()
    return time.time() - start


def create_indexes():
    """Создаёт индексы для оптимизации запросов"""
    
    print("🔧 Подключение к БД...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # ===== ПРОВЕРКА СУЩЕСТВУЮЩИХ ИНДЕКСОВ =====
    
    print("\n📋 Проверка существующих индексов...")
    
    cursor.execute("""
        SELECT name, tbl_name 
        FROM sqlite_master 
        WHERE type='index' AND sql IS NOT NULL
        ORDER BY tbl_name, name
    """)
    
    existing_indexes = cursor.fetchall()
    print(f"✅ Найдено индексов: {len(existing_indexes)}")
    
    for idx_name, tbl_name in existing_indexes:
        print(f"   • {tbl_name}.{idx_name}")
    
    # ===== ИЗМЕРЕНИЕ ДО ИНДЕКСОВ =====
    
    print("\n⏱ Измерение производительности ДО добавления индексов...")
    
    # Получаем количество записей
    cursor.execute("SELECT COUNT(*) FROM error_reports")
    total_errors = cursor.fetchone()[0]
    print(f"   Записей в error_reports: {total_errors}")
    
    if total_errors > 0:
        # Тестовый запрос 1: Поиск по user_id + telephony_code + status
        test_query_1 = """
            SELECT id, created_at FROM error_reports 
            WHERE user_id = ? AND telephony_code = ? AND status = 'new'
            ORDER BY created_at DESC LIMIT 1
        """
        time_before_1 = measure_query_time(cursor, test_query_1, (123456, 'bmw'))
        print(f"   Запрос 1 (user+tel+status): {time_before_1*1000:.2f}ms")
        
        # Тестовый запрос 2: Поиск по resolved_at
        test_query_2 = """
            SELECT COUNT(*) FROM error_reports 
            WHERE DATE(resolved_at) = DATE('now')
        """
        time_before_2 = measure_query_time(cursor, test_query_2)
        print(f"   Запрос 2 (resolved_at): {time_before_2*1000:.2f}ms")
    else:
        print("   ⚠️ Нет данных для тестирования")
        time_before_1 = 0
        time_before_2 = 0
    
    # ===== СОЗДАНИЕ ИНДЕКСОВ =====
    
    print("\n🔨 Создание индексов...")
    
    indexes_to_create = [
        # Индекс для поиска необработанных ошибок конкретного пользователя
        (
            "idx_error_reports_user_tel_status",
            """
            CREATE INDEX IF NOT EXISTS idx_error_reports_user_tel_status 
            ON error_reports(user_id, telephony_code, status, created_at DESC)
            """,
            "Для support_callback (поиск последней необработанной ошибки)"
        ),
        
        # Индекс для аналитики по дате решения
        (
            "idx_error_reports_resolved_at",
            """
            CREATE INDEX IF NOT EXISTS idx_error_reports_resolved_at 
            ON error_reports(resolved_at)
            """,
            "Для статистики (фильтр по дате решения)"
        ),
        
        # Индекс для аналитики по дате создания
        (
            "idx_error_reports_created_at",
            """
            CREATE INDEX IF NOT EXISTS idx_error_reports_created_at 
            ON error_reports(created_at)
            """,
            "Для дашборда (фильтр по дате создания)"
        ),
        
        # Индекс для фильтрации по типу телефонии
        (
            "idx_error_reports_telephony",
            """
            CREATE INDEX IF NOT EXISTS idx_error_reports_telephony 
            ON error_reports(telephony_code, created_at DESC)
            """,
            "Для статистики по телефониям"
        ),
        
        # Индекс для времени ответа (аналитика)
        (
            "idx_error_reports_response_time",
            """
            CREATE INDEX IF NOT EXISTS idx_error_reports_response_time 
            ON error_reports(resolved_at, response_time_seconds)
            WHERE response_time_seconds IS NOT NULL
            """,
            "Для статистики времени ответа"
        ),
        
        # Индекс для SIP менеджеров (дата последнего обновления)
        (
            "idx_manager_sips_last_updated",
            """
            CREATE INDEX IF NOT EXISTS idx_manager_sips_last_updated 
            ON manager_sips(last_updated)
            """,
            "Для проверки валидности SIP"
        ),
        
        # Индекс для статистики менеджеров по дням
        (
            "idx_manager_daily_stats_date",
            """
            CREATE INDEX IF NOT EXISTS idx_manager_daily_stats_date 
            ON manager_daily_stats(date, tubes_total DESC)
            """,
            "Для статистики менеджеров"
        ),
    ]
    
    created_count = 0
    skipped_count = 0
    
    for idx_name, sql, description in indexes_to_create:
        if check_index_exists(cursor, idx_name):
            print(f"   ⏭ Пропущен: {idx_name} (уже существует)")
            skipped_count += 1
        else:
            try:
                cursor.execute(sql)
                print(f"   ✅ Создан: {idx_name}")
                print(f"      {description}")
                created_count += 1
            except Exception as e:
                print(f"   ❌ Ошибка создания {idx_name}: {e}")
    
    conn.commit()
    
    # ===== ИЗМЕРЕНИЕ ПОСЛЕ ИНДЕКСОВ =====
    
    if total_errors > 0:
        print("\n⏱ Измерение производительности ПОСЛЕ добавления индексов...")
        
        time_after_1 = measure_query_time(cursor, test_query_1, (123456, 'bmw'))
        print(f"   Запрос 1 (user+tel+status): {time_after_1*1000:.2f}ms")
        
        time_after_2 = measure_query_time(cursor, test_query_2)
        print(f"   Запрос 2 (resolved_at): {time_after_2*1000:.2f}ms")
        
        # Улучшение
        if time_before_1 > 0:
            improvement_1 = ((time_before_1 - time_after_1) / time_before_1) * 100
            print(f"\n📊 Улучшение запроса 1: {improvement_1:.1f}%")
        
        if time_before_2 > 0:
            improvement_2 = ((time_before_2 - time_after_2) / time_before_2) * 100
            print(f"📊 Улучшение запроса 2: {improvement_2:.1f}%")
    
    # ===== VACUUM =====
    
    print("\n🧹 Оптимизация БД (VACUUM)...")
    cursor.execute("VACUUM")
    print("   ✅ VACUUM выполнен")
    
    # ===== ANALYZE =====
    
    print("\n📊 Обновление статистики (ANALYZE)...")
    cursor.execute("ANALYZE")
    print("   ✅ ANALYZE выполнен")
    
    conn.close()
    
    # ===== ИТОГИ =====
    
    print("\n" + "="*50)
    print("✅ ЗАВЕРШЕНО")
    print("="*50)
    print(f"📊 Создано индексов: {created_count}")
    print(f"⏭ Пропущено (уже есть): {skipped_count}")
    print(f"📋 Всего индексов в БД: {len(existing_indexes) + created_count}")
    
    if created_count > 0:
        print("\n💡 Рекомендация: Перезапустите бота для применения изменений")


if __name__ == "__main__":
    try:
        create_indexes()
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()