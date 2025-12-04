"""
ИСПРАВЛЕННЫЙ ФАЙЛ: handlers/quick_errors.py
Обработчики быстрых ошибок BMW с SIP

ИЗМЕНЕНИЯ:
✅ handle_quick_error_callback теперь возвращает состояния ConversationHandler
✅ handle_custom_error_input интегрирован в ConversationHandler
✅ Удалена проверка waiting_custom_bmw (состояние управляется ConversationHandler)
✅ ConversationHandler обрабатывает callback от inline кнопок
"""
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from database.models import db
from keyboards.inline import get_quick_errors_keyboard
from keyboards.reply import get_menu_by_role
from config.constants import MESSAGES, QUICK_ERRORS, MAX_SIP_LENGTH, MAX_CUSTOM_ERROR_LENGTH
from config.settings import settings
from utils.state import get_user_role
from utils.logger import logger

# Состояния разговора
WAITING_SIP, WAITING_CUSTOM_ERROR = range(2)


async def handle_bmw_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик выбора BMW из Reply меню
    
    Args:
        update: Update объект
        context: Контекст пользователя
    """
    user_id = update.effective_user.id
    
    # Проверяем, указан ли SIP сегодня
    if db.is_sip_valid_today(user_id):
        # SIP указан - показываем кнопки ошибок
        sip_data = db.get_manager_sip(user_id)
        sip = sip_data['sip_number']
        
        await update.message.reply_text(
            MESSAGES["choose_quick_error"].format(sip=sip),
            reply_markup=get_quick_errors_keyboard()
        )
        return ConversationHandler.END
    else:
        # SIP не указан - просим ввести
        await update.message.reply_text(MESSAGES["sip_prompt"])
        return WAITING_SIP


async def handle_sip_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик ввода SIP номера
    
    Args:
        update: Update объект
        context: Контекст пользователя
    """
    user_id = update.effective_user.id
    sip_text = update.message.text.strip()
    
    if not sip_text or len(sip_text) > MAX_SIP_LENGTH:
        await update.message.reply_text(MESSAGES["sip_invalid"])
        return WAITING_SIP
    
    # Сохраняем SIP
    db.save_manager_sip(user_id, sip_text)
    
    logger.info(f"✅ SIP сохранён для user_id={user_id}: {sip_text}")
    
    # Показываем кнопки ошибок
    await update.message.reply_text(
        MESSAGES["sip_saved"].format(sip=sip_text),
        reply_markup=get_quick_errors_keyboard()
    )
    
    return ConversationHandler.END


