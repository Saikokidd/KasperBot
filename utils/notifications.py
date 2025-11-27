"""
Модуль для отправки уведомлений администраторам
"""
from datetime import datetime
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError

from config.settings import settings
from utils.logger import logger


class NotificationService:
    """Сервис для отправки уведомлений админам"""
    
    # Защита от спама - не отправлять одинаковые уведомления чаще чем раз в N минут
    _last_notifications = {}
    _cooldown_minutes = 30
    
    @staticmethod
    async def notify_critical_error(
        bot: Bot,
        error_type: str,
        details: str,
        additional_info: Optional[str] = None
    ):
        """
        Отправить критическое уведомление админам
        
        Args:
            bot: Экземпляр бота
            error_type: Тип ошибки (например: "Google Sheets", "Планировщик")
            details: Детали ошибки
            additional_info: Дополнительная информация
        """
        # Проверка на спам
        notification_key = f"{error_type}:{details[:50]}"
        
        if NotificationService._is_recently_sent(notification_key):
            logger.debug(f"⏭ Пропускаем уведомление (cooldown): {error_type}")
            return
        
        # Формируем сообщение
        message = NotificationService._format_critical_message(
            error_type, details, additional_info
        )
        
        # Отправляем всем админам
        success_count = 0
        for admin_id in settings.ADMINS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode="HTML"
                )
                success_count += 1
                logger.info(f"✅ Критическое уведомление отправлено админу {admin_id}")
            except TelegramError as e:
                logger.error(f"❌ Не удалось уведомить админа {admin_id}: {e}")
        
        if success_count > 0:
            # Сохраняем время последней отправки
            NotificationService._last_notifications[notification_key] = datetime.now()
            logger.info(f"📨 Критическое уведомление отправлено {success_count} админам")
    
    @staticmethod
    async def notify_warning(
        bot: Bot,
        warning_type: str,
        details: str
    ):
        """
        Отправить предупреждение админам
        
        Args:
            bot: Экземпляр бота
            warning_type: Тип предупреждения
            details: Детали
        """
        message = (
            f"⚠️ <b>ПРЕДУПРЕЖДЕНИЕ</b>\n\n"
            f"📝 {warning_type}\n"
            f"ℹ️ {details}\n\n"
            f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        
        for admin_id in settings.ADMINS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode="HTML"
                )
            except TelegramError as e:
                logger.error(f"❌ Не удалось отправить предупреждение админу {admin_id}: {e}")
    
    @staticmethod
    async def notify_recovery(
        bot: Bot,
        service_name: str
    ):
        """
        Уведомление о восстановлении после ошибок
        
        Args:
            bot: Экземпляр бота
            service_name: Название сервиса который восстановился
        """
        message = (
            f"✅ <b>ВОССТАНОВЛЕНИЕ</b>\n\n"
            f"📊 {service_name}\n"
            f"✅ Работа восстановлена после ошибок\n\n"
            f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        
        for admin_id in settings.ADMINS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode="HTML"
                )
            except TelegramError:
                pass  # Не логируем ошибки для recovery уведомлений
    
    @staticmethod
    def _format_critical_message(
        error_type: str,
        details: str,
        additional_info: Optional[str]
    ) -> str:
        """Форматирует критическое сообщение"""
        
        # Ограничиваем длину details
        if len(details) > 500:
            details = details[:497] + "..."
        
        message = (
            f"🚨 <b>КРИТИЧЕСКАЯ ОШИБКА</b>\n\n"
            f"📊 <b>Компонент:</b> {error_type}\n"
            f"❌ <b>Ошибка:</b>\n<code>{details}</code>\n"
        )
        
        if additional_info:
            message += f"\nℹ️ <b>Доп. информация:</b>\n{additional_info}\n"
        
        message += f"\n⏰ <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        
        return message
    
    @staticmethod
    def _is_recently_sent(notification_key: str) -> bool:
        """Проверяет был ли уже отправлен такой же notification недавно"""
        if notification_key not in NotificationService._last_notifications:
            return False
        
        last_time = NotificationService._last_notifications[notification_key]
        minutes_passed = (datetime.now() - last_time).total_seconds() / 60
        
        return minutes_passed < NotificationService._cooldown_minutes
    
    @staticmethod
    def clear_cooldowns():
        """Очистить все cooldowns (для тестирования)"""
        NotificationService._last_notifications.clear()


# Глобальный экземпляр
notification_service = NotificationService()
