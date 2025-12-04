"""
Обработчики команд бота
"""
from telegram import Update
from telegram.ext import ContextTypes
from config.constants import MESSAGES
from services.user_service import user_service
from database.models import db
from keyboards.reply import get_manager_menu, get_admin_menu, get_pult_menu
from utils.state import clear_all_states
from utils.logger import logger


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /start
    
    Args:
        update: Update объект
        context: Контекст пользователя
    """
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name or "Пользователь"
    
    # Проверка доступа
    if not user_service.has_access(user_id):
        user_service.log_access_denied(user_id)
        await update.message.reply_text(MESSAGES["access_denied"])
        return
    
    # Очистка всех состояний при старте
    clear_all_states(context)
    
    # ===== АВТООБНОВЛЕНИЕ ИНФОРМАЦИИ В БД =====
    # Если менеджер уже есть в БД, обновляем его username/first_name
    if db.is_manager(user_id):
        try:
            conn = db._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE managers SET username = ?, first_name = ? WHERE user_id = ?",
                (username, first_name, user_id)
            )
            conn.commit()
            conn.close()
            logger.info(f"✅ Обновлены данные менеджера {user_id}: {username}, {first_name}")
        except Exception as e:
            logger.error(f"❌ Ошибка обновления данных менеджера: {e}")
    
    # Автоматическое определение роли (приоритет: админ > пульт > менеджер)
    if user_service.is_admin(user_id):
        # Админ - админ меню
        context.user_data["role"] = "admin"
        user_service.log_user_start(user_id, first_name, "админ")
        
        await update.message.reply_text(
            f"👋 Привет, {first_name}!\n\n"
            f"👑 Режим администратора\n"
            f"Выберите действие из меню:",
            reply_markup=get_admin_menu()
        )
    elif user_service.is_pult(user_id):
        # Пульт - меню пульта
        context.user_data["role"] = "pult"
        user_service.log_user_start(user_id, first_name, "пульт")
        
        await update.message.reply_text(
            f"👋 Привет, {first_name}!\n\n"
            f"📊 Режим пульта\n"
            f"Выберите действие из меню:",
            reply_markup=get_pult_menu()
        )
    else:
        # Менеджер - меню менеджера
        context.user_data["role"] = "manager"
        user_service.log_user_start(user_id, first_name, "менеджер")
        
        await update.message.reply_text(
            f"👋 Привет, {first_name}!\n\n"
            f"Выберите действие из меню:",
            reply_markup=get_manager_menu()
        )