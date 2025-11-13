"""
Конфигурация бота: загрузка переменных окружения и валидация
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
    
    def _validate_env(self):
        """Проверка наличия всех необходимых переменных окружения"""
        required = {
            "BOT_TOKEN": os.getenv("BOT_TOKEN"),
            "ADMIN_ID": os.getenv("ADMIN_ID"),
            "BMW_GROUP_ID": os.getenv("BMW_GROUP_ID"),
            "ZVONARI_GROUP_ID": os.getenv("ZVONARI_GROUP_ID")
        }
        
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ValueError(f"❌ Отсутствуют переменные в .env: {', '.join(missing)}")
    
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


# Создаём глобальный экземпляр настроек
settings = Settings()