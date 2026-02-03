#!/usr/bin/env python3
"""
Скрипт обновления информации о менеджерах через Telegram API
Получает username и first_name для всех менеджеров в БД
"""
import asyncio
from telegram import Bot
from database.models import db
from config.settings import settings
from utils.logger import logger


async def update_managers_info():
    """Обновляет информацию о менеджерах через Telegram API"""

    logger.info("🔄 Начало обновления информации о менеджерах...")

    bot = Bot(token=settings.BOT_TOKEN)

    managers = db.get_all_managers()
    logger.info(f"📊 Найдено менеджеров: {len(managers)}")

    updated = 0
    failed = 0

    for manager in managers:
        user_id = manager["user_id"]

        try:
            # Получаем информацию о пользователе через API
            chat = await bot.get_chat(user_id)

            username = chat.username
            first_name = chat.first_name

            # Обновляем в БД
            conn = db._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE managers SET username = ?, first_name = ? WHERE user_id = ?",
                (username, first_name, user_id),
            )
            conn.commit()
            conn.close()

            updated += 1
            logger.info(f"✅ Обновлён {user_id}: @{username} ({first_name})")

        except Exception as e:
            failed += 1
            logger.error(f"❌ Не удалось обновить {user_id}: {e}")

    logger.info("✅ Обновление завершено!")
    logger.info(f"📊 Обновлено: {updated}, Ошибок: {failed}")


if __name__ == "__main__":
    asyncio.run(update_managers_info())
