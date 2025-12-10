"""
УНИВЕРСАЛЬНАЯ СИСТЕМА БЫСТРЫХ ОШИБОК
Работает с любыми белыми телефониями, где включены быстрые ошибки

ИСПРАВЛЕНИЕ: name задаётся при создании ConversationHandler
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, 
    filters, CallbackQueryHandler
)
from database.models import db
from keyboards.inline import get_quick_errors_keyboard
from keyboards.reply import get_menu_by_role
from config.constants import (
    MESSAGES, QUICK_ERRORS, MAX_SIP_LENGTH, 
    MAX_CUSTOM_ERROR_LENGTH, SIP_PATTERN
)
from config.settings import settings
from utils.state import get_user_role
from utils.logger import logger

# Состояния разговора
WAITING_SIP, WAITING_CUSTOM_ERROR, SHOWING_ERRORS = range(3)


def get_quick_errors_telephonies():
    """
    Получить список телефоний с включёнными быстрыми ошибками
    
    Returns:
        Список словарей с данными телефоний
    """
    return db.get_quick_errors_telephonies()


def get_quick_errors_regex():
    """
    Построить regex для всех телефоний с быстрыми ошибками
    
    Returns:
        Regex pattern (str) или None если нет телефоний
    """
    telephonies = get_quick_errors_telephonies()
    
    if not telephonies:
        return None
    
    # Строим regex: ^(BMW|Wizard|Телефония3)$
    names = [tel['name'] for tel in telephonies]
    pattern = f"^({'|'.join(names)})$"
    
    logger.debug(f"📞 Regex для быстрых ошибок: {pattern}")
    return pattern


async def handle_telephony_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик выбора телефонии с быстрыми ошибками
    
    Универсальный - работает для любой белой телефонии
    """
    user_id = update.effective_user.id
    tel_name = update.message.text.strip()
    
    logger.info(f"🔵 Выбрана телефония с быстрыми ошибками: {tel_name} от user_id={user_id}")
    
    # Ищем телефонию в списке активных
    telephonies = get_quick_errors_telephonies()
    selected_tel = None
    
    for tel in telephonies:
        if tel['name'] == tel_name:
            selected_tel = tel
            break
    
    if not selected_tel:
        logger.error(f"❌ Телефония {tel_name} не найдена среди доступных для быстрых ошибок")
        await update.message.reply_text(
            "⚠️ Эта телефония временно недоступна для быстрых ошибок."
        )
        return ConversationHandler.END
    
    # Сохраняем в контекст
    context.user_data["quick_errors_tel"] = selected_tel
    
    # Проверяем, указан ли SIP сегодня
    if db.is_sip_valid_today(user_id):
        sip_data = db.get_manager_sip(user_id)
        
        if not sip_data or not sip_data.get('sip_number'):
            logger.warning(f"⚠️ SIP данные повреждены для user_id={user_id}")
            await update.message.reply_text(MESSAGES["sip_prompt"])
            return WAITING_SIP
        
        sip = sip_data['sip_number']
        logger.info(f"✅ SIP уже указан сегодня: {sip}")
        
        context.user_data["quick_errors_sip"] = sip
        
        await update.message.reply_text(
            MESSAGES["choose_quick_error"].format(sip=sip),
            reply_markup=get_quick_errors_keyboard()
        )
        return SHOWING_ERRORS
    else:
        logger.info(f"⚠️ SIP не указан, запрашиваем у user_id={user_id}")
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_quick_errors")]
        ])
        
        await update.message.reply_text(
            MESSAGES["sip_prompt"] + "\n\n" +
            "💡 SIP - это номер из 3-5 цифр (например: 101, 1234)\n"
            "Если не знаете - уточните у администратора.",
            reply_markup=keyboard
        )
        return WAITING_SIP


