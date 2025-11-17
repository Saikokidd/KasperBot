"""
Сервис управления ботом (менеджеры, телефонии, рассылка)
"""
from typing import List, Dict, Optional, Tuple
from telegram import Bot, error as telegram_error
from database.models import db
from config.settings import settings
from utils.logger import logger


class ManagementService:
    """Сервис для управления менеджерами, телефониями и рассылок"""
    
    # ===== МЕНЕДЖЕРЫ =====
    
    @staticmethod
    def add_manager(user_id: int, username: str = None, 
                   first_name: str = None, added_by: int = None) -> Tuple[bool, str]:
        """Добавляет менеджера"""
        # Проверка что не админ/пульт
        if user_id in settings.ADMINS:
            return False, "❌ Это администратор! Менеджером сделать нельзя."
        
        if user_id in settings.PULT:
            return False, "❌ Это пульт! Менеджером сделать нельзя."
        
        # Проверка что не добавлен уже
        if db.is_manager(user_id):
            return False, "⚠️ Этот пользователь уже является менеджером."
        
        # Добавление
        success = db.add_manager(user_id, username, first_name, added_by)
        
        if success:
            # Обновляем список в памяти (для быстрого доступа)
            if user_id not in settings.MANAGERS:
                settings.MANAGERS.append(user_id)
            return True, f"✅ Менеджер добавлен!\n\nID: {user_id}"
        else:
            return False, "❌ Ошибка добавления менеджера."
    
    @staticmethod
    def remove_manager(user_id: int) -> Tuple[bool, str]:
        """Удаляет менеджера"""
        if not db.is_manager(user_id):
            return False, "⚠️ Пользователь не является менеджером."
        
        success = db.remove_manager(user_id)
        
        if success:
            # Удаляем из памяти
            if user_id in settings.MANAGERS:
                settings.MANAGERS.remove(user_id)
            return True, f"✅ Менеджер удалён!\n\nID: {user_id}"
        else:
            return False, "❌ Ошибка удаления менеджера."
    
    @staticmethod
    def get_managers_list() -> str:
        """Возвращает форматированный список менеджеров"""
        managers = db.get_all_managers()
        
        if not managers:
            return "📋 Список менеджеров пуст."
        
        text = f"👥 <b>Менеджеры ({len(managers)}):</b>\n\n"
        
        for i, m in enumerate(managers, 1):
            username = f"@{m['username']}" if m['username'] else "без username"
            name = m['first_name'] or "Неизвестно"
            text += f"{i}. <b>{name}</b> ({username})\n"
            text += f"   ID: <code>{m['user_id']}</code>\n\n"
        
        return text
    
    # ===== ТЕЛЕФОНИИ =====
    
    @staticmethod
    def add_telephony(name: str, code: str, tel_type: str, 
                     group_id: int, created_by: int = None) -> Tuple[bool, str]:
        """Добавляет телефонию"""
        # Валидация
        if not name or not code:
            return False, "❌ Название и код обязательны!"
        
        if tel_type not in ['white', 'black']:
            return False, "❌ Тип должен быть 'white' или 'black'!"
        
        # Проверка что group_id валидный
        if not str(group_id).startswith('-'):
            return False, "❌ ID группы должен начинаться с '-' (например: -1001234567890)"
        
        # Добавление
        success = db.add_telephony(name, code, tel_type, group_id, created_by)
        
        if success:
            type_emoji = "⚪️" if tel_type == "white" else "⚫️"
            type_name = "Белая (с кнопками)" if tel_type == "white" else "Чёрная (без кнопок)"
            
            return True, (
                f"✅ Телефония добавлена!\n\n"
                f"📞 Название: <b>{name}</b>\n"
                f"🔑 Код: <code>{code}</code>\n"
                f"{type_emoji} Тип: {type_name}\n"
                f"💬 Группа: <code>{group_id}</code>"
            )
        else:
            return False, "❌ Ошибка: такая телефония или код уже существует!"
    
    @staticmethod
    def remove_telephony(code: str) -> Tuple[bool, str]:
        """Удаляет телефонию"""
        tel = db.get_telephony_by_code(code)
        
        if not tel:
            return False, f"⚠️ Телефония с кодом '{code}' не найдена."
        
        success = db.remove_telephony(code)
        
        if success:
            return True, f"✅ Телефония удалена!\n\n📞 {tel['name']} ({code})"
        else:
            return False, "❌ Ошибка удаления телефонии."
    
    @staticmethod
    def get_telephonies_list() -> str:
        """Возвращает форматированный список телефоний"""
        telephonies = db.get_all_telephonies()
        
        if not telephonies:
            return "📋 Список телефоний пуст."
        
        text = f"📞 <b>Телефонии ({len(telephonies)}):</b>\n\n"
        
        for i, tel in enumerate(telephonies, 1):
            type_emoji = "⚪️" if tel['type'] == "white" else "⚫️"
            type_name = "Белая" if tel['type'] == "white" else "Чёрная"
            
            text += f"{i}. {type_emoji} <b>{tel['name']}</b>\n"
            text += f"   Код: <code>{tel['code']}</code>\n"
            text += f"   Тип: {type_name}\n"
            text += f"   Группа: <code>{tel['group_id']}</code>\n\n"
        
        return text
    
    # ===== РАССЫЛКА =====
    
    @staticmethod
    async def broadcast_message(bot: Bot, message, sent_by: int) -> Dict:
        """Отправляет рассылку всем менеджерам"""
        managers = db.get_all_managers()
        
        stats = {
            "total": len(managers),
            "success": 0,
            "failed": 0,
            "failed_ids": []
        }
        
        for manager in managers:
            user_id = manager['user_id']
            
            try:
                # Копируем сообщение менеджеру
                await message.copy(chat_id=user_id)
                stats["success"] += 1
                logger.info(f"✅ Рассылка отправлена user_id={user_id}")
                
            except telegram_error.TelegramError as e:
                stats["failed"] += 1
                stats["failed_ids"].append(user_id)
                logger.error(f"❌ Не удалось отправить рассылку user_id={user_id}: {e}")
        
        logger.info(
            f"📊 Рассылка завершена: {stats['success']}/{stats['total']} успешно"
        )
        
        return stats


# Глобальный экземпляр сервиса
management_service = ManagementService()