"""
Обработчики управления ботом (для админов)
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from services.management_service import management_service
from services.user_service import user_service
from keyboards.inline import get_management_menu, get_telephony_type_keyboard
from utils.logger import logger


# Состояния для ConversationHandler
(WAITING_MANAGER_ID, WAITING_MANAGER_ID_REMOVE,
 WAITING_TEL_NAME, WAITING_TEL_CODE, WAITING_TEL_TYPE, WAITING_TEL_GROUP,
 WAITING_TEL_CODE_REMOVE, WAITING_BROADCAST_MESSAGE) = range(8)


# ===== ГЛАВНОЕ МЕНЮ УПРАВЛЕНИЯ =====

async def show_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления"""
    query = update.callback_query
    if query:
        await query.answer()
    
    keyboard = get_management_menu()
    text = (
        "⚙️ <b>Управление ботом</b>\n\n"
        "Выберите действие:"
    )
    
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
        "Отправьте ID пользователя (число) или перешлите любое сообщение от него.\n\n"
        "Отмена: /cancel",
        parse_mode="HTML"
    )
    
    return WAITING_MANAGER_ID


async def add_manager_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ID менеджера"""
    # Если переслали сообщение
    if update.message.forward_from:
        user_id = update.message.forward_from.id
        username = update.message.forward_from.username
        first_name = update.message.forward_from.first_name
    else:
        # Если просто написали ID
        try:
            user_id = int(update.message.text.strip())
            username = None
            first_name = None
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат! Отправьте число (ID пользователя) или перешлите сообщение от него."
            )
            return WAITING_MANAGER_ID
    
    # Добавляем
    success, message = management_service.add_manager(
        user_id, username, first_name, update.effective_user.id
    )
    
    await update.message.reply_text(message, parse_mode="HTML")
    
    # Возвращаем в меню
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« К управлению менеджерами", callback_data="mgmt_managers")]
    ])
    await update.message.reply_text("Готово!", reply_markup=keyboard)
    
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
    
    await update.message.reply_text(message, parse_mode="HTML")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« К управлению менеджерами", callback_data="mgmt_managers")]
    ])
    await update.message.reply_text("Готово!", reply_markup=keyboard)
    
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
    """Начало добавления телефонии - запрос названия"""
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
    """Обработка названия, запрос кода"""
    name = update.message.text.strip()
    context.user_data['tel_name'] = name
    
    await update.message.reply_text(
        f"✅ Название: <b>{name}</b>\n\n"
        f"Шаг 2/4: Введите код телефонии (латиница, lowercase)\n"
        f"(Например: bmw, megafon, beeline)\n"
        f"Код используется в callback и должен быть уникальным.",
        parse_mode="HTML"
    )
    
    return WAITING_TEL_CODE


async def add_telephony_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кода, запрос типа"""
    code = update.message.text.strip().lower()
    
    # Валидация кода
    if not code.isalnum():
        await update.message.reply_text(
            "❌ Код должен содержать только латинские буквы и цифры!\n"
            "Попробуйте снова:"
        )
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
    """Обработка типа, запрос ID группы"""
    query = update.callback_query
    await query.answer()
    
    tel_type = query.data.split("_")[2]  # tel_type_white или tel_type_black
    context.user_data['tel_type'] = tel_type
    
    type_name = "⚪️ Белая (с кнопками саппорта)" if tel_type == "white" else "⚫️ Чёрная (без кнопок)"
    
    await query.message.edit_text(
        f"✅ Тип: {type_name}\n\n"
        f"Шаг 4/4: Введите ID группы для отправки ошибок\n"
        f"(Должен начинаться с '-', например: -1001234567890)\n\n"
        f"<b>Как получить ID группы:</b>\n"
        f"1. Добавьте бота @userinfobot в группу\n"
        f"2. Скопируйте Chat ID\n"
        f"3. Отправьте сюда",
        parse_mode="HTML"
    )
    
    return WAITING_TEL_GROUP


