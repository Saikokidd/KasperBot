"""
handlers/menu.py
✅ ИЗМЕНЕНИЕ: добавлен обработчик кнопки "Статистика баз"
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config.constants import USEFUL_LINKS, MESSAGES
from keyboards.reply import get_menu_by_role
from keyboards.inline import get_management_menu, get_quick_errors_keyboard
from utils.state import (
    get_user_role,
    set_support_mode,
    set_tel_choice,
    clear_all_states,
)
from utils.logger import logger


async def handle_support_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки "Поддержка"""
    set_support_mode(context, True)
    await update.message.reply_text(MESSAGES["support_prompt"])


async def handle_telephony_errors_button(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Обработчик кнопки "Ошибки телефонии" """
    clear_all_states(context)

    from database.models import db

    telephonies = db.get_all_telephonies()

    if not telephonies:
        await update.message.reply_text(
            "⚠️ Нет доступных телефоний.\nОбратитесь к администратору."
        )
        return

    buttons = [
        [InlineKeyboardButton(tel["name"], callback_data=f"select_tel_{tel['code']}")]
        for tel in telephonies
    ]

    await update.message.reply_text(
        MESSAGES["choose_telephony"],
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def handle_telephony_selection_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Обработчик Inline кнопок выбора телефонии"""
    query = update.callback_query
    await query.answer()

    tel_code = query.data.split("_")[2]
    logger.info(f"📞 Выбрана телефония через Inline: {tel_code}")

    from database.models import db

    tel = db.get_telephony_by_code(tel_code)

    if not tel:
        await query.message.edit_text("⚠️ Телефония не найдена.\nПопробуйте снова.")
        return

    is_quick = db.is_quick_error_telephony(tel_code)

    if is_quick:
        logger.info(f"⚡️ Телефония {tel_code} использует быстрые ошибки")

        user_id = query.from_user.id

        if db.is_sip_valid_today(user_id):
            sip_data = db.get_manager_sip(user_id)

            if sip_data and sip_data.get("sip_number"):
                sip = sip_data["sip_number"]
                logger.info(f"✅ SIP уже указан: {sip}")

                context.user_data["quick_error_sip"] = sip
                context.user_data["quick_error_tel_name"] = tel["name"]
                context.user_data["quick_error_tel_code"] = tel_code
                context.user_data["quick_error_group_id"] = tel["group_id"]

                await query.message.edit_text(
                    MESSAGES["choose_quick_error"].format(sip=sip),
                    reply_markup=get_quick_errors_keyboard(),
                )
                return

        logger.info("⚠️ SIP не указан, запрашиваем")

        context.user_data["quick_error_tel_name"] = tel["name"]
        context.user_data["quick_error_tel_code"] = tel_code
        context.user_data["quick_error_group_id"] = tel["group_id"]
        context.user_data["awaiting_sip_for_quick_error"] = True

        await query.message.edit_text(MESSAGES["sip_prompt"])
        return

    else:
        logger.info(f"📝 Телефония {tel_code} использует обычный ввод")

        set_tel_choice(context, tel["name"], tel_code)

        logger.info(
            f"✅ User {query.from_user.id} выбрал телефонию: {tel['name']} ({tel_code})"
        )

        await query.message.edit_text(
            f"✅ Вы выбрали: <b>{tel['name']}</b>\n\n"
            f"📝 Теперь отправьте описание ошибки\n"
            f"⏱ Выбор активен 10 минут.",
            parse_mode="HTML",
        )


async def handle_useful_links_button(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Обработчик кнопки "Полезные ссылки" """
    links_text = "🔗 <b>Полезные ссылки:</b>\n\n"
    for i, (name, url) in enumerate(USEFUL_LINKS.items(), 1):
        links_text += f"{i}. <a href='{url}'>{name}</a>\n"

    await update.message.reply_text(links_text, parse_mode="HTML")


async def handle_stats_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки "Статистика трубок" """
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


async def handle_managers_stats_button(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Обработчик кнопки "Статистика менеджеров" """
    try:
        from services.managers_stats_service import managers_stats_service

        stats_text = await managers_stats_service.get_managers_stats()
        await update.message.reply_text(stats_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики менеджеров: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ Ошибка при получении статистики менеджеров.\nПопробуйте позже."
        )


# ✅ НОВЫЙ ОБРАБОТЧИК: Статистика баз
async def handle_base_stats_button(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Обработчик кнопки "Статистика баз" — данные по поставщикам за сегодня"""
    from services.base_stats_service import base_stats_service

    loading_msg = None
    try:
        loading_msg = await update.message.reply_text("⏳ Загружаю данные...")
        stats_text = await base_stats_service.get_today_stats_text()

        if loading_msg:
            await loading_msg.edit_text(stats_text, parse_mode="HTML")
        else:
            await update.message.reply_text(stats_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики баз: {e}", exc_info=True)
        # Если loading_msg уже отправлен — редактируем его, иначе отправляем новое
        error_text = "⚠️ Ошибка при получении статистики баз.\nПопробуйте позже."
        try:
            if loading_msg:
                await loading_msg.edit_text(error_text)
            else:
                await update.message.reply_text(error_text)
        except Exception:
            await update.message.reply_text(error_text)


async def handle_bot_management_button(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Обработчик кнопки "Управление ботом" """
    keyboard = get_management_menu()

    await update.message.reply_text(
        "⚙️ <b>Управление ботом</b>\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def handle_errors_stats_button(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Обработчик кнопки 'Статистика ошибок'"""
    from services.analytics_service import analytics_service
    from handlers.analytics import get_dashboard_navigation

    stats_text = analytics_service.get_dashboard_overview("today")
    keyboard = get_dashboard_navigation(page=1, period="today")

    await update.message.reply_text(
        stats_text, parse_mode="HTML", reply_markup=keyboard
    )


async def handle_back_to_menu_button(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Обработчик кнопки "◀️ Меню" — возврат в главное меню"""
    clear_all_states(context)

    role = get_user_role(context)
    current_menu = get_menu_by_role(role)

    await update.message.reply_text(
        "📋 Главное меню\n\nВыберите действие:", reply_markup=current_menu
    )


async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главный обработчик кнопок меню"""
    text = update.message.text
    role = get_user_role(context)
    user_id = update.effective_user.id

    logger.debug(f"Кнопка '{text}' от user_id={user_id}, роль={role}")

    if not role:
        await update.message.reply_text(MESSAGES["session_expired"])
        return

    menu_actions = {
        "Ошибки телефонии": handle_telephony_errors_button,
        "Полезные ссылки": handle_useful_links_button,
        "Статистика трубок": handle_stats_button,
        "Статистика менеджеров": handle_managers_stats_button,
        "Статистика баз": handle_base_stats_button,          # ✅ новая кнопка
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
            MESSAGES["unknown_command"], reply_markup=current_menu
        )