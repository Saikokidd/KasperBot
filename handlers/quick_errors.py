"""
handlers/quick_errors.py - ИСПРАВЛЕННАЯ ВЕРСИЯ

ИЗМЕНЕНИЯ:
✅ Убрана создание ConversationHandler при импорте
✅ Добавлена функция get_quick_errors_conv() для динамического создания
✅ Улучшена обработка ошибок
✅ Добавлены подробные логи
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
from config.settings import settings
from utils.state import get_user_role
from utils.logger import logger
from typing import List

# Состояния разговора
WAITING_SIP, WAITING_CUSTOM_ERROR, SHOWING_ERRORS = range(3)


def get_quick_errors_telephony_names() -> List[str]:
    """
    Получить список телефоний с включёнными быстрыми ошибками
    
    Returns:
        Список названий телефоний (для entry_points)
    """
    try:
        telephonies = db.get_quick_errors_telephonies()
        names = [tel['name'] for tel in telephonies]
        
        if names:
            logger.info(f"✅ Быстрые ошибки доступны для: {', '.join(names)}")
        else:
            logger.warning("⚠️ Нет телефоний с включёнными быстрыми ошибками")
        
        return names
    except Exception as e:
        logger.error(f"❌ Ошибка получения телефоний для быстрых ошибок: {e}")
        return []


async def handle_quick_error_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик выбора телефонии с быстрыми ошибками
    
    Args:
        update: Update объект
        context: Контекст пользователя
    
    Returns:
        SHOWING_ERRORS если SIP указан, WAITING_SIP если нет
    """
    user_id = update.effective_user.id
    text = update.message.text
    
    logger.info(f"⚡️ Быстрая ошибка: user {user_id} выбрал '{text}'")
    
    # Получаем телефонию из БД
    telephonies = db.get_quick_errors_telephonies()
    tel_data = None
    
    for tel in telephonies:
        if tel['name'] == text:
            tel_data = tel
            break
    
    if not tel_data:
        logger.error(f"❌ Телефония '{text}' не найдена среди быстрых ошибок")
        return ConversationHandler.END
    
    # Сохраняем информацию о телефонии
    context.user_data['quick_error_tel_name'] = tel_data['name']
    context.user_data['quick_error_tel_code'] = tel_data['code']
    context.user_data['quick_error_group_id'] = tel_data['group_id']
    
    # Проверяем, указан ли SIP сегодня
    if db.is_sip_valid_today(user_id):
        sip_data = db.get_manager_sip(user_id)
        
        if not sip_data or not sip_data.get('sip_number'):
            logger.warning(f"⚠️ SIP данные повреждены для user_id={user_id}")
            await update.message.reply_text(MESSAGES["sip_prompt"])
            return WAITING_SIP
        
        sip = sip_data['sip_number']
        logger.info(f"✅ SIP уже указан: {sip}")
        
        context.user_data["quick_error_sip"] = sip
        
        await update.message.reply_text(
            MESSAGES["choose_quick_error"].format(sip=sip),
            reply_markup=get_quick_errors_keyboard()
        )
        return SHOWING_ERRORS
    else:
        logger.info(f"⚠️ SIP не указан, запрашиваем")
        await update.message.reply_text(MESSAGES["sip_prompt"])
        return WAITING_SIP


async def handle_sip_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода SIP номера"""
    user_id = update.effective_user.id
    sip_text = update.message.text.strip()
    
    logger.info(f"📞 Введён SIP от user_id={user_id}: {sip_text}")
    
    # Валидация формата SIP
    if not sip_text or len(sip_text) > MAX_SIP_LENGTH or not SIP_PATTERN.match(sip_text):
        logger.warning(f"⚠️ Неверный формат SIP: '{sip_text}'")
        await update.message.reply_text(MESSAGES["sip_invalid"])
        return WAITING_SIP
    
    # Сохраняем SIP
    db.save_manager_sip(user_id, sip_text)
    context.user_data["quick_error_sip"] = sip_text
    
    logger.info(f"✅ SIP сохранён: {sip_text}")
    
    # Показываем кнопки ошибок
    await update.message.reply_text(
        MESSAGES["sip_saved"].format(sip=sip_text),
        reply_markup=get_quick_errors_keyboard()
    )
    
    return SHOWING_ERRORS

async def handle_quick_error_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку быстрой ошибки"""
    query = update.callback_query
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Пользователь"
    
    logger.debug(f"🔘 Callback от user_id={user_id}: {query.data}")
    
    await query.answer()
    
    # Получаем код ошибки
    error_code = query.data.split("_")[1]
    
    logger.info(f"🔘 Нажата кнопка ошибки {error_code}")
    
    # Получаем SIP
    sip = context.user_data.get("quick_error_sip")
    
    if not sip:
        # Пытаемся восстановить из БД
        if db.is_sip_valid_today(user_id):
            sip_data = db.get_manager_sip(user_id)
            if sip_data and sip_data.get('sip_number'):
                sip = sip_data['sip_number']
                context.user_data["quick_error_sip"] = sip
                logger.info(f"✅ SIP восстановлен из БД: {sip}")
            else:
                logger.error(f"❌ SIP данные повреждены")
                await query.message.edit_text(
                    "⚠️ Ошибка: SIP не найден.\n"
                    "Попробуйте снова через меню 'Ошибки телефонии'"
                )
                return ConversationHandler.END
        else:
            logger.error(f"❌ SIP не найден")
            await query.message.edit_text(
                "⚠️ Ошибка: SIP не найден.\n"
                "Попробуйте снова через меню 'Ошибки телефонии'"
            )
            return ConversationHandler.END
    
    # Если "Свой вариант"
    if error_code == "10":
        logger.info(f"✏️ Выбран свой вариант")
        await query.message.edit_text(MESSAGES["custom_error_prompt"])
        return WAITING_CUSTOM_ERROR
    
    # Получаем текст ошибки
    error_text = QUICK_ERRORS.get(error_code, "Неизвестная ошибка")
    
    logger.info(f"📤 Отправка быстрой ошибки: {error_text}")
    
    # Получаем данные телефонии
    tel_code = context.user_data.get('quick_error_tel_code')
    tel_name = context.user_data.get('quick_error_tel_name')
    group_id = context.user_data.get('quick_error_group_id')
    
    if not all([tel_code, tel_name, group_id]):
        logger.error(f"❌ Данные телефонии не найдены в контексте")
        await query.message.edit_text("⚠️ Ошибка: данные телефонии потеряны")
        return ConversationHandler.END
    
    # Отправляем в группу
    success = await send_quick_error_to_group(
        context.bot, user_id, username, sip, error_text,
        tel_code, group_id
    )
    
    if not success:
        await query.message.edit_text("⚠️ Не удалось отправить ошибку")
        return ConversationHandler.END
    
    # Уведомляем пользователя
    await query.message.edit_text(
        f"✅ Ошибка отправлена в саппорт!\n\n"
        f"📞 {tel_name}\n"
        f"SIP: {sip}\n"
        f"Ошибка: {error_text}"
    )
    
    # Очищаем контекст
    context.user_data.pop("quick_error_sip", None)
    context.user_data.pop("quick_error_tel_code", None)
    context.user_data.pop("quick_error_tel_name", None)
    context.user_data.pop("quick_error_group_id", None)
    
    return ConversationHandler.END