async def handle_sip_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода SIP номера"""
    user_id = update.effective_user.id
    sip_text = update.message.text.strip()
    
    logger.info(f"📞 Введён SIP от user_id={user_id}: {sip_text}")
    
    # Валидация формата
    if not sip_text or len(sip_text) > MAX_SIP_LENGTH or not SIP_PATTERN.match(sip_text):
        logger.warning(f"⚠️ Неверный формат SIP: '{sip_text}' от user_id={user_id}")
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_quick_errors")]
        ])
        
        await update.message.reply_text(
            MESSAGES["sip_invalid"] + "\n\n" +
            "💡 Примеры правильного формата:\n" +
            "• 101\n" +
            "• 1234\n" +
            "• 56789\n\n" +
            "Попробуйте ещё раз:",
            reply_markup=keyboard
        )
        return WAITING_SIP
    
    # Сохраняем SIP
    db.save_manager_sip(user_id, sip_text)
    context.user_data["quick_errors_sip"] = sip_text
    
    logger.info(f"✅ SIP сохранён для user_id={user_id}: {sip_text}")
    
    # Показываем кнопки ошибок
    await update.message.reply_text(
        MESSAGES["sip_saved"].format(sip=sip_text),
        reply_markup=get_quick_errors_keyboard()
    )
    
    return SHOWING_ERRORS


async def cancel_quick_errors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена процесса быстрых ошибок"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    logger.info(f"❌ Отмена быстрых ошибок от user_id={user_id}")
    
    # Очистка контекста
    context.user_data.pop("quick_errors_tel", None)
    context.user_data.pop("quick_errors_sip", None)
    
    role = get_user_role(context)
    current_menu = get_menu_by_role(role)
    
    await query.message.edit_text("❌ Отменено. Используйте меню:")
    await query.message.reply_text(
        "Выберите действие:",
        reply_markup=current_menu
    )
    
    return ConversationHandler.END


async def handle_quick_error_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку быстрой ошибки"""
    query = update.callback_query
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Пользователь"
    
    logger.debug(f"🔘 Callback от user_id={user_id}: {query.data}")
    
    await query.answer()
    
    error_code = query.data.split("_")[1]
    logger.info(f"🔘 Нажата кнопка ошибки {error_code} от user_id={user_id}")
    
    # Получаем SIP и телефонию
    sip = context.user_data.get("quick_errors_sip")
    tel_data = context.user_data.get("quick_errors_tel")
    
    # Проверки
    if not sip:
        logger.error(f"❌ SIP не найден в контексте для user_id={user_id}")
        
        # Пытаемся восстановить из БД
        if db.is_sip_valid_today(user_id):
            sip_data = db.get_manager_sip(user_id)
            if sip_data and sip_data.get('sip_number'):
                sip = sip_data['sip_number']
                context.user_data["quick_errors_sip"] = sip
                logger.info(f"✅ SIP восстановлен из БД: {sip}")
        
        if not sip:
            await query.message.edit_text(
                "⚠️ Ошибка: SIP не найден.\n"
                "Попробуйте снова через меню 'Ошибки телефонии'"
            )
            return ConversationHandler.END
    
    if not tel_data:
        logger.error(f"❌ Данные телефонии не найдены для user_id={user_id}")
        await query.message.edit_text(
            "⚠️ Ошибка: данные телефонии потеряны.\n"
            "Попробуйте снова через меню 'Ошибки телефонии'"
        )
        return ConversationHandler.END
    
    # Если "Свой вариант"
    if error_code == "10":
        logger.info(f"✏️ Выбран свой вариант от user_id={user_id}")
        await query.message.edit_text(MESSAGES["custom_error_prompt"])
        return WAITING_CUSTOM_ERROR
    
    # Получаем текст ошибки
    error_text = QUICK_ERRORS.get(error_code, "Неизвестная ошибка")
    logger.info(f"📤 Отправка быстрой ошибки: {error_text}")
    
    # Отправляем в группу
    success = await send_quick_error_to_group(
        context.bot,
        user_id,
        username,
        sip,
        error_text,
        tel_data
    )
    
    if not success:
        await query.message.edit_text("⚠️ Не удалось отправить ошибку. Попробуйте позже.")
        return ConversationHandler.END
    
    await query.message.edit_text(
        MESSAGES["quick_error_sent"].format(sip=sip, error=error_text)
    )
    
    # Очистка контекста
    context.user_data.pop("quick_errors_sip", None)
    context.user_data.pop("quick_errors_tel", None)
    
    return ConversationHandler.END


async def handle_custom_error_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода своего варианта ошибки"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Пользователь"
    
    error_text = update.message.text.strip()
    sip = context.user_data.get("quick_errors_sip")
    tel_data = context.user_data.get("quick_errors_tel")
    
    logger.info(f"✏️ Custom ошибка от user_id={user_id}: {error_text[:50]}...")
    
    if not sip or not tel_data:
        logger.error(f"❌ SIP или телефония потеряны для user_id={user_id}")
        await update.message.reply_text("⚠️ Ошибка: данные потеряны.")
        
        context.user_data.pop("quick_errors_sip", None)
        context.user_data.pop("quick_errors_tel", None)
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
        context.bot,
        user_id,
        username,
        sip,
        error_text,
        tel_data
    )
    
    if not success:
        await update.message.reply_text("⚠️ Не удалось отправить ошибку.")
        context.user_data.pop("quick_errors_sip", None)
        context.user_data.pop("quick_errors_tel", None)
        return ConversationHandler.END
    
    role = get_user_role(context)
    current_menu = get_menu_by_role(role)
    
    await update.message.reply_text(
        MESSAGES["quick_error_sent"].format(sip=sip, error=error_text),
        reply_markup=current_menu
    )
    
    context.user_data.pop("quick_errors_sip", None)
    context.user_data.pop("quick_errors_tel", None)
    
    return ConversationHandler.END


