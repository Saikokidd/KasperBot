#!/usr/bin/env python3
"""
СКРИПТ ДИАГНОСТИКИ АДМИНИСТРАТИВНОГО ФУНКЦИОНАЛА
Проверяет работоспособность всех критических компонентов

ИСПОЛЬЗОВАНИЕ:
    python3 test_admin_functions.py
"""

import sys
import os
from pathlib import Path

# Цвета для вывода
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def log_ok(msg):
    print(f"{GREEN}✅ {msg}{RESET}")

def log_error(msg):
    print(f"{RED}❌ {msg}{RESET}")

def log_warning(msg):
    print(f"{YELLOW}⚠️  {msg}{RESET}")

def log_info(msg):
    print(f"{BLUE}ℹ️  {msg}{RESET}")

def check_file_structure():
    """Проверка структуры файлов"""
    print("\n" + "="*60)
    print("🔍 ПРОВЕРКА СТРУКТУРЫ ФАЙЛОВ")
    print("="*60 + "\n")
    
    errors = []
    warnings = []
    
    # Критические файлы
    critical_files = {
        "handlers/management.py": "Основной файл управления (было managment.py)",
        "database/models.py": "Модели БД",
        "config/settings.py": "Настройки",
        "main.py": "Главный файл",
        ".env": "Переменные окружения"
    }
    
    for file_path, description in critical_files.items():
        if Path(file_path).exists():
            log_ok(f"{file_path} - {description}")
        else:
            log_error(f"{file_path} ОТСУТСТВУЕТ - {description}")
            errors.append(file_path)
    
    # Проверка старого файла
    if Path("handlers/managment.py").exists():
        log_warning("handlers/managment.py - СТАРЫЙ ФАЙЛ (с опечаткой), нужно переименовать!")
        warnings.append("Старый файл managment.py")
    
    return len(errors) == 0, errors, warnings


