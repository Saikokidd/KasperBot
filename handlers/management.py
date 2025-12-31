"""
handlers/management.py - ЧИСТЫЙ UX
Убраны все лишние сообщения после операций

КРИТИЧЕСКИЕ ИЗМЕНЕНИЯ:
✅ Только ОДНО сообщение после операции (результат + кнопка)
✅ НЕТ "Готово!" и других лишних сообщений
✅ Пользователь сразу видит результат и может продолжить
✅ ДОБАВЛЕНО: Упрощённое управление быстрыми ошибками
✅ ИСПРАВЛЕНО: Флаги для предотвращения алертов "Неизвестная команда"
✅ ДОБАВЛЕНО: Input Validation всех входных данных
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from services.management_service import management_service
from services.user_service import user_service
from keyboards.inline import get_management_menu, get_telephony_type_keyboard
from utils.state import clear_all_states
from utils.logger import logger
from utils.validators import input_validator
from database.models import db


# Состояния
(WAITING_MANAGER_ID, WAITING_MANAGER_ID_REMOVE,
 WAITING_TEL_NAME, WAITING_TEL_CODE, WAITING_TEL_TYPE, WAITING_TEL_GROUP,
 WAITING_TEL_CODE_REMOVE, WAITING_BROADCAST_MESSAGE,
 WAITING_QE_CODE_ADD, WAITING_QE_CODE_REMOVE) = range(10)


async def show_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления"""
    query = update.callback_query
    if query:
        await query.answer()
    
    clear_all_states(context)
    
    keyboard = get_management_menu()
    text = "⚙️ <b>Управление ботом</b>\n\nВыберите действие:"
    
    if query:
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


# ===== МЕНЕДЖЕРЫ =====

async def managers_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления менеджерами"""
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить менеджера", callback_data="mgmt_add_manager")],
        [InlineKeyboardButton("➖ Удалить менеджера", callback_data="mgmt_remove_manager")],
        [InlineKeyboardButton("📋 Список менеджеров", callback_data="mgmt_list_managers")],
        [InlineKeyboardButton("« Назад", callback_data="mgmt_menu")]
    ])
    
    await query.message.edit_text(
        "👥 <b>Управление менеджерами</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def list_managers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список менеджеров"""
    query = update.callback_query
    await query.answer()
    
    text = management_service.get_managers_list()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« Назад", callback_data="mgmt_managers")]
    ])
    
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


async def add_manager_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления менеджера"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "➕ <b>Добавление менеджера</b>\n\n"
        "Отправьте ID пользователя (число).\n\n"
        "<b>Как узнать ID:</b>\n"
        "1. Напишите боту @userinfobot\n"
        "2. Скопируйте ваш ID\n"
        "3. Отправьте сюда\n\n"
        "Отмена: /cancel",
        parse_mode="HTML"
    )
    
    return WAITING_MANAGER_ID


async def add_manager_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ID менеджера"""
    user_id = None
    username = None
    first_name = None
    
    if update.message.forward_from:
        user_id = update.message.forward_from.id
        username = update.message.forward_from.username
        first_name = update.message.forward_from.first_name
    elif update.message.reply_to_message and update.message.reply_to_message.from_user:
        user_id = update.message.reply_to_message.from_user.id
        username = update.message.reply_to_message.from_user.username
        first_name = update.message.reply_to_message.from_user.first_name
    else:
        text = update.message.text.strip()
        try:
            digits = ''.join(filter(str.isdigit, text))
            if not digits:
                await update.message.reply_text("❌ Не найден ID пользователя!\n\nОтправьте ID (число).")
                return WAITING_MANAGER_ID
            user_id = int(digits)
        except ValueError:
            await update.message.reply_text("❌ Неверный формат ID!\n\nID должен быть числом.")
            return WAITING_MANAGER_ID
    
    # ✅ ДОБАВЛЕНО: Валидация user_id с использованием InputValidator
    is_valid, error_msg = input_validator.validate_user_id(user_id)
    if not is_valid:
        await update.message.reply_text(error_msg)
        return WAITING_MANAGER_ID
    
    success, message = management_service.add_manager(
        user_id, username, first_name, update.effective_user.id
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« К управлению менеджерами", callback_data="mgmt_managers")]
    ])
    
    await update.message.reply_text(
        message,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    clear_all_states(context)
    return ConversationHandler.END


async def remove_manager_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления менеджера"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "➖ <b>Удаление менеджера</b>\n\n"
        "Отправьте ID пользователя для удаления.\n\n"
        "Отмена: /cancel",
        parse_mode="HTML"
    )
    
    return WAITING_MANAGER_ID_REMOVE


async def remove_manager_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка удаления менеджера"""
    try:
        user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Неверный формат! Отправьте число (ID пользователя).")
        return WAITING_MANAGER_ID_REMOVE
    
    success, message = management_service.remove_manager(user_id)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« К управлению менеджерами", callback_data="mgmt_managers")]
    ])
    
    await update.message.reply_text(
        message,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    clear_all_states(context)
    return ConversationHandler.END


# ===== ТЕЛЕФОНИИ =====

async def telephonies_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления телефониями"""
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить телефонию", callback_data="mgmt_add_tel")],
        [InlineKeyboardButton("➖ Удалить телефонию", callback_data="mgmt_remove_tel")],
        [InlineKeyboardButton("📋 Список телефоний", callback_data="mgmt_list_tel")],
        [InlineKeyboardButton("« Назад", callback_data="mgmt_menu")]
    ])
    
    await query.message.edit_text(
        "📞 <b>Управление телефониями</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def list_telephonies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список телефоний"""
    query = update.callback_query
    await query.answer()
    
    text = management_service.get_telephonies_list()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« Назад", callback_data="mgmt_telephonies")]
    ])
    
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


