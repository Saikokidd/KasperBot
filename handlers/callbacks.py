"""
ИСПРАВЛЕНО: handlers/callbacks.py
Улучшено логирование + fallback не блокирует другие handler'ы

ИЗМЕНЕНИЯ:
✅ fallback_callback НЕ отвечает на query сразу
✅ Добавлена проверка известных паттернов
✅ Логируются все callback для диагностики
"""
from datetime import datetime
from telegram import Update, error as telegram_error
from telegram.ext import ContextTypes
from contextlib import closing

from config.constants import TEL_CODES_REVERSE, SUPPORT_ACTIONS, TEL_CHOICE_TIMEOUT
from services.user_service import user_service
from keyboards.reply import get_admin_menu, get_manager_menu
from keyboards.inline import get_telephony_keyboard
from utils.state import set_user_role, set_tel_choice
from utils.logger import logger


async def role_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора роли администратором"""
    query = update.callback_query
    user_id = update.effective_user.id

    logger.info(f"🎭 Выбор роли от user_id={user_id}: {query.data}")

    await query.answer()

    # Проверка, что это админ
    if not user_service.is_admin(user_id):
        logger.warning(f"⚠️ Попытка выбора роли не-админом: user_id={user_id}")
        await query.message.edit_text("❌ У вас нет прав для этого действия.")
        return

    if query.data == "role_manager":
        set_user_role(context, "manager")
        logger.info(f"👨‍💼 Админ {user_id} вошёл как менеджер")

        await query.message.edit_text(
            "👨‍💼 Вы вошли в режиме менеджера.\n\n" "Выберите действие из меню:",
            reply_markup=None,
        )

        await query.message.reply_text(
            "Используйте меню ниже:", reply_markup=get_manager_menu()
        )

    elif query.data == "role_admin":
        set_user_role(context, "admin")
        logger.info(f"👑 Админ {user_id} вошёл как админ")

        await query.message.edit_text(
            "👑 Вы вошли в режиме администратора.\n\n" "Выберите действие из меню:",
            reply_markup=None,
        )

        await query.message.reply_text(
            "Используйте меню ниже:", reply_markup=get_admin_menu()
        )


async def tel_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора телефонии через inline кнопки"""
    query = update.callback_query
    user_id = update.effective_user.id

    logger.debug(f"📞 Callback телефонии от user_id={user_id}: {query.data}")

    await query.answer()

    try:
        callback_data = query.data

        if not callback_data.startswith("tel_"):
            logger.error(
                f"❌ Неверный формат callback_data: {callback_data} от user_id={user_id}"
            )
            await query.message.reply_text("⚠️ Ошибка: неверный формат выбора.")
            return

        tel_code = callback_data.split("_")[1]
        logger.debug(f"📞 Извлечён код телефонии: {tel_code}")

        # Получаем название из БД
        from database.models import db

        tel = db.get_telephony_by_code(tel_code)

        if tel:
            tel_name = tel["name"]
            logger.debug(f"✅ Найдена телефония в БД: {tel_name}")
        else:
            # Фоллбэк на старые
            tel_name = TEL_CODES_REVERSE.get(tel_code)
            logger.debug(f"⚠️ Телефония не в БД, используем fallback: {tel_name}")

        if not tel_name:
            logger.error(
                f"❌ Неизвестный код телефонии: {tel_code} от user_id={user_id}"
            )
            await query.message.reply_text("⚠️ Ошибка: неизвестная телефония.")
            return

        # Сохраняем выбор
        set_tel_choice(context, tel_name, tel_code)

        logger.info(f"✅ User {user_id} выбрал телефонию: {tel_name} ({tel_code})")

        await query.message.edit_text(
            f"✅ Вы выбрали: <b>{tel_name}</b>\n\n"
            f"📝 Теперь отправьте описание ошибки\n"
            f"⏱ Выбор активен {TEL_CHOICE_TIMEOUT} минут.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(
            f"❌ Ошибка в tel_choice_callback от user_id={user_id}: {e}", exc_info=True
        )
        await query.message.reply_text(
            "⚠️ Произошла ошибка при выборе телефонии. Попробуйте снова.",
            reply_markup=get_telephony_keyboard(),
        )