async def handle_quick_error_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик нажатия на кнопку быстрой ошибки
    
    Args:
        update: Update объект
        context: Контекст пользователя
    
    Returns:
        WAITING_CUSTOM_ERROR если выбран "Свой вариант", иначе ConversationHandler.END
    """
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Пользователь"
    
    # Получаем код ошибки (qerr_1 → 1)
    error_code = query.data.split("_")[1]
    
    # Проверяем наличие SIP
    sip_data = db.get_manager_sip(user_id)
    if not sip_data or not sip_data.get('sip_number'):
        await query.message.edit_text(
            "⚠️ SIP не найден или некорректен.\n"
            "Попробуйте снова через меню 'Ошибки телефонии' → 'BMW'"
        )
        return ConversationHandler.END
    
    sip = sip_data['sip_number']
    
    # Если "Свой вариант" - переходим к вводу текста
    if error_code == "10":
        await query.message.edit_text(MESSAGES["custom_error_prompt"])
        context.user_data["bmw_sip"] = sip
        return WAITING_CUSTOM_ERROR  # ✅ ПЕРЕХОД В СОСТОЯНИЕ ОЖИДАНИЯ
    
    # Получаем текст ошибки
    error_text = QUICK_ERRORS.get(error_code, "Неизвестная ошибка")
    
    # Отправляем в группу BMW
    success = await send_quick_error_to_group(
        context.bot, user_id, username, sip, error_text
    )
    
    if not success:
        await query.message.edit_text("⚠️ Не удалось отправить ошибку. Попробуйте позже.")
        return ConversationHandler.END
    
    # Уведомляем пользователя
    await query.message.edit_text(
        MESSAGES["quick_error_sent"].format(sip=sip, error=error_text)
    )
    
    return ConversationHandler.END


async def handle_custom_error_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик ввода своего варианта ошибки
    
    Args:
        update: Update объект
        context: Контекст пользователя
    
    Returns:
        ConversationHandler.END после обработки
    """
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Пользователь"
    
    error_text = update.message.text.strip()
    sip = context.user_data.get("bmw_sip")
    
    try:
        if not sip:
            await update.message.reply_text("⚠️ Ошибка: SIP не найден.")
            return ConversationHandler.END
        
        if not error_text or len(error_text) > MAX_CUSTOM_ERROR_LENGTH:
            await update.message.reply_text(
                f"⚠️ Описание ошибки должно быть от 1 до {MAX_CUSTOM_ERROR_LENGTH} символов."
            )
            return WAITING_CUSTOM_ERROR  # Остаёмся в состоянии ожидания
        
        # Отправляем в группу
        success = await send_quick_error_to_group(
            context.bot, user_id, username, sip, error_text
        )
        
        if not success:
            await update.message.reply_text("⚠️ Не удалось отправить ошибку. Попробуйте позже.")
            return ConversationHandler.END
        
        # Уведомляем пользователя
        await update.message.reply_text(
            MESSAGES["quick_error_sent"].format(sip=sip, error=error_text)
        )
        
        return ConversationHandler.END
        
    finally:
        # Очистка состояния в любом случае
        context.user_data.pop("bmw_sip", None)
        logger.debug(f"🧹 Состояние custom BMW очищено для user_id={user_id}")


async def handle_change_sip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик кнопки "Изменить SIP"
    
    Args:
        update: Update объект
        context: Контекст пользователя
    
    Returns:
        WAITING_SIP для перехода в состояние ввода SIP
    """
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(MESSAGES["sip_prompt"])
    
    return WAITING_SIP


async def send_quick_error_to_group(bot, user_id: int, username: str, sip: str, error_text: str) -> bool:
    """
    Отправляет быструю ошибку в группу BMW
    
    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
        username: Имя пользователя
        sip: SIP номер
        error_text: Текст ошибки
        
    Returns:
        True если успешно
    """
    group_id = settings.BMW_GROUP_ID
    tel_code = "bmw"
    
    # Компактный формат
    msg = f"От {username}\nSIP: {sip}  {error_text}"
    
    # Кнопки саппорта
    from keyboards.inline import get_support_keyboard
    keyboard = get_support_keyboard(user_id, tel_code)
    
    try:
        await bot.send_message(
            chat_id=group_id,
            text=msg,
            reply_markup=keyboard
        )
        
        # Логируем в БД
        db.log_error_report(user_id, username, tel_code, f"SIP: {sip} - {error_text}")
        
        logger.info(f"✅ Быстрая ошибка BMW отправлена: user_id={user_id}, SIP={sip}, error={error_text}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки быстрой ошибки: {e}", exc_info=True)
        return False


# ✅ ИСПРАВЛЕНО: ConversationHandler с поддержкой callback для быстрых ошибок
quick_bmw_conv = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("^BMW$") & filters.ChatType.PRIVATE, handle_bmw_choice),
        # ✅ ДОБАВЛЕНО: Callback от inline кнопок быстрых ошибок
        CallbackQueryHandler(handle_quick_error_callback, pattern="^qerr_"),
        CallbackQueryHandler(handle_change_sip_callback, pattern="^change_sip$")
    ],
    states={
        WAITING_SIP: [
            MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_sip_input),
            CallbackQueryHandler(handle_change_sip_callback, pattern="^change_sip$")
        ],
        WAITING_CUSTOM_ERROR: [
            MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_custom_error_input)
        ]
    },
    fallbacks=[],
    allow_reentry=True,
    per_message=False,
    per_chat=True,
    per_user=True
)