async def add_telephony_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Финальный шаг - сохранение телефонии"""
    try:
        group_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Неверный формат! Должно быть число (например: -1001234567890)")
        return WAITING_TEL_GROUP
    
    # Получаем данные
    name = context.user_data.get('tel_name')
    code = context.user_data.get('tel_code')
    tel_type = context.user_data.get('tel_type')
    
    # Добавляем
    success, message = management_service.add_telephony(
        name, code, tel_type, group_id, update.effective_user.id
    )
    
    await update.message.reply_text(message, parse_mode="HTML")
    
    # Очищаем данные
    context.user_data.pop('tel_name', None)
    context.user_data.pop('tel_code', None)
    context.user_data.pop('tel_type', None)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« К управлению телефониями", callback_data="mgmt_telephonies")]
    ])
    await update.message.reply_text("Готово!", reply_markup=keyboard)
    
    return ConversationHandler.END


async def remove_telephony_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления телефонии"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "➖ <b>Удаление телефонии</b>\n\n"
        "Отправьте код телефонии для удаления.\n"
        "(Посмотреть коды: /cancel → Список телефоний)\n\n"
        "Отмена: /cancel",
        parse_mode="HTML"
    )
    
    return WAITING_TEL_CODE_REMOVE


async def remove_telephony_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка удаления телефонии"""
    code = update.message.text.strip().lower()
    
    success, message = management_service.remove_telephony(code)
    
    await update.message.reply_text(message, parse_mode="HTML")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« К управлению телефониями", callback_data="mgmt_telephonies")]
    ])
    await update.message.reply_text("Готово!", reply_markup=keyboard)
    
    return ConversationHandler.END


# ===== РАССЫЛКА =====

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало рассылки"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "📢 <b>Рассылка менеджерам</b>\n\n"
        "Отправьте сообщение для рассылки (текст, фото, документ и т.д.)\n"
        "Оно будет отправлено ВСЕМ менеджерам.\n\n"
        "Отмена: /cancel",
        parse_mode="HTML"
    )
    
    return WAITING_BROADCAST_MESSAGE


async def broadcast_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка и отправка рассылки"""
    # Подтверждение
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да, отправить", callback_data="broadcast_confirm"),
            InlineKeyboardButton("❌ Отмена", callback_data="mgmt_menu")
        ]
    ])
    
    # Сохраняем message_id для последующей копии
    context.user_data['broadcast_message_id'] = update.message.message_id
    context.user_data['broadcast_chat_id'] = update.message.chat_id
    
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
        return
    
    await query.message.edit_text("📤 Отправка рассылки...\nЭто может занять время.")
    
    # Получаем список менеджеров и отправляем напрямую
    try:
        from database.models import db
        managers = db.get_all_managers()
        
        stats = {
            "total": len(managers),
            "success": 0,
            "failed": 0,
            "failed_ids": []
        }
        
        # Отправляем каждому менеджеру
        for manager in managers:
            user_id = manager['user_id']
            
            try:
                # Копируем сообщение напрямую
                await context.bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=chat_id,
                    message_id=message_id
                )
                stats["success"] += 1
                logger.info(f"✅ Рассылка отправлена user_id={user_id}")
                
            except Exception as e:
                stats["failed"] += 1
                stats["failed_ids"].append(user_id)
                logger.error(f"❌ Не удалось отправить рассылку user_id={user_id}: {e}")
        
        logger.info(f"📊 Рассылка завершена: {stats['success']}/{stats['total']} успешно")
        
    except Exception as e:
        logger.error(f"❌ Ошибка рассылки: {e}", exc_info=True)
        await query.message.edit_text("❌ Ошибка при отправке рассылки")
        return
    
    result_text = (
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📊 Статистика:\n"
        f"• Всего менеджеров: {stats['total']}\n"
        f"• Успешно: {stats['success']}\n"
        f"• Ошибок: {stats['failed']}"
    )
    
    if stats['failed'] > 0:
        result_text += f"\n\n⚠️ Не удалось отправить: {len(stats['failed_ids'])} пользователям"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« Назад", callback_data="mgmt_menu")]
    ])
    
    await query.message.edit_text(result_text, parse_mode="HTML", reply_markup=keyboard)
    
    # Очищаем данные
    context.user_data.pop('broadcast_message_id', None)
    context.user_data.pop('broadcast_chat_id', None)


# ===== ОТМЕНА =====

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущей операции"""
    await update.message.reply_text(
        "❌ Операция отменена.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("« К управлению", callback_data="mgmt_menu")]
        ])
    )
    
    # Очищаем все временные данные
    context.user_data.pop('tel_name', None)
    context.user_data.pop('tel_code', None)
    context.user_data.pop('tel_type', None)
    context.user_data.pop('broadcast_message_id', None)
    context.user_data.pop('broadcast_chat_id', None)
    
    return ConversationHandler.END


# ===== УПРАВЛЕНИЕ БЫСТРЫМИ ОШИБКАМИ =====