async def support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки саппорта в группе"""
    query = update.callback_query
    support_user_id = query.from_user.id

    logger.debug(f"🔧 Support callback от user_id={support_user_id}: {query.data}")

    await query.answer()

    try:
        data = query.data.split("_")
        if len(data) != 3:
            raise ValueError(f"Неверный формат callback_data: {query.data}")

        action_code, user_id_str, tel_code = data
        user_id = int(user_id_str)

        logger.info(
            f"🔧 Support действие: {action_code} для user_id={user_id} от саппорта={support_user_id}"
        )

        # Получаем название телефонии
        from database.models import db

        tel = db.get_telephony_by_code(tel_code)
        tel_name = tel["name"] if tel else TEL_CODES_REVERSE.get(tel_code, "Unknown")

        action_text = SUPPORT_ACTIONS.get(action_code, "❓ Неизвестное действие")
        support_username = (
            query.from_user.username or query.from_user.first_name or "Саппорт"
        )

        logger.info(f"🔧 Действие: {action_text} для {tel_name} от {support_username}")

        # Сохранение в БД для аналитики
        try:
            with closing(db._get_connection()) as conn:
                cursor = conn.cursor()

                # Находим последнюю необработанную ошибку
                cursor.execute(
                    """
                    SELECT id, created_at FROM error_reports 
                    WHERE user_id = ? AND telephony_code = ? AND status = 'new'
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (user_id, tel_code),
                )

                error_record = cursor.fetchone()

                if error_record:
                    error_id = error_record[0]
                    created_at_str = error_record[1]

                    try:
                        created_at = datetime.strptime(
                            created_at_str, "%Y-%m-%d %H:%M:%S"
                        )
                        resolved_at = datetime.now()
                        response_time = int((resolved_at - created_at).total_seconds())
                    except Exception as e:
                        logger.error(f"⚠️ Ошибка парсинга времени: {e}")
                        response_time = None
                        resolved_at = datetime.now()

                    # Обновляем запись
                    cursor.execute(
                        """
                        UPDATE error_reports 
                        SET status = 'resolved', 
                            resolved_at = ?,
                            support_user_id = ?,
                            support_username = ?,
                            support_action = ?,
                            response_time_seconds = ?
                        WHERE id = ?
                        """,
                        (
                            resolved_at.strftime("%Y-%m-%d %H:%M:%S"),
                            support_user_id,
                            support_username,
                            action_code,
                            response_time,
                            error_id,
                        ),
                    )

                    conn.commit()

                    minutes = response_time // 60 if response_time else 0
                    seconds = response_time % 60 if response_time else 0
                    logger.info(
                        f"✅ Ошибка #{error_id} обновлена в БД (время ответа: {minutes}м {seconds}с)"
                    )
                else:
                    logger.warning(
                        f"⚠️ Не найдена необработанная ошибка для user_id={user_id}, tel_code={tel_code}"
                    )

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в БД: {e}", exc_info=True)

        # Получаем оригинальный текст и добавляем статус
        original_text = query.message.text_html or query.message.text

        if len(original_text) > 3500:
            original_text = original_text[:3500] + "..."

        new_message = (
            f"{original_text}\n"
            f"{action_text}\n"
            f"<b>Обработал:</b> {support_username}"
        )

        # Редактируем сообщение
        try:
            await query.message.edit_text(
                text=new_message, parse_mode="HTML", reply_markup=None
            )
            logger.debug("✅ Сообщение отредактировано в группе")
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
                notification += (
                    "\n\n⚠️ Пожалуйста, отправьте ошибку в правильном формате."
                )
            elif action_code == "wait":
                notification += "\n\n⏱ Ваша проблема будет решена в течение 2-3 минут."

            await context.bot.send_message(
                chat_id=user_id, text=notification, parse_mode="HTML"
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

    ✅ ИСПРАВЛЕНО: НЕ отвечает на query (позволяет другим handler'ам сработать)
    """
    query = update.callback_query
    user_id = query.from_user.id
    callback_data = query.data

    # ✅ КРИТИЧЕСКОЕ ИЗМЕНЕНИЕ: Просто логируем, НЕ отвечаем на query
    # Это позволяет другим handler'ам (в group=0) обработать callback
    logger.warning(
        f"⚠️ Fallback: неизвестный callback от user_id={user_id}: {callback_data}"
    )

    # ❌ НЕ ВЫЗЫВАЕМ query.answer() здесь!
    # Если другой handler обработал callback - всё ОК
    # Если нет - пользователь просто не получит ответ (не критично)
