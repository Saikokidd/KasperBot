"""
handlers/quick_errors.py - ИСПРАВЛЕНО
Убрана Reply клавиатура из edit_text()

ИЗМЕНЕНИЯ:
✅ edit_text() теперь без reply_markup
✅ Reply меню отправляется отдельным сообщением
✅ Исправлена ошибка "Inline keyboard expected"
"""
from telegram import Update
from telegram.ext import ContextTypes
from database.models import db
from keyboards.inline import get_quick_errors_keyboard
from keyboards.reply import get_menu_by_role
from config.constants import (
    MESSAGES,
    QUICK_ERRORS,
    MAX_SIP_LENGTH,
    MAX_CUSTOM_ERROR_LENGTH,
    SIP_PATTERN,
)
from utils.state import get_user_role
from utils.logger import logger


async def handle_quick_error_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """
    Обработка нажатия кнопки быстрой ошибки

    ✅ ИСПРАВЛЕНО: Убрана Reply клавиатура из edit_text()

    Callback: qerr_1, qerr_2, ..., qerr_10
    """
    query = update.callback_query
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Пользователь"

    await query.answer()

    error_code = query.data.split("_")[1]
    logger.info(f"🔘 Кнопка ошибки {error_code} от user_id={user_id}")

    # Получаем SIP
    sip = context.user_data.get("quick_error_sip")

    if not sip:
        # Восстанавливаем из БД
        if db.is_sip_valid_today(user_id):
            sip_data = db.get_manager_sip(user_id)
            if sip_data:
                sip = sip_data["sip_number"]
                context.user_data["quick_error_sip"] = sip

        if not sip:
            await query.message.edit_text("⚠️ SIP не найден. Попробуйте снова.")
            return

    # Свой вариант (кнопка 10)
    if error_code == "10":
        # ✅ ИСПРАВЛЕНИЕ: Удаляем Inline клавиатуру при запросе кастомной ошибки
        await query.message.edit_text(
            MESSAGES["custom_error_prompt"], reply_markup=None
        )
        context.user_data["awaiting_custom_error"] = True
        return

    # Стандартная ошибка
    error_text = QUICK_ERRORS.get(error_code, "Неизвестная ошибка")

    # Получаем данные телефонии
    tel_code = context.user_data.get("quick_error_tel_code")
    tel_name = context.user_data.get("quick_error_tel_name")
    group_id = context.user_data.get("quick_error_group_id")

    if not all([tel_code, tel_name, group_id]):
        await query.message.edit_text("⚠️ Данные телефонии потеряны")
        return

    # Отправляем
    success = await send_quick_error_to_group(
        context.bot, user_id, username, sip, error_text, tel_code, group_id
    )

    if not success:
        await query.message.edit_text("⚠️ Не удалось отправить")
        return

    # ✅ ИСПРАВЛЕНИЕ: Редактируем с явным reply_markup=None (удаляем Inline кнопки)
    success_text = (
        f"✅ Ошибка отправлена!\n\n"
        f"📞 {tel_name}\n"
        f"SIP: {sip}\n"
        f"Ошибка: {error_text}"
    )

    await query.message.edit_text(
        success_text, reply_markup=None  # ✅ КРИТИЧНО: Явно удаляем Inline клавиатуру
    )

    # ✅ ИСПРАВЛЕНИЕ: Reply меню отправляем ОТДЕЛЬНЫМ сообщением
    role = get_user_role(context)
    current_menu = get_menu_by_role(role)

    await context.bot.send_message(
        chat_id=user_id, text="Выберите действие:", reply_markup=current_menu
    )

    # Очищаем контекст
    context.user_data.pop("quick_error_sip", None)
    context.user_data.pop("quick_error_tel_code", None)
    context.user_data.pop("quick_error_tel_name", None)
    context.user_data.pop("quick_error_group_id", None)


