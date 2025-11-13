"""
Обработчики callback запросов (inline кнопки)
"""
from datetime import datetime
from telegram import Update, error as telegram_error
from telegram.ext import ContextTypes

from config.settings import settings
from config.constants import TEL_CODES_REVERSE, SUPPORT_ACTIONS, TEL_CHOICE_TIMEOUT
from services.user_service import user_service
from keyboards.reply import get_admin_menu, get_manager_menu, get_menu_by_role
from keyboards.inline import get_telephony_keyboard
from utils.state import set_user_role, get_user_role, set_tel_choice
from utils.logger import logger


async def role_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик выбора роли администратором
    
    Args:
        update: Update объект
        context: Контекст пользователя
    """
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Проверка, что это админ
    if not user_service.is_admin(user_id):
        await query.message.edit_text("❌ У вас нет прав для этого действия.")
        return
    
    if query.data == "role_manager":
        set_user_role(context, "manager")
        logger.info(f"👨‍💼 Админ {user_id} вошёл как менеджер")
        
        await query.message.edit_text(
            "👨‍💼 Вы вошли в режиме менеджера.\n\n"
            "Выберите действие из меню:",
            reply_markup=None
        )
        
        await query.message.reply_text(
            "Используйте меню ниже:",
            reply_markup=get_manager_menu()
        )
        
    elif query.data == "role_admin":
        set_user_role(context, "admin")
        logger.info(f"👑 Админ {user_id} вошёл как админ")
        
        await query.message.edit_text(
            "👑 Вы вошли в режиме администратора.\n\n"
            "Выберите действие из меню:",
            reply_markup=None
        )
        
        await query.message.reply_text(
            "Используйте меню ниже:",
            reply_markup=get_admin_menu()
        )


async def tel_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик выбора телефонии через inline кнопки
    
    Args:
        update: Update объект
        context: Контекст пользователя
    """
    query = update.callback_query
    await query.answer()
    
    try:
        callback_data = query.data
        logger.debug(f"Callback data: {callback_data}")
        
        if not callback_data.startswith("tel_"):
            logger.error(f"❌ Неверный формат callback_data: {callback_data}")
            await query.message.reply_text("⚠️ Ошибка: неверный формат выбора.")
            return
        
        tel_code = callback_data.split("_")[1]
        tel_name = TEL_CODES_REVERSE.get(tel_code)
        
        if not tel_name:
            logger.error(f"❌ Неизвестный код телефонии: {tel_code}")
            await query.message.reply_text("⚠️ Ошибка: неизвестная телефония.")
            return
        
        # Сохраняем выбор
        set_tel_choice(context, tel_name, tel_code)
        
        logger.info(f"✅ User {update.effective_user.id} выбрал телефонию: {tel_name} ({tel_code})")
        
        await query.message.edit_text(
            f"✅ Вы выбрали: <b>{tel_name}</b>\n\n"
            f"📝 Теперь отправьте описание ошибки\n"
            f"⏱ Выбор активен {TEL_CHOICE_TIMEOUT} минут.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в tel_choice: {e}", exc_info=True)
        await query.message.reply_text(
            "⚠️ Произошла ошибка при выборе телефонии. Попробуйте снова.",
            reply_markup=get_telephony_keyboard()
        )


async def support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик нажатий на кнопки саппорта в группе (только для BMW)
    
    Args:
        update: Update объект
        context: Контекст пользователя
    """
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data.split("_")
        if len(data) != 3:
            raise ValueError(f"Неверный формат callback_data: {query.data}")
        
        action_code, user_id_str, tel_code = data
        user_id = int(user_id_str)
        tel_name = TEL_CODES_REVERSE.get(tel_code, "Unknown")
        
        action_text = SUPPORT_ACTIONS.get(action_code, "❓ Неизвестное действие")
        support_user = query.from_user.first_name or "Саппорт"
        
        logger.info(f"🔧 Саппорт действие: {action_text} для ошибки от user_id={user_id} ({tel_name}) от {support_user}")
        
        # Получаем оригинальный текст и добавляем статус
        original_text = query.message.text_html or query.message.text
        
        # Обрезаем если слишком длинно
        if len(original_text) > 3500:
            original_text = original_text[:3500] + "..."
        
        new_message = (
            f"{original_text}\n"
            f"{action_text}\n"
            f"<b>Обработал:</b> {support_user}"
        )
        
        # Редактируем текущее сообщение (убираем кнопки и добавляем статус)
        try:
            await query.message.edit_text(
                text=new_message,
                parse_mode="HTML",
                reply_markup=None  # Убираем кнопки
            )
        except telegram_error.TelegramError as e:
            logger.error(f"⚠️ Не удалось отредактировать сообщение: {e}")
        
        # Уведомляем пользователя
        try:
            notification = (
                f"💬 <b>Ответ от саппорта</b>\n\n"
                f"📞 Телефония: {tel_name}\n"
                f"Статус: {action_text}"
            )
            
            if action_code == "wrong":
                notification += "\n\n⚠️ Пожалуйста, отправьте ошибку в правильном формате."
            elif action_code == "wait":
                notification += "\n\n⏱ Ваша проблема будет решена в течение 2-3 минут."
            
            await context.bot.send_message(
                chat_id=user_id,
                text=notification,
                parse_mode="HTML"
            )
            logger.info(f"✅ Уведомление отправлено user_id={user_id}")
        except telegram_error.TelegramError as e:
            logger.error(f"⚠️ Не удалось уведомить user_id={user_id}: {e}")
            
    except ValueError as e:
        logger.error(f"❌ Ошибка валидации в support_callback: {e}")
        await query.message.reply_text("⚠️ Ошибка обработки: неверный формат данных.")
    except Exception as e:
        logger.error(f"❌ Unexpected error в support_callback: {e}", exc_info=True)
        await query.message.reply_text("⚠️ Произошла ошибка при обработке ответа.")


async def fallback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик неизвестных callback запросов
    
    Args:
        update: Update объект
        context: Контекст пользователя
    """
    query = update.callback_query
    logger.warning(f"⚠️ Неизвестный callback: {query.data} от user_id={query.from_user.id}")
    await query.answer()
    
    role = get_user_role(context)
    current_menu = get_menu_by_role(role)
    
    await query.message.reply_text(
        "⚠️ Неизвестная команда. Попробуйте снова.",
        reply_markup=current_menu
    )