"""
Сервис для работы с телефонией и отправкой ошибок
"""
from telegram import Update, error as telegram_error
from telegram.ext import ContextTypes

from config.settings import settings
from config.constants import TEL_CODES_REVERSE, MESSAGES
from keyboards.inline import get_support_keyboard
from database.models import db
from utils.logger import logger


class TelephonyService:
    """Сервис для работы с телефонией"""

    @staticmethod
    def get_group_id(tel_name: str) -> int:
        """
        Возвращает ID группы для телефонии

        Args:
            tel_name: Название телефонии

        Returns:
            ID группы или None
        """
        # Сначала проверяем в БД
        telephonies = db.get_all_telephonies()
        for tel in telephonies:
            if tel["name"] == tel_name:
                return tel["group_id"]

        # Если нет в БД, проверяем старые из settings
        telephony_groups = settings.get_telephony_groups()
        return telephony_groups.get(tel_name)

    @staticmethod
    def get_tel_name_from_code(tel_code: str) -> str:
        """
        Преобразует код телефонии в название

        Args:
            tel_code: Код телефонии (bmw, zvon)

        Returns:
            Название телефонии или "Unknown"
        """
        # Проверяем в БД
        tel = db.get_telephony_by_code(tel_code)
        if tel:
            return tel["name"]

        # Если нет в БД, проверяем старые
        return TEL_CODES_REVERSE.get(tel_code, "Unknown")

    @staticmethod
    async def send_error_to_group(
        bot,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        group_id: int,
        tel_code: str,
        username: str,
        error_text: str,
    ) -> bool:
        """
        Отправляет ошибку в группу телефонии

        Args:
            bot: Экземпляр бота
            update: Update объект
            context: Контекст
            group_id: ID группы
            tel_code: Код телефонии
            username: Имя пользователя
            error_text: Текст ошибки

        Returns:
            True если отправка успешна
        """
        user_id = update.effective_user.id

        # Формирование сообщения
        msg = f"От: {username}\n{error_text}"

        # Кнопки (проверяем тип телефонии)
        keyboard = get_support_keyboard(user_id, tel_code)

        try:
            # Отправка основного сообщения
            sent_msg = await bot.send_message(
                chat_id=group_id, text=msg, reply_markup=keyboard
            )

            # Отправка медиа (если есть)
            if update.message.photo:
                await bot.send_photo(
                    chat_id=group_id,
                    photo=update.message.photo[-1].file_id,
                    reply_to_message_id=sent_msg.message_id,
                )
                logger.info("📸 Отправлено фото к ошибке")
            elif update.message.document:
                await bot.send_document(
                    chat_id=group_id,
                    document=update.message.document.file_id,
                    reply_to_message_id=sent_msg.message_id,
                )
                logger.info("📎 Отправлен документ к ошибке")
            
            # ✅ ФИКС: явный return True после успешной отправки
            logger.info(f"✅ Ошибка успешно отправлена в группу {group_id}")
            return True

        except telegram_error.TelegramError as e:
            logger.error(
                f"❌ Telegram error при отправке в группу {group_id}: {e}", exc_info=True
            )
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error при отправке ошибки: {e}", exc_info=True)
            return False

    @staticmethod
    def validate_error_text(error_text: str, has_media: bool) -> tuple:
        """
        Валидирует текст ошибки

        Args:
            error_text: Текст для проверки
            has_media: Есть ли медиа файлы

        Returns:
            (is_valid: bool, error_message: str)
        """
        # Проверка длины
        if len(error_text) > 1000:
            return False, MESSAGES["error_too_long"].format(length=len(error_text))

        # Проверка на пустоту
        if len(error_text.strip()) == 0 and not has_media:
            return False, MESSAGES["error_empty"]

        return True, None

    @staticmethod
    def get_success_message(tel_code: str, tel_name: str) -> str:
        """
        Возвращает сообщение об успешной отправке в зависимости от телефонии

        Args:
            tel_code: Код телефонии
            tel_name: Название телефонии

        Returns:
            Текст сообщения
        """
        # Проверяем тип телефонии
        tel = db.get_telephony_by_code(tel_code)

        if tel:
            # Из БД
            if tel["type"] == "black":
                return MESSAGES["error_sent_zvon"].format(tel=tel_name)
            else:
                return MESSAGES["error_sent_bmw"].format(tel=tel_name)
        else:
            # Старые
            if tel_code == "zvon":
                return MESSAGES["error_sent_zvon"].format(tel=tel_name)
            else:
                return MESSAGES["error_sent_bmw"].format(tel=tel_name)


# Глобальный экземпляр сервиса
telephony_service = TelephonyService()