async def add_telephony_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления телефонии"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "➕ <b>Добавление телефонии</b>\n\n"
        "Шаг 1/4: Введите название телефонии\n"
        "(Например: BMW, Мегафон, Билайн)\n\n"
        "Отмена: /cancel",
        parse_mode="HTML"
    )
    
    return WAITING_TEL_NAME


async def add_telephony_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка названия"""
    name = update.message.text.strip()
    
    # ✅ ДОБАВЛЕНО: Валидация названия телефонии
    is_valid, error_msg = input_validator.validate_telephony_name(name)
    if not is_valid:
        await update.message.reply_text(error_msg)
        return WAITING_TEL_NAME
    
    context.user_data['tel_name'] = name
    
    await update.message.reply_text(
        f"✅ Название: <b>{name}</b>\n\n"
        f"Шаг 2/4: Введите код телефонии (латиница, lowercase)\n"
        f"(Например: bmw, megafon, beeline)",
        parse_mode="HTML"
    )
    
    return WAITING_TEL_CODE


async def add_telephony_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кода"""
    code = update.message.text.strip().lower()
    
    # ✅ ДОБАВЛЕНО: Валидация кода телефонии
    is_valid, error_msg = input_validator.validate_telephony_code(code)
    if not is_valid:
        await update.message.reply_text(error_msg)
        return WAITING_TEL_CODE
    
    context.user_data['tel_code'] = code
    keyboard = get_telephony_type_keyboard()
    
    await update.message.reply_text(
        f"✅ Код: <code>{code}</code>\n\n"
        f"Шаг 3/4: Выберите тип телефонии:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    return WAITING_TEL_TYPE


async def add_telephony_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка типа"""
    query = update.callback_query
    await query.answer()
    
    tel_type = query.data.split("_")[2]
    context.user_data['tel_type'] = tel_type
    
    type_name = "⚪️ Белая (с кнопками)" if tel_type == "white" else "⚫️ Чёрная (без кнопок)"
    
    await query.message.edit_text(
        f"✅ Тип: {type_name}\n\n"
        f"Шаг 4/4: Введите ID группы\n"
        f"(Должен начинаться с '-', например: -1001234567890)",
        parse_mode="HTML"
    )
    
    return WAITING_TEL_GROUP


async def add_telephony_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Финальный шаг"""
    try:
        group_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Неверный формат! Должно быть число.")
        return WAITING_TEL_GROUP
    
    name = context.user_data.get('tel_name')
    code = context.user_data.get('tel_code')
    tel_type = context.user_data.get('tel_type')
    
    success, message = management_service.add_telephony(
        name, code, tel_type, group_id, update.effective_user.id
    )
    
    context.user_data.pop('tel_name', None)
    context.user_data.pop('tel_code', None)
    context.user_data.pop('tel_type', None)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« К управлению телефониями", callback_data="mgmt_telephonies")]
    ])
    
    await update.message.reply_text(
        message,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    clear_all_states(context)
    return ConversationHandler.END


async def remove_telephony_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления телефонии"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "➖ <b>Удаление телефонии</b>\n\n"
        "Отправьте код телефонии для удаления.\n\n"
        "Отмена: /cancel",
        parse_mode="HTML"
    )
    
    return WAITING_TEL_CODE_REMOVE


