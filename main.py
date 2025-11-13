"""
Главная точка входа для запуска Telegram бота
Совместим с bash-скриптами: start.sh, stop.sh, status.sh
"""
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters
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


def register_handlers(app: Application):
    """
    Регистрирует все обработчики бота
    
    Args:
        app: Экземпляр Application
    """
    # Команды
    app.add_handler(CommandHandler("start", start_command))
    
    # Callback обработчики (порядок важен!)
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
        logger.info(f"📞 Телефонии: {', '.join(settings.get_telephony_groups().keys())}")
        
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