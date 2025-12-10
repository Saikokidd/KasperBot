"""
ИСПРАВЛЕННАЯ ВЕРСИЯ: main.py
Исправлены критические проблемы с handler'ами

КРИТИЧЕСКИЕ ИЗМЕНЕНИЯ:
✅ Исправлен импорт handlers/management (было managment)
✅ ConversationHandler'ы в group=1 (не блокируют callback)
✅ Inline callback'ы в group=0 (более высокий приоритет)
✅ fallback_callback СТРОГО в конце
✅ Добавлено подробное логирование
"""
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)
from config.settings import settings
from utils.logger import logger
from utils.shutdown import shutdown_handler

# Импортируем обработчики
from handlers.commands import start_command
from handlers.health import health_command
from handlers.callbacks import (
    role_choice_callback,
    tel_choice_callback,
    support_callback,
    fallback_callback
)
from handlers.messages import message_handler
from handlers.errors import error_handler

# ✅ ИСПРАВЛЕНО: Правильное имя файла
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

# Импортируем обработчики аналитики
from handlers.analytics import (
    show_errors_stats_menu, show_general_stats, show_general_stats_period,
    show_managers_stats, show_managers_stats_period,
    show_support_stats, show_support_stats_period,
    show_response_time_stats, show_response_time_stats_period,
    show_dashboard_start, show_dashboard_page
)

# Импортируем ConversationHandler для быстрых ошибок
from handlers.quick_errors import quick_errors_conv, get_quick_errors_telephony_names


def register_handlers(app: Application):
    """
    Регистрирует все обработчики бота
    
    ✅ ИСПРАВЛЕНО: Правильный порядок с group приоритетами
    
    Args:
        app: Экземпляр Application
    """
    logger.info("🔧 Начало регистрации обработчиков...")
    
    # ===== GROUP -1: КОМАНДЫ (Наивысший приоритет) =====
    app.add_handler(CommandHandler("start", start_command), group=-1)
    app.add_handler(CommandHandler("health", health_command), group=-1)
    logger.info("✅ Команды зарегистрированы (group=-1)")
    
    # ===== GROUP 0: INLINE CALLBACK HANDLERS (Высокий приоритет) =====
    
    # Управление - СПЕЦИФИЧНЫЕ callback ПЕРВЫМИ
    app.add_handler(CallbackQueryHandler(show_management_menu, pattern="^mgmt_menu$"), group=0)
    app.add_handler(CallbackQueryHandler(quick_errors_menu, pattern="^mgmt_quick_errors$"), group=0)
    app.add_handler(CallbackQueryHandler(toggle_quick_errors_callback, pattern="^toggle_qe_"), group=0)
    app.add_handler(CallbackQueryHandler(show_quick_errors_info, pattern="^qe_info$"), group=0)
    app.add_handler(CallbackQueryHandler(managers_menu, pattern="^mgmt_managers$"), group=0)
    app.add_handler(CallbackQueryHandler(list_managers, pattern="^mgmt_list_managers$"), group=0)
    app.add_handler(CallbackQueryHandler(telephonies_menu, pattern="^mgmt_telephonies$"), group=0)
    app.add_handler(CallbackQueryHandler(list_telephonies, pattern="^mgmt_list_tel$"), group=0)
    app.add_handler(CallbackQueryHandler(broadcast_confirm, pattern="^broadcast_confirm$"), group=0)
    logger.info("✅ Callback управления зарегистрированы (group=0)")
    
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
    logger.info("✅ Callback статистики зарегистрированы (group=0)")
    
    # Основные callback
    app.add_handler(CallbackQueryHandler(role_choice_callback, pattern="^role_"), group=0)
    app.add_handler(CallbackQueryHandler(tel_choice_callback, pattern="^tel_"), group=0)
    app.add_handler(CallbackQueryHandler(support_callback, pattern="^(fix|wait|wrong|sim)_"), group=0)
    logger.info("✅ Основные callback зарегистрированы (group=0)")
    
    # ===== GROUP 1: CONVERSATION HANDLERS (Средний приоритет) =====
    
    # ✅ КРИТИЧЕСКОЕ ИЗМЕНЕНИЕ: ConversationHandler'ы в отдельном group
    # Это предотвращает блокировку inline callback'ов
    
    # Добавление менеджера
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
    
    # Удаление менеджера
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
    
    # Добавление телефонии
    add_tel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_telephony_start, pattern="^mgmt_add_tel$")],
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
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        name='add_telephony'
    )
    app.add_handler(add_tel_conv, group=1)
    
    # Удаление телефонии
    remove_tel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(remove_telephony_start, pattern="^mgmt_remove_tel$")],
        states={
            WAITING_TEL_CODE_REMOVE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, remove_telephony_process)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        name='remove_telephony'
    )
    app.add_handler(remove_tel_conv, group=1)
    
    # Рассылка
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_start, pattern="^mgmt_broadcast$")],
        states={
            WAITING_BROADCAST_MESSAGE: [
                MessageHandler((filters.ALL & ~filters.COMMAND), broadcast_process)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        name='broadcast'
    )
    app.add_handler(broadcast_conv, group=1)
    
    logger.info("✅ ConversationHandler'ы управления зарегистрированы (group=1)")
    
    # Быстрые ошибки
    if quick_errors_conv:
        app.add_handler(quick_errors_conv, group=1)
        logger.info("✅ ConversationHandler быстрых ошибок зарегистрирован (group=1)")
        
        telephony_names = get_quick_errors_telephony_names()
        if telephony_names:
            logger.info(f"📞 Быстрые ошибки доступны для: {', '.join(telephony_names)}")
    else:
        logger.warning("⚠️ Система быстрых ошибок отключена")
    
    # ===== GROUP 2: MESSAGE HANDLERS (Низкий приоритет) =====
    
    app.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND & filters.ChatType.PRIVATE,
        message_handler
    ), group=2)
    logger.info("✅ Message handler зарегистрирован (group=2)")
    
    # ===== FALLBACK CALLBACK ВРЕМЕННО ОТКЛЮЧЁН =====
    # ❌ ПРОБЛЕМА: fallback_callback блокирует другие handler'ы
    # Он вызывает query.answer() первым, после чего специфичные handler'ы
    # не могут обновить сообщение
    
    # TODO: Исправить fallback_callback чтобы он не блокировал
    # app.add_handler(CallbackQueryHandler(fallback_callback), group=10)
    logger.info("⚠️ Fallback callback ОТКЛЮЧЁН (блокирует другие handler'ы)")
    
    # ===== ERROR HANDLER =====
    app.add_error_handler(error_handler)
    logger.info("✅ Error handler зарегистрирован")
    
    logger.info("✅ ВСЕ обработчики зарегистрированы успешно!")
    
    # ✅ НОВОЕ: Логируем количество handler'ов в каждом group
    for group_num in [-1, 0, 1, 2, 10]:
        handlers_in_group = [h for h in app.handlers.get(group_num, [])]
        logger.info(f"   Group {group_num}: {len(handlers_in_group)} handler(s)")


