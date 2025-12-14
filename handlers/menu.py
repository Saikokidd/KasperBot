"""
handlers/menu.py - ПОЛНОЕ ИСПРАВЛЕНИЕ
Правильная работа с Inline кнопками телефоний + проверка быстрых ошибок

КРИТИЧЕСКИЕ ИЗМЕНЕНИЯ:
✅ НЕ используем Reply клавиатуру для телефоний (только Inline)
✅ Всегда очищаем состояние при возврате в меню
✅ Не показываем лишних предупреждений
✅ ДОБАВЛЕНО: Проверка быстрых ошибок через БД
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config.constants import USEFUL_LINKS, MESSAGES
from keyboards.reply import get_menu_by_role
from keyboards.inline import get_management_menu, get_quick_errors_keyboard
from utils.state import get_user_role, set_support_mode, clear_tel_choice, set_tel_choice, clear_all_states
from utils.logger import logger


async def handle_support_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки "Поддержка"""
    set_support_mode(context, True)
    await update.message.reply_text(MESSAGES["support_prompt"])


async def handle_telephony_errors_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик кнопки "Ошибки телефонии"
    
    ✅ КРИТИЧНО: Очищаем старое состояние перед показом кнопок
    """
    # ✅ КРИТИЧНО: Очищаем состояние
    clear_all_states(context)
    
    # Получаем все телефонии из БД
    from database.models import db
    telephonies = db.get_all_telephonies()
    
    if not telephonies:
        await update.message.reply_text(
            "⚠️ Нет доступных телефоний.\n"
            "Обратитесь к администратору."
        )
        return
    
    # Создаём Inline кнопки
    buttons = []
    for tel in telephonies:
        buttons.append([
            InlineKeyboardButton(
                tel['name'], 
                callback_data=f"select_tel_{tel['code']}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(buttons)
    
    await update.message.reply_text(
        MESSAGES["choose_telephony"],
        reply_markup=keyboard
    )


async def handle_telephony_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик Inline кнопок выбора телефонии
    
    ✅ КРИТИЧНО: Проверяет быстрая ли телефония через БД
    """
    query = update.callback_query
    await query.answer()
    
    # Извлекаем код телефонии
    tel_code = query.data.split("_")[2]
    
    logger.info(f"📞 Выбрана телефония через Inline: {tel_code}")
    
    # Получаем данные телефонии из БД
    from database.models import db
    tel = db.get_telephony_by_code(tel_code)
    
    if not tel:
        await query.message.edit_text(
            "⚠️ Телефония не найдена.\n"
            "Попробуйте снова."
        )
        return
    
    # ✅ КРИТИЧЕСКАЯ ПРОВЕРКА: Быстрая ли телефония?
    is_quick = db.is_quick_error_telephony(tel_code)
    
    if is_quick:
        # ===== БЫСТРЫЕ ОШИБКИ =====
        logger.info(f"⚡️ Телефония {tel_code} использует быстрые ошибки")
        
        user_id = query.from_user.id
        
        # Проверяем SIP
        if db.is_sip_valid_today(user_id):
            sip_data = db.get_manager_sip(user_id)
            
            if sip_data and sip_data.get('sip_number'):
                sip = sip_data['sip_number']
                logger.info(f"✅ SIP уже указан: {sip}")
                
                # Сохраняем контекст
                context.user_data["quick_error_sip"] = sip
                context.user_data["quick_error_tel_name"] = tel['name']
                context.user_data["quick_error_tel_code"] = tel_code
                context.user_data["quick_error_group_id"] = tel['group_id']
                
                # Показываем кнопки ошибок
                await query.message.edit_text(
                    MESSAGES["choose_quick_error"].format(sip=sip),
                    reply_markup=get_quick_errors_keyboard()
                )
                return
        
        # SIP не указан - запрашиваем
        logger.info(f"⚠️ SIP не указан, запрашиваем")
        
        # Сохраняем контекст
        context.user_data["quick_error_tel_name"] = tel['name']
        context.user_data["quick_error_tel_code"] = tel_code
        context.user_data["quick_error_group_id"] = tel['group_id']
        context.user_data["awaiting_sip_for_quick_error"] = True
        
        await query.message.edit_text(MESSAGES["sip_prompt"])
        
        # Здесь должен подхватить message_handler для обработки SIP
        return
    
    else:
        # ===== ОБЫЧНЫЙ FLOW =====
        logger.info(f"📝 Телефония {tel_code} использует обычный ввод")
        
        # Сохраняем выбор
        set_tel_choice(context, tel['name'], tel_code)
        
        logger.info(f"✅ User {query.from_user.id} выбрал телефонию: {tel['name']} ({tel_code})")
        
        # Уведомляем пользователя
        await query.message.edit_text(
            f"✅ Вы выбрали: <b>{tel['name']}</b>\n\n"
            f"📝 Теперь отправьте описание ошибки\n"
            f"⏱ Выбор активен 10 минут.",
            parse_mode="HTML"
        )


