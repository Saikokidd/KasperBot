"""
main.py - ПОЛНАЯ ВЕРСИЯ
С поддержкой Inline выбора телефонии

ИЗМЕНЕНИЯ:
✅ Добавлен import handle_telephony_selection_callback
✅ Зарегистрирован callback для выбора телефонии (group=0)
✅ quick_errors опционален (работает если включён)
"""
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
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
    support_callback
)
from handlers.messages import message_handler
from handlers.errors import error_handler

# ✅ НОВОЕ: Импорт обработчика Inline выбора телефонии
from handlers.menu import handle_telephony_selection_callback

from handlers.management import (
    show_management_menu,
    managers_menu, list_managers, add_manager_start, add_manager_process,
    remove_manager_start, remove_manager_process,
    telephonies_menu, list_telephonies, 
    add_telephony_start, add_telephony_name, add_telephony_code, 
    add_telephony_type, add_telephony_group,
    remove_telephony_start, remove_telephony_process,
    broadcast_start, broadcast_process, broadcast_confirm,
    cancel_conversation,
    quick_errors_menu, toggle_quick_errors_callback, show_quick_errors_info,
    WAITING_MANAGER_ID, WAITING_MANAGER_ID_REMOVE,
    WAITING_TEL_NAME, WAITING_TEL_CODE, WAITING_TEL_TYPE, WAITING_TEL_GROUP,
    WAITING_TEL_CODE_REMOVE, WAITING_BROADCAST_MESSAGE
)

from handlers.analytics import (
    show_errors_stats_menu, show_general_stats, show_general_stats_period,
    show_managers_stats, show_managers_stats_period,
    show_support_stats, show_support_stats_period,
    show_response_time_stats, show_response_time_stats_period,
    show_dashboard_start, show_dashboard_page
)

from handlers.quick_errors import get_quick_errors_conv, get_quick_errors_telephony_names


async def fallback_callback(update, context):
    """Fallback для неизвестных callback"""
    query = update.callback_query
    
    known_patterns = [
        'mgmt_', 'role_', 'tel_', 'fix_', 'wait_', 'wrong_', 'sim_',
        'qerr_', 'cancel_quick_errors', 'change_sip',
        'stats_', 'dash_', 'toggle_qe_', 'qe_info',
        'broadcast_confirm', 'tel_type_', 'noop',
        'select_tel_'  # ✅ НОВОЕ
    ]
    
    is_known = any(query.data.startswith(p) for p in known_patterns)
    
    if not is_known:
        logger.warning(f"⚠️ Неизвестный callback: {query.data}")
        await query.answer("⚠️ Эта кнопка больше не активна", show_alert=False)


