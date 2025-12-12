#!/usr/bin/env python3
"""
Диагностика проблемы с выбором телефонии
"""
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

print("="*60)
print("🔍 ДИАГНОСТИКА ПРОБЛЕМЫ С ТЕЛЕФОНИЕЙ")
print("="*60)

# ===== 1. ПРОВЕРКА БД =====
print("\n1️⃣ ПРОВЕРКА БАЗЫ ДАННЫХ")
print("-"*60)

try:
    from database.models import db
    
    # Все телефонии
    all_tels = db.get_all_telephonies()
    print(f"📋 Всего телефоний в БД: {len(all_tels)}")
    
    for tel in all_tels:
        qe_status = "✅ ВКЛ" if tel.get('quick_errors_enabled') else "❌ ВЫКЛ"
        print(f"   • {tel['name']} ({tel['code']}) - Быстрые ошибки: {qe_status}")
    
    # Телефонии с quick_errors
    qe_tels = db.get_quick_errors_telephonies()
    print(f"\n📊 Телефоний с ВКЛЮЧЁННЫМИ быстрыми ошибками: {len(qe_tels)}")
    
    for tel in qe_tels:
        print(f"   ✅ {tel['name']} ({tel['code']})")
    
    if not qe_tels:
        print("   ⚠️ НЕТ телефоний с включёнными быстрыми ошибками!")
        print("   ℹ️ Все телефонии будут обрабатываться через message_handler")
    
except Exception as e:
    print(f"❌ Ошибка проверки БД: {e}")
    import traceback
    traceback.print_exc()

# ===== 2. ПРОВЕРКА HANDLERS =====
print("\n2️⃣ ПРОВЕРКА HANDLERS")
print("-"*60)

try:
    from handlers.quick_errors import (
        get_quick_errors_telephony_names,
        get_quick_errors_conv
    )
    
    # Имена телефоний для ConversationHandler
    qe_names = get_quick_errors_telephony_names()
    print(f"📝 Телефонии для ConversationHandler: {qe_names}")
    
    if not qe_names:
        print("   ⚠️ Список ПУСТОЙ - ConversationHandler будет None")
    else:
        print(f"   ✅ ConversationHandler будет слушать: {', '.join(qe_names)}")
    
    # Проверяем ConversationHandler
    conv = get_quick_errors_conv()
    
    if conv is None:
        print("   ⚠️ get_quick_errors_conv() вернул None")
        print("   ℹ️ Все телефонии будут обрабатываться message_handler")
    else:
        print(f"   ✅ ConversationHandler создан")
        print(f"   Entry points: {len(conv.entry_points)}")
        
        # Проверяем фильтры
        for ep in conv.entry_points:
            print(f"      • {type(ep).__name__}")
            if hasattr(ep, 'filters'):
                print(f"        Фильтр: {ep.filters}")
    
except Exception as e:
    print(f"❌ Ошибка проверки handlers: {e}")
    import traceback
    traceback.print_exc()

# ===== 3. ПРОВЕРКА MESSAGES.PY =====
print("\n3️⃣ ПРОВЕРКА MESSAGES.PY")
print("-"*60)

