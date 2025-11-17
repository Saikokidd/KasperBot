"""
Главная точка входа для запуска Telegram бота
Совместим с bash-скриптами: start.sh, stop.sh, status.sh
"""
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)
from config.settings import settings
from utils.logger import logger

# Импортируем обработчики
from handlers.commands import start_command
from handlers.callbacks import (
    role_choice_callback,
    tel_choice_callback,
    support_callback,
    fallback_callback
)
from handlers.messages import message_handler
from handlers.errors import error_handler

# Импортируем обработчики управления
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
    WAITING_MANAGER_ID, WAITING_MANAGER_ID_REMOVE,
    WAITING_TEL_NAME, WAITING_TEL_CODE, WAITING_TEL_TYPE, WAITING_TEL_GROUP,
    WAITING_TEL_CODE_REMOVE, WAITING_BROADCAST_MESSAGE
)


def register_handlers(app: Application):
    """
    Регистрирует все обработчики бота
    
    Args:
        app: Экземпляр Application
    """
    # Команды
    app.add_handler(CommandHandler("start", start_command))
    
    # ===== CONVERSATION HANDLERS ДЛЯ УПРАВЛЕНИЯ =====
    
    # Добавление менеджера
    add_manager_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_manager_start, pattern="^mgmt_add_manager$")],
        states={
            WAITING_MANAGER_ID: [MessageHandler(filters.TEXT | filters.FORWARDED, add_manager_process)]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )
    app.add_handler(add_manager_conv)
    
    # Удаление менеджера
    remove_manager_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(remove_manager_start, pattern="^mgmt_remove_manager$")],
        states={
            WAITING_MANAGER_ID_REMOVE: [MessageHandler(filters.TEXT, remove_manager_process)]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )
    app.add_handler(remove_manager_conv)
    
    # Добавление телефонии
    add_tel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_telephony_start, pattern="^mgmt_add_tel$")],
        states={
            WAITING_TEL_NAME: [MessageHandler(filters.TEXT, add_telephony_name)],
            WAITING_TEL_CODE: [MessageHandler(filters.TEXT, add_telephony_code)],
            WAITING_TEL_TYPE: [CallbackQueryHandler(add_telephony_type, pattern="^tel_type_")],
            WAITING_TEL_GROUP: [MessageHandler(filters.TEXT, add_telephony_group)]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )
    app.add_handler(add_tel_conv)
    
    # Удаление телефонии
    remove_tel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(remove_telephony_start, pattern="^mgmt_remove_tel$")],
        states={
            WAITING_TEL_CODE_REMOVE: [MessageHandler(filters.TEXT, remove_telephony_process)]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )
    app.add_handler(remove_tel_conv)
    
    # Рассылка
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_start, pattern="^mgmt_broadcast$")],
        states={
            WAITING_BROADCAST_MESSAGE: [MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_process)]
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )
    app.add_handler(broadcast_conv)
    
    # ===== CALLBACK HANDLERS ДЛЯ УПРАВЛЕНИЯ =====
    
    app.add_handler(CallbackQueryHandler(show_management_menu, pattern="^mgmt_menu$"))
    app.add_handler(CallbackQueryHandler(managers_menu, pattern="^mgmt_managers$"))
    app.add_handler(CallbackQueryHandler(list_managers, pattern="^mgmt_list_managers$"))
    app.add_handler(CallbackQueryHandler(telephonies_menu, pattern="^mgmt_telephonies$"))
    app.add_handler(CallbackQueryHandler(list_telephonies, pattern="^mgmt_list_tel$"))
    app.add_handler(CallbackQueryHandler(broadcast_confirm, pattern="^broadcast_confirm$"))
    
    # ===== ОСНОВНЫЕ CALLBACK ОБРАБОТЧИКИ =====
    
    app.add_handler(CallbackQueryHandler(role_choice_callback, pattern="^role_"))
    app.add_handler(CallbackQueryHandler(tel_choice_callback, pattern="^tel_"))
    app.add_handler(CallbackQueryHandler(support_callback, pattern="^(fix|wait|wrong|sim)_"))
    app.add_handler(CallbackQueryHandler(fallback_callback))
    
    # Обработчик сообщений
    app.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND & filters.ChatType.PRIVATE,
        message_handler
    ))
    
    # Обработчик ошибок
    app.add_error_handler(error_handler)


def main():
    """
    Главная функция запуска бота
    Совместима с bash-скриптами для управления ботом
    """
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
        
        # Запуск polling
        app.run_polling(allowed_updates=["message", "callback_query"])
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске бота: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()