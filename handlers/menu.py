"""
Обработчики кнопок меню
"""
from telegram import Update
from telegram.ext import ContextTypes

from config.constants import USEFUL_LINKS, MESSAGES
from keyboards.reply import get_menu_by_role
from keyboards.inline import get_telephony_keyboard, get_management_menu
from utils.state import get_user_role, set_support_mode, clear_tel_choice
from utils.logger import logger


async def handle_support_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик кнопки "Поддержка"
    
    Args:
        update: Update объект
        context: Контекст пользователя
    """
    set_support_mode(context, True)
    await update.message.reply_text(MESSAGES["support_prompt"])


async def handle_telephony_errors_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик кнопки "Ошибки телефонии"
    
    Args:
        update: Update объект
        context: Контекст пользователя
    """
    clear_tel_choice(context)  # Сбрасываем предыдущий выбор
    await update.message.reply_text(
        MESSAGES["choose_telephony"],
        reply_markup=get_telephony_keyboard()
    )


async def handle_useful_links_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик кнопки "Полезные ссылки"
    
    Args:
        update: Update объект
        context: Контекст пользователя
    """
    links_text = "🔗 <b>Полезные ссылки:</b>\n\n"
    for i, (name, url) in enumerate(USEFUL_LINKS.items(), 1):
        links_text += f"{i}. <a href='{url}'>{name}</a>\n"
    
    await update.message.reply_text(links_text, parse_mode="HTML")


async def handle_stats_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик кнопки "Статистика трубок" (только для админа в личке)
    
    Args:
        update: Update объект
        context: Контекст пользователя
    """
    try:
        from services.stats_service import stats_service
        
        # Получаем статистику
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
    """
    Обработчик кнопки "Статистика менеджеров"
    
    Args:
        update: Update объект
        context: Контекст пользователя
    """
    try:
        from services.managers_stats_service import managers_stats_service
        
        # Получаем статистику менеджеров
        stats_text = await managers_stats_service.get_managers_stats()
        
        await update.message.reply_text(stats_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики менеджеров: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ Ошибка при получении статистики менеджеров.\n"
            "Попробуйте позже."
        )


async def handle_bot_management_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик кнопки "Управление ботом"
    
    Args:
        update: Update объект
        context: Контекст пользователя
    """
    # Показываем меню управления через inline кнопки
    keyboard = get_management_menu()
    
    await update.message.reply_text(
        "⚙️ <b>Управление ботом</b>\n\n"
        "Выберите раздел:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Главный обработчик кнопок меню
    
    Args:
        update: Update объект
        context: Контекст пользователя
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