async def handle_useful_links_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки "Полезные ссылки"""
    links_text = "🔗 <b>Полезные ссылки:</b>\n\n"
    for i, (name, url) in enumerate(USEFUL_LINKS.items(), 1):
        links_text += f"{i}. <a href='{url}'>{name}</a>\n"
    
    await update.message.reply_text(links_text, parse_mode="HTML")


async def handle_stats_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки "Статистика трубок"""
    try:
        from services.stats_service import stats_service
        
        stats_text = await stats_service.get_perezvoni_stats()
        await update.message.reply_text(stats_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ Ошибка при получении статистики.\n"
            "Google Sheets API не настроен или произошла ошибка.\n"
            "Обратитесь к администратору."
        )


async def handle_managers_stats_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки "Статистика менеджеров"""
    try:
        from services.managers_stats_service import managers_stats_service
        
        stats_text = await managers_stats_service.get_managers_stats()
        await update.message.reply_text(stats_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики менеджеров: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ Ошибка при получении статистики менеджеров.\n"
            "Попробуйте позже."
        )


async def handle_bot_management_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки "Управление ботом"""
    keyboard = get_management_menu()
    
    await update.message.reply_text(
        "⚙️ <b>Управление ботом</b>\n\n"
        "Выберите раздел:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def handle_errors_stats_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Статистика ошибок'"""
    from services.analytics_service import analytics_service
    from handlers.analytics import get_dashboard_navigation
    
    stats_text = analytics_service.get_dashboard_overview("today")
    keyboard = get_dashboard_navigation(page=1, period="today")
    
    await update.message.reply_text(
        stats_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def handle_back_to_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик кнопки "◀️ Меню" - возврат в главное меню
    
    ✅ КРИТИЧНО: Очищаем ВСЁ состояние при возврате
    """
    # ✅ КРИТИЧНО: Полная очистка состояния
    clear_all_states(context)
    
    role = get_user_role(context)
    current_menu = get_menu_by_role(role)
    
    # ✅ ИСПРАВЛЕНО: Обновляем Reply клавиатуру
    await update.message.reply_text(
        "📋 Главное меню\n\nВыберите действие:",
        reply_markup=current_menu
    )


async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Главный обработчик кнопок меню
    """
    text = update.message.text
    role = get_user_role(context)
    user_id = update.effective_user.id
    
    logger.debug(f"Кнопка '{text}' от user_id={user_id}, роль={role}")
    
    # Если роль не установлена
    if not role:
        await update.message.reply_text(MESSAGES["session_expired"])
        return
    
    # Маппинг кнопок на функции
    menu_actions = {
        "Ошибки телефонии": handle_telephony_errors_button,
        "Полезные ссылки": handle_useful_links_button,
        "Статистика трубок": handle_stats_button,
        "Статистика менеджеров": handle_managers_stats_button,
        "Управление ботом": handle_bot_management_button,
        "Статистика ошибок": handle_errors_stats_button,
        "◀️ Меню": handle_back_to_menu_button,
    }
    
    action = menu_actions.get(text)
    if action:
        await action(update, context)
    else:
        logger.warning(f"⚠️ Неизвестная команда кнопки: '{text}' от user_id={user_id}")
        current_menu = get_menu_by_role(role)
        await update.message.reply_text(
            MESSAGES["unknown_command"],
            reply_markup=current_menu
        )