async def handle_change_sip_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Обработка кнопки 'Изменить SIP'"""
    query = update.callback_query
    await query.answer()

    # ✅ ИСПРАВЛЕНИЕ: Удаляем Inline клавиатуру при изменении SIP
    await query.message.edit_text(MESSAGES["sip_prompt"], reply_markup=None)
    context.user_data["awaiting_sip_for_quick_error"] = True


async def handle_sip_input_for_quick_error(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """
    Обработка ввода SIP (вызывается из message_handler)

    Returns:
        True если сообщение обработано как SIP
    """
    if not context.user_data.get("awaiting_sip_for_quick_error"):
        return False

    user_id = update.effective_user.id
    sip_text = update.message.text.strip()

    logger.info(f"📞 Введён SIP для быстрых ошибок: {sip_text}")

    # Валидация
    if (
        not sip_text
        or len(sip_text) > MAX_SIP_LENGTH
        or not SIP_PATTERN.match(sip_text)
    ):
        logger.warning(f"⚠️ Неверный SIP: '{sip_text}'")
        await update.message.reply_text(MESSAGES["sip_invalid"])
        return True

    # Сохраняем
    db.save_manager_sip(user_id, sip_text)
    context.user_data["quick_error_sip"] = sip_text
    context.user_data.pop("awaiting_sip_for_quick_error", None)

    logger.info(f"✅ SIP сохранён: {sip_text}")

    # Показываем кнопки ошибок
    await update.message.reply_text(
        MESSAGES["sip_saved"].format(sip=sip_text),
        reply_markup=get_quick_errors_keyboard(),
    )

    return True


async def handle_custom_error_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """
    Обработка ввода кастомной ошибки (вызывается из message_handler)

    ✅ ИСПРАВЛЕНО: Убрана Reply клавиатура из reply_text

    Returns:
        True если сообщение обработано как кастомная ошибка
    """
    if not context.user_data.get("awaiting_custom_error"):
        return False

    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Пользователь"
    error_text = update.message.text.strip()
    sip = context.user_data.get("quick_error_sip")

    if not sip:
        await update.message.reply_text("⚠️ SIP не найден")
        return True

    # Валидация
    if not error_text or len(error_text) > MAX_CUSTOM_ERROR_LENGTH:
        await update.message.reply_text(
            f"⚠️ Длина: 1-{MAX_CUSTOM_ERROR_LENGTH} символов (сейчас: {len(error_text)})"
        )
        return True

    # Получаем данные телефонии
    tel_code = context.user_data.get("quick_error_tel_code")
    tel_name = context.user_data.get("quick_error_tel_name")
    group_id = context.user_data.get("quick_error_group_id")

    if not all([tel_code, tel_name, group_id]):
        await update.message.reply_text("⚠️ Данные телефонии потеряны")
        return True

    # Отправляем
    success = await send_quick_error_to_group(
        context.bot, user_id, username, sip, error_text, tel_code, group_id
    )

    if not success:
        await update.message.reply_text("⚠️ Не удалось отправить")
        return True

    # ✅ ИСПРАВЛЕНИЕ: Отправляем ТОЛЬКО текст (без Reply клавиатуры)
    success_text = (
        f"✅ Ошибка отправлена!\n\n"
        f"📞 {tel_name}\n"
        f"SIP: {sip}\n"
        f"Ошибка: {error_text}"
    )

    await update.message.reply_text(success_text)

    # ✅ ИСПРАВЛЕНИЕ: Reply меню отправляем ОТДЕЛЬНО
    role = get_user_role(context)
    current_menu = get_menu_by_role(role)

    await update.message.reply_text("Выберите действие:", reply_markup=current_menu)

    # Очищаем
    context.user_data.pop("quick_error_sip", None)
    context.user_data.pop("quick_error_tel_code", None)
    context.user_data.pop("quick_error_tel_name", None)
    context.user_data.pop("quick_error_group_id", None)
    context.user_data.pop("awaiting_custom_error", None)

    return True


async def send_quick_error_to_group(
    bot,
    user_id: int,
    username: str,
    sip: str,
    error_text: str,
    tel_code: str,
    group_id: int,
) -> bool:
    """Отправка быстрой ошибки в группу"""
    msg = f"От {username}\nSIP: {sip}  {error_text}"

    from keyboards.inline import get_support_keyboard

    keyboard = get_support_keyboard(user_id, tel_code)

    try:
        await bot.send_message(chat_id=group_id, text=msg, reply_markup=keyboard)

        db.log_error_report(user_id, username, tel_code, f"SIP: {sip} - {error_text}")
        logger.info(f"✅ Быстрая ошибка отправлена: {tel_code}, SIP={sip}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}")
        return False
