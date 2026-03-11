"""
handlers/messages.py - ПОЛНОЕ ИСПРАВЛЕНИЕ
Правильная логика обработки сообщений

КРИТИЧЕСКИЕ ИЗМЕНЕНИЯ:
✅ НЕ показывает предупреждение о телефонии если пользователь просто пишет текст
✅ Предупреждение только ПОСЛЕ нажатия кнопки "Ошибки телефонии"
✅ Используем флаг "awaiting_error" для определения намерения пользователя
✅ Добавлена "Статистика баз" в menu_texts
"""
from telegram import Update, error as telegram_error
from telegram.ext import ContextTypes

from config.settings import settings
from config.constants import MESSAGES
from services.user_service import user_service
from services.telephony_service import telephony_service
from keyboards.reply import get_menu_by_role
from utils.state import (
    get_user_role,
    is_support_mode,
    set_support_mode,
    get_tel_choice,
    clear_tel_choice,
    is_tel_choice_expired,
)
from utils.logger import logger
from handlers.menu import handle_menu_button


async def handle_support_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Обрабатывает сообщения в режиме поддержки"""
    if not is_support_mode(context):
        return False

    support_msg = (
        f"💬 <b>Вопрос в поддержку</b>\n\n"
        f"👤 От: {update.effective_user.first_name}\n"
        f"🆔 ID: {update.effective_user.id}\n"
        f"{'─' * 30}\n"
        f"📝 Вопрос:\n{update.message.text}"
    )

    try:
        for admin_id in settings.ADMINS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id, text=support_msg, parse_mode="HTML"
                )
            except telegram_error.TelegramError as e:
                logger.error(f"⚠️ Не удалось отправить админу {admin_id}: {e}")

        role = get_user_role(context)
        current_menu = get_menu_by_role(role)

        await update.message.reply_text(
            MESSAGES["support_sent"], reply_markup=current_menu
        )
        logger.info(f"✅ Вопрос в поддержку от user_id={update.effective_user.id}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки в поддержку: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ Не удалось отправить вопрос.\nПопробуйте позже."
        )

    set_support_mode(context, False)
    return True


async def handle_error_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает сообщение как описание ошибки телефонии

    ✅ КРИТИЧНО: Работает ТОЛЬКО если пользователь уже выбрал телефонию
    """
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Пользователь"
    role = get_user_role(context)

    # Получаем выбор телефонии
    tel, tel_code = get_tel_choice(context)

    # Проверка timeout
    if tel and is_tel_choice_expired(context):
        clear_tel_choice(context)
        tel = None
        tel_code = None
        logger.info(f"⏱ Истёк timeout выбора телефонии для user_id={user_id}")

    # ✅ КРИТИЧНО: Если телефония НЕ выбрана - НЕ обрабатываем как ошибку
    if not tel or not tel_code:
        return False

    group_id = telephony_service.get_group_id(tel)
    if not group_id:
        logger.error(f"❌ Не найдена группа для телефонии: {tel}")
        await update.message.reply_text(
            "⚠️ Ошибка: не назначена группа для этой телефонии."
        )
        return True

    # Валидация текста
    error_text = update.message.text or update.message.caption or ""
    has_media = bool(update.message.photo or update.message.document)

    is_valid, error_msg = telephony_service.validate_error_text(error_text, has_media)
    if not is_valid:
        await update.message.reply_text(error_msg)
        return True

    # Отправка в группу
    success = await telephony_service.send_error_to_group(
        context.bot, update, context, group_id, tel_code, username, error_text
    )

    if not success:
        await update.message.reply_text(
            "⚠️ Не удалось отправить ошибку в саппорт.\n"
            "Попробуйте позже или обратитесь к администратору."
        )
        return True

    # Очистка и возврат в меню
    clear_tel_choice(context)
    current_menu = get_menu_by_role(role)

    success_msg = telephony_service.get_success_message(tel_code, tel)

    await update.message.reply_text(
        success_msg, parse_mode="HTML", reply_markup=current_menu
    )

    return True


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Главный обработчик текстовых сообщений

    ✅ КРИТИЧНО: Игнорирует сообщения обработанные ConversationHandler
    ✅ ДОБАВЛЕНО: Поддержка быстрых ошибок (SIP и кастомные ошибки)
    """
    user_id = update.effective_user.id

    # Проверка доступа
    if not user_service.has_access(user_id):
        return

    text = update.message.text
    if not text:
        return

    management_keys = [
        "tel_name",
        "tel_code",
        "tel_type",
        "broadcast_message_id",
        "broadcast_chat_id",
        "awaiting_qe_code_add",
        "awaiting_qe_code_remove",
    ]

    if any(key in context.user_data for key in management_keys):
        logger.debug("🔇 Игнорируем сообщение - ConversationHandler активен")
        return

    # Игнорируем чистые числа (ID) длиннее 5 символов
    text_clean = text.strip()
    if text_clean.isdigit() and len(text_clean) > 5:
        logger.debug(f"🔇 Игнорируем ID {text_clean} (обработан ConversationHandler)")
        return

    logger.debug(f"📨 Сообщение от user_id={user_id}: '{text[:50]}...'")

    # Проверка режима поддержки
    if await handle_support_message(update, context):
        return

    # Проверка быстрых ошибок
    from handlers.quick_errors import (
        handle_sip_input_for_quick_error,
        handle_custom_error_input,
    )

    if await handle_sip_input_for_quick_error(update, context):
        return

    if await handle_custom_error_input(update, context):
        return

    # ✅ Список кнопок меню — "Статистика баз" добавлена
    menu_texts = {
        "Ошибки телефонии",
        "Полезные ссылки",
        "Статистика трубок",
        "Статистика менеджеров",
        "Статистика баз",        # ✅ ДОБАВЛЕНО
        "Статистика ошибок",
        "Управление ботом",
        "◀️ Меню",
    }

    if text in menu_texts:
        await handle_menu_button(update, context)
        return

    # Пытаемся обработать как ошибку телефонии
    handled = await handle_error_message(update, context)

    if handled:
        return

    # Если не обработано — показываем "Неизвестная команда"
    role = get_user_role(context)
    current_menu = get_menu_by_role(role)

    await update.message.reply_text(
        MESSAGES["unknown_command"], reply_markup=current_menu
    )