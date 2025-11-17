"""
Модели базы данных для KasperBot
"""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
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
                support_action TEXT
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
        
        conn.commit()
        conn.close()
        logger.info("✅ Таблицы БД созданы/проверены")
    
    # ===== МЕНЕДЖЕРЫ =====
    
    def add_manager(self, user_id: int, username: str = None, 
                    first_name: str = None, added_by: int = None) -> bool:
        """Добавляет менеджера в БД"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO managers (user_id, username, first_name, added_by) VALUES (?, ?, ?, ?)",
                (user_id, username, first_name, added_by)
            )
            conn.commit()
            conn.close()
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
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM managers WHERE user_id = ?", (user_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()
            if deleted:
                logger.info(f"✅ Менеджер {user_id} удалён")
            return deleted
        except Exception as e:
            logger.error(f"❌ Ошибка удаления менеджера: {e}")
            return False
    
    def get_all_managers(self) -> List[Dict]:
        """Возвращает список всех менеджеров"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, username, first_name, added_at FROM managers ORDER BY added_at DESC"
            )
            rows = cursor.fetchall()
            conn.close()
            
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
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM managers WHERE user_id = ?", (user_id,))
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception as e:
            logger.error(f"❌ Ошибка проверки менеджера: {e}")
            return False
    
    # ===== ТЕЛЕФОНИИ =====
    
    def add_telephony(self, name: str, code: str, tel_type: str, 
                      group_id: int, created_by: int = None) -> bool:
        """Добавляет телефонию"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO telephonies (name, code, type, group_id, created_by) VALUES (?, ?, ?, ?, ?)",
                (name, code.lower(), tel_type, group_id, created_by)
            )
            conn.commit()
            conn.close()
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
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM telephonies WHERE code = ?", (code,))
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()
            if deleted:
                logger.info(f"✅ Телефония {code} удалена")
            return deleted
        except Exception as e:
            logger.error(f"❌ Ошибка удаления телефонии: {e}")
            return False
    
    def get_all_telephonies(self) -> List[Dict]:
        """Возвращает список всех телефоний"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, code, type, group_id, enabled FROM telephonies WHERE enabled = 1 ORDER BY name"
            )
            rows = cursor.fetchall()
            conn.close()
            
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
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, code, type, group_id, enabled FROM telephonies WHERE code = ?",
                (code,)
            )
            row = cursor.fetchone()
            conn.close()
            
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
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE telephonies SET group_id = ? WHERE code = ?",
                (new_group_id, code)
            )
            updated = cursor.rowcount > 0
            conn.commit()
            conn.close()
            if updated:
                logger.info(f"✅ Группа телефонии {code} обновлена")
            return updated
        except Exception as e:
            logger.error(f"❌ Ошибка обновления группы: {e}")
            return False
    
    # ===== ИСТОРИЯ ОШИБОК =====
    
    def log_error_report(self, user_id: int, username: str, 
                        telephony_code: str, description: str) -> int:
        """Логирует отправленную ошибку"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO error_reports (user_id, username, telephony_code, description) VALUES (?, ?, ?, ?)",
                (user_id, username, telephony_code, description)
            )
            report_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return report_id
        except Exception as e:
            logger.error(f"❌ Ошибка логирования ошибки: {e}")
            return None


# Глобальный экземпляр БД
db = Database()