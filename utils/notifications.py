"""
ИСПРАВЛЕНО: utils/notifications.py
Добавлена автоочистка старых уведомлений

ИЗМЕНЕНИЯ:
✅ Добавлена автоочистка _last_notifications
✅ Ограничен размер словаря (max 100 записей)
✅ Удаление старых записей (> 24 часа)
"""
from datetime import datetime, timedelta
from typing import Optional
import html
from telegram import Bot
from telegram.error import TelegramError

from config.settings import settings
from utils.logger import logger


class NotificationService:
    """Сервис для отправки уведомлений админам"""

    # Защита от спама
    _last_notifications = {}
    _cooldown_minutes = 30

    # ✅ НОВОЕ: Защита от утечки памяти
    _max_cache_size = 100  # Максимум записей в кэше
    _max_cache_age_hours = 24  # Максимальный возраст записи

    @staticmethod
    def _cleanup_old_notifications():
        """
        Очищает старые записи из кэша уведомлений

        ✅ НОВОЕ: Автоматическая очистка при каждом вызове
        """
        try:
            now = datetime.now()
            cutoff_time = now - timedelta(
                hours=NotificationService._max_cache_age_hours
            )

            # Удаляем старые записи
            keys_to_delete = [
                key
                for key, timestamp in NotificationService._last_notifications.items()
                if timestamp < cutoff_time
            ]

            for key in keys_to_delete:
                del NotificationService._last_notifications[key]

            if keys_to_delete:
                logger.debug(
                    f"🧹 Очищено {len(keys_to_delete)} старых уведомлений из кэша"
                )

            # Если всё ещё слишком много - удаляем самые старые
            if (
                len(NotificationService._last_notifications)
                > NotificationService._max_cache_size
            ):
                # Сортируем по времени и удаляем самые старые
                sorted_items = sorted(
                    NotificationService._last_notifications.items(), key=lambda x: x[1]
                )

                excess = len(sorted_items) - NotificationService._max_cache_size
                for key, _ in sorted_items[:excess]:
                    del NotificationService._last_notifications[key]

                logger.debug(f"🧹 Удалено {excess} записей для соблюдения лимита кэша")

        except Exception as e:
            logger.error(f"❌ Ошибка очистки кэша уведомлений: {e}")

    @staticmethod
    async def notify_critical_error(
        bot: Bot, error_type: str, details: str, additional_info: Optional[str] = None
    ):
        """Отправить критическое уведомление админам"""

        # ✅ НОВОЕ: Автоочистка перед проверкой
        NotificationService._cleanup_old_notifications()

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
                    chat_id=admin_id, text=message, parse_mode="HTML"
                )
                success_count += 1
                logger.info(f"✅ Критическое уведомление отправлено админу {admin_id}")
            except TelegramError as e:
                logger.error(f"❌ Не удалось уведомить админа {admin_id}: {e}")

        if success_count > 0:
            # Сохраняем время последней отправки
            NotificationService._last_notifications[notification_key] = datetime.now()
            logger.info(f"📨 Критическое уведомление отправлено {success_count} админам")
            logger.debug(
                f"📊 Кэш уведомлений: {len(NotificationService._last_notifications)} записей"
            )

    @staticmethod
    async def notify_warning(bot: Bot, warning_type: str, details: str):
        """Отправить предупреждение админам"""

        # ✅ НОВОЕ: Автоочистка
        NotificationService._cleanup_old_notifications()

        # Экранируем пользовательский ввод для HTML
        safe_details = html.escape(details)

        message = (
            f"⚠️ <b>ПРЕДУПРЕЖДЕНИЕ</b>\n\n"
            f"📝 {html.escape(warning_type)}\n"
            f"ℹ️ {safe_details}\n\n"
            f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        for admin_id in settings.ADMINS:
            try:
                await bot.send_message(
                    chat_id=admin_id, text=message, parse_mode="HTML"
                )
            except TelegramError as e:
                logger.error(
                    f"❌ Не удалось отправить предупреждение админу {admin_id}: {e}"
                )

    @staticmethod
    async def notify_recovery(bot: Bot, service_name: str):
        """Уведомление о восстановлении после ошибок"""
        message = (
            f"✅ <b>ВОССТАНОВЛЕНИЕ</b>\n\n"
            f"📊 {html.escape(service_name)}\n"
            f"✅ Работа восстановлена после ошибок\n\n"
            f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        for admin_id in settings.ADMINS:
            try:
                await bot.send_message(
                    chat_id=admin_id, text=message, parse_mode="HTML"
                )
            except TelegramError:
                pass

    @staticmethod
    def _format_critical_message(
        error_type: str, details: str, additional_info: Optional[str]
    ) -> str:
        """Форматирует критическое сообщение"""

        # Экранируем детали, чтобы избежать ошибок парсинга HTML
        details = html.escape(details)

        # Ограничиваем длину details
        if len(details) > 500:
            details = details[:497] + "..."

        message = (
            f"🚨 <b>КРИТИЧЕСКАЯ ОШИБКА</b>\n\n"
            f"📊 <b>Компонент:</b> {html.escape(error_type)}\n"
            f"❌ <b>Ошибка:</b>\n<code>{details}</code>\n"
        )

        if additional_info:
            message += f"\nℹ️ <b>Доп. информация:</b>\n{html.escape(additional_info)}\n"

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
        logger.info("🧹 Кэш уведомлений очищен вручную")

    @staticmethod
    def get_cache_stats() -> dict:
        """
        ✅ НОВОЕ: Получить статистику кэша

        Returns:
            Словарь со статистикой
        """
        return {
            "cache_size": len(NotificationService._last_notifications),
            "max_cache_size": NotificationService._max_cache_size,
            "cooldown_minutes": NotificationService._cooldown_minutes,
            "max_cache_age_hours": NotificationService._max_cache_age_hours,
        }


# Глобальный экземпляр
notification_service = NotificationService()