async def quick_errors_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления быстрыми ошибками"""
    query = update.callback_query
    await query.answer()
    
    # Получаем все белые телефонии со статусом
    from database.models import db
    telephonies = db.get_white_telephonies_with_qe_status()
    
    if not telephonies:
        await query.message.edit_text(
            "⚠️ <b>Быстрые ошибки</b>\n\n"
            "Нет белых телефоний в системе.\n"
            "Добавьте белую телефонию чтобы использовать быстрые ошибки.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Назад", callback_data="mgmt_menu")]
            ])
        )
        return
    
    # Формируем клавиатуру
    from keyboards.inline import get_quick_errors_management_keyboard
    keyboard = get_quick_errors_management_keyboard(telephonies)
    
    # Подсчитываем статистику
    enabled_count = sum(1 for t in telephonies if t['quick_errors_enabled'])
    total_count = len(telephonies)
    
    text = (
        f"⚡️ <b>Управление быстрыми ошибками</b>\n\n"
        f"📊 Статус: {enabled_count}/{total_count} активно\n\n"
        f"Выберите телефонию для переключения:\n"
        f"✅ = Включены | ❌ = Выключены"
    )
    
    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def toggle_quick_errors_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключить быстрые ошибки для телефонии"""
    query = update.callback_query
    await query.answer("Переключаю...")
    
    # Извлекаем код телефонии из callback_data
    # Формат: toggle_qe_bmw
    tel_code = query.data.split("_")[2]
    
    logger.info(f"⚡️ Переключение быстрых ошибок для {tel_code}")
    
    # Переключаем в БД
    from database.models import db
    new_state = db.toggle_quick_errors(tel_code)
    
    if new_state is None:
        await query.answer("❌ Ошибка переключения", show_alert=True)
        return
    
    # Уведомляем пользователя
    status_text = "✅ Включены" if new_state else "❌ Выключены"
    await query.answer(f"⚡️ Быстрые ошибки: {status_text}", show_alert=True)
    
    # Обновляем меню
    await quick_errors_menu(update, context)
    
    # ВАЖНО: Перезагружаем ConversationHandler
    logger.info("🔄 Пересоздание ConversationHandler для быстрых ошибок...")
    
    try:
        # Удаляем старый handler
        from main import app  # Предполагаем что app доступен глобально
        
        # Находим handler по имени (если задавали name при add_handler)
        for handler in app.handlers[0]:  # Группа 0
            if hasattr(handler, 'name') and handler.name == 'quick_errors':
                app.remove_handler(handler)
                logger.info("✅ Старый handler удалён")
                break
        
        # Создаём новый
        from handlers.quick_errors import create_quick_errors_conv
        new_conv = create_quick_errors_conv()
        
        if new_conv:
            app.add_handler(new_conv, group=0)
            new_conv.name = 'quick_errors'  # Задаём имя для поиска
            logger.info("✅ Новый handler добавлен")
            
            # Логируем доступные телефонии
            from handlers.quick_errors import get_quick_errors_telephony_names
            names = get_quick_errors_telephony_names()
            logger.info(f"📞 Быстрые ошибки доступны для: {', '.join(names)}")
        else:
            logger.warning("⚠️ Нет активных телефоний для быстрых ошибок")
    
    except Exception as e:
        logger.error(f"❌ Ошибка перезагрузки handler: {e}")


async def show_quick_errors_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о системе быстрых ошибок"""
    query = update.callback_query
    await query.answer()
    
    from database.models import db
    telephonies = db.get_white_telephonies_with_qe_status()
    
    info_text = (
        "ℹ️ <b>О БЫСТРЫХ ОШИБКАХ</b>\n\n"
        "<b>Что это:</b>\n"
        "Система быстрых ошибок позволяет менеджерам отправлять стандартные ошибки "
        "через встроенное меню с кнопками, указав только свой SIP.\n\n"
        "<b>Как работает:</b>\n"
        "1️⃣ Менеджер нажимает на белую телефонию (например BMW)\n"
        "2️⃣ Указывает свой SIP один раз в день\n"
        "3️⃣ Выбирает тип ошибки из списка (10 вариантов)\n"
        "4️⃣ Ошибка автоматически отправляется в группу\n\n"
        "<b>Для каких телефоний доступно:</b>\n"
        "Только для белых телефоний (с кнопками саппорта).\n\n"
    )
    
    if telephonies:
        info_text += "<b>Ваши белые телефонии:</b>\n"
        for tel in telephonies:
            status = "✅ Включены" if tel['quick_errors_enabled'] else "❌ Выключены"
            info_text += f"• {tel['name']}: {status}\n"
    else:
        info_text += "⚠️ Нет белых телефоний в системе."
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« Назад", callback_data="mgmt_quick_errors")]
    ])
    
    await query.message.edit_text(
        info_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )