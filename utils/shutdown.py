"""
Модуль для корректной остановки бота при получении сигналов
"""
import signal
import sys
from typing import Callable, List
from utils.logger import logger


class ShutdownHandler:
    """Обработчик корректной остановки бота"""

    def __init__(self):
        self._shutdown_callbacks: List[Callable] = []
        self._shutdown_in_progress = False

    def register_callback(self, callback: Callable):
        """
        Регистрирует callback для вызова при остановке

        Args:
            callback: Функция для вызова (без аргументов)
        """
        self._shutdown_callbacks.append(callback)
        logger.info(f"✅ Зарегистрирован shutdown callback: {callback.__name__}")

    def setup_handlers(self):
        """Устанавливает обработчики сигналов"""
        signal.signal(signal.SIGINT, self._signal_handler)  # Ctrl+C
        signal.signal(signal.SIGTERM, self._signal_handler)  # systemctl stop
        logger.info("✅ Обработчики сигналов установлены (SIGINT, SIGTERM)")

    def _signal_handler(self, sig, frame):
        """Обработчик сигналов остановки"""
        if self._shutdown_in_progress:
            logger.warning("⚠️ Shutdown уже в процессе, игнорируем повторный сигнал")
            return

        self._shutdown_in_progress = True

        signal_name = signal.Signals(sig).name
        logger.info(f"🛑 Получен сигнал {signal_name}, начинаем корректную остановку...")

        # Вызываем все зарегистрированные callbacks
        for callback in self._shutdown_callbacks:
            try:
                logger.info(f"🔄 Выполнение: {callback.__name__}")
                callback()
            except Exception as e:
                logger.error(f"❌ Ошибка в {callback.__name__}: {e}")

        logger.info("✅ Корректная остановка завершена")
        sys.exit(0)


# Глобальный экземпляр
shutdown_handler = ShutdownHandler()
