"""
services/user_service.py - ЕДИНЫЙ ИСТОЧНИК ПОЛЬЗОВАТЕЛЕЙ

КРИТИЧЕСКИЕ ИЗМЕНЕНИЯ:
✅ Админы/Пульт - только из .env (безопасность)
✅ Менеджеры - только из БД (управление через бота)
✅ Автомиграция старых MANAGERS_IDS в БД при старте
✅ Логирование источника доступа
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
        
        ЛОГИКА:
        1. Админы из .env - да
        2. Пульт из .env - да
        3. Менеджеры из БД - да
        4. Остальные - нет
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если доступ разрешён
        """
        # 1. Проверяем админов (всегда из .env)
        if user_id in settings.ADMINS:
            logger.debug(f"✅ Доступ: {user_id} - админ (.env)")
            return True
        
        # 2. Проверяем пульт (всегда из .env)
        if user_id in settings.PULT:
            logger.debug(f"✅ Доступ: {user_id} - пульт (.env)")
            return True
        
        # 3. Проверяем менеджеров (ТОЛЬКО из БД)
        if db.is_manager(user_id):
            logger.debug(f"✅ Доступ: {user_id} - менеджер (БД)")
            return True
        
        logger.debug(f"❌ Доступ запрещён: {user_id} - не найден")
        return False
    
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
    def is_manager(user_id: int) -> bool:
        """
        Проверяет, является ли пользователь менеджером
        
        ✅ НОВОЕ: ТОЛЬКО из БД (не из .env)
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если пользователь менеджер
        """
        # Админы и пульт НЕ являются менеджерами
        if user_id in settings.ADMINS or user_id in settings.PULT:
            return False
        
        return db.is_manager(user_id)
    
    @staticmethod
    def get_user_source(user_id: int) -> str:
        """
        ✅ НОВОЕ: Определяет источник доступа пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            "admin_env", "pult_env", "manager_db" или "none"
        """
        if user_id in settings.ADMINS:
            return "admin_env"
        
        if user_id in settings.PULT:
            return "pult_env"
        
        if db.is_manager(user_id):
            return "manager_db"
        
        return "none"
    
    @staticmethod
    def log_access_denied(user_id: int):
        """Логирует попытку доступа без прав"""
        logger.warning(f"❌ Отказ в доступе для user_id={user_id}")
    
    @staticmethod
    def log_user_start(user_id: int, username: str, role: str):
        """Логирует запуск бота пользователем"""
        source = user_service.get_user_source(user_id)
        logger.info(
            f"✅ {role.capitalize()} {user_id} ({username}) запустил бота "
            f"[источник: {source}]"
        )
    
    @staticmethod
    def migrate_env_managers_to_db():
        """
        ✅ НОВОЕ: Миграция старых MANAGERS_IDS из .env в БД
        
        Запускается ОДИН РАЗ при старте бота.
        Добавляет в БД всех менеджеров из settings.MANAGERS,
        которых там ещё нет.
        """
        # Получаем список из .env (если есть старый MANAGERS_IDS)
        managers_from_env = getattr(settings, '_legacy_managers', [])
        
        if not managers_from_env:
            logger.info("ℹ️ Нет старых менеджеров для миграции из .env")
            return
        
        migrated = 0
        skipped = 0
        
        for user_id in managers_from_env:
            # Пропускаем админов и пульт
            if user_id in settings.ADMINS or user_id in settings.PULT:
                continue
            
            # Проверяем есть ли уже в БД
            if db.is_manager(user_id):
                skipped += 1
                continue
            
            # Добавляем в БД
            success = db.add_manager(
                user_id=user_id,
                username=None,  # Будет обновлено при первом /start
                first_name=None,
                added_by=None  # Миграция
            )
            
            if success:
                migrated += 1
                logger.info(f"✅ Мигрирован менеджер из .env: {user_id}")
        
        if migrated > 0:
            logger.info(
                f"✅ Миграция завершена: добавлено {migrated}, "
                f"пропущено {skipped}"
            )


# Глобальный экземпляр сервиса
user_service = UserService()