async def handle_custom_error_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода своего варианта ошибки"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Пользователь"
    
    error_text = update.message.text.strip()
    sip = context.user_data.get("quick_error_sip")
    
    logger.info(f"✏️ Custom ошибка: {error_text[:50]}...")
    
    # Проверка SIP
    if not sip:
        logger.error(f"❌ SIP потерян из контекста")
        await update.message.reply_text("⚠️ Ошибка: SIP не найден")
        return ConversationHandler.END
    
    # Валидация
    if not error_text or len(error_text) > MAX_CUSTOM_ERROR_LENGTH:
        await update.message.reply_text(
            f"⚠️ Описание должно быть от 1 до {MAX_CUSTOM_ERROR_LENGTH} символов.\n"
            f"Сейчас: {len(error_text)} символов"
        )
        return WAITING_CUSTOM_ERROR
    
    # Получаем данные телефонии
    tel_code = context.user_data.get('quick_error_tel_code')
    tel_name = context.user_data.get('quick_error_tel_name')
    group_id = context.user_data.get('quick_error_group_id')
    
    if not all([tel_code, tel_name, group_id]):
        logger.error(f"❌ Данные телефонии не найдены")
        await update.message.reply_text("⚠️ Ошибка: данные телефонии потеряны")
        return ConversationHandler.END
    
    # Отправляем в группу
    success = await send_quick_error_to_group(
        context.bot, user_id, username, sip, error_text,
        tel_code, group_id
    )
    
    if not success:
        await update.message.reply_text("⚠️ Не удалось отправить ошибку")
        return ConversationHandler.END
    
    # Уведомляем пользователя
    role = get_user_role(context)
    current_menu = get_menu_by_role(role)
    
    await update.message.reply_text(
        f"✅ Ошибка отправлена в саппорт!\n\n"
        f"📞 {tel_name}\n"
        f"SIP: {sip}\n"
        f"Ошибка: {error_text}",
        reply_markup=current_menu
    )
    
    # Очищаем контекст
    context.user_data.pop("quick_error_sip", None)
    context.user_data.pop("quick_error_tel_code", None)
    context.user_data.pop("quick_error_tel_name", None)
    context.user_data.pop("quick_error_group_id", None)
    
    return ConversationHandler.END


async def handle_change_sip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Изменить SIP'"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    logger.info(f"⚙️ Запрос на изменение SIP от user_id={user_id}")
    
    await query.message.edit_text(MESSAGES["sip_prompt"])
    
    return WAITING_SIP


async def send_quick_error_to_group(
    bot, 
    user_id: int, 
    username: str, 
    sip: str, 
    error_text: str,
    tel_code: str,
    group_id: int
) -> bool:
    """Отправляет быструю ошибку в группу"""
    
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
        
        logger.info(f"✅ Быстрая ошибка отправлена: {tel_code}, SIP={sip}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки быстрой ошибки: {e}", exc_info=True)
        return False


def get_quick_errors_conv():
    """
    ✅ НОВОЕ: Создаёт ConversationHandler для быстрых ошибок ДИНАМИЧЕСКИ
    
    Вызывается из main.py при регистрации handlers
    
    Returns:
        ConversationHandler или None если нет телефоний
    """
    # Получаем список телефоний с быстрыми ошибками
    telephony_names = get_quick_errors_telephony_names()
    
    if not telephony_names:
        logger.warning("⚠️ Нет телефоний с быстрыми ошибками - ConversationHandler не создан")
        return None
    
    # Создаём фильтр для entry_points
    telephony_filter = filters.Regex(f"^({'|'.join(telephony_names)})$")
    
    logger.info(f"✅ Создание ConversationHandler для: {', '.join(telephony_names)}")
    
    conv = ConversationHandler(
        entry_points=[
            # Текстовое сообщение с названием телефонии
            MessageHandler(
                telephony_filter & filters.ChatType.PRIVATE, 
                handle_quick_error_choice
            ),
            # Кнопки быстрых ошибок работают ВСЕГДА
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


# ✅ ИСПРАВЛЕНО: Экспортируем функцию вместо объекта
quick_errors_conv = None  # Будет создан в main.py