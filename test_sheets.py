#!/usr/bin/env python3
import os
from dotenv import load_dotenv  # ВАЖНО: добавлено!
from oauth2client.service_account import ServiceAccountCredentials
import gspread

# Загрузка .env файла
load_dotenv()

# Проверка переменных
sheet_id = os.getenv("GOOGLE_SHEETS_ID")
creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")

print("=" * 50)
print("GOOGLE_SHEETS_ID:", sheet_id)
print("Файл credentials существует:", os.path.exists(creds_file))
print("=" * 50)

if not sheet_id:
    print("❌ GOOGLE_SHEETS_ID не найден в .env!")
    exit(1)

try:
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        creds_file, scope
    )
    
    client = gspread.authorize(creds)
    print("✅ Авторизация успешна")
    
    # Пытаемся открыть таблицу
    spreadsheet = client.open_by_key(sheet_id)
    print(f"✅ Таблица найдена: {spreadsheet.title}")
    
    # Попытка создать/получить лист
    try:
        worksheet = spreadsheet.worksheet("Тест")
        print(f"✅ Лист 'Тест' найден")
    except:
        worksheet = spreadsheet.add_worksheet(title="Тест", rows=10, cols=5)
        print(f"✅ Лист 'Тест' создан")
    
    print("=" * 50)
    print("✅ ВСЁ РАБОТАЕТ!")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()