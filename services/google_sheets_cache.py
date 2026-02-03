"""
services/google_sheets_cache.py - КЭШ И FALLBACK ДЛЯ GOOGLE SHEETS

НАЗНАЧЕНИЕ:
✅ Сохранение данных на диск перед запросом
✅ Возврат кэшированных данных если API недоступна
✅ Автоматическая ротация кэша (максимум 2 часа)
✅ Graceful degradation вместо полного краха бота
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from utils.logger import logger


class GoogleSheetsCache:
    """Класс для управления кэшем Google Sheets"""

    CACHE_DIR = Path("cache")
    CACHE_LIFETIME_HOURS = 2

    def __init__(self):
        """Инициализирует директорию кэша"""
        self.CACHE_DIR.mkdir(exist_ok=True)
        logger.info(f"📁 Google Sheets кэш директория: {self.CACHE_DIR}")

    @staticmethod
    def _get_cache_path(key: str) -> Path:
        """
        Получает путь файла кэша для ключа

        Args:
            key: Ключ кэша (например "manager_stats_123")

        Returns:
            Path к файлу кэша
        """
        return GoogleSheetsCache.CACHE_DIR / f"{key}.json"

    @staticmethod
    def save_to_cache(key: str, data: Any) -> bool:
        """
        Сохраняет данные в кэш с timestamp'ом

        Args:
            key: Ключ кэша
            data: Данные для сохранения (dict или list)

        Returns:
            True если успешно, False если ошибка
        """
        try:
            cache_path = GoogleSheetsCache._get_cache_path(key)

            cache_data = {"timestamp": datetime.now().isoformat(), "data": data}

            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            logger.debug(f"💾 Кэш сохранён: {key}")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения кэша {key}: {e}")
            return False

    @staticmethod
    def load_from_cache(key: str, max_age_hours: int = None) -> Optional[Any]:
        """
        Загружает данные из кэша если они ещё актуальны

        Args:
            key: Ключ кэша
            max_age_hours: Максимальный возраст кэша в часах (по умолчанию CACHE_LIFETIME_HOURS)

        Returns:
            Данные из кэша или None если кэш истёк/не найден
        """
        if max_age_hours is None:
            max_age_hours = GoogleSheetsCache.CACHE_LIFETIME_HOURS

        try:
            cache_path = GoogleSheetsCache._get_cache_path(key)

            if not cache_path.exists():
                logger.debug(f"📭 Кэш не найден: {key}")
                return None

            with open(cache_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            # Проверяем timestamp
            timestamp_str = cache_data.get("timestamp")
            if not timestamp_str:
                logger.warning(f"⚠️ Кэш без timestamp: {key}")
                return None

            cached_time = datetime.fromisoformat(timestamp_str)
            age = datetime.now() - cached_time

            if age > timedelta(hours=max_age_hours):
                logger.warning(
                    f"⏰ Кэш истёк ({age.total_seconds()/3600:.1f} часов): {key}"
                )
                cache_path.unlink()  # Удаляем старый кэш
                return None

            logger.debug(
                f"✅ Кэш загружен ({age.total_seconds()/60:.1f} минут назад): {key}"
            )
            return cache_data.get("data")

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки кэша {key}: {e}")
            return None

    @staticmethod
    def clear_cache(key: Optional[str] = None) -> bool:
        """
        Очищает кэш (конкретный ключ или весь кэш)

        Args:
            key: Ключ для очистки (если None - очищает весь кэш)

        Returns:
            True если успешно
        """
        try:
            if key:
                cache_path = GoogleSheetsCache._get_cache_path(key)
                if cache_path.exists():
                    cache_path.unlink()
                    logger.info(f"🧹 Кэш очищен: {key}")
            else:
                # Очищаем весь кэш
                for cache_file in GoogleSheetsCache.CACHE_DIR.glob("*.json"):
                    cache_file.unlink()
                logger.info("🧹 Весь кэш очищен")

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка очистки кэша: {e}")
            return False

    @staticmethod
    def get_cache_status() -> Dict[str, Any]:
        """
        Получает статус кэша (количество файлов, размер и т.д.)

        Returns:
            Dict с информацией о кэше
        """
        try:
            cache_files = list(GoogleSheetsCache.CACHE_DIR.glob("*.json"))
            total_size = sum(f.stat().st_size for f in cache_files)

            return {
                "files_count": len(cache_files),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "files": [f.stem for f in cache_files],
            }

        except Exception as e:
            logger.error(f"❌ Ошибка получения статуса кэша: {e}")
            return {"error": str(e)}


# Глобальный инстанс кэша
sheets_cache = GoogleSheetsCache()
