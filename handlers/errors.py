"""
Глобальный обработчик ошибок бота
"""
from telegram import Update
from telegram.ext import ContextTypes
from utils.logger import logger


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Глобальный обработчик ошибок
    
    Args:
        update: Update объект
        context: Контекст с информацией об ошибке
    """
    logger.error(
        f"❌ Exception while handling an update: {context.error}",
        exc_info=context.error
    )
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ Произошла ошибка при обработке вашего запроса.\n"
                "Попробуйте снова или обратитесь в поддержку."
            )
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке сообщения об ошибке: {e}")