def main():
    """Главная функция запуска бота"""
    try:
        logger.info("🚀 Запуск бота...")
        logger.info(f"📋 Менеджеров в системе: {len(settings.MANAGERS)}")
        logger.info(f"👑 Admin ID: {settings.ADMIN_ID}")
        
        # Инициализация БД
        from database.models import db
        logger.info("✅ База данных инициализирована")
        
        # Создание приложения
        app = Application.builder().token(settings.BOT_TOKEN).build()
        
        # Регистрация обработчиков
        register_handlers(app)
        
        logger.info("✅ Бот успешно запущен и готов к работе!")
        
        # ===== ЗАПУСК ПЛАНИРОВЩИКА =====
        try:
            from services.scheduler_service import scheduler_service
            
            scheduler_service.set_bot(app.bot)
            
            if not scheduler_service.scheduler.running:
                scheduler_service.start()
                logger.info("✅ Планировщик задач настроен")
            else:
                logger.info("✅ Планировщик уже запущен")
        except Exception as e:
            logger.warning(f"⚠️ Планировщик не запущен: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # ===== РЕГИСТРАЦИЯ SHUTDOWN CALLBACKS =====
        def stop_scheduler():
            try:
                from services.scheduler_service import scheduler_service
                scheduler_service.stop()
            except Exception as e:
                logger.error("Ошибка остановки планировщика: %s", e)
        
        def stop_application():
            try:
                logger.info("Остановка Telegram приложения...")
            except Exception as e:
                logger.error("Ошибка остановки приложения: %s", e)
        
        shutdown_handler.register_callback(stop_scheduler)
        shutdown_handler.register_callback(stop_application)
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
        logger.error(f"❌ Критическая ошибка при запуске бота: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()