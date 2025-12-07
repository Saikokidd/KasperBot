"""Сервис для работы с Google Sheets
Автоматическое обновление статистики менеджеров

ИЗМЕНЕНИЯ:
✅ update_stats() разбита на подфункции (легче читать и поддерживать)
✅ Каждая подфункция решает одну задачу
✅ Добавлены type hints
"""
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pytz
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from gspread.exceptions import WorksheetNotFound, APIError

from utils.logger import logger
from config.settings import settings
from config.constants import PAVLOGRAD_MANAGERS, NAME_MAP
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
import logging
from gspread.exceptions import APIError
import aiohttp

# Настройка retry для API запросов
API_RETRY_CONFIG = {
    'stop': stop_after_attempt(3),
    'wait': wait_exponential(min=2, max=10),
    'retry': retry_if_exception_type((
        APIError,
        aiohttp.ClientError,
        TimeoutError
    )),
    'before_sleep': before_sleep_log(logger, logging.WARNING)
}

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
        
        if not self.sheet_id:
            logger.error("❌ GOOGLE_SHEETS_ID не найден в .env файле!")
            return
        
        if not self._authorize():
            logger.error("❌ Не удалось авторизоваться в Google Sheets")
            return
        
        logger.info("✅ Google Sheets сервис инициализирован")
    
    def _authorize(self) -> bool:
        """Авторизация в Google Sheets"""
        try:
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
            self.spreadsheet = self.client.open_by_key(self.sheet_id)
            
            logger.info(f"✅ Google Sheets авторизация успешна: {self.spreadsheet.title}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка авторизации Google Sheets: {e}")
            return False
    
    def _get_week_range(self, date: datetime) -> Tuple[datetime, datetime]:
        """Получить диапазон недели (понедельник-суббота)"""
        start = date - timedelta(days=date.weekday())
        end = start + timedelta(days=5)
        return start, end
    
    def _get_week_title(self, start: datetime, end: datetime) -> str:
        """Создать название листа для недели"""
        months = {
            1: "Января", 2: "Февраля", 3: "Марта", 4: "Апреля",
            5: "Мая", 6: "Июня", 7: "Июля", 8: "Августа",
            9: "Сентября", 10: "Октября", 11: "Ноября", 12: "Декабря"
        }
        
        month_name = months[start.month]
        return f"Неделя {start.day}-{end.day} {month_name} {start.year}"
    
    async def _create_weekly_sheet(self) -> Optional[object]:
        """Создать новый лист для недели с заголовками и форматированием"""
        if not self.client or not self.spreadsheet:
            return None
        
        try:
            now = datetime.now(self.timezone)
            start, end = self._get_week_range(now)
            title = self._get_week_title(start, end)
            
            try:
                worksheet = self.spreadsheet.worksheet(title)
                logger.info(f"📋 Лист '{title}' уже существует")
                return worksheet
            except WorksheetNotFound:
                pass
            
            worksheet = self.spreadsheet.add_worksheet(
                title=title,
                rows=100,
                cols=17
            )
            
            logger.info(f"✅ Создан новый лист: {title}")
            
            # Заголовки
            headers = [
                ["№", "Менеджер", "ПН\nтруб", "ВТ\nтруб", "СР\nтруб", "ЧТ\nтруб", "ПТ\nтруб", "СБ\nтруб", "Итого\nтрубок"]
            ]
            
            worksheet.update('A1:I1', headers)
            
            # Применяем форматирование
            self._format_worksheet_headers(worksheet)
            
            logger.info(f"✅ Заголовки и форматирование применены к листу '{title}'")
            return worksheet
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания листа: {e}")
            return None
    
    def _format_worksheet_headers(self, worksheet) -> None:
        """
        ✅ НОВОЕ: Применить форматирование к заголовкам листа
        
        Args:
            worksheet: Объект worksheet для форматирования
        """
        # Заголовки: синий фон, белый текст
        worksheet.format('A1:I1', {
            "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.8},
            "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True},
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE"
        })
        
        # Ширина колонок
        body = {
            "requests": [
                {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 40}, "fields": "pixelSize"}},
                {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2}, "properties": {"pixelSize": 120}, "fields": "pixelSize"}},
                {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 9}, "properties": {"pixelSize": 70}, "fields": "pixelSize"}},
                {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "ROWS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 50}, "fields": "pixelSize"}},
            ]
        }
        self.spreadsheet.batch_update(body)
        
        # Центрирование
        worksheet.format('A:I', {
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE"
        })
        
        # Рамки
        worksheet.format('A1:I100', {
            "borders": {
                "top": {"style": "SOLID"},
                "bottom": {"style": "SOLID"},
                "left": {"style": "SOLID"},
                "right": {"style": "SOLID"}
            }
        })
    
    @retry(**API_RETRY_CONFIG)
    async def _get_managers_stats(self, target_date: str) -> List[Dict]:
        """Получить статистику по всем менеджерам"""
        try:
            from services.managers_stats_service import managers_stats_service
            
            raw_data = await managers_stats_service._fetch_managers_data()
            logger.info(f"📥 Получено {len(raw_data)} записей из рабочей таблицы")
            
            # Группируем по менеджерам
            stats_by_manager = {}
            unmatched_names = set()
            
            for row in raw_data:
                manager = row.get("менеджер", "").strip()
                color = row.get("цвет", "").strip()
                
                if not manager or not color:
                    continue
                
                manager_lower = manager.lower()
                normalized_name = NAME_MAP.get(manager_lower, manager)
                
                if manager_lower not in NAME_MAP:
                    unmatched_names.add(manager)
                
                if normalized_name not in stats_by_manager:
                    stats_by_manager[normalized_name] = {
                        "ЖЕЛТЫЙ": 0,
                        "ЗЕЛЕНЫЙ": 0,
                        "ФИОЛЕТОВЫЙ": 0
                    }
                
                if color in stats_by_manager[normalized_name]:
                    stats_by_manager[normalized_name][color] += 1
            
            if unmatched_names:
                logger.warning(f"⚠️ Неизвестные имена менеджеров: {unmatched_names}")
            
            # Формируем список в фиксированном порядке
            managers_data = []
            
            for manager_name in PAVLOGRAD_MANAGERS:
                if manager_name in stats_by_manager:
                    colors = stats_by_manager[manager_name]
                    tubes = sum(colors.values())
                    green = colors["ЗЕЛЕНЫЙ"]
                    purple = colors["ФИОЛЕТОВЫЙ"]
                    yellow = colors["ЖЕЛТЫЙ"]
                    
                    logger.info(f"📊 {manager_name}: {tubes} трубок (🟩{green} 🟪{purple} 🟨{yellow})")
                else:
                    tubes = green = purple = yellow = 0
                
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
            raise
    
    def _prepare_data_updates(
        self, 
        managers_data: List[Dict], 
        weekday: int
    ) -> Tuple[List[Dict], int]:
        """
        ✅ НОВОЕ: Подготовить данные для обновления
        
        Args:
            managers_data: Список менеджеров с данными
            weekday: Номер дня недели (0-5)
            
        Returns:
            (updates, total_row) - список обновлений и номер итоговой строки
        """
        updates = []
        tubes_col = 3 + weekday
        tubes_col_letter = chr(64 + tubes_col)
        
        # 1. Номера и имена менеджеров
        names_range_values = []
        for idx, manager in enumerate(managers_data, start=1):
            names_range_values.append([idx, manager['name']])
        
        updates.append({
            'range': f'A2:B{len(managers_data)+1}',
            'values': names_range_values
        })
        
        # 2. Трубки за текущий день
        tubes_values = [[manager['tubes']] for manager in managers_data]
        updates.append({
            'range': f'{tubes_col_letter}2:{tubes_col_letter}{len(managers_data)+1}',
            'values': tubes_values
        })
        
        logger.info(f"📝 Запись данных в колонку {tubes_col_letter}2:{tubes_col_letter}{len(managers_data)+1}")
        
        # 3. Формулы для "Итого трубок"
        formulas_total = [
            [f"=SUM(C{idx+1}:H{idx+1})"] 
            for idx, _ in enumerate(managers_data, start=1)
        ]
        updates.append({
            'range': f'I2:I{len(managers_data)+1}',
            'values': formulas_total
        })
        
        total_row = len(managers_data) + 2
        
        return updates, total_row
    
    def _prepare_total_row_updates(
        self, 
        total_row: int,
        managers_count: int
    ) -> List[Dict]:
        """
        ✅ НОВОЕ: Подготовить обновления для итоговой строки
        
        Args:
            total_row: Номер итоговой строки
            managers_count: Количество менеджеров
            
        Returns:
            Список обновлений для итоговой строки
        """
        updates = []
        
        # Заголовок "ИТОГО:"
        updates.append({
            'range': f'A{total_row}:B{total_row}',
            'values': [["", "ИТОГО:"]]
        })
        
        # Формулы для каждого дня недели + итого
        for col in range(3, 9):
            col_letter = chr(64 + col)
            updates.append({
                'range': f'{col_letter}{total_row}',
                'values': [[f"=SUM({col_letter}2:{col_letter}{total_row-1})"]]
            })
        
        updates.append({
            'range': f'I{total_row}',
            'values': [[f"=SUM(I2:I{total_row-1})"]]
        })
        
        return updates
    
    def _prepare_timestamp_update(
        self, 
        total_row: int,
        current_time: str
    ) -> Dict:
        """
        ✅ НОВОЕ: Подготовить обновление с временем последнего обновления
        
        Args:
            total_row: Номер итоговой строки
            current_time: Текущее время (форматированное)
            
        Returns:
            Обновление для строки с временем
        """
        time_row = total_row + 2
        
        return {
            'range': f'A{time_row}:I{time_row}',
            'values': [[f"📊 Обновлено: {current_time}", "", "", "", "", "", "", "", ""]]
        }
    
    def _apply_formatting(
        self, 
        worksheet, 
        total_row: int
    ) -> None:
        """
        ✅ НОВОЕ: Применить форматирование к итоговой строке и времени
        
        Args:
            worksheet: Объект worksheet
            total_row: Номер итоговой строки
        """
        time_row = total_row + 2
        
        # Форматирование итоговой строки
        worksheet.format(f'A{total_row}:I{total_row}', {
            "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
            "textFormat": {"bold": True},
            "horizontalAlignment": "CENTER"
        })
        
        # Форматирование строки с временем
        worksheet.format(f'A{time_row}:I{time_row}', {
            "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
            "textFormat": {"italic": True, "fontSize": 9},
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE"
        })
        
        # Объединение ячеек для времени
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
    
    @retry(**API_RETRY_CONFIG)
    async def update_stats(self):
        """
        ✅ РЕФАКТОРИНГ: Обновить статистику в Google Sheets
        
        Теперь функция просто оркестрирует процесс,
        вся логика разбита на подфункции
        """
        if not self.client or not self.spreadsheet:
            raise Exception("Google Sheets сервис не инициализирован")
        
        try:
            now = datetime.now(self.timezone)
            if now.weekday() == 6:  # 6 = воскресенье
                logger.info("📅 Воскресенье - обновление статистики пропущено")
            return
            start, end = self._get_week_range(now)
            title = self._get_week_title(start, end)
            
            logger.info(f"🔄 Обновление статистики для листа: {title}")
            
            # 1. Получение или создание листа
            try:
                worksheet = self.spreadsheet.worksheet(title)
            except WorksheetNotFound:
                worksheet = await self._create_weekly_sheet()
                if not worksheet:
                    raise Exception("Не удалось создать лист")
            
            # 2. Проверка дня недели
            weekday = now.weekday()
            if weekday > 5:
                logger.info("📅 Воскресенье - обновление не требуется")
                return
            
            # 3. Получение статистики менеджеров
            current_date = now.strftime("%Y-%m-%d")
            managers_data = await self._get_managers_stats(current_date)
            
            if not managers_data:
                logger.warning("⚠️ Нет данных для обновления")
                return
            
            # 4. Подготовка обновлений
            data_updates, total_row = self._prepare_data_updates(managers_data, weekday)
            total_row_updates = self._prepare_total_row_updates(total_row, len(managers_data))
            timestamp_update = self._prepare_timestamp_update(total_row, now.strftime("%d.%m.%Y %H:%M"))
            
            # 5. Объединение всех обновлений
            all_updates = data_updates + total_row_updates + [timestamp_update]
            
            # 6. Отправка одним батчем
            logger.info(f"📤 Отправка {len(all_updates)} обновлений одним батчем...")
            worksheet.batch_update(all_updates, value_input_option='USER_ENTERED')
            
            # 7. Применение форматирования
            self._apply_formatting(worksheet, total_row)
            
            logger.info(f"✅ Статистика обновлена: {len(managers_data)} менеджеров")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статистики: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    async def create_weekly_sheet_if_needed(self):
        """Создать новый лист для недели если наступил понедельник"""
        if not self.client or not self.spreadsheet:
            logger.error("❌ Google Sheets сервис не инициализирован")
            return
        
        try:
            now = datetime.now(self.timezone)
            
            if now.weekday() != 0:
                logger.info("📅 Не понедельник - создание листа не требуется")
                return
            
            await self._create_weekly_sheet()
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания еженедельного листа: {e}")


# Глобальный экземпляр сервиса
google_sheets_service = GoogleSheetsService()