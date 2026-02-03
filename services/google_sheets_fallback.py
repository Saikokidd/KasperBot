"""
services/google_sheets_fallback.py - ОБЁРТКА GOOGLE SHEETS С FALLBACK

НАЗНАЧЕНИЕ:
✅ Обёртка над GoogleSheetsService с fallback на кэш
✅ Логирование всех ошибок
✅ Graceful degradation - возврат кэшированных данных при ошибке API
✅ Автоматическое сохранение успешных результатов в кэш
"""
from typing import Optional, Dict, Any, List
from services.google_sheets_cache import sheets_cache
from utils.logger import logger


class GoogleSheetsFallback:
    """Обёртка для Google Sheets с fallback на кэш"""

    def __init__(self, google_sheets_service):
        """
        Инициализирует fallback wrapper

        Args:
            google_sheets_service: Инстанс GoogleSheetsService
        """
        self.service = google_sheets_service
        self.logger = logger

    def get_manager_stats_safe(
        self, manager_id: int, use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Получает статистику менеджера с fallback на кэш

        Args:
            manager_id: ID менеджера
            use_cache: Использовать ли кэш при ошибке

        Returns:
            Dict со статистикой или None
        """
        cache_key = f"manager_stats_{manager_id}"

        try:
            self.logger.debug(
                f"📊 Получаем статистику менеджера {manager_id} из Google Sheets..."
            )

            stats = self.service.get_manager_stats(manager_id)

            # Успешно! Сохраняем в кэш
            sheets_cache.save_to_cache(cache_key, stats)
            self.logger.info(f"✅ Статистика менеджера {manager_id} успешно получена")

            return stats

        except Exception as e:
            self.logger.warning(f"⚠️ Ошибка получения статистики из Google Sheets: {e}")

            if use_cache:
                self.logger.info(
                    f"💾 Используем кэшированную статистику для менеджера {manager_id}"
                )
                cached_stats = sheets_cache.load_from_cache(cache_key, max_age_hours=24)

                if cached_stats:
                    self.logger.info("✅ Возвращаем кэшированную статистику")
                    return cached_stats
                else:
                    self.logger.error(f"❌ Кэш не найден для менеджера {manager_id}")
                    return None
            else:
                self.logger.error("❌ Не удалось получить статистику и кэш отключён")
                return None

    def get_all_managers_stats_safe(
        self, use_cache: bool = True
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Получает статистику всех менеджеров с fallback на кэш

        Args:
            use_cache: Использовать ли кэш при ошибке

        Returns:
            List со статистикой или None
        """
        cache_key = "all_managers_stats"

        try:
            self.logger.debug(
                "📊 Получаем статистику всех менеджеров из Google Sheets..."
            )

            stats = self.service.get_all_managers_stats()

            # Успешно! Сохраняем в кэш
            sheets_cache.save_to_cache(cache_key, stats)
            self.logger.info("✅ Статистика всех менеджеров успешно получена")

            return stats

        except Exception as e:
            self.logger.warning(f"⚠️ Ошибка получения статистики всех менеджеров: {e}")

            if use_cache:
                self.logger.info(
                    "💾 Используем кэшированную статистику всех менеджеров"
                )
                cached_stats = sheets_cache.load_from_cache(cache_key, max_age_hours=24)

                if cached_stats:
                    self.logger.info(
                        f"✅ Возвращаем кэшированную статистику ({len(cached_stats)} менеджеров)"
                    )
                    return cached_stats
                else:
                    self.logger.error("❌ Кэш не найден для всех менеджеров")
                    return None
            else:
                return None

    def sync_stats_safe(self) -> bool:
        """
        Синхронизирует статистику с fallback

        Returns:
            True если успешно, False если ошибка
        """
        try:
            self.logger.debug("🔄 Синхронизируем статистику с Google Sheets...")

            result = self.service.sync_stats()

            self.logger.info("✅ Синхронизация успешна")
            return result

        except Exception as e:
            self.logger.warning(f"⚠️ Ошибка синхронизации: {e}")
            self.logger.warning("⚠️ Синхронизация будет повторена в следующем цикле")

            # Возвращаем True чтобы бот продолжал работать
            return False

    def clear_stats_cache(self, manager_id: Optional[int] = None) -> bool:
        """
        Очищает кэш статистики

        Args:
            manager_id: ID менеджера (если None - очищает весь кэш)

        Returns:
            True если успешно
        """
        if manager_id:
            cache_key = f"manager_stats_{manager_id}"
            return sheets_cache.clear_cache(cache_key)
        else:
            return sheets_cache.clear_cache("all_managers_stats")

    def get_cache_health(self) -> Dict[str, Any]:
        """
        Получает статус здоровья кэша

        Returns:
            Dict с информацией о кэше
        """
        return sheets_cache.get_cache_status()


# Если нужна глобальная обёртка, инициализируем её
# В main.py сервис инициализируется вот так:
# from services.google_sheets_service import google_sheets
# from services.google_sheets_fallback import GoogleSheetsFallback
# sheets_fallback = GoogleSheetsFallback(google_sheets)
