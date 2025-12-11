"""
handlers/messages.py - ПОЛНАЯ ВЕРСИЯ С ДИНАМИЧЕСКОЙ ПРОВЕРКОЙ
Проверяет БД при КАЖДОМ выборе телефонии

КРИТИЧЕСКОЕ ИЗМЕНЕНИЕ:
✅ handle_telephony_choice() проверяет quick_errors_enabled НАПРЯМУЮ из БД
✅ Если включены - НЕ обрабатывает (пропускает для quick_errors.py)
✅ Если выключены - обрабатывает как обычную телефонию
"""
from telegram import Update, error as telegram_error
from telegram.ext import ContextTypes

from config.settings import settings
from config.constants import MESSAGES
from services.user_service import user_service
from services.telephony_service import telephony_service
from keyboards.reply import get_menu_by_role
from utils.state import (
    get_user_role, is_support_mode, set_support_mode,
    get_tel_choice, clear_tel_choice, is_tel_choice_expired,
    set_tel_choice
)
from utils.logger import logger
from handlers.menu import handle_menu_button


async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Обрабатывает сообщения в режиме поддержки"""
    if not is_support_mode(context):
        return False
    
    support_msg = (
        f"💬 <b>Вопрос в поддержку</b>\n\n"
        f"👤 От: {update.effective_user.first_name}\n"
        f"🆔 ID: {update.effective_user.id}\n"
        f"{'─' * 30}\n"
        f"📝 Вопрос:\n{update.message.text}"
    )
    
    try:
        for admin_id in settings.ADMINS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=support_msg,
                    parse_mode="HTML"
                )
            except telegram_error.TelegramError as e:
                logger.error(f"⚠️ Не удалось отправить админу {admin_id}: {e}")
        
        role = get_user_role(context)
        current_menu = get_menu_by_role(role)
        
        await update.message.reply_text(
            MESSAGES["support_sent"],
            reply_markup=current_menu
        )
        logger.info(f"✅ Вопрос в поддержку от user_id={update.effective_user.id}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки в поддержку: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ Не удалось отправить вопрос.\nПопробуйте позже."
        )
    
    set_support_mode(context, False)
    return True


async def handle_telephony_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Обрабатывает выбор телефонии из Reply кнопок (BMW, Звонари, Аврора, Berlin)
    
    ✅ КРИТИЧЕСКОЕ ИЗМЕНЕНИЕ: Проверяет БД динамически
    
    Args:
        update: Update объект
        context: Контекст пользователя
        
    Returns:
        True если обработано как выбор телефонии
    """
    text = update.message.text
    
    # Получаем все телефонии из БД
    from database.models import db
    telephonies = db.get_all_telephonies()
    
    # Создаём словарь название → телефония
    tel_map = {}
    if telephonies:
        for tel in telephonies:
            tel_map[tel['name']] = tel
    else:
        # Фолбэк на старые (если БД пустая)
        tel_map = {
            "BMW": {"name": "BMW", "code": "bmw", "quick_errors_enabled": False},
            "Звонари": {"name": "Звонари", "code": "zvon", "quick_errors_enabled": False}
        }
    
    # Проверяем, является ли текст названием телефонии
    if text in tel_map:
        tel_data = tel_map[text]
        tel_name = tel_data['name']
        tel_code = tel_data['code']
        
        # ✅ КРИТИЧЕСКИ ВАЖНО: Проверяем quick_errors_enabled
        quick_errors = tel_data.get('quick_errors_enabled', False)
        
        logger.info(
            f"📞 User {update.effective_user.id} выбрал {tel_name} "
            f"(quick_errors={quick_errors})"
        )
        
        # ✅ ЕСЛИ БЫСТРЫЕ ОШИБКИ ВКЛЮЧЕНЫ - НЕ ОБРАБАТЫВАЕМ
        if quick_errors:
            logger.info(f"⚡️ {tel_name}: быстрые ошибки ВКЛЮЧЕНЫ - пропускаем для quick_errors.py")
            # Возвращаем False - пусть обработает quick_errors.py
            return False
        
        # ✅ ИНАЧЕ - ОБЫЧНАЯ ОБРАБОТКА
        logger.info(f"📝 {tel_name}: обычный режим (quick_errors выключены)")
        
        # Сохраняем выбор
        set_tel_choice(context, tel_name, tel_code)
        
        await update.message.reply_text(
            f"✅ Вы выбрали: <b>{tel_name}</b>\n\n"
            f"📝 Теперь отправьте описание ошибки",
            parse_mode="HTML"
        )
        return True
    
    return False


