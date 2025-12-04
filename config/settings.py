"""
УЛУЧШЕНО: config/settings.py
Добавлена полная валидация всех переменных окружения

ИЗМЕНЕНИЯ:
✅ Валидация GOOGLE_APPS_SCRIPT_URL
✅ Валидация GOOGLE_SHEETS_ID
✅ Проверка формата ID групп
✅ Улучшенные сообщения об ошибках
"""
import os
from dotenv import load_dotenv
from typing import Dict, List

# Загрузка переменных окружения
load_dotenv()


class Settings:
    """Класс для хранения всех настроек бота"""
    
    def __init__(self):
        self._validate_env()
        self._load_env()
        self._parse_managers()
        self._parse_admins()
        self._parse_pult()
        self._validate_optional_env()
    
    def _validate_env(self):
        """Проверка наличия всех ОБЯЗАТЕЛЬНЫХ переменных окружения"""
        required = {
            "BOT_TOKEN": os.getenv("BOT_TOKEN"),
            "ADMIN_ID": os.getenv("ADMIN_ID"),
            "BMW_GROUP_ID": os.getenv("BMW_GROUP_ID"),
            "ZVONARI_GROUP_ID": os.getenv("ZVONARI_GROUP_ID")
        }
        
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ValueError(f"❌ Отсутствуют ОБЯЗАТЕЛЬНЫЕ переменные в .env: {', '.join(missing)}")
        
        # ✅ НОВОЕ: Валидация формата токена
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token or ":" not in bot_token:
            raise ValueError("❌ Неверный формат BOT_TOKEN (должен быть вида: 123456789:ABC...)")
        
        # ✅ НОВОЕ: Валидация ID групп (должны начинаться с "-")
        bmw_group = os.getenv("BMW_GROUP_ID")
        zvon_group = os.getenv("ZVONARI_GROUP_ID")
        
        if not bmw_group.startswith("-"):
            raise ValueError(f"❌ BMW_GROUP_ID должен начинаться с '-' (сейчас: {bmw_group})")
        
        if not zvon_group.startswith("-"):
            raise ValueError(f"❌ ZVONARI_GROUP_ID должен начинаться с '-' (сейчас: {zvon_group})")
    
    def _validate_optional_env(self):
        """
        ✅ НОВОЕ: Проверка опциональных переменных окружения
        Выводит предупреждения если они не настроены
        """
        from utils.logger import logger
        
        warnings = []
        
        # Google Sheets URL
        if not self.GOOGLE_APPS_SCRIPT_URL:
            warnings.append("GOOGLE_APPS_SCRIPT_URL не настроен - статистика трубок не будет работать")
        elif not (self.GOOGLE_APPS_SCRIPT_URL.startswith("http://") or 
                  self.GOOGLE_APPS_SCRIPT_URL.startswith("https://")):
            warnings.append(f"GOOGLE_APPS_SCRIPT_URL имеет неверный формат: {self.GOOGLE_APPS_SCRIPT_URL}")
        
        # Google Sheets ID
        google_sheets_id = os.getenv("GOOGLE_SHEETS_ID")
        if not google_sheets_id:
            warnings.append("GOOGLE_SHEETS_ID не настроен - автообновление статистики не будет работать")
        
        # Google Credentials
        google_creds = os.getenv("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")
        if not os.path.exists(google_creds):
            warnings.append(f"Файл {google_creds} не найден - Google Sheets интеграция не будет работать")
        
        # Выводим предупреждения
        if warnings:
            logger.warning("⚠️ Обнаружены проблемы с конфигурацией:")
            for warning in warnings:
                logger.warning(f"   • {warning}")
            logger.warning("⚠️ Некоторые функции могут быть недоступны")
    
    def _load_env(self):
        """Загрузка переменных окружения"""
        self.BOT_TOKEN = os.getenv("BOT_TOKEN")
        self.ADMIN_ID = int(os.getenv("ADMIN_ID"))
        self.BMW_GROUP_ID = int(os.getenv("BMW_GROUP_ID"))
        self.ZVONARI_GROUP_ID = int(os.getenv("ZVONARI_GROUP_ID"))
        self.GOOGLE_APPS_SCRIPT_URL = os.getenv("GOOGLE_APPS_SCRIPT_URL", "")
    
    def _parse_managers(self):
        """Парсинг списка менеджеров из .env"""
        managers_str = os.getenv("MANAGERS_IDS", "")
        self.MANAGERS = [
            int(id.strip()) 
            for id in managers_str.split(",") 
            if id.strip().isdigit()
        ]
        
        # Добавляем админа в список менеджеров, если его там нет
        if self.ADMIN_ID not in self.MANAGERS:
            self.MANAGERS.append(self.ADMIN_ID)
    
    def _parse_admins(self):
        """Парсинг списка админов из .env"""
        admins_str = os.getenv("ADMIN_IDS", "")
        
        if admins_str:
            # Если есть ADMIN_IDS - используем его
            self.ADMINS = [
                int(id.strip()) 
                for id in admins_str.split(",") 
                if id.strip().isdigit()
            ]
        else:
            # Иначе используем старый ADMIN_ID
            self.ADMINS = [self.ADMIN_ID]
        
        # Добавляем всех админов в менеджеры
        for admin_id in self.ADMINS:
            if admin_id not in self.MANAGERS:
                self.MANAGERS.append(admin_id)
    
    def _parse_pult(self):
        """Парсинг списка пульта из .env"""
        pult_str = os.getenv("PULT_IDS", "")
        
        if pult_str:
            self.PULT = [
                int(id.strip()) 
                for id in pult_str.split(",") 
                if id.strip().isdigit()
            ]
        else:
            self.PULT = []
        
        # Добавляем пульт в менеджеры
        for pult_id in self.PULT:
            if pult_id not in self.MANAGERS:
                self.MANAGERS.append(pult_id)
    
    def get_telephony_groups(self) -> Dict[str, int]:
        """Возвращает маппинг телефонии на группы"""
        return {
            "BMW": self.BMW_GROUP_ID,
            "Звонари": self.ZVONARI_GROUP_ID
        }
    
    def validate_runtime(self) -> List[str]:
        """
        ✅ НОВОЕ: Проверка конфигурации во время работы
        
        Returns:
            Список проблем (пустой если всё ОК)
        """
        issues = []
        
        # Проверка доступности групп (можно расширить)
        if self.BMW_GROUP_ID == self.ZVONARI_GROUP_ID:
            issues.append("BMW_GROUP_ID и ZVONARI_GROUP_ID одинаковые!")
        
        # Проверка что есть хотя бы один менеджер
        if not self.MANAGERS:
            issues.append("Нет ни одного менеджера в системе!")
        
        # Проверка что есть хотя бы один админ
        if not self.ADMINS:
            issues.append("Нет ни одного админа в системе!")
        
        return issues


# Создаём глобальный экземпляр настроек
try:
    settings = Settings()
    
    # ✅ НОВОЕ: Проверяем runtime проблемы
    runtime_issues = settings.validate_runtime()
    if runtime_issues:
        from utils.logger import logger
        logger.warning("⚠️ Обнаружены проблемы конфигурации:")
        for issue in runtime_issues:
            logger.warning(f"   • {issue}")
except Exception as e:
    print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось загрузить настройки!")
    print(f"   Причина: {e}")
    print(f"   Проверьте файл .env и убедитесь что все обязательные переменные установлены")
    raise