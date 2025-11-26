"""
Обработчики для полного дашборда статистики ошибок
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services.analytics_service import analytics_service
from utils.logger import logger


def get_dashboard_navigation(page: int, period: str = "today") -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру навигации по дашборду
    
    Args:
        page: Номер текущей страницы (1-4)
        period: Период ('today', 'week', 'month')
        
    Returns:
        InlineKeyboardMarkup с кнопками навигации
    """
    buttons = []
    
    # Навигация по страницам
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f"dash_page_{page-1}_{period}"))
    if page < 4:
        nav_buttons.append(InlineKeyboardButton("Далее ▶️", callback_data=f"dash_page_{page+1}_{period}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Прямые переходы
    page_buttons = [
        InlineKeyboardButton("📊" if page == 1 else "1", callback_data=f"dash_page_1_{period}"),
        InlineKeyboardButton("👥" if page == 2 else "2", callback_data=f"dash_page_2_{period}"),
        InlineKeyboardButton("🛠" if page == 3 else "3", callback_data=f"dash_page_3_{period}"),
        InlineKeyboardButton("⏱" if page == 4 else "4", callback_data=f"dash_page_4_{period}")
    ]
    buttons.append(page_buttons)
    
    # Выбор периода
    period_buttons = [
        InlineKeyboardButton("📅" if period == "today" else "Сегодня", callback_data=f"dash_page_{page}_today"),
        InlineKeyboardButton("📆" if period == "week" else "Неделя", callback_data=f"dash_page_{page}_week"),
        InlineKeyboardButton("📊" if period == "month" else "Месяц", callback_data=f"dash_page_{page}_month")
    ]
    buttons.append(period_buttons)
    
    # Дополнительные действия
    buttons.append([
        InlineKeyboardButton("🔄 Обновить", callback_data=f"dash_page_{page}_{period}"),
        InlineKeyboardButton("🏠 Главная", callback_data="stats_menu")
    ])
    
    return InlineKeyboardMarkup(buttons)


async def show_errors_stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню статистики с выбором периода"""
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Сегодня", callback_data="dash_start_today")],
        [InlineKeyboardButton("📆 Неделя", callback_data="dash_start_week")],
        [InlineKeyboardButton("📊 Месяц", callback_data="dash_start_month")],
    ])
    
    await query.message.edit_text(
        "📊 <b>ДАШБОРД СТАТИСТИКИ ОШИБОК</b>\n\n"
        "Выберите период для просмотра:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def show_dashboard_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускает дашборд с выбранным периодом"""
    query = update.callback_query
    await query.answer("Загрузка дашборда...")
    
    # Получаем период из callback_data
    period = query.data.split("_")[-1]  # today, week, month
    
    # Показываем первую страницу
    stats_text = analytics_service.get_dashboard_overview(period)
    keyboard = get_dashboard_navigation(page=1, period=period)
    
    await query.message.edit_text(
        stats_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def show_dashboard_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает конкретную страницу дашборда"""
    query = update.callback_query
    await query.answer("Загрузка...")
    
    # Парсим callback_data: dash_page_2_today
    parts = query.data.split("_")
    page = int(parts[2])
    period = parts[3]
    
    # Получаем данные для страницы
    if page == 1:
        stats_text = analytics_service.get_dashboard_overview(period)
    elif page == 2:
        stats_text = analytics_service.get_dashboard_managers(period)
    elif page == 3:
        stats_text = analytics_service.get_dashboard_support(period)
    elif page == 4:
        stats_text = analytics_service.get_dashboard_timing(period)
    else:
        stats_text = "⚠️ Неверный номер страницы"
    
    keyboard = get_dashboard_navigation(page=page, period=period)
    
    await query.message.edit_text(
        stats_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


# ===== СТАРЫЕ ОБРАБОТЧИКИ (для обратной совместимости) =====

async def show_general_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перенаправляет на дашборд"""
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Сегодня", callback_data="dash_start_today")],
        [InlineKeyboardButton("📆 Неделя", callback_data="dash_start_week")],
        [InlineKeyboardButton("📊 Месяц", callback_data="dash_start_month")],
        [InlineKeyboardButton("« Назад", callback_data="stats_menu")]
    ])
    
    await query.message.edit_text(
        "📊 <b>Открыть полный дашборд?</b>\n\n"
        "Выберите период:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def show_general_stats_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Заглушка - перенаправляет на дашборд"""
    await show_dashboard_start(update, context)


async def show_managers_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перенаправляет на страницу 2 дашборда"""
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Сегодня", callback_data="dash_page_2_today")],
        [InlineKeyboardButton("📆 Неделя", callback_data="dash_page_2_week")],
        [InlineKeyboardButton("📊 Месяц", callback_data="dash_page_2_month")],
        [InlineKeyboardButton("« Назад", callback_data="stats_menu")]
    ])
    
    await query.message.edit_text(
        "👥 <b>Статистика менеджеров</b>\n\nВыберите период:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def show_managers_stats_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Заглушка"""
    await show_dashboard_page(update, context)


async def show_support_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перенаправляет на страницу 3 дашборда"""
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Сегодня", callback_data="dash_page_3_today")],
        [InlineKeyboardButton("📆 Неделя", callback_data="dash_page_3_week")],
        [InlineKeyboardButton("📊 Месяц", callback_data="dash_page_3_month")],
        [InlineKeyboardButton("« Назад", callback_data="stats_menu")]
    ])
    
    await query.message.edit_text(
        "🛠 <b>Статистика саппорта</b>\n\nВыберите период:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def show_support_stats_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Заглушка"""
    await show_dashboard_page(update, context)


async def show_response_time_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перенаправляет на страницу 4 дашборда"""
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Сегодня", callback_data="dash_page_4_today")],
        [InlineKeyboardButton("📆 Неделя", callback_data="dash_page_4_week")],
        [InlineKeyboardButton("📊 Месяц", callback_data="dash_page_4_month")],
        [InlineKeyboardButton("« Назад", callback_data="stats_menu")]
    ])
    
    await query.message.edit_text(
        "⏱ <b>Время реакции</b>\n\nВыберите период:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def show_response_time_stats_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Заглушка"""
    await show_dashboard_page(update, context)