async def handle_change_sip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Изменить SIP'"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    logger.info(f"⚙️ Запрос на изменение SIP от user_id={user_id}")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_quick_errors")]
    ])
    
    await query.message.edit_text(
        MESSAGES["sip_prompt"] + "\n\n" +
        "💡 SIP - это номер из 3-5 цифр",
        reply_markup=keyboard
    )
    
    return WAITING_SIP


async def send_quick_error_to_group(
    bot, 
    user_id: int, 
    username: str, 
    sip: str, 
    error_text: str,
    tel_data: dict
) -> bool:
    """
    Отправляет быструю ошибку в группу телефонии
    
    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
        username: Имя пользователя
        sip: SIP номер
        error_text: Текст ошибки
        tel_data: Данные телефонии {'name', 'code', 'group_id'}
        
    Returns:
        True если успешно
    """
    group_id = tel_data['group_id']
    tel_code = tel_data['code']
    tel_name = tel_data['name']
    
    msg = f"От {username}\nSIP: {sip}  {error_text}"
    
    from keyboards.inline import get_support_keyboard
    keyboard = get_support_keyboard(user_id, tel_code)
    
    try:
        await bot.send_message(
            chat_id=group_id,
            text=msg,
            reply_markup=keyboard
        )
        
        db.log_error_report(
            user_id, 
            username, 
            tel_code, 
            f"SIP: {sip} - {error_text}"
        )
        
        logger.info(
            f"✅ Быстрая ошибка: {tel_name} → группа {group_id}, "
            f"user_id={user_id}, SIP={sip}"
        )
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}", exc_info=True)
        return False


# ============================================================================
# ДИНАМИЧЕСКОЕ СОЗДАНИЕ ConversationHandler
# ============================================================================

def create_quick_errors_conv():
    """
    Создать ConversationHandler для быстрых ошибок
    
    Returns:
        ConversationHandler или None если нет доступных телефоний
    """
    # Получаем regex
    regex_pattern = get_quick_errors_regex()
    
    if not regex_pattern:
        logger.warning("⚠️ Нет телефоний с включёнными быстрыми ошибками")
        return None
    
    logger.info(f"✅ Создание ConversationHandler для быстрых ошибок: {regex_pattern}")
    
    # Создаём фильтр для кнопок меню (чтобы исключить их)
    menu_buttons_pattern = (
        "^(Ошибки телефонии|Полезные ссылки|Статистика трубок|"
        "Статистика менеджеров|Управление ботом|Статистика ошибок|◀️ Меню|"
        "Звонари|Wizard)$"
    )
    
    # ✅ ИСПРАВЛЕНО: Добавляем name при создании
    return ConversationHandler(
        name='quick_errors',  # ✅ Указываем name здесь
        entry_points=[
            MessageHandler(
                filters.Regex(regex_pattern) & 
                filters.ChatType.PRIVATE,
                handle_telephony_choice
            ),
            CallbackQueryHandler(handle_quick_error_callback, pattern="^qerr_"),
            CallbackQueryHandler(handle_change_sip_callback, pattern="^change_sip$"),
        ],
        states={
            WAITING_SIP: [
                MessageHandler(
                    filters.TEXT & 
                    ~filters.COMMAND & 
                    ~filters.Regex(menu_buttons_pattern) &
                    filters.ChatType.PRIVATE,
                    handle_sip_input
                ),
                CallbackQueryHandler(cancel_quick_errors, pattern="^cancel_quick_errors$"),
            ],
            SHOWING_ERRORS: [
                CallbackQueryHandler(handle_quick_error_callback, pattern="^qerr_"),
                CallbackQueryHandler(handle_change_sip_callback, pattern="^change_sip$"),
            ],
            WAITING_CUSTOM_ERROR: [
                MessageHandler(
                    filters.TEXT & 
                    ~filters.COMMAND &
                    filters.ChatType.PRIVATE,
                    handle_custom_error_input
                )
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_quick_errors, pattern="^cancel_quick_errors$"),
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=True  # ✅ Убираем предупреждение
    )


# Создаём handler при импорте модуля
quick_errors_conv = create_quick_errors_conv()


# Функция для внешнего использования (логирование)
def get_quick_errors_telephony_names():
    """Получить список названий телефоний для быстрых ошибок"""
    telephonies = get_quick_errors_telephonies()
    return [tel['name'] for tel in telephonies]


# ============================================================================
# КОНЕЦ ФАЙЛА handlers/quick_errors.py
# ============================================================================