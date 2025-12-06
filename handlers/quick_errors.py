"""
ИСПРАВЛЕННЫЙ ФАЙЛ: handlers/quick_errors.py
Добавлена валидация SIP и обработка None

ИЗМЕНЕНИЯ:
✅ Валидация формата SIP (только цифры) в handle_sip_input()
✅ Обработка None в handle_quick_error_callback()
✅ Улучшено логирование
"""
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from database.models import db
from keyboards.inline import get_quick_errors_keyboard
from keyboards.reply import get_menu_by_role
from config.constants import MESSAGES, QUICK_ERRORS, MAX_SIP_LENGTH, MAX_CUSTOM_ERROR_LENGTH, SIP_PATTERN
from config.settings import settings
from utils.state import get_user_role
from utils.logger import logger

# Состояния разговора
WAITING_SIP, WAITING_CUSTOM_ERROR, SHOWING_ERRORS = range(3)


async def handle_bmw_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик выбора BMW из Reply меню
    
    Args:
        update: Update объект
        context: Контекст пользователя
    
    Returns:
        SHOWING_ERRORS если SIP указан, WAITING_SIP если нет
    """
    user_id = update.effective_user.id
    
    logger.info(f"🔵 BMW выбран user_id={user_id}")
    
    # Проверяем, указан ли SIP сегодня
    if db.is_sip_valid_today(user_id):
        # SIP указан - показываем кнопки ошибок
        sip_data = db.get_manager_sip(user_id)
        
        # ✅ ИСПРАВЛЕНИЕ 1: Проверка на None
        if not sip_data or not sip_data.get('sip_number'):
            logger.warning(f"⚠️ SIP данные повреждены для user_id={user_id}, запрашиваем заново")
            await update.message.reply_text(MESSAGES["sip_prompt"])
            return WAITING_SIP
        
        sip = sip_data['sip_number']
        
        logger.info(f"✅ SIP уже указан сегодня: {sip}")
        
        # Сохраняем SIP в контексте
        context.user_data["bmw_sip"] = sip
        
        await update.message.reply_text(
            MESSAGES["choose_quick_error"].format(sip=sip),
            reply_markup=get_quick_errors_keyboard()
        )
        return SHOWING_ERRORS
    else:
        logger.info(f"⚠️ SIP не указан, запрашиваем у user_id={user_id}")
        
        await update.message.reply_text(MESSAGES["sip_prompt"])
        return WAITING_SIP


async def handle_sip_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик ввода SIP номера
    
    Args:
        update: Update объект
        context: Контекст пользователя
    
    Returns:
        WAITING_SIP при ошибке, SHOWING_ERRORS при успехе
    """
    user_id = update.effective_user.id
    sip_text = update.message.text.strip()
    
    logger.info(f"📞 Введён SIP от user_id={user_id}: {sip_text}")
    
    # ✅ ИСПРАВЛЕНИЕ 2: Валидация формата SIP (только цифры)
    if not sip_text or len(sip_text) > MAX_SIP_LENGTH or not SIP_PATTERN.match(sip_text):
        logger.warning(f"⚠️ Неверный формат SIP: '{sip_text}' от user_id={user_id}")
        await update.message.reply_text(MESSAGES["sip_invalid"])
        return WAITING_SIP
    
    # Сохраняем SIP в БД и контексте
    db.save_manager_sip(user_id, sip_text)
    context.user_data["bmw_sip"] = sip_text
    
    logger.info(f"✅ SIP сохранён для user_id={user_id}: {sip_text}")
    
    # Показываем кнопки ошибок
    await update.message.reply_text(
        MESSAGES["sip_saved"].format(sip=sip_text),
        reply_markup=get_quick_errors_keyboard()
    )
    
    return SHOWING_ERRORS