async def handle_error_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает сообщение как описание ошибки телефонии"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Пользователь"
    role = get_user_role(context)
    
    # Получаем выбор телефонии
    tel, tel_code = get_tel_choice(context)
    
    # Проверка timeout
    if tel and is_tel_choice_expired(context):
        clear_tel_choice(context)
        tel = None
        tel_code = None
        logger.info(f"⏱ Истёк timeout выбора телефонии для user_id={user_id}")
    
    # Если телефония не выбрана
    if not tel or not tel_code:
        current_menu = get_menu_by_role(role)
        await update.message.reply_text(
            "⚠️ Сначала выберите телефонию через кнопку 'Ошибки телефонии'",
            reply_markup=current_menu
        )
        return
    
    # Получаем ID группы
    group_id = telephony_service.get_group_id(tel)
    if not group_id:
        logger.error(f"❌ Не найдена группа для телефонии: {tel}")
        await update.message.reply_text("⚠️ Ошибка: не назначена группа для этой телефонии.")
        return
    
    # Получение и валидация текста
    error_text = update.message.text or update.message.caption or ""
    has_media = bool(update.message.photo or update.message.document)
    
    is_valid, error_msg = telephony_service.validate_error_text(error_text, has_media)
    if not is_valid:
        await update.message.reply_text(error_msg)
        return
    
    # Отправка в группу
    success = await telephony_service.send_error_to_group(
        context.bot,
        update,
        context,
        group_id,
        tel_code,
        username,
        error_text
    )
    
    if not success:
        await update.message.reply_text(
            "⚠️ Не удалось отправить ошибку в саппорт.\n"
            "Попробуйте позже или обратитесь к администратору."
        )
        return
    
    # Очистка выбора и возврат в меню
    clear_tel_choice(context)
    current_menu = get_menu_by_role(role)
    
    # Получаем правильное сообщение для телефонии
    success_msg = telephony_service.get_success_message(tel_code, tel)
    
    await update.message.reply_text(
        success_msg,
        parse_mode="HTML",
        reply_markup=current_menu
    )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главный обработчик всех текстовых сообщений"""
    user_id = update.effective_user.id
    
    # Проверка доступа
    if not user_service.has_access(user_id):
        return
    
    text = update.message.text
    if not text:
        return
    
    logger.debug(f"📨 Сообщение от user_id={user_id}: '{text[:50]}...'")
    
    # Проверка режима поддержки
    if await handle_support_message(update, context):
        return
    
    # ✅ КРИТИЧЕСКИ ВАЖНО: Проверка выбора телефонии с динамической проверкой БД
    telephony_handled = await handle_telephony_choice(update, context)
    
    if telephony_handled:
        # Обработано как обычная телефония
        return
    
    # Если не обработано здесь - может быть быстрая ошибка (обработает quick_errors.py)
    # или это кнопка меню
    
    # Список кнопок меню
    menu_texts = {
        "Ошибки телефонии", "Полезные ссылки",
        "Статистика трубок", "Статистика менеджеров", 
        "Статистика ошибок",
        "Управление ботом",
        "◀️ Меню"
    }
    
    # Если это кнопка меню
    if text in menu_texts:
        await handle_menu_button(update, context)
    else:
        # Иначе - это описание ошибки
        await handle_error_message(update, context)