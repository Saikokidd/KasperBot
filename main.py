"""
main.py - ПОЛНАЯ ВЕРСИЯ с быстрыми ошибками

ИЗМЕНЕНИЯ:
✅ Добавлены ConversationHandlers для быстрых ошибок
✅ Правильная регистрация в нужных группах
✅ Обработка callback'ов для быстрых ошибок
"""
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)
from config.settings import settings
from utils.logger import logger
from utils.shutdown import shutdown_handler

# Импорты обработчиков
from handlers.commands import start_command
from handlers.health import health_command
from handlers.callbacks import (
    role_choice_callback,
    tel_choice_callback,
    support_callback,
)
from handlers.messages import message_handler
from handlers.errors import error_handler

from handlers.menu import handle_telephony_selection_callback

from handlers.management import (
    show_management_menu,
    managers_menu,
    list_managers,
    add_manager_start,
    add_manager_process,
    remove_manager_start,
    remove_manager_process,
    telephonies_menu,
    list_telephonies,
    add_telephony_start,
    add_telephony_name,
    add_telephony_code,
    add_telephony_type,
    add_telephony_group,
    remove_telephony_start,
    remove_telephony_process,
    broadcast_start,
    broadcast_process,
    broadcast_confirm,
    quick_errors_menu,
    quick_errors_list,
    quick_errors_add_start,
    quick_errors_add_process,
    quick_errors_remove_start,
    quick_errors_remove_process,
    cancel_conversation,
    WAITING_MANAGER_ID,
    WAITING_MANAGER_ID_REMOVE,
    WAITING_TEL_NAME,
    WAITING_TEL_CODE,
    WAITING_TEL_TYPE,
    WAITING_TEL_GROUP,
    WAITING_TEL_CODE_REMOVE,
    WAITING_BROADCAST_MESSAGE,
    WAITING_QE_CODE_ADD,
    WAITING_QE_CODE_REMOVE,
)

from handlers.analytics import (
    show_errors_stats_menu,
    show_general_stats,
    show_general_stats_period,
    show_managers_stats,
    show_managers_stats_period,
    show_support_stats,
    show_support_stats_period,
    show_response_time_stats,
    show_response_time_stats_period,
    show_dashboard_start,
    show_dashboard_page,
)

# ✅ НОВОЕ: Импорт обработчиков быстрых ошибок
from handlers.quick_errors import (
    handle_quick_error_callback,
    handle_change_sip_callback,
)



async def fallback_callback(update, context):
    """Fallback для неизвестных callback"""
    query = update.callback_query

    known_patterns = [
        "mgmt_",
        "role_",
        "tel_",
        "fix_",
        "wait_",
        "wrong_",
        "sim_",
        "stats_",
        "dash_",
        "broadcast_confirm",
        "tel_type_",
        "noop",
        "select_tel_",
        "qerr_",
        "change_sip",
    ]

    is_known = any(query.data.startswith(p) for p in known_patterns)

    if not is_known:
        logger.warning(f"⚠️ Неизвестный callback: {query.data}")
        await query.answer("⚠️ Эта кнопка больше не активна", show_alert=False)


async def rate_limit_middleware(update, context):
    """
    Middleware для защиты от спама

    ✅ ДОБАВЛЕНО: Rate limiting для сообщений и callback'ов
    """
    from utils.rate_limiter import rate_limiter

    if not update.effective_user:
        return

    user_id = update.effective_user.id

    # Проверка для сообщений
    if update.message:
        allowed, msg = rate_limiter.check_message_rate(user_id)
        if not allowed:
            logger.warning(f"⚠️ Rate limit: сообщение от {user_id}")
            await update.message.reply_text(msg)
            return False  # Блокируем обработчик

    # Проверка для callback'ов
    elif update.callback_query:
        allowed, msg = rate_limiter.check_callback_rate(user_id)
        if not allowed:
            logger.warning(f"⚠️ Rate limit: callback от {user_id}")
            try:
                await update.callback_query.answer(msg, show_alert=True)
            except Exception as e:
                logger.debug(f"Rate limit: unable to send callback alert: {e}")
            return False  # Блокируем обработчик

    return True  # Разрешаем обработчик