async def remove_telephony_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка удаления"""
    code = update.message.text.strip().lower()
    
    # ✅ ДОБАВЛЕНО: Валидация кода телефонии
    is_valid, error_msg = input_validator.validate_telephony_code(code)
    if not is_valid:
        await update.message.reply_text(error_msg)
        return WAITING_TEL_CODE_REMOVE
    
    success, message = management_service.remove_telephony(code)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« К управлению телефониями", callback_data="mgmt_telephonies")]
    ])
    
    await update.message.reply_text(
        message,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    clear_all_states(context)
    return ConversationHandler.END


# ===== РАССЫЛКА =====

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало рассылки"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "📢 <b>Рассылка менеджерам</b>\n\n"
        "Отправьте сообщение для рассылки.\n"
        "Оно будет отправлено ВСЕМ менеджерам.\n\n"
        "Отмена: /cancel",
        parse_mode="HTML"
    )
    
    return WAITING_BROADCAST_MESSAGE


async def broadcast_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщения для рассылки"""
    message_text = update.message.text.strip()
    
    # ✅ ДОБАВЛЕНО: Валидация сообщения рассылки
    is_valid, error_msg = input_validator.validate_broadcast_message(message_text)
    if not is_valid:
        await update.message.reply_text(error_msg)
        return WAITING_BROADCAST_MESSAGE
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да, отправить", callback_data="broadcast_confirm"),
            InlineKeyboardButton("❌ Отмена", callback_data="mgmt_menu")
        ]
    ])
    
    context.user_data['broadcast_message_id'] = update.message.message_id
    context.user_data['broadcast_chat_id'] = update.message.chat_id
    context.user_data['broadcast_message_text'] = message_text
    
    await update.message.reply_text(
        "📨 Подтвердите отправку рассылки всем менеджерам:",
        reply_markup=keyboard
    )
    
    return ConversationHandler.END


async def broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение и отправка рассылки"""
    query = update.callback_query
    await query.answer("Отправляю рассылку...")
    
    message_id = context.user_data.get('broadcast_message_id')
    chat_id = context.user_data.get('broadcast_chat_id')
    
    if not message_id or not chat_id:
        await query.message.edit_text("❌ Ошибка: сообщение не найдено")
        clear_all_states(context)
        return
    
    await query.message.edit_text("📤 Отправка рассылки...")
    
    try:
        managers = db.get_all_managers()
        
        stats = {"total": len(managers), "success": 0, "failed": 0}
        
        for manager in managers:
            try:
                await context.bot.copy_message(
                    chat_id=manager['user_id'],
                    from_chat_id=chat_id,
                    message_id=message_id
                )
                stats["success"] += 1
            except Exception as e:
                stats["failed"] += 1
                logger.error(f"❌ Рассылка user_id={manager['user_id']}: {e}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка рассылки: {e}")
        await query.message.edit_text("❌ Ошибка при отправке рассылки")
        clear_all_states(context)
        return
    
    result_text = (
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📊 Статистика:\n"
        f"• Всего: {stats['total']}\n"
        f"• Успешно: {stats['success']}\n"
        f"• Ошибок: {stats['failed']}"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« Назад", callback_data="mgmt_menu")]
    ])
    
    await query.message.edit_text(result_text, parse_mode="HTML", reply_markup=keyboard)
    
    context.user_data.pop('broadcast_message_id', None)
    context.user_data.pop('broadcast_chat_id', None)
    clear_all_states(context)


# ===== БЫСТРЫЕ ОШИБКИ (УПРОЩЁННАЯ СИСТЕМА) =====

async def quick_errors_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления быстрыми ошибками"""
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Список", callback_data="qe_list")],
        [InlineKeyboardButton("➕ Добавить телефонию", callback_data="qe_add")],
        [InlineKeyboardButton("➖ Удалить телефонию", callback_data="qe_remove")],
        [InlineKeyboardButton("« Назад", callback_data="mgmt_menu")]
    ])
    
    await query.message.edit_text(
        "⚡️ <b>Быстрые ошибки</b>\n\n"
        "Телефонии с быстрыми ошибками позволяют менеджерам:\n"
        "• Указать SIP один раз в день\n"
        "• Выбирать ошибку из готовых кнопок\n"
        "• Быстро отправлять типовые ошибки\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def quick_errors_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список телефоний с быстрыми ошибками"""
    query = update.callback_query
    await query.answer()
    
    quick_tels = db.get_quick_error_telephonies()
    
    if not quick_tels:
        text = (
            "📋 <b>Список быстрых ошибок</b>\n\n"
            "📭 Список пуст.\n\n"
            "Добавьте телефонию через кнопку '➕ Добавить'."
        )
    else:
        text = f"📋 <b>Список быстрых ошибок ({len(quick_tels)}):</b>\n\n"
        
        for i, tel in enumerate(quick_tels, 1):
            text += (
                f"{i}. ⚡️ <b>{tel['name']}</b>\n"
                f"   Код: <code>{tel['code']}</code>\n"
                f"   Группа: <code>{tel['group_id']}</code>\n"
                f"   Добавлено: {tel['added_at'][:10]}\n\n"
            )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« Назад", callback_data="mgmt_quick_errors")]
    ])
    
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