def check_database():
    """Проверка БД"""
    print("\n" + "="*60)
    print("🗄️  ПРОВЕРКА БАЗЫ ДАННЫХ")
    print("="*60 + "\n")
    
    errors = []
    
    try:
        from database.models import db
        log_ok("База данных импортирована")
        
        # Проверка таблиц
        conn = db._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['managers', 'telephonies', 'error_reports', 'manager_sips']
        
        for table in required_tables:
            if table in tables:
                log_ok(f"Таблица {table} существует")
            else:
                log_error(f"Таблица {table} ОТСУТСТВУЕТ")
                errors.append(f"Таблица {table}")
        
        # Проверка колонки quick_errors_enabled
        cursor.execute("PRAGMA table_info(telephonies)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "quick_errors_enabled" in columns:
            log_ok("Колонка quick_errors_enabled существует")
        else:
            log_error("Колонка quick_errors_enabled ОТСУТСТВУЕТ - нужна миграция!")
            errors.append("Колонка quick_errors_enabled")
            log_info("Запустите: python3 scripts/add_quick_errors_column.py")
        
        conn.close()
        
    except Exception as e:
        log_error(f"Ошибка проверки БД: {e}")
        errors.append(str(e))
    
    return len(errors) == 0, errors


def check_imports():
    """Проверка импортов"""
    print("\n" + "="*60)
    print("📦 ПРОВЕРКА ИМПОРТОВ")
    print("="*60 + "\n")
    
    errors = []
    
    # Критические импорты
    imports_to_test = [
        ("handlers.management", "Модуль управления (НОВОЕ ИМЯ)"),
        ("handlers.menu", "Обработчики меню"),
        ("handlers.quick_errors", "Быстрые ошибки"),
        ("database.models", "Модели БД"),
        ("config.settings", "Настройки"),
    ]
    
    for module_name, description in imports_to_test:
        try:
            __import__(module_name)
            log_ok(f"{module_name} - {description}")
        except ImportError as e:
            log_error(f"{module_name} - {description}: {e}")
            errors.append(module_name)
    
    # Проверка старого импорта (должен упасть)
    try:
        __import__("handlers.managment")
        log_warning("handlers.managment ИМПОРТИРУЕТСЯ - файл с опечаткой всё ещё существует!")
    except ImportError:
        log_ok("handlers.managment НЕ импортируется (правильно, файл переименован)")
    
    return len(errors) == 0, errors


def check_env_variables():
    """Проверка переменных окружения"""
    print("\n" + "="*60)
    print("🔐 ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ")
    print("="*60 + "\n")
    
    errors = []
    
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = {
        "BOT_TOKEN": "Токен бота",
        "ADMIN_ID": "ID администратора",
        "BMW_GROUP_ID": "ID группы BMW",
        "ZVONARI_GROUP_ID": "ID группы Звонари"
    }
    
    for var_name, description in required_vars.items():
        value = os.getenv(var_name)
        if value:
            # Маскируем токен
            if var_name == "BOT_TOKEN":
                masked_value = value[:10] + "..." + value[-10:]
                log_ok(f"{var_name} = {masked_value} - {description}")
            else:
                log_ok(f"{var_name} = {value} - {description}")
        else:
            log_error(f"{var_name} ОТСУТСТВУЕТ - {description}")
            errors.append(var_name)
    
    return len(errors) == 0, errors


def check_handlers():
    """Проверка обработчиков"""
    print("\n" + "="*60)
    print("🎯 ПРОВЕРКА ОБРАБОТЧИКОВ")
    print("="*60 + "\n")
    
    errors = []
    
    try:
        from handlers.management import (
            show_management_menu,
            managers_menu,
            add_manager_start,
            quick_errors_menu,
            toggle_quick_errors_callback
        )
        log_ok("Все обработчики управления импортируются")
        
        # Проверка что это функции
        if callable(show_management_menu):
            log_ok("show_management_menu - функция")
        else:
            log_error("show_management_menu - НЕ функция")
            errors.append("show_management_menu")
        
        if callable(toggle_quick_errors_callback):
            log_ok("toggle_quick_errors_callback - функция")
        else:
            log_error("toggle_quick_errors_callback - НЕ функция")
            errors.append("toggle_quick_errors_callback")
        
    except Exception as e:
        log_error(f"Ошибка импорта обработчиков: {e}")
        errors.append(str(e))
    
    return len(errors) == 0, errors


def main():
    """Главная функция диагностики"""
    print("\n" + "="*60)
    print("🚨 ДИАГНОСТИКА АДМИНИСТРАТИВНОГО ФУНКЦИОНАЛА")
    print("="*60)
    
    results = {
        "Структура файлов": check_file_structure(),
        "База данных": check_database(),
        "Импорты": check_imports(),
        "Переменные окружения": check_env_variables(),
        "Обработчики": check_handlers()
    }
    
    # Итоги
    print("\n" + "="*60)
    print("📊 ИТОГИ ДИАГНОСТИКИ")
    print("="*60 + "\n")
    
    all_ok = True
    critical_errors = []
    all_warnings = []
    
    for test_name, (passed, errors, *warnings) in results.items():
        if passed:
            log_ok(f"{test_name}: ВСЁ ОК")
        else:
            log_error(f"{test_name}: ОШИБКИ")
            all_ok = False
            critical_errors.extend(errors)
        
        if warnings and warnings[0]:
            all_warnings.extend(warnings[0])
    
    print("\n" + "="*60)
    
    if all_ok and not all_warnings:
        print(f"{GREEN}✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!{RESET}")
        print(f"{GREEN}   Бот готов к запуску в продакшн{RESET}")
        return 0
    elif not all_ok:
        print(f"{RED}❌ ОБНАРУЖЕНЫ КРИТИЧЕСКИЕ ОШИБКИ!{RESET}\n")
        print(f"{RED}Список проблем:{RESET}")
        for error in critical_errors:
            print(f"  {RED}• {error}{RESET}")
        
        print(f"\n{YELLOW}НЕОБХОДИМЫЕ ДЕЙСТВИЯ:{RESET}")
        
        if "handlers/management.py" in critical_errors:
            print(f"  {YELLOW}1. Переименовать файл:{RESET}")
            print(f"     mv handlers/managment.py handlers/management.py")
        
        if "Колонка quick_errors_enabled" in critical_errors:
            print(f"  {YELLOW}2. Запустить миграцию БД:{RESET}")
            print(f"     python3 scripts/add_quick_errors_column.py")
        
        print(f"\n{RED}НЕЛЬЗЯ ЗАПУСКАТЬ В ПРОДАКШН!{RESET}")
        return 1
    else:
        print(f"{YELLOW}⚠️  ЕСТЬ ПРЕДУПРЕЖДЕНИЯ{RESET}\n")
        print(f"{YELLOW}Список предупреждений:{RESET}")
        for warning in all_warnings:
            print(f"  {YELLOW}• {warning}{RESET}")
        
        print(f"\n{GREEN}Можно запускать, но проверьте предупреждения{RESET}")
        return 0


if __name__ == "__main__":
    sys.exit(main())