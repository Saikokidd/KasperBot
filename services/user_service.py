"""
Сервис для работы с пользователями
"""
from config.settings import settings
from database.models import db
from utils.logger import logger


class UserService:
    """Сервис для управления пользователями и их правами"""
    
    @staticmethod
    def has_access(user_id: int) -> bool:
        """
        Проверяет, есть ли у пользователя доступ к боту
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если доступ разрешён
        """
        # Проверяем в .env (админы, пульт, старые менеджеры)
        if user_id in settings.MANAGERS:
            return True
        
        # Проверяем в БД (новые менеджеры)
        return db.is_manager(user_id)
    
    @staticmethod
    def is_admin(user_id: int) -> bool:
        """
        Проверяет, является ли пользователь администратором
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если пользователь админ
        """
        return user_id in settings.ADMINS
    
    @staticmethod
    def is_pult(user_id: int) -> bool:
        """
        Проверяет, является ли пользователь пультом
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если пользователь пульт
        """
        return user_id in settings.PULT
    
    @staticmethod
    def log_access_denied(user_id: int):
        """
        Логирует попытку доступа без прав
        
        Args:
            user_id: ID пользователя
        """
        logger.warning(f"❌ Отказ в доступе для user_id={user_id}")
    
    @staticmethod
    def log_user_start(user_id: int, username: str, role: str):
        """
        Логирует запуск бота пользователем
        
        Args:
            user_id: ID пользователя
            username: Имя пользователя
            role: Роль пользователя
        """
        logger.info(f"✅ {role.capitalize()} {user_id} ({username}) запустил бота")


# Глобальный экземпляр сервиса
user_service = UserService()