try:
    messages_path = Path("handlers/messages.py")
    
    if not messages_path.exists():
        print("❌ handlers/messages.py НЕ НАЙДЕН!")
    else:
        with open(messages_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем что НЕТ handle_telephony_choice
        if "def handle_telephony_choice" in content:
            print("❌ handle_telephony_choice ВСЁ ЕЩЁ ЕСТЬ!")
            print("   ⚠️ Эта функция конфликтует с quick_errors!")
        else:
            print("✅ handle_telephony_choice удалена")
        
        # Проверяем handle_error_message
        if "async def handle_error_message" in content:
            print("✅ handle_error_message существует")
            
            # Проверяем логику
            if "get_tel_choice(context)" in content:
                print("   ✅ Использует get_tel_choice()")
            else:
                print("   ⚠️ Не использует get_tel_choice()")
            
            if "is_tel_choice_expired(context)" in content:
                print("   ✅ Проверяет timeout")
            else:
                print("   ⚠️ Не проверяет timeout")
        else:
            print("❌ handle_error_message НЕ НАЙДЕНА!")
    
except Exception as e:
    print(f"❌ Ошибка проверки messages.py: {e}")

# ===== 4. ПРОВЕРКА MAIN.PY =====
print("\n4️⃣ ПРОВЕРКА MAIN.PY")
print("-"*60)

try:
    main_path = Path("main.py")
    
    if not main_path.exists():
        print("❌ main.py НЕ НАЙДЕН!")
    else:
        with open(main_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Импорт
        if "from handlers.quick_errors import get_quick_errors_conv" in content:
            print("✅ Импорт get_quick_errors_conv найден")
        else:
            print("❌ Импорт get_quick_errors_conv НЕ НАЙДЕН!")
        
        # Создание
        if "quick_errors_conv = get_quick_errors_conv()" in content:
            print("✅ Вызов get_quick_errors_conv() найден")
        else:
            print("❌ Вызов get_quick_errors_conv() НЕ НАЙДЕН!")
        
        # Регистрация
        if "if quick_errors_conv:" in content or "if quick_errors_conv is not None:" in content:
            print("✅ Проверка на None перед регистрацией")
        else:
            print("⚠️ НЕТ проверки на None!")
        
        if "app.add_handler(quick_errors_conv, group=0)" in content:
            print("✅ Регистрация в group=0")
        else:
            print("❌ Регистрация НЕ НАЙДЕНА или не в group=0!")
        
        # Порядок handlers
        qe_pos = content.find("app.add_handler(quick_errors_conv")
        msg_pos = content.find("app.add_handler(MessageHandler")
        
        if qe_pos > 0 and msg_pos > 0:
            if qe_pos < msg_pos:
                print("✅ quick_errors ПЕРЕД message_handler")
            else:
                print("❌ quick_errors ПОСЛЕ message_handler!")
        else:
            print("⚠️ Не удалось определить порядок")
    
except Exception as e:
    print(f"❌ Ошибка проверки main.py: {e}")

# ===== 5. ПРОВЕРКА MENU.PY =====
print("\n5️⃣ ПРОВЕРКА MENU.PY")
print("-"*60)

try:
    menu_path = Path("handlers/menu.py")
    
    if not menu_path.exists():
        print("❌ handlers/menu.py НЕ НАЙДЕН!")
    else:
        with open(menu_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем handle_telephony_errors_button
        if "async def handle_telephony_errors_button" in content:
            print("✅ handle_telephony_errors_button существует")
            
            # Проверяем что показывает Reply клавиатуру
            if "get_telephony_menu()" in content:
                print("   ✅ Показывает Reply клавиатуру")
            else:
                print("   ⚠️ НЕ показывает Reply клавиатуру!")
        else:
            print("❌ handle_telephony_errors_button НЕ НАЙДЕНА!")
    
except Exception as e:
    print(f"❌ Ошибка проверки menu.py: {e}")

# ===== ИТОГИ =====
print("\n" + "="*60)
print("📊 ДИАГНОСТИКА ЗАВЕРШЕНА")
print("="*60)

print("\n🔍 ЧТО ПРОВЕРИТЬ:")
print("1. Если телефоний с quick_errors=1 НЕТ -> все должны работать через message_handler")
print("2. Если телефонии есть, но не работают -> проверьте main.py")
print("3. Если 'Аврора' в списке qe_names, но quick_errors_enabled=0 -> ПРОБЛЕМА в БД!")
print("4. Проверьте логи бота при выборе телефонии")

print("\n📝 КОМАНДЫ ДЛЯ ПРОВЕРКИ:")
print("# Проверить статус телефоний в БД:")
print("sqlite3 bot_data.db 'SELECT name, code, quick_errors_enabled FROM telephonies'")
print()
print("# Включить быстрые ошибки для Авроры:")
print("sqlite3 bot_data.db \"UPDATE telephonies SET quick_errors_enabled=1 WHERE name='Аврора'\"")
print()
print("# ИЛИ выключить для всех (если не нужны):")
print("sqlite3 bot_data.db 'UPDATE telephonies SET quick_errors_enabled=0'")
print()
print("# Посмотреть логи бота:")
print("tail -f bot.log | grep -i 'quick\\|телефон\\|аврор'")