"""
services/quick_error_service.py - СЕРВИС ДЛЯ БЫСТРЫХ ОШИБОК

НАЗНАЧЕНИЕ:
✅ Отделение логики быстрых ошибок от handlers/management.py
✅ CRUD операции для быстрых ошибок
✅ Связь между БМВ телефониями и быстрыми ошибками
✅ Валидация и логирование
"""
from typing import Optional, Tuple, List, Dict, Any
from database.models import db
from utils.logger import logger
from config.validators import InputValidator
from config.constants import QUICK_ERRORS, MAX_SIP_LENGTH


class QuickErrorService:
    """Сервис для управления быстрыми ошибками"""

    @staticmethod
    def get_quick_error_by_code(code: str) -> Optional[Dict[str, str]]:
        """
        Получает описание быстрой ошибки по коду

        Args:
            code: Код ошибки (1-10 или "custom")

        Returns:
            Dict с описанием или None
        """
        if code in QUICK_ERRORS:
            return {"code": code, "name": QUICK_ERRORS[code]}

        logger.warning(f"⚠️ Неизвестный код быстрой ошибки: {code}")
        return None

    @staticmethod
    def get_all_quick_errors() -> Dict[str, str]:
        """
        Получает все доступные быстрые ошибки

        Returns:
            Dict {код: описание}
        """
        return QUICK_ERRORS.copy()

    @staticmethod
    def add_quick_error_telephony(tel_code: str) -> Tuple[bool, Optional[str]]:
        """
        Добавляет телефонию к быстрым ошибкам

        Args:
            tel_code: Код телефонии

        Returns:
            (success, message)
        """
        # Валидация кода
        is_valid, error = InputValidator.validate_telephony_code(tel_code)
        if not is_valid:
            logger.warning(f"❌ Невалидный код телефонии: {error}")
            return False, error

        # Проверяем существование телефонии
        tel = db.get_telephony_by_code(tel_code)
        if not tel:
            error = f"❌ Телефония {tel_code} не найдена в БД"
            logger.warning(error)
            return False, error

        try:
            conn = db._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR IGNORE INTO quick_error_telephonies (tel_code)
                VALUES (?)
            """,
                (tel_code,),
            )

            if cursor.rowcount == 0:
                conn.close()
                msg = f"⚠️ Телефония {tel_code} уже добавлена к быстрым ошибкам"
                logger.warning(msg)
                return False, msg

            conn.commit()
            conn.close()

            msg = f"✅ Телефония {tel['name']} ({tel_code}) добавлена к быстрым ошибкам"
            logger.info(msg)
            return True, msg

        except Exception as e:
            logger.error(f"❌ Ошибка добавления быстрой ошибки: {e}")
            return False, f"❌ Ошибка базы данных: {str(e)}"

    @staticmethod
    def remove_quick_error_telephony(tel_code: str) -> Tuple[bool, Optional[str]]:
        """
        Удаляет телефонию из быстрых ошибок

        Args:
            tel_code: Код телефонии

        Returns:
            (success, message)
        """
        # Валидация кода
        is_valid, error = InputValidator.validate_telephony_code(tel_code)
        if not is_valid:
            logger.warning(f"❌ Невалидный код телефонии: {error}")
            return False, error

        try:
            conn = db._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM quick_error_telephonies
                WHERE tel_code = ?
            """,
                (tel_code,),
            )

            if cursor.rowcount == 0:
                conn.close()
                msg = f"⚠️ Телефония {tel_code} не найдена в быстрых ошибках"
                logger.warning(msg)
                return False, msg

            conn.commit()
            conn.close()

            msg = f"✅ Телефония {tel_code} удалена из быстрых ошибок"
            logger.info(msg)
            return True, msg

        except Exception as e:
            logger.error(f"❌ Ошибка удаления быстрой ошибки: {e}")
            return False, f"❌ Ошибка базы данных: {str(e)}"

    @staticmethod
    def get_quick_error_telephonies() -> List[Dict[str, Any]]:
        """
        Получает все телефонии с быстрыми ошибками

        Returns:
            List со данными телефоний
        """
        try:
            conn = db._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT t.id, t.name, t.code, t.type, q.added_at
                FROM quick_error_telephonies q
                JOIN telephonies t ON q.tel_code = t.code
                ORDER BY q.added_at DESC
            """
            )

            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            conn.close()

            return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error(f"❌ Ошибка получения телефоний быстрых ошибок: {e}")
            return []

    @staticmethod
    def is_quick_error_enabled(tel_code: str) -> bool:
        """
        Проверяет, включены ли быстрые ошибки для телефонии

        Args:
            tel_code: Код телефонии

        Returns:
            True если быстрые ошибки включены
        """
        return db.is_quick_error_telephony(tel_code)

    @staticmethod
    def validate_quick_error_code(code: str) -> Tuple[bool, Optional[str]]:
        """
        Валидирует код быстрой ошибки

        Args:
            code: Код ошибки (должен быть в QUICK_ERRORS)

        Returns:
            (is_valid, error_message)
        """
        if not code or not code.strip():
            return False, "❌ Код ошибки не может быть пустым"

        code = code.strip()

        if code not in QUICK_ERRORS and code != "custom":
            codes_list = ", ".join(QUICK_ERRORS.keys())
            return (
                False,
                f"❌ Неизвестный код ошибки '{code}'. Допустимые: {codes_list}, custom",
            )

        return True, None

    @staticmethod
    def validate_sip_for_quick_error(sip: str) -> Tuple[bool, Optional[str]]:
        """
        Валидирует SIP номер для быстрой ошибки

        Args:
            sip: SIP номер

        Returns:
            (is_valid, error_message)
        """
        return InputValidator.validate_sip_number(sip)

    @staticmethod
    def format_quick_error_message(
        tel_name: str, tel_code: str, sip: str, error_code: str, error_name: str
    ) -> str:
        """
        Форматирует сообщение о быстрой ошибке для отправки в группу

        Args:
            tel_name: Название телефонии
            tel_code: Код телефонии
            sip: SIP номер
            error_code: Код ошибки
            error_name: Описание ошибки

        Returns:
            Форматированное сообщение
        """
        message = (
            f"⚡️ <b>БЫСТРАЯ ОШИБКА - {tel_name.upper()}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📞 <b>Телефония:</b> {tel_name} ({tel_code})\n"
            f"🔢 <b>SIP:</b> {sip}\n"
            f"❌ <b>Ошибка:</b> {error_code}. {error_name}\n"
        )
        return message