def register_handlers(app: Application):
    """Регистрация всех обработчиков"""
    logger.info("🔧 Начало регистрации обработчиков...")

    # ===== GROUP -1: КОМАНДЫ =====
    app.add_handler(CommandHandler("start", start_command), group=-1)
    app.add_handler(CommandHandler("health", health_command), group=-1)
    logger.info("✅ Команды (group=-1)")

    # ===== GROUP 0: CALLBACKS =====

    # Выбор телефонии (Inline)
    app.add_handler(
        CallbackQueryHandler(
            handle_telephony_selection_callback, pattern="^select_tel_"
        ),
        group=0,
    )
    logger.info("✅ Inline выбор телефонии (group=0)")

    # ✅ НОВОЕ: Быстрые ошибки (callback'и)
    app.add_handler(
        CallbackQueryHandler(handle_quick_error_callback, pattern="^qerr_"), group=0
    )
    app.add_handler(
        CallbackQueryHandler(handle_change_sip_callback, pattern="^change_sip$"),
        group=0,
    )
    logger.info("✅ Быстрые ошибки callbacks (group=0)")

    # Управление
    app.add_handler(
        CallbackQueryHandler(show_management_menu, pattern="^mgmt_menu$"), group=0
    )
    app.add_handler(
        CallbackQueryHandler(managers_menu, pattern="^mgmt_managers$"), group=0
    )
    app.add_handler(
        CallbackQueryHandler(list_managers, pattern="^mgmt_list_managers$"), group=0
    )
    app.add_handler(
        CallbackQueryHandler(telephonies_menu, pattern="^mgmt_telephonies$"), group=0
    )
    app.add_handler(
        CallbackQueryHandler(list_telephonies, pattern="^mgmt_list_tel$"), group=0
    )
    app.add_handler(
        CallbackQueryHandler(broadcast_confirm, pattern="^broadcast_confirm$"), group=0
    )

    # Быстрые ошибки (меню управления)
    app.add_handler(
        CallbackQueryHandler(quick_errors_menu, pattern="^mgmt_quick_errors$"), group=0
    )
    app.add_handler(
        CallbackQueryHandler(quick_errors_list, pattern="^qe_list$"), group=0
    )

    # Статистика
    app.add_handler(
        CallbackQueryHandler(show_errors_stats_menu, pattern="^stats_menu$"), group=0
    )
    app.add_handler(
        CallbackQueryHandler(show_dashboard_start, pattern="^dash_start_"), group=0
    )
    app.add_handler(
        CallbackQueryHandler(show_dashboard_page, pattern="^dash_page_"), group=0
    )
    app.add_handler(
        CallbackQueryHandler(show_general_stats, pattern="^stats_general$"), group=0
    )
    app.add_handler(
        CallbackQueryHandler(show_general_stats_period, pattern="^stats_gen_"), group=0
    )
    app.add_handler(
        CallbackQueryHandler(show_managers_stats, pattern="^stats_managers$"), group=0
    )
    app.add_handler(
        CallbackQueryHandler(show_managers_stats_period, pattern="^stats_mgr_"), group=0
    )
    app.add_handler(
        CallbackQueryHandler(show_support_stats, pattern="^stats_support$"), group=0
    )
    app.add_handler(
        CallbackQueryHandler(show_support_stats_period, pattern="^stats_sup_"), group=0
    )
    app.add_handler(
        CallbackQueryHandler(show_response_time_stats, pattern="^stats_response_time$"),
        group=0,
    )
    app.add_handler(
        CallbackQueryHandler(show_response_time_stats_period, pattern="^stats_time_"),
        group=0,
    )

    # Основные callback
    app.add_handler(
        CallbackQueryHandler(role_choice_callback, pattern="^role_"), group=0
    )
    app.add_handler(CallbackQueryHandler(tel_choice_callback, pattern="^tel_"), group=0)
    app.add_handler(
        CallbackQueryHandler(support_callback, pattern="^(fix|wait|wrong|sim)_"),
        group=0,
    )

    # Fallback
    app.add_handler(CallbackQueryHandler(fallback_callback), group=0)

    logger.info("✅ Callbacks (group=0)")

    # ===== GROUP 1: CONVERSATIONHANDLERS =====

    # Менеджеры
    add_manager_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_manager_start, pattern="^mgmt_add_manager$")
        ],
        states={
            WAITING_MANAGER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_manager_process),
                MessageHandler(filters.FORWARDED, add_manager_process),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        per_message=False,
        per_chat=True,
        per_user=True,
        allow_reentry=True,
        name="add_manager",
    )
    app.add_handler(add_manager_conv, group=1)

    remove_manager_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(remove_manager_start, pattern="^mgmt_remove_manager$")
        ],
        states={
            WAITING_MANAGER_ID_REMOVE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, remove_manager_process)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        per_message=False,
        per_chat=True,
        per_user=True,
        allow_reentry=True,
        name="remove_manager",
    )
    app.add_handler(remove_manager_conv, group=1)

    # Телефонии
    add_tel_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_telephony_start, pattern="^mgmt_add_tel$")
        ],
        states={
            WAITING_TEL_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_telephony_name)
            ],
            WAITING_TEL_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_telephony_code)
            ],
            WAITING_TEL_TYPE: [
                CallbackQueryHandler(add_telephony_type, pattern="^tel_type_")
            ],
            WAITING_TEL_GROUP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_telephony_group)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        per_message=False,
        per_chat=True,
        per_user=True,
        allow_reentry=True,
        name="add_telephony",
    )
    app.add_handler(add_tel_conv, group=1)

    remove_tel_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(remove_telephony_start, pattern="^mgmt_remove_tel$")
        ],
        states={
            WAITING_TEL_CODE_REMOVE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, remove_telephony_process
                )
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        per_message=False,
        per_chat=True,
        per_user=True,
        allow_reentry=True,
        name="remove_telephony",
    )
    app.add_handler(remove_tel_conv, group=1)

    # Рассылка
    broadcast_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(broadcast_start, pattern="^mgmt_broadcast$")
        ],
        states={
            WAITING_BROADCAST_MESSAGE: [
                MessageHandler((filters.ALL & ~filters.COMMAND), broadcast_process)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        per_message=False,
        per_chat=True,
        per_user=True,
        allow_reentry=True,
        name="broadcast",
    )
    app.add_handler(broadcast_conv, group=1)

    # ✅ НОВОЕ: Быстрые ошибки (управление через админку)
    qe_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(quick_errors_add_start, pattern="^qe_add$")],
        states={
            WAITING_QE_CODE_ADD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, quick_errors_add_process
                )
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        per_message=False,
        per_chat=True,
        per_user=True,
        allow_reentry=True,
        name="qe_add",
    )
    app.add_handler(qe_add_conv, group=1)

    qe_remove_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(quick_errors_remove_start, pattern="^qe_remove$")
        ],
        states={
            WAITING_QE_CODE_REMOVE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, quick_errors_remove_process
                )
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        per_message=False,
        per_chat=True,
        per_user=True,
        allow_reentry=True,
        name="qe_remove",
    )
    app.add_handler(qe_remove_conv, group=1)

    logger.info("✅ Management ConversationHandlers (group=1)")

    # ===== GROUP 2: MESSAGE HANDLER (ПОСЛЕДНИМ!) =====

    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND & filters.ChatType.PRIVATE, message_handler
        ),
        group=2,
    )
    logger.info("✅ message_handler (group=2)")

    # ===== ERROR HANDLER =====
    app.add_error_handler(error_handler)
    logger.info("✅ error_handler")

    logger.info("✅ ВСЕ обработчики зарегистрированы!")

    for group_num in [-1, 0, 1, 2]:
        handlers_in_group = app.handlers.get(group_num, [])
        logger.info(f"   Group {group_num}: {len(handlers_in_group)} handler(s)")