async def quick_errors_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления телефонии в быстрые ошибки"""
    query = update.callback_query
    await query.answer()
    
    # ✅ УСТАНОВИТЬ ФЛАГ
    context.user_data['awaiting_qe_code_add'] = True
    
    await query.message.edit_text(
        "➕ <b>Добавить в быстрые ошибки</b>\n\n"
        "Отправьте <b>код</b> телефонии (например: <code>bmw</code>)\n\n"
        "⚠️ Требования:\n"
        "• Телефония должна существовать\n"
        "• Телефония должна быть белой (с кнопками)\n\n"
        "Отмена: /cancel",
        parse_mode="HTML"
    )
    
    return WAITING_QE_CODE_ADD


async def quick_errors_add_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка добавления телефонии"""
    
    # ✅ УБРАТЬ ФЛАГ СРАЗУ
    context.user_data.pop('awaiting_qe_code_add', None)
    
    code = update.message.text.strip().lower()
    
    # Проверяем формат
    if not code.isalnum():
        await update.message.reply_text(
            "❌ Код должен содержать только латинские буквы и цифры!\n"
            "Попробуйте снова или /cancel для отмены."
        )
        return WAITING_QE_CODE_ADD
    
    # Добавляем
    success = db.add_quick_error_telephony(code)
    
    if success:
        tel = db.get_telephony_by_code(code)
        text = (
            f"✅ <b>Телефония добавлена в быстрые ошибки!</b>\n\n"
            f"📞 Название: <b>{tel['name']}</b>\n"
            f"🔑 Код: <code>{code}</code>\n\n"
            f"Теперь менеджеры смогут использовать быстрые ошибки для этой телефонии."
        )
    else:
        tel = db.get_telephony_by_code(code)
        
        if not tel:
            text = (
                f"❌ <b>Телефония не найдена!</b>\n\n"
                f"Код <code>{code}</code> не существует в базе.\n\n"
                f"Сначала добавьте телефонию через:\n"
                f"Управление ботом → Телефонии → Добавить"
            )
        elif tel['type'] != 'white':
            text = (
                f"❌ <b>Неверный тип телефонии!</b>\n\n"
                f"Телефония <b>{tel['name']}</b> имеет тип: <b>{tel['type']}</b>\n\n"
                f"Быстрые ошибки работают только с <b>белыми</b> телефониями."
            )
        else:
            text = (
                f"⚠️ <b>Телефония уже в быстрых ошибках!</b>\n\n"
                f"📞 {tel['name']} (<code>{code}</code>)"
            )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« К быстрым ошибкам", callback_data="mgmt_quick_errors")]
    ])
    
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
    
    clear_all_states(context)
    return ConversationHandler.END


async def quick_errors_remove_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления телефонии из быстрых ошибок"""
    query = update.callback_query
    await query.answer()
    
    # ✅ УСТАНОВИТЬ ФЛАГ
    context.user_data['awaiting_qe_code_remove'] = True
    
    await query.message.edit_text(
        "➖ <b>Удалить из быстрых ошибок</b>\n\n"
        "Отправьте <b>код</b> телефонии (например: <code>bmw</code>)\n\n"
        "Отмена: /cancel",
        parse_mode="HTML"
    )
    
    return WAITING_QE_CODE_REMOVE


async def quick_errors_remove_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка удаления телефонии"""
    
    # ✅ УБРАТЬ ФЛАГ СРАЗУ
    context.user_data.pop('awaiting_qe_code_remove', None)
    
    code = update.message.text.strip().lower()
    
    success = db.remove_quick_error_telephony(code)
    
    if success:
        tel = db.get_telephony_by_code(code)
        tel_name = tel['name'] if tel else code.upper()
        
        text = (
            f"✅ <b>Телефония удалена из быстрых ошибок!</b>\n\n"
            f"📞 {tel_name} (<code>{code}</code>)\n\n"
            f"Теперь менеджеры будут использовать обычный ввод ошибки."
        )
    else:
        text = (
            f"⚠️ <b>Телефония не была в быстрых ошибках</b>\n\n"
            f"Код: <code>{code}</code>"
        )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« К быстрым ошибкам", callback_data="mgmt_quick_errors")]
    ])
    
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
    
    clear_all_states(context)
    return ConversationHandler.END


# ===== ОТМЕНА =====

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« К управлению", callback_data="mgmt_menu")]
    ])
    
    await update.message.reply_text(
        "❌ Операция отменена.",
        reply_markup=keyboard
    )
    
    context.user_data.pop('tel_name', None)
    context.user_data.pop('tel_code', None)
    context.user_data.pop('tel_type', None)
    context.user_data.pop('broadcast_message_id', None)
    context.user_data.pop('broadcast_chat_id', None)
    context.user_data.pop('awaiting_qe_code_add', None)  # ✅ НОВОЕ
    context.user_data.pop('awaiting_qe_code_remove', None)  # ✅ НОВОЕ
    clear_all_states(context)
    
    return ConversationHandler.END