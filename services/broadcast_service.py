"""
services/broadcast_service.py - СЕРВИС ДЛЯ РАССЫЛОК

НАЗНАЧЕНИЕ:
✅ Отделение логики рассылок от handlers/management.py
✅ Управление рассылками (создание, отправка, истории)
✅ Безопасная отправка с обработкой ошибок
✅ Логирование всех рассылок в БД
"""
from typing import Optional, Tuple, List
from telegram.ext import ContextTypes
from telegram import error as telegram_error
from database.models import db
from utils.logger import logger
from config.validators import InputValidator


class BroadcastService:
    """Сервис для управления рассылками"""
    
    @staticmethod
    def validate_message(message: str) -> Tuple[bool, Optional[str]]:
        """
        Валидирует сообщение для рассылки
        
        Args:
            message: Текст сообщения
            
        Returns:
            (is_valid, error_message)
        """
        is_valid, error = InputValidator.validate_error_description(message)
        
        if not is_valid:
            return False, error
        
        # Проверяем длину (limit Telegram API)
        if len(message) > 4096:
            return False, f"❌ Сообщение слишком длинное ({len(message)}/4096 символов)"
        
        return True, None
    
    @staticmethod
    async def send_to_group(
        context: ContextTypes.DEFAULT_TYPE,
        group_id: int,
        message: str,
        parse_mode: str = "HTML"
    ) -> Tuple[bool, Optional[str]]:
        """
        Отправляет сообщение в группу с обработкой ошибок
        
        Args:
            context: Контекст бота
            group_id: ID группы для отправки
            message: Текст сообщения
            parse_mode: Режим парсинга (HTML, Markdown и т.д.)
            
        Returns:
            (success, error_message)
        """
        # Валидация ID группы
        is_valid, error = InputValidator.validate_group_id(group_id)
        if not is_valid:
            logger.error(f"❌ Невалидный ID группы: {error}")
            return False, error
        
        # Валидация сообщения
        is_valid, error = BroadcastService.validate_message(message)
        if not is_valid:
            logger.error(f"❌ Невалидное сообщение: {error}")
            return False, error
        
        try:
            await context.bot.send_message(
                chat_id=group_id,
                text=message,
                parse_mode=parse_mode
            )
            
            logger.info(f"✅ Сообщение отправлено в группу {group_id}")
            return True, None
            
        except telegram_error.ChatNotFound:
            error = f"❌ Группа {group_id} не найдена"
            logger.error(error)
            return False, error
            
        except telegram_error.ChatAdministratorRequired:
            error = f"❌ Бот не администратор в группе {group_id}"
            logger.error(error)
            return False, error
            
        except telegram_error.BadRequest as e:
            error = f"❌ Ошибка формата сообщения: {e}"
            logger.error(error)
            return False, error
            
        except Exception as e:
            error = f"❌ Ошибка отправки сообщения: {e}"
            logger.error(error)
            return False, error
    
    @staticmethod
    async def broadcast_to_all_managers(
        context: ContextTypes.DEFAULT_TYPE,
        message: str,
        parse_mode: str = "HTML"
    ) -> Tuple[bool, int, int]:
        """
        Отправляет рассылку всем менеджерам (в личные сообщения)
        
        Args:
            context: Контекст бота
            message: Текст сообщения
            parse_mode: Режим парсинга
            
        Returns:
            (success, sent_count, failed_count)
        """
        # Валидация сообщения
        is_valid, error = BroadcastService.validate_message(message)
        if not is_valid:
            logger.error(f"❌ Невалидное сообщение: {error}")
            return False, 0, 0
        
        managers = db.get_all_managers()
        
        if not managers:
            logger.warning("⚠️ Нет менеджеров в БД для рассылки")
            return False, 0, 0
        
        sent_count = 0
        failed_count = 0
        
        for manager in managers:
            try:
                await context.bot.send_message(
                    chat_id=manager['user_id'],
                    text=message,
                    parse_mode=parse_mode
                )
                sent_count += 1
                logger.debug(f"✅ Сообщение отправлено менеджеру {manager['user_id']}")
                
            except Exception as e:
                failed_count += 1
                logger.warning(f"⚠️ Ошибка отправки менеджеру {manager['user_id']}: {e}")
        
        logger.info(f"📢 Рассылка завершена: {sent_count} успешно, {failed_count} ошибок")
        
        return True, sent_count, failed_count
    
    @staticmethod
    async def broadcast_to_group_managers(
        context: ContextTypes.DEFAULT_TYPE,
        group_id: int,
        message: str,
        parse_mode: str = "HTML"
    ) -> Tuple[bool, Optional[str]]:
        """
        Отправляет рассылку в группу менеджеров
        
        Args:
            context: Контекст бота
            group_id: ID группы
            message: Текст сообщения
            parse_mode: Режим парсинга
            
        Returns:
            (success, error_message)
        """
        return await BroadcastService.send_to_group(
            context, group_id, message, parse_mode
        )
    
    @staticmethod
    def log_broadcast(
        message: str,
        target: str,
        target_id: int,
        status: str = "sent"
    ) -> bool:
        """
        Логирует рассылку в БД
        
        Args:
            message: Текст сообщения
            target: Тип цели ("group" или "managers")
            target_id: ID цели (group_id или 0 для всех менеджеров)
            status: Статус ("sent", "failed", "pending")
            
        Returns:
            True если успешно
        """
        try:
            conn = db._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR IGNORE INTO broadcasts 
                (message, target_type, target_id, status, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (message, target, target_id, status))
            
            conn.commit()
            conn.close()
            
            logger.info(f"💾 Рассылка залогирована: {target} #{target_id} ({status})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка логирования рассылки: {e}")
            return False
    
    @staticmethod
    def get_broadcast_history(limit: int = 10) -> List[dict]:
        """
        Получает историю рассылок
        
        Args:
            limit: Максимальное количество записей
            
        Returns:
            List со строками истории
        """
        try:
            conn = db._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM broadcasts
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(zip(columns, row)) for row in rows]
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения истории рассылок: {e}")
            return []
