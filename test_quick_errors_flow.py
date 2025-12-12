#!/usr/bin/env python3
"""
Тест работы быстрых ошибок

Проверяет:
1. Есть ли телефонии с quick_errors_enabled=1
2. Правильно ли зарегистрирован ConversationHandler
3. Порядок handlers в main.py
"""

import sys
from pathlib import Path

# Цвета
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


def test_database():
    """Проверка БД"""
    print("\n" + "="*60)
    print("🗄️  ПРОВЕРКА БД")
    print("="*60 + "\n")
    
    errors = []
    
    try:
        from database.models import db
        
        # Проверяем колонку quick_errors_enabled
        conn = db._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(telephonies)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "quick_errors_enabled" not in columns:
            log_error("Колонка quick_errors_enabled НЕ СУЩЕСТВУЕТ!")
            log_info("Запустите: python3 scripts/add_quick_errors_column.py")
            errors.append("Колонка quick_errors_enabled")
            conn.close()
            return False, errors
        
        log_ok("Колонка quick_errors_enabled существует")
        
        # Проверяем телефонии с quick_errors
        cursor.execute("""
            SELECT name, code, quick_errors_enabled 
            FROM telephonies 
            WHERE type = 'white'
            ORDER BY name
        """)
        
        white_tels = cursor.fetchall()
        
        if not white_tels:
            log_warning("Нет белых телефоний в БД")
            log_info("Добавьте белую телефонию через 'Управление ботом'")
        else:
            log_info(f"Найдено белых телефоний: {len(white_tels)}")
            
            for name, code, qe_enabled in white_tels:
                status = "✅ Включены" if qe_enabled else "❌ Выключены"
                print(f"   • {name} ({code}): быстрые ошибки {status}")
            
            # Проверяем есть ли хотя бы одна с включёнными
            enabled_count = sum(1 for _, _, qe in white_tels if qe)
            
            if enabled_count == 0:
                log_warning("Быстрые ошибки ВЫКЛЮЧЕНЫ для всех телефоний")
                log_info("Включите через: Управление ботом → Быстрые ошибки")
            else:
                log_ok(f"Быстрые ошибки включены для {enabled_count} телефоний")
        
        conn.close()
        
    except Exception as e:
        log_error(f"Ошибка проверки БД: {e}")
        errors.append(str(e))
    
    return len(errors) == 0, errors


def test_handlers():
    """Проверка handlers"""
    print("\n" + "="*60)
    print("🎯 ПРОВЕРКА HANDLERS")
    print("="*60 + "\n")
    
    errors = []
    
    try:
        from handlers.quick_errors import get_quick_errors_conv, get_quick_errors_telephony_names
        
        log_ok("Модуль quick_errors импортирован")
        
        # Проверяем что функция возвращает ConversationHandler
        conv = get_quick_errors_conv()
        
        if conv is None:
            log_warning("get_quick_errors_conv() вернул None")
            log_info("Проверьте что есть телефонии с quick_errors_enabled=1")
        else:
            log_ok("ConversationHandler создан")
            
            # Проверяем entry_points
            entry_points = conv.entry_points
            log_info(f"Entry points: {len(entry_points)}")
            
            for ep in entry_points:
                print(f"   • {type(ep).__name__}")
            
            # Проверяем состояния
            states = conv.states
            log_info(f"Состояний: {len(states)}")
        
        # Проверяем список телефоний
        telephony_names = get_quick_errors_telephony_names()
        
        if telephony_names:
            log_ok(f"Телефонии с быстрыми ошибками: {', '.join(telephony_names)}")
        else:
            log_warning("Нет телефоний с быстрыми ошибками")
            log_info("Это нормально если вы их не включали")
        
    except Exception as e:
        log_error(f"Ошибка проверки handlers: {e}")
        errors.append(str(e))
    
    return len(errors) == 0, errors


