"""
handlers/quick_errors.py - ФИНАЛЬНОЕ РЕШЕНИЕ
Единый ConversationHandler обрабатывает ВСЁ

РЕШЕНИЕ ПРОБЛЕМЫ:
✅ entry_points слушает текст телефоний (BMW, Звонари и т.д.)
✅ НЕ конфликтует с messages.py (разные группы handlers)
✅ Автоматически запускается при выборе телефонии с quick_errors
"""
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, 
    MessageHandler, CallbackQueryHandler, filters
)
from database.models import db
from keyboards.inline import get_quick_errors_keyboard
from keyboards.reply import get_menu_by_role
from config.constants import MESSAGES, QUICK_ERRORS, MAX_SIP_LENGTH, MAX_CUSTOM_ERROR_LENGTH, SIP_PATTERN
from utils.state import get_user_role
from utils.logger import logger
from typing import List

# Состояния
WAITING_SIP, WAITING_CUSTOM_ERROR, SHOWING_ERRORS = range(3)


def get_quick_errors_telephony_names() -> List[str]:
    """Получить телефонии с быстрыми ошибками"""
    try:
        telephonies = db.get_quick_errors_telephonies()
        names = [tel['name'] for tel in telephonies]
        
        if names:
            logger.info(f"✅ Быстрые ошибки: {', '.join(names)}")
        else:
            logger.warning("⚠️ Нет телефоний с быстрыми ошибками")
        
        return names
    except Exception as e:
        logger.error(f"❌ Ошибка получения телефоний: {e}")
        return []


async def handle_quick_error_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ✅ ФИНАЛЬНОЕ РЕШЕНИЕ: Entry point - выбор телефонии
    
    Вызывается НАПРЯМУЮ когда user пишет название телефонии
    """
    user_id = update.effective_user.id
    text = update.message.text
    
    logger.info(f"⚡️ Quick error: user {user_id} выбрал '{text}'")
    
    # Получаем телефонию из БД
    telephonies = db.get_quick_errors_telephonies()
    tel_data = None
    
    for tel in telephonies:
        if tel['name'] == text:
            tel_data = tel
            break
    
    if not tel_data:
        logger.error(f"❌ Телефония '{text}' не найдена")
        return ConversationHandler.END
    
    # Сохраняем данные телефонии
    context.user_data['quick_error_tel_name'] = tel_data['name']
    context.user_data['quick_error_tel_code'] = tel_data['code']
    context.user_data['quick_error_group_id'] = tel_data['group_id']
    
    logger.info(f"✅ Сохранены данные телефонии: {tel_data['name']}")
    
    # Проверяем SIP
    if db.is_sip_valid_today(user_id):
        sip_data = db.get_manager_sip(user_id)
        
        if sip_data and sip_data.get('sip_number'):
            sip = sip_data['sip_number']
            logger.info(f"✅ SIP уже указан: {sip}")
            
            context.user_data["quick_error_sip"] = sip
            
            await update.message.reply_text(
                MESSAGES["choose_quick_error"].format(sip=sip),
                reply_markup=get_quick_errors_keyboard()
            )
            return SHOWING_ERRORS
    
    # SIP не указан - запрашиваем
    logger.info(f"⚠️ SIP не указан, запрашиваем")
    await update.message.reply_text(MESSAGES["sip_prompt"])
    return WAITING_SIP


async def handle_sip_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода SIP"""
    user_id = update.effective_user.id
    sip_text = update.message.text.strip()
    
    logger.info(f"📞 Введён SIP: {sip_text}")
    
    # Валидация
    if not sip_text or len(sip_text) > MAX_SIP_LENGTH or not SIP_PATTERN.match(sip_text):
        logger.warning(f"⚠️ Неверный SIP: '{sip_text}'")
        await update.message.reply_text(MESSAGES["sip_invalid"])
        return WAITING_SIP
    
    # Сохраняем
    db.save_manager_sip(user_id, sip_text)
    context.user_data["quick_error_sip"] = sip_text
    
    logger.info(f"✅ SIP сохранён: {sip_text}")
    
    # Показываем кнопки
    await update.message.reply_text(
        MESSAGES["sip_saved"].format(sip=sip_text),
        reply_markup=get_quick_errors_keyboard()
    )
    
    return SHOWING_ERRORS