def register_handlers(app: Application):
    """
    Регистрация всех обработчиков
    
    ПОРЯДОК:
    1. group=-1: Команды
    2. group=0: Callbacks + quick_errors ConversationHandler (опционально)
    3. group=1: Остальные ConversationHandlers
    4. group=2: message_handler (ПОСЛЕДНИМ!)
    """
    logger.info("🔧 Начало регистрации обработчиков...")
    
    # ===== GROUP -1: КОМАНДЫ =====
    app.add_handler(CommandHandler("start", start_command), group=-1)
    app.add_handler(CommandHandler("health", health_command), group=-1)
    logger.info("✅ Команды (group=-1)")
    
    # ===== GROUP 0: CALLBACKS + QUICK_ERRORS =====
    
    # ✅ НОВОЕ: Выбор телефонии через Inline кнопки
    app.add_handler(
        CallbackQueryHandler(handle_telephony_selection_callback, pattern="^select_tel_"),
        group=0
    )
    logger.info("✅ Inline выбор телефонии зарегистрирован (group=0)")
    
    # Управление
    app.add_handler(CallbackQueryHandler(show_management_menu, pattern="^mgmt_menu$"), group=0)
    app.add_handler(CallbackQueryHandler(quick_errors_menu, pattern="^mgmt_quick_errors$"), group=0)
    app.add_handler(CallbackQueryHandler(toggle_quick_errors_callback, pattern="^toggle_qe_"), group=0)
    app.add_handler(CallbackQueryHandler(show_quick_errors_info, pattern="^qe_info$"), group=0)
    app.add_handler(CallbackQueryHandler(managers_menu, pattern="^mgmt_managers$"), group=0)
    app.add_handler(CallbackQueryHandler(list_managers, pattern="^mgmt_list_managers$"), group=0)
    app.add_handler(CallbackQueryHandler(telephonies_menu, pattern="^mgmt_telephonies$"), group=0)
    app.add_handler(CallbackQueryHandler(list_telephonies, pattern="^mgmt_list_tel$"), group=0)
    app.add_handler(CallbackQueryHandler(broadcast_confirm, pattern="^broadcast_confirm$"), group=0)
    
    # Статистика
    app.add_handler(CallbackQueryHandler(show_errors_stats_menu, pattern="^stats_menu$"), group=0)
    app.add_handler(CallbackQueryHandler(show_dashboard_start, pattern="^dash_start_"), group=0)
    app.add_handler(CallbackQueryHandler(show_dashboard_page, pattern="^dash_page_"), group=0)
    app.add_handler(CallbackQueryHandler(show_general_stats, pattern="^stats_general$"), group=0)
    app.add_handler(CallbackQueryHandler(show_general_stats_period, pattern="^stats_gen_"), group=0)
    app.add_handler(CallbackQueryHandler(show_managers_stats, pattern="^stats_managers$"), group=0)
    app.add_handler(CallbackQueryHandler(show_managers_stats_period, pattern="^stats_mgr_"), group=0)
    app.add_handler(CallbackQueryHandler(show_support_stats, pattern="^stats_support$"), group=0)
    app.add_handler(CallbackQueryHandler(show_support_stats_period, pattern="^stats_sup_"), group=0)
    app.add_handler(CallbackQueryHandler(show_response_time_stats, pattern="^stats_response_time$"), group=0)
    app.add_handler(CallbackQueryHandler(show_response_time_stats_period, pattern="^stats_time_"), group=0)
    
    # Основные callback
    app.add_handler(CallbackQueryHandler(role_choice_callback, pattern="^role_"), group=0)
    app.add_handler(CallbackQueryHandler(tel_choice_callback, pattern="^tel_"), group=0)
    app.add_handler(CallbackQueryHandler(support_callback, pattern="^(fix|wait|wrong|sim)_"), group=0)
    
    # Fallback
    app.add_handler(CallbackQueryHandler(fallback_callback), group=0)
    
    logger.info("✅ Callbacks (group=0)")
    
    # ✅ ОПЦИОНАЛЬНО: quick_errors В GROUP 0 (если включены быстрые ошибки)
    quick_errors_conv = get_quick_errors_conv()
    
    if quick_errors_conv:
        app.add_handler(quick_errors_conv, group=0)
        logger.info("✅ quick_errors ConversationHandler (group=0)")
        
        telephony_names = get_quick_errors_telephony_names()
        if telephony_names:
            logger.info(f"   📞 Быстрые ошибки: {', '.join(telephony_names)}")
    else:
        logger.info("ℹ️ quick_errors отключены (нет телефоний с quick_errors_enabled=1)")
    
    # ===== GROUP 1: ОСТАЛЬНЫЕ CONVERSATIONHANDLERS =====
    
    # ConversationHandler управления
    add_manager_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_manager_start, pattern="^mgmt_add_manager$")],
        states={
            WAITING_MANAGER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_manager_process),
                MessageHandler(filters.FORWARDED, add_manager_process)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        name='add_manager'
    )
    app.add_handler(add_manager_conv, group=1)
    
    remove_manager_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(remove_manager_start, pattern="^mgmt_remove_manager$")],
        states={
            WAITING_MANAGER_ID_REMOVE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, remove_manager_process)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        name='remove_manager'
    )
    app.add_handler(remove_manager_conv, group=1)
    
    add_tel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_telephony_start, pattern="^mgmt_add_tel$")],
        states={
            WAITING_TEL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_telephony_name)],
            WAITING_TEL_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_telephony_code)],
            WAITING_TEL_TYPE: [CallbackQueryHandler(add_telephony_type, pattern="^tel_type_")],
            WAITING_TEL_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_telephony_group)]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        name='add_telephony'
    )
    app.add_handler(add_tel_conv, group=1)
    
    remove_tel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(remove_telephony_start, pattern="^mgmt_remove_tel$")],
        states={
            WAITING_TEL_CODE_REMOVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_telephony_process)]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        name='remove_telephony'
    )
    app.add_handler(remove_tel_conv, group=1)
    
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_start, pattern="^mgmt_broadcast$")],
        states={
            WAITING_BROADCAST_MESSAGE: [MessageHandler((filters.ALL & ~filters.COMMAND), broadcast_process)]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        name='broadcast'
    )
    app.add_handler(broadcast_conv, group=1)
    
    logger.info("✅ Management ConversationHandlers (group=1)")
    
    # ===== GROUP 2: MESSAGE HANDLER (ПОСЛЕДНИМ!) =====
    
    app.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND & filters.ChatType.PRIVATE,
        message_handler
    ), group=2)
    logger.info("✅ message_handler (group=2)")
    
    # ===== ERROR HANDLER =====
    app.add_error_handler(error_handler)
    logger.info("✅ error_handler")
    
    logger.info("✅ ВСЕ обработчики зарегистрированы!")
    
    # Логируем количество
    for group_num in [-1, 0, 1, 2]:
        handlers_in_group = app.handlers.get(group_num, [])
        logger.info(f"   Group {group_num}: {len(handlers_in_group)} handler(s)")


def main():
    """Главная функция запуска бота"""
    try:
        logger.info("🚀 Запуск бота...")
        logger.info(f"📋 Менеджеров: {len(settings.MANAGERS)}")
        logger.info(f"👑 Admin ID: {settings.ADMIN_ID}")
        
        # Инициализация БД
        from database.models import db
        logger.info("✅ БД инициализирована")
        
        # Создание приложения
        app = Application.builder().token(settings.BOT_TOKEN).build()
        
        # Регистрация обработчиков
        register_handlers(app)
        
        logger.info("✅ Бот готов к работе!")
        
        # Запуск планировщика
        try:
            from services.scheduler_service import scheduler_service
            
            scheduler_service.set_bot(app.bot)
            
            if not scheduler_service.scheduler.running:
                scheduler_service.start()
                logger.info("✅ Планировщик запущен")
        except Exception as e:
            logger.warning(f"⚠️ Планировщик не запущен: {e}")
        
        # Регистрация shutdown callbacks
        def stop_scheduler():
            try:
                from services.scheduler_service import scheduler_service
                scheduler_service.stop()
            except Exception as e:
                logger.error(f"Ошибка остановки планировщика: {e}")
        
        shutdown_handler.register_callback(stop_scheduler)
        shutdown_handler.setup_handlers()
        
        # Запуск polling
        logger.info("🔄 Запуск polling...")
        app.run_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True
        )
        
    except KeyboardInterrupt:
        logger.info("⌨️ Получен Ctrl+C")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()