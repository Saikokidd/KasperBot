"""
Обработчики для статистики ошибок
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services.analytics_service import analytics_service
from utils.logger import logger


async def show_errors_stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню статистики ошибок"""
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Общая статистика", callback_data="stats_general")],
        [InlineKeyboardButton("�� По менеджерам", callback_data="stats_managers")],
        [InlineKeyboardButton("🛠 По саппорту", callback_data="stats_support")],
        [InlineKeyboardButton("⏱ Время реакции", callback_data="stats_response_time")],
        [InlineKeyboardButton("« Назад", callback_data="stats_back")]
    ])
    
    await query.message.edit_text(
        "📊 <b>Статистика ошибок</b>\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def show_general_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает общую статистику"""
    query = update.callback_query
    await query.answer()
    
    # Выбор периода
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Сегодня", callback_data="stats_gen_today")],
        [InlineKeyboardButton("📆 Неделя", callback_data="stats_gen_week")],
        [InlineKeyboardButton("📊 Месяц", callback_data="stats_gen_month")],
        [InlineKeyboardButton("« Назад", callback_data="stats_menu")]
    ])
    
    await query.message.edit_text(
        "📈 <b>Общая статистика</b>\n\nВыберите период:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def show_general_stats_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает общую статистику за период"""
    query = update.callback_query
    await query.answer("Загрузка...")
    
    # Получаем период из callback_data
    period = query.data.split("_")[-1]  # today, week, month
    
    stats_text = analytics_service.get_general_stats(period)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« Назад", callback_data="stats_general")]
    ])
    
    await query.message.edit_text(
        stats_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def show_managers_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику по менеджерам"""
    query = update.callback_query
    await query.answer()
    
    # Выбор периода
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Сегодня", callback_data="stats_mgr_today")],
        [InlineKeyboardButton("📆 Неделя", callback_data="stats_mgr_week")],
        [InlineKeyboardButton("📊 Месяц", callback_data="stats_mgr_month")],
        [InlineKeyboardButton("« Назад", callback_data="stats_menu")]
    ])
    
    await query.message.edit_text(
        "👤 <b>Статистика по менеджерам</b>\n\nВыберите период:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def show_managers_stats_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику менеджеров за период"""
    query = update.callback_query
    await query.answer("Загрузка...")
    
    # Получаем период
    period = query.data.split("_")[-1]
    
    stats_text = analytics_service.get_managers_stats(period, limit=10)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« Назад", callback_data="stats_managers")]
    ])
    
    await query.message.edit_text(
        stats_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def show_support_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику по саппорту"""
    query = update.callback_query
    await query.answer()
    
    # Выбор периода
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Сегодня", callback_data="stats_sup_today")],
        [InlineKeyboardButton("📆 Неделя", callback_data="stats_sup_week")],
        [InlineKeyboardButton("📊 Месяц", callback_data="stats_sup_month")],
        [InlineKeyboardButton("« Назад", callback_data="stats_menu")]
    ])
    
    await query.message.edit_text(
        "🛠 <b>Статистика по саппорту</b>\n\nВыберите период:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def show_support_stats_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику саппорта за период"""
    query = update.callback_query
    await query.answer("Загрузка...")
    
    period = query.data.split("_")[-1]
    
    stats_text = analytics_service.get_support_stats(period, limit=10)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« Назад", callback_data="stats_support")]
    ])
    
    await query.message.edit_text(
        stats_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def show_response_time_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику времени реакции"""
    query = update.callback_query
    await query.answer()
    
    # Выбор периода
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Сегодня", callback_data="stats_time_today")],
        [InlineKeyboardButton("📆 Неделя", callback_data="stats_time_week")],
        [InlineKeyboardButton("📊 Месяц", callback_data="stats_time_month")],
        [InlineKeyboardButton("« Назад", callback_data="stats_menu")]
    ])
    
    await query.message.edit_text(
        "⏱ <b>Время реакции саппорта</b>\n\nВыберите период:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def show_response_time_stats_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику времени за период"""
    query = update.callback_query
    await query.answer("Загрузка...")
    
    period = query.data.split("_")[-1]
    
    stats_text = analytics_service.get_response_time_stats(period)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« Назад", callback_data="stats_response_time")]
    ])
    
    await query.message.edit_text(
        stats_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
