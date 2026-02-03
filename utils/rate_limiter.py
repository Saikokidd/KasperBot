"""
utils/rate_limiter.py - Защита от спама и DDoS

ИЗМЕНЕНИЯ:
✅ Ограничение сообщений: 5 в 10 секунд
✅ Ограничение callback'ов: 50 в минуту
✅ Блокировка спамеров на 1 минуту
✅ Логирование попыток спама
"""
from datetime import datetime, timedelta
from typing import Dict, Tuple
from collections import defaultdict
from utils.logger import logger


class RateLimiter:
    """Ограничитель частоты запросов (в памяти)"""

    def __init__(self):
        # {user_id: [(timestamp, count), ...]}
        self.message_timestamps: Dict[int, list] = defaultdict(list)
        self.callback_timestamps: Dict[int, list] = defaultdict(list)
        self.blocked_users: Dict[int, datetime] = {}

        # Конфиги
        self.MESSAGE_LIMIT = 5  # сообщений
        self.MESSAGE_WINDOW = 10  # секунд
        self.CALLBACK_LIMIT = 50  # callback'ов
        self.CALLBACK_WINDOW = 60  # секунд
        self.BLOCK_DURATION = 60  # секунд
        self.CLEANUP_INTERVAL = 300  # секунд (чистка старых записей)

    def _cleanup_old_entries(self, timestamps: list, window_seconds: int) -> list:
        """Удалить старые записи за пределами окна"""
        now = datetime.now()
        cutoff_time = now - timedelta(seconds=window_seconds)
        return [ts for ts in timestamps if ts > cutoff_time]

    def is_user_blocked(self, user_id: int) -> bool:
        """Проверить, заблокирован ли пользователь"""
        if user_id not in self.blocked_users:
            return False

        if datetime.now() > self.blocked_users[user_id]:
            # Блокировка истекла
            del self.blocked_users[user_id]
            logger.info(f"🔓 Пользователь {user_id} разблокирован")
            return False

        return True

    def check_message_rate(self, user_id: int) -> Tuple[bool, str]:
        """
        Проверить лимит сообщений

        Returns:
            (allowed, message)
        """
        if self.is_user_blocked(user_id):
            return (
                False,
                "⏱️ Вы отправляете слишком много сообщений. Попробуйте через минуту.",
            )

        now = datetime.now()

        # Очистить старые записи
        self.message_timestamps[user_id] = self._cleanup_old_entries(
            self.message_timestamps[user_id], self.MESSAGE_WINDOW
        )

        # Проверить лимит
        if len(self.message_timestamps[user_id]) >= self.MESSAGE_LIMIT:
            logger.warning(f"⚠️ Спам сообщений от user_id={user_id}")
            self.blocked_users[user_id] = now + timedelta(seconds=self.BLOCK_DURATION)
            return (
                False,
                "⏱️ Вы отправляете слишком много сообщений. Попробуйте через минуту.",
            )

        # Добавить новую запись
        self.message_timestamps[user_id].append(now)
        return True, ""

    def check_callback_rate(self, user_id: int) -> Tuple[bool, str]:
        """
        Проверить лимит callback'ов

        Returns:
            (allowed, message)
        """
        if self.is_user_blocked(user_id):
            return False, "⏱️ Вы активны слишком часто. Попробуйте через минуту."

        now = datetime.now()

        # Очистить старые записи
        self.callback_timestamps[user_id] = self._cleanup_old_entries(
            self.callback_timestamps[user_id], self.CALLBACK_WINDOW
        )

        # Проверить лимит
        if len(self.callback_timestamps[user_id]) >= self.CALLBACK_LIMIT:
            logger.warning(f"⚠️ Спам callback'ов от user_id={user_id}")
            self.blocked_users[user_id] = now + timedelta(seconds=self.BLOCK_DURATION)
            return False, "⏱️ Вы активны слишком часто. Попробуйте через минуту."

        # Добавить новую запись
        self.callback_timestamps[user_id].append(now)
        return True, ""

    def cleanup(self):
        """
        Очистить память от мёртвых записей
        Вызывается периодически (например, каждый час)
        """
        now = datetime.now()
        cutoff_time = now - timedelta(seconds=self.CLEANUP_INTERVAL)

        # Очистить callback таймстампы
        for user_id in list(self.callback_timestamps.keys()):
            self.callback_timestamps[user_id] = [
                ts for ts in self.callback_timestamps[user_id] if ts > cutoff_time
            ]
            if not self.callback_timestamps[user_id]:
                del self.callback_timestamps[user_id]

        # Очистить message таймстампы
        for user_id in list(self.message_timestamps.keys()):
            self.message_timestamps[user_id] = [
                ts for ts in self.message_timestamps[user_id] if ts > cutoff_time
            ]
            if not self.message_timestamps[user_id]:
                del self.message_timestamps[user_id]

        # Очистить истекшие блокировки
        for user_id in list(self.blocked_users.keys()):
            if datetime.now() > self.blocked_users[user_id]:
                del self.blocked_users[user_id]

        logger.debug(
            f"🧹 Rate limiter: очищено {len(self.message_timestamps)} пользователей в памяти"
        )


# Глобальный экземпляр
rate_limiter = RateLimiter()