async def handle_quick_error_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия кнопки ошибки"""
    query = update.callback_query
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Пользователь"
    
    await query.answer()
    
    error_code = query.data.split("_")[1]
    logger.info(f"🔘 Кнопка ошибки {error_code}")
    
    # Получаем SIP
    sip = context.user_data.get("quick_error_sip")
    
    if not sip:
        # Восстанавливаем из БД
        if db.is_sip_valid_today(user_id):
            sip_data = db.get_manager_sip(user_id)
            if sip_data:
                sip = sip_data['sip_number']
                context.user_data["quick_error_sip"] = sip
        
        if not sip:
            await query.message.edit_text("⚠️ SIP не найден")
            return ConversationHandler.END
    
    # Свой вариант
    if error_code == "10":
        await query.message.edit_text(MESSAGES["custom_error_prompt"])
        return WAITING_CUSTOM_ERROR
    
    # Стандартная ошибка
    error_text = QUICK_ERRORS.get(error_code, "Неизвестная ошибка")
    
    # Получаем данные телефонии
    tel_code = context.user_data.get('quick_error_tel_code')
    tel_name = context.user_data.get('quick_error_tel_name')
    group_id = context.user_data.get('quick_error_group_id')
    
    if not all([tel_code, tel_name, group_id]):
        await query.message.edit_text("⚠️ Данные телефонии потеряны")
        return ConversationHandler.END
    
    # Отправляем
    success = await send_quick_error_to_group(
        context.bot, user_id, username, sip, error_text,
        tel_code, group_id
    )
    
    if not success:
        await query.message.edit_text("⚠️ Не удалось отправить")
        return ConversationHandler.END
    
    await query.message.edit_text(
        f"✅ Ошибка отправлена!\n\n"
        f"📞 {tel_name}\n"
        f"SIP: {sip}\n"
        f"Ошибка: {error_text}"
    )
    
    # Очищаем
    context.user_data.pop("quick_error_sip", None)
    context.user_data.pop("quick_error_tel_code", None)
    context.user_data.pop("quick_error_tel_name", None)
    context.user_data.pop("quick_error_group_id", None)
    
    return ConversationHandler.END


async def handle_custom_error_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка своего варианта ошибки"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Пользователь"
    error_text = update.message.text.strip()
    sip = context.user_data.get("quick_error_sip")
    
    if not sip:
        await update.message.reply_text("⚠️ SIP не найден")
        return ConversationHandler.END
    
    # Валидация
    if not error_text or len(error_text) > MAX_CUSTOM_ERROR_LENGTH:
        await update.message.reply_text(
            f"⚠️ Длина: 1-{MAX_CUSTOM_ERROR_LENGTH} символов (сейчас: {len(error_text)})"
        )
        return WAITING_CUSTOM_ERROR
    
    # Получаем данные телефонии
    tel_code = context.user_data.get('quick_error_tel_code')
    tel_name = context.user_data.get('quick_error_tel_name')
    group_id = context.user_data.get('quick_error_group_id')
    
    if not all([tel_code, tel_name, group_id]):
        await update.message.reply_text("⚠️ Данные телефонии потеряны")
        return ConversationHandler.END
    
    # Отправляем
    success = await send_quick_error_to_group(
        context.bot, user_id, username, sip, error_text,
        tel_code, group_id
    )
    
    if not success:
        await update.message.reply_text("⚠️ Не удалось отправить")
        return ConversationHandler.END
    
    role = get_user_role(context)
    current_menu = get_menu_by_role(role)
    
    await update.message.reply_text(
        f"✅ Ошибка отправлена!\n\n"
        f"📞 {tel_name}\n"
        f"SIP: {sip}\n"
        f"Ошибка: {error_text}",
        reply_markup=current_menu
    )
    
    # Очищаем
    context.user_data.pop("quick_error_sip", None)
    context.user_data.pop("quick_error_tel_code", None)
    context.user_data.pop("quick_error_tel_name", None)
    context.user_data.pop("quick_error_group_id", None)
    
    return ConversationHandler.END


async def handle_change_sip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопки 'Изменить SIP'"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(MESSAGES["sip_prompt"])
    return WAITING_SIP


async def send_quick_error_to_group(
    bot, user_id: int, username: str, sip: str, 
    error_text: str, tel_code: str, group_id: int
) -> bool:
    """Отправка ошибки в группу"""
    msg = f"От {username}\nSIP: {sip}  {error_text}"
    
    from keyboards.inline import get_support_keyboard
    keyboard = get_support_keyboard(user_id, tel_code)
    
    try:
        await bot.send_message(
            chat_id=group_id,
            text=msg,
            reply_markup=keyboard
        )
        
        db.log_error_report(user_id, username, tel_code, f"SIP: {sip} - {error_text}")
        logger.info(f"✅ Быстрая ошибка отправлена: {tel_code}, SIP={sip}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}")
        return False


def get_quick_errors_conv():
    """
    ✅ ФИНАЛЬНОЕ РЕШЕНИЕ: ConversationHandler с текстовыми entry_points
    
    РЕГИСТРАЦИЯ В main.py:
    app.add_handler(quick_errors_conv, group=0)  # ДО message_handler!
    """
    telephony_names = get_quick_errors_telephony_names()
    
    if not telephony_names:
        logger.warning("⚠️ Нет телефоний с быстрыми ошибками")
        return None
    
    # Фильтр для entry_points
    telephony_filter = filters.Regex(f"^({'|'.join(telephony_names)})$")
    
    logger.info(f"✅ ConversationHandler для: {', '.join(telephony_names)}")
    
    conv = ConversationHandler(
        entry_points=[
            # ✅ Слушаем текст телефоний (BMW, Звонари и т.д.)
            MessageHandler(
                telephony_filter & filters.ChatType.PRIVATE, 
                handle_quick_error_choice
            ),
            # Callback кнопки работают всегда
            CallbackQueryHandler(handle_quick_error_callback, pattern="^qerr_"),
            CallbackQueryHandler(handle_change_sip_callback, pattern="^change_sip$"),
        ],
        states={
            WAITING_SIP: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, 
                    handle_sip_input
                ),
            ],
            SHOWING_ERRORS: [
                CallbackQueryHandler(handle_quick_error_callback, pattern="^qerr_"),
                CallbackQueryHandler(handle_change_sip_callback, pattern="^change_sip$"),
            ],
            WAITING_CUSTOM_ERROR: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, 
                    handle_custom_error_input
                )
            ]
        },
        fallbacks=[],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        name='quick_errors'
    )
    
    return conv


quick_errors_conv = None