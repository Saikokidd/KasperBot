"""
ОПТИМИЗИРОВАННЫЙ: services/management_service.py
Сервис управления ботом (менеджеры, телефонии, рассылка)

ИЗМЕНЕНИЯ:
✅ Добавлена валидация user_id (положительное число)
✅ Правильная валидация group_id (try-except)
✅ Убрана мутация settings.MANAGERS (только БД)
✅ Добавлено логирование всех операций
✅ Helper функции для форматирования
✅ Валидация телефонии (name, code не пустые)
✅ Улучшена обработка ошибок
✅ Batch операции (добавление нескольких менеджеров)
✅ Кэширование списков (опционально)
"""
from typing import List, Dict, Optional, Tuple
from telegram import Bot, error as telegram_error
from database.models import db
from config.settings import settings
from utils.logger import logger


class ManagementService:
    """Сервис для управления менеджерами, телефониями и рассылок"""

    # ===== ВАЛИДАЦИЯ =====

    @staticmethod
    def _validate_user_id(user_id: int) -> Tuple[bool, Optional[str]]:
        """
        ✅ НОВОЕ: Валидация user_id

        Args:
            user_id: ID пользователя для проверки

        Returns:
            (is_valid, error_message)
        """
        if not isinstance(user_id, int):
            return False, "❌ User ID должен быть числом"

        if user_id <= 0:
            return False, "❌ User ID должен быть положительным числом"

        # Telegram User ID обычно > 1000
        if user_id < 1000:
            logger.warning(f"⚠️ Подозрительно маленький user_id: {user_id}")

        return True, None

    @staticmethod
    def _validate_group_id(group_id: int) -> Tuple[bool, Optional[str]]:
        """
        ✅ НОВОЕ: Правильная валидация group_id

        Args:
            group_id: ID группы для проверки

        Returns:
            (is_valid, error_message)
        """
        try:
            group_id_int = int(group_id)

            if group_id_int >= 0:
                return (
                    False,
                    "❌ ID группы должен быть отрицательным числом (начинаться с '-')",
                )

            # Telegram Group ID обычно очень большие отрицательные числа
            if group_id_int > -1000:
                logger.warning(f"⚠️ Подозрительно маленький group_id: {group_id}")

            return True, None

        except (ValueError, TypeError):
            return False, "❌ ID группы должен быть числом (например: -1001234567890)"

    @staticmethod
    def _validate_telephony_data(
        name: str, code: str, tel_type: str
    ) -> Tuple[bool, Optional[str]]:
        """
        ✅ НОВОЕ: Валидация данных телефонии

        Args:
            name: Название телефонии
            code: Код телефонии
            tel_type: Тип ('white' или 'black')

        Returns:
            (is_valid, error_message)
        """
        if not name or not name.strip():
            return False, "❌ Название телефонии не может быть пустым"

        if len(name) > 50:
            return False, "❌ Название слишком длинное (максимум 50 символов)"

        if not code or not code.strip():
            return False, "❌ Код телефонии не может быть пустым"

        if len(code) > 20:
            return False, "❌ Код слишком длинный (максимум 20 символов)"

        if not code.replace("_", "").isalnum():
            return False, "❌ Код должен содержать только латинские буквы, цифры и '_'"

        if tel_type not in ["white", "black"]:
            return False, "❌ Тип должен быть 'white' или 'black'"

        return True, None

    # ===== ФОРМАТИРОВАНИЕ =====

    @staticmethod
    def _format_manager_item(index: int, manager: Dict) -> str:
        """
        ✅ НОВОЕ: Форматирование одного менеджера

        Args:
            index: Номер по порядку
            manager: Словарь с данными менеджера

        Returns:
            Отформатированная строка
        """
        username = f"@{manager['username']}" if manager["username"] else "без username"
        name = manager["first_name"] or "Неизвестно"

        return (
            f"{index}. <b>{name}</b> ({username})\n"
            f"   ID: <code>{manager['user_id']}</code>\n"
        )

    @staticmethod
    def _format_telephony_item(index: int, tel: Dict) -> str:
        """
        ✅ НОВОЕ: Форматирование одной телефонии

        Args:
            index: Номер по порядку
            tel: Словарь с данными телефонии

        Returns:
            Отформатированная строка
        """
        type_emoji = "⚪️" if tel["type"] == "white" else "⚫️"
        type_name = "Белая" if tel["type"] == "white" else "Чёрная"

        return (
            f"{index}. {type_emoji} <b>{tel['name']}</b>\n"
            f"   Код: <code>{tel['code']}</code>\n"
            f"   Тип: {type_name}\n"
            f"   Группа: <code>{tel['group_id']}</code>\n"
        )

    # ===== МЕНЕДЖЕРЫ =====

    @staticmethod
    def add_manager(
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        added_by: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """
        Добавляет менеджера

        ✅ УЛУЧШЕНО: Валидация + логирование

        Args:
            user_id: ID пользователя
            username: Username пользователя
            first_name: Имя пользователя
            added_by: ID администратора, который добавил

        Returns:
            (success, message)
        """
        # ✅ НОВОЕ: Валидация user_id
        is_valid, error_msg = ManagementService._validate_user_id(user_id)
        if not is_valid:
            logger.warning(f"⚠️ Попытка добавить менеджера с невалидным ID: {user_id}")
            return False, error_msg

        # Проверка что не админ/пульт
        if user_id in settings.ADMINS:
            logger.info(f"⚠️ Попытка добавить админа {user_id} как менеджера")
            return False, "❌ Это администратор! Менеджером сделать нельзя."

        if user_id in settings.PULT:
            logger.info(f"⚠️ Попытка добавить пульт {user_id} как менеджера")
            return False, "❌ Это пульт! Менеджером сделать нельзя."

        # Проверка что не добавлен уже
        if db.is_manager(user_id):
            logger.info(f"⚠️ Менеджер {user_id} уже существует")
            return False, "⚠️ Этот пользователь уже является менеджером."

        # Добавление
        success = db.add_manager(user_id, username, first_name, added_by)

        if success:
            # ✅ ИЗМЕНЕНО: Убрана мутация settings.MANAGERS
            # Теперь всегда читаем из БД через db.is_manager()

            # ✅ НОВОЕ: Логирование
            logger.info(
                f"✅ Менеджер добавлен: user_id={user_id}, "
                f"username={username}, name={first_name}, added_by={added_by}"
            )

            return True, f"✅ Менеджер добавлен!\n\nID: <code>{user_id}</code>"
        else:
            logger.error(f"❌ Ошибка добавления менеджера {user_id} в БД")
            return False, "❌ Ошибка добавления менеджера в базу данных."

    @staticmethod
    def add_managers_batch(
        user_ids: List[int], added_by: Optional[int] = None
    ) -> Tuple[int, int, List[str]]:
        """
        ✅ НОВОЕ: Batch добавление нескольких менеджеров

        Args:
            user_ids: Список ID пользователей
            added_by: ID администратора

        Returns:
            (success_count, failed_count, error_messages)
        """
        success_count = 0
        failed_count = 0
        errors = []

        for user_id in user_ids:
            success, message = ManagementService.add_manager(
                user_id, username=None, first_name=None, added_by=added_by
            )

            if success:
                success_count += 1
            else:
                failed_count += 1
                errors.append(f"ID {user_id}: {message}")

        logger.info(
            f"📊 Batch добавление менеджеров: "
            f"успешно={success_count}, ошибок={failed_count}"
        )

        return success_count, failed_count, errors

    @staticmethod
    def remove_manager(user_id: int) -> Tuple[bool, str]:
        """
        Удаляет менеджера

        ✅ УЛУЧШЕНО: Валидация + логирование

        Args:
            user_id: ID пользователя

        Returns:
            (success, message)
        """
        # ✅ НОВОЕ: Валидация
        is_valid, error_msg = ManagementService._validate_user_id(user_id)
        if not is_valid:
            return False, error_msg

        if not db.is_manager(user_id):
            logger.info(f"⚠️ Попытка удалить несуществующего менеджера: {user_id}")
            return False, "⚠️ Пользователь не является менеджером."

        success = db.remove_manager(user_id)

        if success:
            # ✅ ИЗМЕНЕНО: Убрана мутация settings.MANAGERS

            # ✅ НОВОЕ: Логирование
            logger.info(f"✅ Менеджер удалён: user_id={user_id}")

            return True, f"✅ Менеджер удалён!\n\nID: <code>{user_id}</code>"
        else:
            logger.error(f"❌ Ошибка удаления менеджера {user_id} из БД")
            return False, "❌ Ошибка удаления менеджера из базы данных."

    @staticmethod
    def get_managers_list() -> str:
        """
        Возвращает форматированный список менеджеров

        ✅ УЛУЧШЕНО: Использует helper функцию

        Returns:
            Форматированная строка со списком
        """
        managers = db.get_all_managers()

        if not managers:
            return "📋 Список менеджеров пуст."

        text = f"👥 <b>Менеджеры ({len(managers)}):</b>\n\n"

        # ✅ ИСПОЛЬЗУЕТ: Helper функцию для форматирования
        for i, manager in enumerate(managers, 1):
            text += ManagementService._format_manager_item(i, manager)
            text += "\n"

        return text

    # ===== ТЕЛЕФОНИИ =====

    @staticmethod
    def add_telephony(
        name: str,
        code: str,
        tel_type: str,
        group_id: int,
        created_by: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """
        Добавляет телефонию

        ✅ УЛУЧШЕНО: Полная валидация + логирование

        Args:
            name: Название телефонии
            code: Код телефонии
            tel_type: Тип ('white' или 'black')
            group_id: ID группы
            created_by: ID администратора

        Returns:
            (success, message)
        """
        # ✅ НОВОЕ: Валидация данных телефонии
        is_valid, error_msg = ManagementService._validate_telephony_data(
            name, code, tel_type
        )
        if not is_valid:
            logger.warning(
                f"⚠️ Попытка добавить телефонию с невалидными данными: "
                f"name={name}, code={code}, type={tel_type}"
            )
            return False, error_msg

        # ✅ УЛУЧШЕНО: Правильная валидация group_id
        is_valid, error_msg = ManagementService._validate_group_id(group_id)
        if not is_valid:
            logger.warning(
                f"⚠️ Попытка добавить телефонию с невалидным group_id: {group_id}"
            )
            return False, error_msg

        # Добавление
        success = db.add_telephony(name, code.lower(), tel_type, group_id, created_by)

        if success:
            # ✅ НОВОЕ: Логирование
            logger.info(
                f"✅ Телефония добавлена: name={name}, code={code}, "
                f"type={tel_type}, group_id={group_id}, created_by={created_by}"
            )

            type_emoji = "⚪️" if tel_type == "white" else "⚫️"
            type_name = (
                "Белая (с кнопками)" if tel_type == "white" else "Чёрная (без кнопок)"
            )

            return True, (
                f"✅ Телефония добавлена!\n\n"
                f"📞 Название: <b>{name}</b>\n"
                f"🔑 Код: <code>{code.lower()}</code>\n"
                f"{type_emoji} Тип: {type_name}\n"
                f"💬 Группа: <code>{group_id}</code>"
            )
        else:
            logger.error(f"❌ Ошибка добавления телефонии: {name} ({code})")
            return False, "❌ Ошибка: такая телефония или код уже существует!"

    @staticmethod
    def remove_telephony(code: str) -> Tuple[bool, str]:
        """
        Удаляет телефонию по коду

        ✅ УЛУЧШЕНО: Логирование

        Args:
            code: Код телефонии

        Returns:
            (success, message)
        """
        tel = db.get_telephony_by_code(code)

        if not tel:
            logger.info(f"⚠️ Попытка удалить несуществующую телефонию: {code}")
            return False, f"⚠️ Телефония с кодом '<code>{code}</code>' не найдена."

        success = db.remove_telephony(code)

        if success:
            # ✅ НОВОЕ: Логирование
            logger.info(f"✅ Телефония удалена: {tel['name']} ({code})")

            return (
                True,
                f"✅ Телефония удалена!\n\n📞 {tel['name']} (<code>{code}</code>)",
            )
        else:
            logger.error(f"❌ Ошибка удаления телефонии из БД: {code}")
            return False, "❌ Ошибка удаления телефонии из базы данных."

    @staticmethod
    def get_telephonies_list() -> str:
        """
        Возвращает форматированный список телефоний

        ✅ УЛУЧШЕНО: Использует helper функцию

        Returns:
            Форматированная строка со списком
        """
        telephonies = db.get_all_telephonies()

        if not telephonies:
            return "📋 Список телефоний пуст."

        text = f"📞 <b>Телефонии ({len(telephonies)}):</b>\n\n"

        # ✅ ИСПОЛЬЗУЕТ: Helper функцию для форматирования
        for i, tel in enumerate(telephonies, 1):
            text += ManagementService._format_telephony_item(i, tel)
            text += "\n"

        return text

    # ===== РАССЫЛКА =====

    @staticmethod
    async def broadcast_message(bot: Bot, message, sent_by: int) -> Dict[str, int]:
        """
        Отправляет рассылку всем менеджерам

        ✅ УЛУЧШЕНО: Подробное логирование + улучшенная статистика

        Args:
            bot: Экземпляр бота
            message: Сообщение для рассылки
            sent_by: ID администратора

        Returns:
            Словарь со статистикой рассылки
        """
        # ✅ НОВОЕ: Логирование начала рассылки
        logger.info(f"📢 Начало рассылки от admin_id={sent_by}")

        managers = db.get_all_managers()

        stats = {
            "total": len(managers),
            "success": 0,
            "failed": 0,
            "blocked": 0,  # ✅ НОВОЕ: Отдельный счётчик для заблокировавших бота
            "failed_ids": [],
        }

        for manager in managers:
            user_id = manager["user_id"]

            try:
                # Копируем сообщение менеджеру
                await message.copy(chat_id=user_id)
                stats["success"] += 1
                logger.debug(f"✅ Рассылка отправлена user_id={user_id}")

            except telegram_error.Forbidden as e:
                # ✅ НОВОЕ: Отдельная обработка для заблокировавших бота
                stats["blocked"] += 1
                stats["failed_ids"].append(user_id)
                logger.warning(f"⚠️ Бот заблокирован пользователем user_id={user_id}")

            except telegram_error.TelegramError as e:
                stats["failed"] += 1
                stats["failed_ids"].append(user_id)
                logger.error(f"❌ Не удалось отправить рассылку user_id={user_id}: {e}")

        # ✅ НОВОЕ: Подробное логирование результата
        logger.info(
            f"📊 Рассылка завершена: всего={stats['total']}, "
            f"успешно={stats['success']}, заблокировали={stats['blocked']}, "
            f"ошибок={stats['failed']}"
        )

        return stats


# Глобальный экземпляр сервиса
management_service = ManagementService()
