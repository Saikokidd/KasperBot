"""
Сервис для работы с Google Sheets
Автоматическое обновление статистики менеджеров
"""
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pytz
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from gspread.exceptions import WorksheetNotFound, APIError

from utils.logger import logger
from config.settings import settings

# Загрузка .env файла
load_dotenv()


class GoogleSheetsService:
    """Сервис для управления Google Sheets со статистикой"""
    
    def __init__(self):
        """Инициализация сервиса"""
        self.client = None
        self.spreadsheet = None
        self.sheet_id = os.getenv("GOOGLE_SHEETS_ID")
        self.credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")
        self.timezone = pytz.timezone('Europe/Kiev')
        
        # Проверка наличия ID таблицы
        if not self.sheet_id:
            logger.error("❌ GOOGLE_SHEETS_ID не найден в .env файле!")
            return
        
        # Авторизация
        if not self._authorize():
            logger.error("❌ Не удалось авторизоваться в Google Sheets")
            return
        
        logger.info("✅ Google Sheets сервис инициализирован")
    
    def _authorize(self) -> bool:
        """
        Авторизация в Google Sheets
        
        Returns:
            True если успешно
        """
        try:
            # Проверка файла credentials
            if not os.path.exists(self.credentials_file):
                logger.error(f"❌ Файл {self.credentials_file} не найден!")
                return False
            
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                self.credentials_file, scope
            )
            
            self.client = gspread.authorize(creds)
            
            # Открытие таблицы
            self.spreadsheet = self.client.open_by_key(self.sheet_id)
            
            logger.info(f"✅ Google Sheets авторизация успешна: {self.spreadsheet.title}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка авторизации Google Sheets: {e}")
            return False
    
    def _get_week_range(self, date: datetime) -> tuple:
        """
        Получить диапазон недели (понедельник-суббота)
        
        Args:
            date: Дата для определения недели
            
        Returns:
            (начало_недели, конец_недели)
        """
        # Понедельник текущей недели
        start = date - timedelta(days=date.weekday())
        # Суббота (5 дней от понедельника)
        end = start + timedelta(days=5)
        
        return start, end
    
    def _get_week_title(self, start: datetime, end: datetime) -> str:
        """
        Создать название листа для недели
        
        Args:
            start: Начало недели
            end: Конец недели
            
        Returns:
            Название вида "Неделя 18-23 Ноября 2024"
        """
        months = {
            1: "Января", 2: "Февраля", 3: "Марта", 4: "Апреля",
            5: "Мая", 6: "Июня", 7: "Июля", 8: "Августа",
            9: "Сентября", 10: "Октября", 11: "Ноября", 12: "Декабря"
        }
        
        month_name = months[start.month]
        return f"Неделя {start.day}-{end.day} {month_name} {start.year}"
    
    async def _create_weekly_sheet(self) -> Optional[object]:
        """
        Создать новый лист для недели с заголовками и форматированием
        
        Returns:
            Worksheet объект или None
        """
        if not self.client or not self.spreadsheet:
            return None
        
        try:
            now = datetime.now(self.timezone)
            start, end = self._get_week_range(now)
            title = self._get_week_title(start, end)
            
            # Проверка существования листа
            try:
                worksheet = self.spreadsheet.worksheet(title)
                logger.info(f"📋 Лист '{title}' уже существует")
                return worksheet
            except WorksheetNotFound:
                pass
            
            # Создание нового листа
            worksheet = self.spreadsheet.add_worksheet(
                title=title,
                rows=100,
                cols=17
            )
            
            logger.info(f"✅ Создан новый лист: {title}")
            
            # ===== ЗАГОЛОВКИ (только трубки) =====
            headers = [
                ["№", "Менеджер", "ПН\nтруб", "ВТ\nтруб", "СР\nтруб", "ЧТ\nтруб", "ПТ\nтруб", "СБ\nтруб", "Итого\nтрубок"]
            ]
            
            worksheet.update('A1:I1', headers)
            
            # ===== ФОРМАТИРОВАНИЕ =====
            
            # Заголовки: синий фон, белый текст, жирный, центр
            worksheet.format('A1:I1', {
                "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.8},
                "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE"
            })
            
            # Ширина колонок и высота строки заголовка
            body = {
                "requests": [
                    # Ширина колонок
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 40}, "fields": "pixelSize"}},  # №
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2}, "properties": {"pixelSize": 120}, "fields": "pixelSize"}},  # Менеджер
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 9}, "properties": {"pixelSize": 70}, "fields": "pixelSize"}},  # ПН-СБ + Итого
                    
                    # Высота первой строки (заголовок)
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "ROWS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 50}, "fields": "pixelSize"}},
                ]
            }
            self.spreadsheet.batch_update(body)
            
            # Центрирование всех ячеек
            worksheet.format('A:I', {
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE"
            })
            
            # Рамки для всей таблицы
            worksheet.format('A1:I100', {
                "borders": {
                    "top": {"style": "SOLID"},
                    "bottom": {"style": "SOLID"},
                    "left": {"style": "SOLID"},
                    "right": {"style": "SOLID"}
                }
            })
            
            logger.info(f"✅ Заголовки и форматирование применены к листу '{title}'")
            return worksheet
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания листа: {e}")
            return None
    
    async def _get_managers_stats(self, target_date: str) -> List[Dict]:
        """
        Получить статистику по всем менеджерам
        
        Args:
            target_date: Дата в формате YYYY-MM-DD (не используется)
            
        Returns:
            Список менеджеров с данными
        """
        try:
            # ✅ ФИКСИРОВАННЫЙ СПИСОК - ТОЛЬКО ПАВЛОГРАД (буква в букву!)
            FIXED_MANAGERS = [
                "Лера", "Эля", "Диана", "Cергей", "Леся", "Диди", 
                "Добряк", "Дима", "Егор", "Алладин", "Ваня", "Аня",
                "Ганжа", "Марик", "Дрон", "Лысый", "Женя", "Ярик",
                "Миша", "Тёма", "Вова"
            ]
            
            # ✅ НОРМАЛИЗАЦИЯ ИМЁН - как написано в рабочей таблице → как в FIXED_MANAGERS
            NAME_MAP = {
                # Основные имена (как есть)
                'лера': 'Лера',
                'эля': 'Эля',
                'диана': 'Диана',
                'cергей': 'Cергей',  # с латинской C!
                'сергей': 'Cергей',  # русская С тоже
                'леся': 'Леся',
                'диди': 'Диди',
                'добряк': 'Добряк',
                'дима': 'Дима',
                'егор': 'Егор',
                'алладин': 'Алладин',
                'ваня': 'Ваня',
                'аня': 'Аня',
                'ганжа': 'Ганжа',
                'марик': 'Марик',
                'дрон': 'Дрон',
                'лысый': 'Лысый',
                'женя': 'Женя',
                'ярик': 'Ярик',
                'миша': 'Миша',
                'тёма': 'Тёма',
                'тема': 'Тёма',  # без ё
                'Вова': 'Тайсон',
                
                # Возможные варианты написания (если есть)
                'серега': 'Cергей',
                'аладдин': 'Алладин',
                'марк': 'Марик',
            }
            
            from services.managers_stats_service import managers_stats_service
            
            # Получаем данные из рабочей таблицы
            raw_data = await managers_stats_service._fetch_managers_data()
            
            logger.info(f"📥 Получено {len(raw_data)} записей из рабочей таблицы")
            
            # Группируем по менеджерам с нормализацией
            stats_by_manager = {}
            unmatched_names = set()  # Для отладки
            
            for row in raw_data:
                manager = row.get("менеджер", "").strip()
                color = row.get("цвет", "").strip()
                
                if not manager or not color:
                    continue
                
                # ✅ Нормализуем имя менеджера
                manager_lower = manager.lower()
                normalized_name = NAME_MAP.get(manager_lower)
                
                if not normalized_name:
                    # Имя не найдено в карте - сохраняем оригинал
                    normalized_name = manager
                    unmatched_names.add(manager)
                
                if normalized_name not in stats_by_manager:
                    stats_by_manager[normalized_name] = {
                        "ЖЕЛТЫЙ": 0,
                        "ЗЕЛЕНЫЙ": 0,
                        "ФИОЛЕТОВЫЙ": 0
                    }
                
                if color in stats_by_manager[normalized_name]:
                    stats_by_manager[normalized_name][color] += 1
            
            # ✅ Логируем неизвестные имена
            if unmatched_names:
                logger.warning(f"⚠️ Неизвестные имена менеджеров: {unmatched_names}")
                logger.warning(f"💡 Добавьте их в NAME_MAP или FIXED_MANAGERS!")
            
            # Формируем финальный список (все менеджеры, даже с 0)
            managers_data = []
            
            for manager_name in FIXED_MANAGERS:
                if manager_name in stats_by_manager:
                    colors = stats_by_manager[manager_name]
                    tubes = sum(colors.values())
                    green = colors["ЗЕЛЕНЫЙ"]
                    purple = colors["ФИОЛЕТОВЫЙ"]
                    yellow = colors["ЖЕЛТЫЙ"]
                    
                    logger.info(f"📊 {manager_name}: {tubes} трубок (🟩{green} 🟪{purple} 🟨{yellow})")
                else:
                    # Менеджера нет в данных - ставим 0
                    tubes = 0
                    green = 0
                    purple = 0
                    yellow = 0
                
                managers_data.append({
                    "name": manager_name,
                    "tubes": tubes,
                    "green": green,
                    "yellow": yellow,
                    "purple": purple
                })
            
            logger.info(f"✅ Сформирован список: {len(managers_data)} менеджеров")
            return managers_data
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики менеджеров: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # В случае ошибки возвращаем всех менеджеров с 0
            FIXED_MANAGERS = [
                "Лера", "Эля", "Диана", "Cергей", "Леся", "Диди", 
                "Добряк", "Дима", "Егор", "Алладин", "Ваня", "Аня",
                "Ганжа", "Марик", "Дрон", "Лысый", "Женя", "Ярик",
                "Миша", "Тёма", "Вова"
            ]
            
            return [
                {"name": name, "tubes": 0, "green": 0, "yellow": 0, "purple": 0}
                for name in FIXED_MANAGERS
            ]
    
    async def update_stats(self):
        """
        Обновить статистику в Google Sheets
        Запускается каждый час (8:00-19:00, ПН-СБ)
        """
        if not self.client or not self.spreadsheet:
            logger.error("❌ Google Sheets сервис не инициализирован")
            return
        
        try:
            now = datetime.now(self.timezone)
            start, end = self._get_week_range(now)
            title = self._get_week_title(start, end)
            
            logger.info(f"🔄 Обновление статистики для листа: {title}")
            
            # Получение или создание листа
            try:
                worksheet = self.spreadsheet.worksheet(title)
            except WorksheetNotFound:
                worksheet = await self._create_weekly_sheet()
                if not worksheet:
                    return
            
            # Получение статистики менеджеров за текущий день
            current_date = now.strftime("%Y-%m-%d")
            managers_data = await self._get_managers_stats(current_date)
            
            if not managers_data:
                logger.warning("⚠️ Нет данных для обновления")
                return
            
            # ===== СОРТИРОВКА ПО КОЛИЧЕСТВУ ТРУБОК =====
            managers_data.sort(key=lambda x: x.get('tubes', 0), reverse=True)
            logger.info(f"🔢 Менеджеры отсортированы по трубкам")
            
            # ===== ОПРЕДЕЛЕНИЕ ДНЯ НЕДЕЛИ С ЛОГАМИ =====
            weekday = now.weekday()
            days_names = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
            
            logger.info(f"📅 Текущая дата: {now.strftime('%d.%m.%Y %H:%M')}")
            logger.info(f"📅 День недели: {days_names[weekday]} (weekday={weekday})")
            
            if weekday > 5:  # Воскресенье - не обновляем
                logger.info("📅 Воскресенье - обновление не требуется")
                return
            
            # Колонка для трубок: C=ПН, D=ВТ, E=СР, F=ЧТ, G=ПТ, H=СБ
            # weekday: 0=ПН, 1=ВТ, 2=СР, 3=ЧТ, 4=ПТ, 5=СБ
            # Нужная колонка: C=3, D=4, E=5, F=6, G=7, H=8
            tubes_col = 3 + weekday  # ✅ C=3 для ПН, D=4 для ВТ
            tubes_col_letter = chr(64 + tubes_col)
            
            col_names = ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ']
            logger.info(f"📊 Будет заполнена колонка: {tubes_col_letter} ({col_names[weekday]})")
            
            # Подготовка данных для обновления (только трубки)
            rows_data = []
            
            for idx, manager in enumerate(managers_data, start=2):  # Начинаем со 2 строки
                name = manager.get('name', 'Неизвестно')
                tubes = manager.get('tubes', 0)
                
                rows_data.append({
                    'row': idx,
                    'name': name,
                    'tubes': tubes
                })
            
            # ===== ОБНОВЛЕНИЕ ТАБЛИЦЫ (BATCH UPDATE) =====
            
            # Подготовка всех обновлений одним батчем
            updates = []
            
            # 1. Номера и имена менеджеров (колонки A-B)
            names_range_values = []
            for idx, data in enumerate(rows_data, start=1):
                names_range_values.append([idx, data['name']])
            
            updates.append({
                'range': f'A2:B{len(rows_data)+1}',
                'values': names_range_values
            })
            
            # 2. Трубки за текущий день (одна колонка)
            tubes_values = [[data['tubes']] for data in rows_data]
            updates.append({
                'range': f'{tubes_col_letter}2:{tubes_col_letter}{len(rows_data)+1}',
                'values': tubes_values
            })
            
            logger.info(f"📝 Запись данных в колонку {tubes_col_letter}2:{tubes_col_letter}{len(rows_data)+1}")
            
            # 3. Формулы для "Итого трубок" (колонка I)
            formulas_total = [
                [f"=SUM(C{data['row']}:H{data['row']})"] 
                for data in rows_data
            ]
            updates.append({
                'range': f'I2:I{len(rows_data)+1}',
                'values': formulas_total
            })
            
            # 4. Итоговая строка
            total_row = len(rows_data) + 2
            
            # Итого: название
            updates.append({
                'range': f'A{total_row}:B{total_row}',
                'values': [["", "ИТОГО:"]]
            })
            
            # Итого: формулы по дням (C-H)
            for col in range(3, 9):
                col_letter = chr(64 + col)
                updates.append({
                    'range': f'{col_letter}{total_row}',
                    'values': [[f"=SUM({col_letter}2:{col_letter}{total_row-1})"]]
                })
            
            # Итого: всего трубок (I)
            updates.append({
                'range': f'I{total_row}',
                'values': [[f"=SUM(I2:I{total_row-1})"]]
            })
            
            # 5. Время обновления (красиво!)
            time_row = total_row + 2
            current_time = now.strftime("%d.%m.%Y %H:%M")
            updates.append({
                'range': f'A{time_row}:I{time_row}',
                'values': [[f"📊 Обновлено: {current_time}", "", "", "", "", "", "", "", ""]]
            })
            
            # ===== ОТПРАВКА ВСЕХ ОБНОВЛЕНИЙ ОДНИМ БАТЧЕМ =====
            logger.info(f"📤 Отправка {len(updates)} обновлений одним батчем...")
            
            worksheet.batch_update(updates, value_input_option='USER_ENTERED')
            
            # ===== ФОРМАТИРОВАНИЕ =====
            
            # Итоговая строка: серый фон, жирный
            worksheet.format(f'A{total_row}:I{total_row}', {
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                "textFormat": {"bold": True},
                "horizontalAlignment": "CENTER"
            })
            
            # Время обновления: курсив, светло-серый фон, по центру
            worksheet.format(f'A{time_row}:I{time_row}', {
                "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
                "textFormat": {"italic": True, "fontSize": 9},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE"
            })
            
            # Объединение ячеек для времени обновления
            merge_request = {
                "requests": [{
                    "mergeCells": {
                        "range": {
                            "sheetId": worksheet.id,
                            "startRowIndex": time_row - 1,
                            "endRowIndex": time_row,
                            "startColumnIndex": 0,
                            "endColumnIndex": 9
                        },
                        "mergeType": "MERGE_ALL"
                    }
                }]
            }
            self.spreadsheet.batch_update(merge_request)
            
            logger.info(f"✅ Статистика обновлена: {len(rows_data)} менеджеров")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статистики: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def create_weekly_sheet_if_needed(self):
        """
        Создать новый лист для недели если наступил понедельник
        Запускается в 00:01 каждый понедельник
        """
        if not self.client or not self.spreadsheet:
            logger.error("❌ Google Sheets сервис не инициализирован")
            return
        
        try:
            now = datetime.now(self.timezone)
            
            # Проверка: это понедельник?
            if now.weekday() != 0:
                logger.info("📅 Не понедельник - создание листа не требуется")
                return
            
            await self._create_weekly_sheet()
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания еженедельного листа: {e}")


# ✅ Глобальный экземпляр сервиса
google_sheets_service = GoogleSheetsService()