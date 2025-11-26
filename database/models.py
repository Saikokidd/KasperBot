"""
ИСПРАВЛЕННАЯ ПОЛНАЯ ВЕРСИЯ: database/models.py
Добавлена поддержка SIP менеджеров

ИЗМЕНЕНИЯ:
✅ Исправлен race condition в reset_all_sips
✅ Добавлены context managers для безопасного закрытия соединений
✅ Улучшена обработка ошибок
"""
import sqlite3
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from pathlib import Path
from contextlib import closing
from utils.logger import logger


class Database:
    """Класс для работы с SQLite базой данных"""
    
    def __init__(self, db_path: str = "bot_data.db"):
        self.db_path = db_path
        self._create_tables()
    
    def _get_connection(self):
        """Создаёт подключение к БД"""
        return sqlite3.connect(self.db_path)
    
    def _create_tables(self):
        """Создаёт все необходимые таблицы"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Таблица менеджеров
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS managers (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                added_by INTEGER
            )
        """)
        
        # Таблица телефоний
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telephonies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                code TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('white', 'black')),
                group_id INTEGER NOT NULL,
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER
            )
        """)
        
        # Таблица истории ошибок
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS error_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                telephony_code TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                support_user_id INTEGER,
                support_username TEXT,
                support_action TEXT,
                response_time_seconds INTEGER
            )
        """)
        
        # Таблица рассылок
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_text TEXT,
                sent_by INTEGER,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                recipients_count INTEGER,
                success_count INTEGER,
                failed_count INTEGER
            )
        """)
        
        # Таблица статистики менеджеров по дням
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manager_daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                date DATE NOT NULL,
                tubes_total INTEGER DEFAULT 0,
                tubes_green INTEGER DEFAULT 0,
                tubes_yellow INTEGER DEFAULT 0,
                tubes_purple INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, date)
            )
        """)
        
        # ✅ НОВАЯ ТАБЛИЦА: SIP менеджеров
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manager_sips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                sip_number TEXT NOT NULL,
                last_updated DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES managers(user_id)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("✅ Таблицы БД созданы/проверены")
    
    # ===== МЕНЕДЖЕРЫ =====
    
    def add_manager(self, user_id: int, username: str = None, 
                    first_name: str = None, added_by: int = None) -> bool:
        """Добавляет менеджера в БД"""
        try:
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO managers (user_id, username, first_name, added_by) VALUES (?, ?, ?, ?)",
                    (user_id, username, first_name, added_by)
                )
                conn.commit()
            logger.info(f"✅ Менеджер {user_id} добавлен в БД")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"⚠️ Менеджер {user_id} уже существует")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка добавления менеджера: {e}")
            return False
    
    def remove_manager(self, user_id: int) -> bool:
        """Удаляет менеджера"""
        try:
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM managers WHERE user_id = ?", (user_id,))
                deleted = cursor.rowcount > 0
                conn.commit()
            if deleted:
                logger.info(f"✅ Менеджер {user_id} удалён")
            return deleted
        except Exception as e:
            logger.error(f"❌ Ошибка удаления менеджера: {e}")
            return False
    
    def get_all_managers(self) -> List[Dict]:
        """Возвращает список всех менеджеров"""
        try:
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT user_id, username, first_name, added_at FROM managers ORDER BY added_at DESC"
                )
                rows = cursor.fetchall()
            
            return [
                {
                    "user_id": row[0],
                    "username": row[1],
                    "first_name": row[2],
                    "added_at": row[3]
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"❌ Ошибка получения менеджеров: {e}")
            return []
    
    def is_manager(self, user_id: int) -> bool:
        """Проверяет, является ли пользователь менеджером"""
        try:
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM managers WHERE user_id = ?", (user_id,))
                exists = cursor.fetchone() is not None
            return exists
        except Exception as e:
            logger.error(f"❌ Ошибка проверки менеджера: {e}")
            return False
    
    def update_manager_info(self, user_id: int, username: str = None, first_name: str = None) -> bool:
        """Обновляет информацию о менеджере"""
        try:
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE managers SET username = ?, first_name = ? WHERE user_id = ?",
                    (username, first_name, user_id)
                )
                updated = cursor.rowcount > 0
                conn.commit()
            if updated:
                logger.info(f"✅ Обновлены данные менеджера {user_id}: {username}, {first_name}")
            return updated
        except Exception as e:
            logger.error(f"❌ Ошибка обновления менеджера: {e}")
            return False
    
    # ===== ТЕЛЕФОНИИ =====
    
    def add_telephony(self, name: str, code: str, tel_type: str, 
                      group_id: int, created_by: int = None) -> bool:
        """Добавляет телефонию"""
        try:
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO telephonies (name, code, type, group_id, created_by) VALUES (?, ?, ?, ?, ?)",
                    (name, code.lower(), tel_type, group_id, created_by)
                )
                conn.commit()
            logger.info(f"✅ Телефония {name} ({tel_type}) добавлена")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"⚠️ Телефония {name} или код {code} уже существует")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка добавления телефонии: {e}")
            return False
    
    def remove_telephony(self, code: str) -> bool:
        """Удаляет телефонию по коду"""
        try:
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM telephonies WHERE code = ?", (code,))
                deleted = cursor.rowcount > 0
                conn.commit()
            if deleted:
                logger.info(f"✅ Телефония {code} удалена")
            return deleted
        except Exception as e:
            logger.error(f"❌ Ошибка удаления телефонии: {e}")
            return False
    
    def get_all_telephonies(self) -> List[Dict]:
        """Возвращает список всех телефоний"""
        try:
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name, code, type, group_id, enabled FROM telephonies WHERE enabled = 1 ORDER BY name"
                )
                rows = cursor.fetchall()
            
            return [
                {
                    "name": row[0],
                    "code": row[1],
                    "type": row[2],
                    "group_id": row[3],
                    "enabled": row[4]
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"❌ Ошибка получения телефоний: {e}")
            return []
    
    def get_telephony_by_code(self, code: str) -> Optional[Dict]:
        """Получает телефонию по коду"""
        try:
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name, code, type, group_id, enabled FROM telephonies WHERE code = ?",
                    (code,)
                )
                row = cursor.fetchone()
            
            if row:
                return {
                    "name": row[0],
                    "code": row[1],
                    "type": row[2],
                    "group_id": row[3],
                    "enabled": row[4]
                }
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения телефонии: {e}")
            return None
    
    def update_telephony_group(self, code: str, new_group_id: int) -> bool:
        """Обновляет ID группы для телефонии"""
        try:
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE telephonies SET group_id = ? WHERE code = ?",
                    (new_group_id, code)
                )
                updated = cursor.rowcount > 0
                conn.commit()
            if updated:
                logger.info(f"✅ Группа телефонии {code} обновлена")
            return updated
        except Exception as e:
            logger.error(f"❌ Ошибка обновления группы: {e}")
            return False
    
    # ===== ИСТОРИЯ ОШИБОК =====
    
    def log_error_report(self, user_id: int, username: str, 
                        telephony_code: str, description: str) -> Optional[int]:
        """Логирует отправленную ошибку"""
        try:
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO error_reports (user_id, username, telephony_code, description) VALUES (?, ?, ?, ?)",
                    (user_id, username, telephony_code, description)
                )
                report_id = cursor.lastrowid
                conn.commit()
            return report_id
        except Exception as e:
            logger.error(f"❌ Ошибка логирования ошибки: {e}")
            return None
    
    def update_error_report(self, report_id: int, support_user_id: int,
                           support_username: str, support_action: str,
                           response_time_seconds: int) -> bool:
        """Обновляет запись об ошибке после обработки саппортом"""
        try:
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE error_reports 
                    SET resolved_at = CURRENT_TIMESTAMP,
                        support_user_id = ?,
                        support_username = ?,
                        support_action = ?,
                        response_time_seconds = ?,
                        status = 'resolved'
                    WHERE id = ?
                """, (support_user_id, support_username, support_action, response_time_seconds, report_id))
                updated = cursor.rowcount > 0
                conn.commit()
            if updated:
                logger.info(f"✅ Ошибка #{report_id} обновлена в БД (время ответа: {response_time_seconds//60}м {response_time_seconds%60}с)")
            return updated
        except Exception as e:
            logger.error(f"❌ Ошибка обновления ошибки: {e}")
            return False
    
    # ===== СТАТИСТИКА МЕНЕДЖЕРОВ =====
    
    def upsert_manager_stats(self, user_id: int, username: str, first_name: str,
                            date_str: str, tubes_total: int, tubes_green: int = 0,
                            tubes_yellow: int = 0, tubes_purple: int = 0) -> bool:
        """Добавляет или обновляет статистику менеджера за день"""
        try:
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO manager_daily_stats 
                    (user_id, username, first_name, date, tubes_total, tubes_green, tubes_yellow, tubes_purple, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id, date) DO UPDATE SET
                        username = excluded.username,
                        first_name = excluded.first_name,
                        tubes_total = excluded.tubes_total,
                        tubes_green = excluded.tubes_green,
                        tubes_yellow = excluded.tubes_yellow,
                        tubes_purple = excluded.tubes_purple,
                        updated_at = CURRENT_TIMESTAMP
                """, (user_id, username, first_name, date_str, tubes_total, tubes_green, tubes_yellow, tubes_purple))
                conn.commit()
            logger.info(f"✅ Статистика менеджера {user_id} ({first_name}) за {date_str} обновлена: {tubes_total} трубок")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения статистики: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def get_managers_stats_for_date(self, date_str: str) -> List[Dict]:
        """Получить статистику всех менеджеров за конкретную дату"""
        try:
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT user_id, username, first_name, tubes_total, tubes_green, tubes_yellow, tubes_purple
                    FROM manager_daily_stats
                    WHERE date = ?
                    ORDER BY tubes_total DESC
                """, (date_str,))
                rows = cursor.fetchall()
            
            return [
                {
                    "user_id": row[0],
                    "username": row[1],
                    "name": row[2],
                    "tubes": row[3],
                    "green": row[4],
                    "yellow": row[5],
                    "purple": row[6]
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return []
    
    def get_managers_stats_for_week(self, start_date: str, end_date: str) -> Dict[int, Dict[str, Dict]]:
        """Получить статистику менеджеров за неделю (ПН-СБ)"""
        try:
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT user_id, username, first_name, date, tubes_total, tubes_green, tubes_yellow, tubes_purple
                    FROM manager_daily_stats
                    WHERE date BETWEEN ? AND ?
                    ORDER BY user_id, date
                """, (start_date, end_date))
                rows = cursor.fetchall()
            
            result = {}
            for row in rows:
                user_id = row[0]
                if user_id not in result:
                    result[user_id] = {
                        "username": row[1],
                        "name": row[2],
                        "dates": {}
                    }
                
                date_key = row[3]
                result[user_id]["dates"][date_key] = {
                    "tubes": row[4],
                    "green": row[5],
                    "yellow": row[6],
                    "purple": row[7]
                }
            
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка получения недельной статистики: {e}")
            return {}
    
    # ===== SIP МЕНЕДЖЕРОВ =====
    
    def save_manager_sip(self, user_id: int, sip_number: str) -> bool:
        """
        Сохранить/обновить SIP менеджера
        
        Args:
            user_id: ID менеджера
            sip_number: Номер SIP
            
        Returns:
            True если успешно
        """
        try:
            today = date.today().isoformat()
            
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO manager_sips (user_id, sip_number, last_updated)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        sip_number = excluded.sip_number,
                        last_updated = excluded.last_updated
                """, (user_id, sip_number, today))
                conn.commit()
            
            logger.info(f"✅ SIP сохранён для user_id={user_id}: {sip_number}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения SIP: {e}")
            return False
    
    def get_manager_sip(self, user_id: int) -> Optional[Dict]:
        """
        Получить SIP менеджера
        
        Args:
            user_id: ID менеджера
            
        Returns:
            {'sip_number': str, 'last_updated': str} или None
        """
        try:
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT sip_number, last_updated 
                    FROM manager_sips 
                    WHERE user_id = ?
                """, (user_id,))
                row = cursor.fetchone()
            
            if row:
                return {
                    'sip_number': row[0],
                    'last_updated': row[1]
                }
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения SIP: {e}")
            return None
    
    def is_sip_valid_today(self, user_id: int) -> bool:
        """
        Проверить, указан ли SIP сегодня
        
        Args:
            user_id: ID менеджера
            
        Returns:
            True если SIP указан сегодня
        """
        sip_data = self.get_manager_sip(user_id)
        
        if not sip_data:
            return False
        
        today = date.today().isoformat()
        return sip_data['last_updated'] == today
    
    def reset_all_sips(self) -> int:
        """
        Сбросить валидность всех SIP (вызывается утром в 8:00)
        
        ✅ ИСПРАВЛЕНО: Теперь не перезатирает SIP, которые уже были обновлены сегодня
        
        Returns:
            Количество сброшенных SIP
        """
        try:
            yesterday = (date.today() - timedelta(days=1)).isoformat()
            today = date.today().isoformat()
            
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                
                # ✅ ИСПРАВЛЕНИЕ: Обновляем только те SIP, которые НЕ были обновлены сегодня
                # Это предотвращает race condition при перезапуске бота
                cursor.execute("""
                    UPDATE manager_sips 
                    SET last_updated = ?
                    WHERE last_updated >= ?
                """, (yesterday, today))
                
                affected = cursor.rowcount
                conn.commit()
            
            if affected > 0:
                logger.info(f"✅ Сброшено {affected} SIP (не обновлённых сегодня)")
            else:
                logger.info("ℹ️ Все SIP уже были сброшены ранее")
            
            return affected
            
        except Exception as e:
            logger.error(f"❌ Ошибка сброса SIP: {e}")
            return 0


# Глобальный экземпляр БД
db = Database()