def test_main_structure():
    """Проверка структуры main.py"""
    print("\n" + "="*60)
    print("📝 ПРОВЕРКА MAIN.PY")
    print("="*60 + "\n")
    
    errors = []
    
    try:
        # Читаем main.py
        main_path = Path("main.py")
        
        if not main_path.exists():
            log_error("main.py не найден!")
            errors.append("main.py")
            return False, errors
        
        with open(main_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем импорт
        if "from handlers.quick_errors import get_quick_errors_conv" in content:
            log_ok("Импорт get_quick_errors_conv найден")
        else:
            log_error("Импорт get_quick_errors_conv НЕ НАЙДЕН!")
            errors.append("Импорт")
        
        # Проверяем вызов
        if "quick_errors_conv = get_quick_errors_conv()" in content:
            log_ok("Вызов get_quick_errors_conv() найден")
        else:
            log_error("Вызов get_quick_errors_conv() НЕ НАЙДЕН!")
            errors.append("Вызов")
        
        # Проверяем регистрацию
        if "app.add_handler(quick_errors_conv, group=0)" in content:
            log_ok("Регистрация в group=0 найдена")
        elif "app.add_handler(quick_errors_conv, group=1)" in content:
            log_error("quick_errors в group=1 вместо group=0!")
            log_info("КРИТИЧНО: Должен быть в group=0 (ДО message_handler)")
            errors.append("Неверная группа")
        else:
            log_error("Регистрация quick_errors НЕ НАЙДЕНА!")
            errors.append("Регистрация")
        
        # Проверяем порядок
        qe_pos = content.find("app.add_handler(quick_errors_conv")
        msg_pos = content.find("app.add_handler(MessageHandler")
        
        if qe_pos > 0 and msg_pos > 0:
            if qe_pos < msg_pos:
                log_ok("quick_errors ПЕРЕД message_handler (правильно)")
            else:
                log_error("quick_errors ПОСЛЕ message_handler (НЕПРАВИЛЬНО!)")
                log_info("quick_errors должен быть ПЕРЕД message_handler")
                errors.append("Неверный порядок")
        
    except Exception as e:
        log_error(f"Ошибка проверки main.py: {e}")
        errors.append(str(e))
    
    return len(errors) == 0, errors


def test_messages_py():
    """Проверка messages.py"""
    print("\n" + "="*60)
    print("📨 ПРОВЕРКА MESSAGES.PY")
    print("="*60 + "\n")
    
    errors = []
    
    try:
        messages_path = Path("handlers/messages.py")
        
        if not messages_path.exists():
            log_error("handlers/messages.py не найден!")
            errors.append("messages.py")
            return False, errors
        
        with open(messages_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем что НЕТ handle_telephony_choice
        if "def handle_telephony_choice" in content:
            log_error("handle_telephony_choice ВСЁ ЕЩЁ ЕСТЬ!")
            log_info("Удалите эту функцию - она конфликтует с quick_errors")
            errors.append("handle_telephony_choice")
        else:
            log_ok("handle_telephony_choice удалена (правильно)")
        
        # Проверяем что НЕТ вызова handle_telephony_choice
        if "await handle_telephony_choice" in content:
            log_error("Вызов handle_telephony_choice ВСЁ ЕЩЁ ЕСТЬ!")
            errors.append("Вызов handle_telephony_choice")
        else:
            log_ok("Вызов handle_telephony_choice удалён (правильно)")
        
    except Exception as e:
        log_error(f"Ошибка проверки messages.py: {e}")
        errors.append(str(e))
    
    return len(errors) == 0, errors


def main():
    """Главная функция теста"""
    print("\n" + "="*60)
    print("🧪 ТЕСТ СИСТЕМЫ БЫСТРЫХ ОШИБОК")
    print("="*60)
    
    results = {
        "База данных": test_database(),
        "Handlers": test_handlers(),
        "main.py": test_main_structure(),
        "messages.py": test_messages_py()
    }
    
    # Итоги
    print("\n" + "="*60)
    print("📊 ИТОГИ ТЕСТА")
    print("="*60 + "\n")
    
    all_ok = True
    critical_errors = []
    
    for test_name, (passed, errors) in results.items():
        if passed:
            log_ok(f"{test_name}: ПРОЙДЕН")
        else:
            log_error(f"{test_name}: ОШИБКИ")
            all_ok = False
            critical_errors.extend(errors)
    
    print("\n" + "="*60)
    
    if all_ok:
        print(f"{GREEN}✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!{RESET}")
        print(f"{GREEN}   Система быстрых ошибок готова к использованию{RESET}")
        print(f"\n{BLUE}ℹ️  Как использовать:{RESET}")
        print(f"   1. Включите быстрые ошибки: Управление ботом → Быстрые ошибки")
        print(f"   2. Выберите телефонию (BMW, Звонари и т.д.)")
        print(f"   3. Укажите SIP (один раз в день)")
        print(f"   4. Выбирайте ошибки из кнопок")
        return 0
    else:
        print(f"{RED}❌ ОБНАРУЖЕНЫ ОШИБКИ!{RESET}\n")
        print(f"{RED}Список проблем:{RESET}")
        for error in critical_errors:
            print(f"  {RED}• {error}{RESET}")
        
        print(f"\n{YELLOW}НЕОБХОДИМЫЕ ДЕЙСТВИЯ:{RESET}")
        
        if "Колонка quick_errors_enabled" in critical_errors:
            print(f"  {YELLOW}1. Добавить колонку в БД:{RESET}")
            print(f"     python3 scripts/add_quick_errors_column.py")
        
        if "handle_telephony_choice" in critical_errors:
            print(f"  {YELLOW}2. Заменить handlers/messages.py{RESET}")
            print(f"     Используйте артефакт messages_minimal")
        
        if any("main.py" in e for e in critical_errors):
            print(f"  {YELLOW}3. Заменить main.py{RESET}")
            print(f"     Используйте артефакт main_fixed")
        
        if "handlers/quick_errors.py" in str(critical_errors):
            print(f"  {YELLOW}4. Заменить handlers/quick_errors.py{RESET}")
            print(f"     Используйте артефакт quick_errors_final")
        
        print(f"\n{RED}ПОСЛЕ ИСПРАВЛЕНИЙ ЗАПУСТИТЕ ТЕСТ СНОВА!{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())