async def handle_quick_error_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик нажатия на кнопку быстрой ошибки (1-9 или 10)
    
    Args:
        update: Update объект
        context: Контекст пользователя
    
    Returns:
        WAITING_CUSTOM_ERROR если выбран "Свой вариант", иначе ConversationHandler.END
    """
    query = update.callback_query
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Пользователь"
    
    logger.debug(f"🔘 Callback от user_id={user_id}: {query.data}")
    
    await query.answer()
    
    # Получаем код ошибки (qerr_1 → 1)
    error_code = query.data.split("_")[1]
    
    logger.info(f"🔘 Нажата кнопка ошибки {error_code} от user_id={user_id}")
    
    # Получаем SIP из контекста
    sip = context.user_data.get("bmw_sip")
    
    # ✅ ИСПРАВЛЕНИЕ 3: Если SIP нет в контексте, пытаемся загрузить из БД
    if not sip:
        logger.warning(f"⚠️ SIP не найден в контексте для user_id={user_id}, проверяем БД...")
        
        if db.is_sip_valid_today(user_id):
            sip_data = db.get_manager_sip(user_id)
            
            # ✅ Проверка на None
            if sip_data and sip_data.get('sip_number'):
                sip = sip_data['sip_number']
                context.user_data["bmw_sip"] = sip
                logger.info(f"✅ SIP восстановлен из БД: {sip}")
            else:
                logger.error(f"❌ SIP данные повреждены в БД для user_id={user_id}")
                await query.message.edit_text(
                    "⚠️ Ошибка: SIP не найден или повреждён.\n"
                    "Попробуйте снова через меню 'Ошибки телефонии' → 'BMW'"
                )
                return ConversationHandler.END
        else:
            logger.error(f"❌ SIP не найден ни в контексте, ни в БД для user_id={user_id}")
            await query.message.edit_text(
                "⚠️ Ошибка: SIP не найден.\n"
                "Попробуйте снова через меню 'Ошибки телефонии' → 'BMW'"
            )
            return ConversationHandler.END
    
    # Если "Свой вариант" - переходим к вводу текста
    if error_code == "10":
        logger.info(f"✏️ Выбран свой вариант, ожидаем текст от user_id={user_id}")
        
        await query.message.edit_text(MESSAGES["custom_error_prompt"])
        return WAITING_CUSTOM_ERROR
    
    # Получаем текст ошибки
    error_text = QUICK_ERRORS.get(error_code, "Неизвестная ошибка")
    
    logger.info(f"📤 Отправка быстрой ошибки: {error_text}")
    
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
    
    # Очищаем контекст
    context.user_data.pop("bmw_sip", None)
    
    return ConversationHandler.END


async def handle_custom_error_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик ввода своего варианта ошибки
    
    Args:
        update: Update объект
        context: Контекст пользователя
    
    Returns:
        WAITING_CUSTOM_ERROR при ошибке валидации, ConversationHandler.END при успехе
    """
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Пользователь"
    
    error_text = update.message.text.strip()
    sip = context.user_data.get("bmw_sip")
    
    logger.info(f"✏️ Custom ошибка от user_id={user_id}: {error_text[:50]}...")
    
    # ✅ Проверка SIP
    if not sip:
        logger.error(f"❌ SIP потерян из контекста для user_id={user_id}")
        await update.message.reply_text("⚠️ Ошибка: SIP не найден.")
        context.user_data.pop("bmw_sip", None)
        return ConversationHandler.END
    
    # Валидация
    if not error_text or len(error_text) > MAX_CUSTOM_ERROR_LENGTH:
        await update.message.reply_text(
            f"⚠️ Описание ошибки должно быть от 1 до {MAX_CUSTOM_ERROR_LENGTH} символов.\n"
            f"Сейчас: {len(error_text)} символов"
        )
        return WAITING_CUSTOM_ERROR
    
    # Отправляем в группу
    success = await send_quick_error_to_group(
        context.bot, user_id, username, sip, error_text
    )
    
    if not success:
        await update.message.reply_text("⚠️ Не удалось отправить ошибку. Попробуйте позже.")
        context.user_data.pop("bmw_sip", None)
        return ConversationHandler.END
    
    # Уведомляем пользователя
    role = get_user_role(context)
    current_menu = get_menu_by_role(role)
    
    await update.message.reply_text(
        MESSAGES["quick_error_sent"].format(sip=sip, error=error_text),
        reply_markup=current_menu
    )
    
    # Очищаем контекст
    context.user_data.pop("bmw_sip", None)
    
    return ConversationHandler.END


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
    
    user_id = update.effective_user.id
    logger.info(f"⚙️ Запрос на изменение SIP от user_id={user_id}")
    
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


# ConversationHandler с поддержкой callback для быстрых ошибок
quick_bmw_conv = ConversationHandler(
    entry_points=[
        # Текстовое сообщение "BMW"
        MessageHandler(filters.Regex("^BMW$") & filters.ChatType.PRIVATE, handle_bmw_choice),
        # Кнопки быстрых ошибок работают ВСЕГДА
        CallbackQueryHandler(handle_quick_error_callback, pattern="^qerr_"),
        CallbackQueryHandler(handle_change_sip_callback, pattern="^change_sip$"),
    ],
    states={
        WAITING_SIP: [
            MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_sip_input),
        ],
        SHOWING_ERRORS: [
            # Дублируем для надёжности (если уже в состоянии)
            CallbackQueryHandler(handle_quick_error_callback, pattern="^qerr_"),
            CallbackQueryHandler(handle_change_sip_callback, pattern="^change_sip$"),
        ],
        WAITING_CUSTOM_ERROR: [
            MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_custom_error_input)
        ]
    },
    fallbacks=[],
    allow_reentry=True,
    per_chat=True,
    per_user=True
)