"""
handlers/telephony_handler.py - УНИФИЦИРОВАННЫЙ ОБРАБОТЧИК ТЕЛЕФОНИИ

НАЗНАЧЕНИЕ:
✅ Единая логика выбора телефонии (вместо дублирования в menu.py, callbacks.py, quick_errors.py)
✅ Проверка быстрых ошибок через БД
✅ Переиспользуемая функция для всех workflow'ов
"""
from typing import Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.models import db
from config.constants import MESSAGES
from utils.state import set_tel_choice
from utils.logger import logger


async def get_telephony_keyboard() -> Optional[InlineKeyboardMarkup]:
    """
    Получает Inline клавиатуру со всеми доступными телефониями

    Returns:
        InlineKeyboardMarkup или None если нет телефоний
    """
    telephonies = db.get_all_telephonies()

    if not telephonies:
        logger.warning("⚠️ Нет доступных телефоний в БД")
        return None

    buttons = []
    for tel in telephonies:
        buttons.append(
            [
                InlineKeyboardButton(
                    tel["name"], callback_data=f"select_tel_{tel['code']}"
                )
            ]
        )

    return InlineKeyboardMarkup(buttons)


async def handle_telephony_selection_unified(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    tel_code: str,
    workflow: str = "standard",
) -> Tuple[bool, Optional[dict]]:
    """
    Унифицированный обработчик выбора телефонии

    Args:
        update: Telegram Update
        context: Контекст пользователя
        tel_code: Код выбранной телефонии (из callback_data)
        workflow: Тип workflow'а ("standard", "quick_error", "analytics")

    Returns:
        (success, tel_data)
        - success: Успешно ли выбрана телефония
        - tel_data: Данные телефонии или None
    """
    logger.info(
        f"📞 Unified обработчик: выбрана телефония {tel_code} (workflow: {workflow})"
    )

    # Валидация кода
    if not tel_code or not tel_code.strip():
        logger.error(f"❌ Пустой код телефонии в workflow {workflow}")
        return False, None

    # Получаем данные телефонии из БД
    tel = db.get_telephony_by_code(tel_code.strip())

    if not tel:
        logger.warning(f"⚠️ Телефония {tel_code} не найдена в БД")
        return False, None

    # Сохраняем выбор в контекст
    try:
        set_tel_choice(context, tel["name"], tel["code"])
    except ValueError as e:
        logger.error(f"❌ Ошибка при сохранении выбора телефонии: {e}")
        return False, None

    logger.info(f"✅ Телефония {tel['name']} сохранена в контекст")

    # Проверяем тип телефонии в зависимости от workflow'а
    if workflow == "quick_error":
        is_quick = db.is_quick_error_telephony(tel_code)
        if not is_quick:
            logger.warning(f"⚠️ Телефония {tel_code} не поддерживает быстрые ошибки")
            return False, tel  # Возвращаем данные но флаг ошибки

    return True, tel


async def send_choose_telephony_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE, use_edit: bool = False
) -> bool:
    """
    Отправляет или редактирует сообщение с выбором телефонии

    Args:
        update: Telegram Update
        context: Контекст пользователя
        use_edit: True если редактировать (edit_text), False если отправить новое (reply_text)

    Returns:
        True если успешно, False если ошибка
    """
    keyboard = await get_telephony_keyboard()

    if not keyboard:
        msg = "⚠️ Нет доступных телефоний.\nОбратитесь к администратору."

        if use_edit and update.callback_query:
            await update.callback_query.message.edit_text(msg)
        elif update.message:
            await update.message.reply_text(msg)

        return False

    text = MESSAGES.get("choose_telephony", "Выберите телефонию:")

    try:
        if use_edit and update.callback_query:
            await update.callback_query.message.edit_text(text, reply_markup=keyboard)
        elif update.message:
            await update.message.reply_text(text, reply_markup=keyboard)
        else:
            logger.error(
                "❌ Нет способа отправить сообщение (нет callback_query и message)"
            )
            return False

        logger.info("✅ Сообщение с выбором телефонии отправлено")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при отправке сообщения о телефонии: {e}")
        return False


async def validate_and_handle_telephony_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    callback_data: str,
    workflow: str = "standard",
) -> Tuple[bool, Optional[dict], Optional[str]]:
    """
    Полная валидация и обработка callback для телефонии

    Args:
        update: Telegram Update
        context: Контекст пользователя
        callback_data: Данные callback'а (например "select_tel_bmw")
        workflow: Тип workflow'а

    Returns:
        (success, tel_data, error_message)
    """
    query = update.callback_query
    user_id = query.from_user.id

    logger.debug(f"📞 Валидация callback: {callback_data} от user {user_id}")

    # Проверяем формат callback'а
    if not callback_data.startswith("select_tel_"):
        error = f"❌ Неверный формат callback'а: {callback_data}"
        logger.error(error)
        return False, None, error

    # Извлекаем код телефонии
    try:
        tel_code = callback_data.split("_", 2)[2]  # select_tel_bmw → bmw
    except IndexError:
        error = f"❌ Не удалось извлечь код телефонии из {callback_data}"
        logger.error(error)
        return False, None, error

    # Обрабатываем выбор
    success, tel = await handle_telephony_selection_unified(
        update, context, tel_code, workflow
    )

    if not success:
        error = f"⚠️ Не удалось выбрать телефонию {tel_code}"
        logger.warning(error)
        return False, None, error

    logger.info(f"✅ Callback обработан успешно: {tel['name']}")
    return True, tel, None