def main():
    """Главная функция запуска бота"""
    try:
        logger.info("🚀 Запуск бота...")

        # Автомиграция менеджеров из .env в БД
        from services.user_service import user_service

        user_service.migrate_env_managers_to_db()

        # Статистика
        logger.info(f"👑 Админов: {len(settings.ADMINS)}")
        logger.info(f"🎛 Пульт: {len(settings.PULT)}")

        from database.models import db

        managers = db.get_all_managers()
        logger.info(f"📋 Менеджеров в БД: {len(managers)}")
        logger.info("✅ БД инициализирована")

        app = Application.builder().token(settings.BOT_TOKEN).build()

        register_handlers(app)

        logger.info("✅ Бот готов к работе!")

        try:
            from services.scheduler_service import scheduler_service

            scheduler_service.set_bot(app.bot)

            if not scheduler_service.scheduler.running:
                scheduler_service.start()
                logger.info("✅ Планировщик запущен")
        except Exception as e:
            logger.warning(f"⚠️ Планировщик не запущен: {e}")

        def stop_scheduler():
            try:
                from services.scheduler_service import scheduler_service

                scheduler_service.stop()
            except Exception as e:
                logger.error(f"Ошибка остановки планировщика: {e}")

        shutdown_handler.register_callback(stop_scheduler)
        shutdown_handler.setup_handlers()

        logger.info("🔄 Запуск polling...")
        app.run_polling(
            allowed_updates=["message", "callback_query"], drop_pending_updates=True
        )

    except KeyboardInterrupt:
        logger.info("⌨️ Получен Ctrl+C")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
