"""
ФИНАЛЬНАЯ ВЕРСИЯ: services/google_sheets_service.py
Правильная работа с датами + горизонтальный layout + пропуск будущих дней

ИСПРАВЛЕНИЯ:
✅ Собирает данные только за ПРОШЕДШИЕ дни текущей недели
✅ Пропускает несуществующие листы БЕЗ ошибок
✅ Горизонтальный layout: ВСЕ ТРУБКИ | ПЕРЕЗВОНЫ | СТАТИСТИКА
✅ Правильное определение текущей недели (ПН-СБ)
✅ Перезапись данных если они изменились в рабочей таблице
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
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)
import logging
import aiohttp

# Настройка retry
API_RETRY_CONFIG = {
    'stop': stop_after_attempt(3),
    'wait': wait_exponential(min=2, max=10),
    'retry': retry_if_exception_type((APIError, aiohttp.ClientError, TimeoutError)),
    'before_sleep': before_sleep_log(logger, logging.WARNING)
}

load_dotenv()

# ===== КОНСТАНТЫ =====
WEEKLY_PLAN = 10  # Недельный план трубок


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
        """
        Получить диапазон текущей недели (понедельник-суббота)
        
        ✅ ИСПРАВЛЕНО: Воскресенье относится к СЛЕДУЮЩЕЙ неделе
        """
        # Если воскресенье (weekday=6) → берём следующий понедельник
        if date.weekday() == 6:
            start = date + timedelta(days=1)  # Следующий понедельник
        else:
            # Иначе находим понедельник текущей недели
            start = date - timedelta(days=date.weekday())
        
        end = start + timedelta(days=5)  # Суббота
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
        """Создать новый лист для недели с горизонтальным layout"""
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
            
            # Создаём лист
            worksheet = self.spreadsheet.add_worksheet(
                title=title,
                rows=100,
                cols=30
            )
            
            logger.info(f"✅ Создан новый лист: {title}")
            
            # Применяем начальное форматирование
            await self._setup_dashboard_layout(worksheet, start, end)
            
            return worksheet
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания листа: {e}")
            return None
    
    async def _setup_dashboard_layout(self, worksheet, start: datetime, end: datetime):
        """
        ✅ НОВОЕ: Горизонтальный layout
        
        A-J: ВСЕ ТРУБКИ
        L-U: ПЕРЕЗВОНЫ  
        W-Y: ОБЩАЯ СТАТИСТИКА
        """
        try:
            months_ru = {
                1: "Января", 2: "Февраля", 3: "Марта", 4: "Апреля",
                5: "Мая", 6: "Июня", 7: "Июля", 8: "Августа",
                9: "Сентября", 10: "Октября", 11: "Ноября", 12: "Декабря"
            }
            
            week_title = f"📊 СТАТИСТИКА НЕДЕЛИ {start.day}-{end.day} {months_ru[start.month].upper()} {start.year}"
            
            # ===== ШАПКА =====
            worksheet.merge_cells('A1:J1')
            worksheet.update('A1', [[week_title]])
            
            # Время обновления
            worksheet.merge_cells('L1:U1')
            worksheet.update('L1', [[f"🔄 Обновлено: {datetime.now(self.timezone).strftime('%d.%m.%Y %H:%M')}"]])
            
            # ===== ТАБЛИЦА 1: ВСЕ ТРУБКИ (A3-J) =====
            worksheet.merge_cells('A3:J3')
            worksheet.update('A3', [["📞 ВСЕ ТРУБКИ"]])
            
            headers_all = [["№", "Менеджер", "ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ИТОГО", "ПЛАН"]]
            worksheet.update('A4:J4', headers_all)
            
            # ===== ТАБЛИЦА 2: ПЕРЕЗВОНЫ (L3-U) =====
            worksheet.merge_cells('L3:U3')
            worksheet.update('L3', [["🟢 ПЕРЕЗВОНЫ"]])
            
            headers_recalls = [["№", "Менеджер", "ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ИТОГО", "%"]]
            worksheet.update('L4:U4', headers_recalls)
            
            # ===== ОБЩАЯ СТАТИСТИКА (W3-Y7) =====
            worksheet.merge_cells('W3:Y3')
            worksheet.update('W3', [["📊 ОБЩАЯ СТАТИСТИКА"]])
            
            stats_headers = [
                ["📞 Всего трубок", "0"],
                ["🟢 Перезвоны", "0"],
                ["📈 % Перезвонов", "0%"],
                ["✓ План выполнен", "0/0"]
            ]
            worksheet.update('W4:X7', stats_headers)
            
            # Применяем форматирование
            self._format_headers(worksheet)
            
            logger.info("✅ Layout дашборда создан (горизонтальный)")
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания layout: {e}")
    
    def _format_headers(self, worksheet):
        """Форматирование заголовков и границ"""
        try:
            # ===== ЦВЕТА =====
            
            # Главный заголовок (синий)
            worksheet.format('A1:J1', {
                "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.7},
                "textFormat": {
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                    "bold": True,
                    "fontSize": 13
                },
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE"
            })
            
            # Время обновления (светло-серый)
            worksheet.format('L1:U1', {
                "backgroundColor": {"red": 0.85, "green": 0.85, "blue": 0.85},
                "textFormat": {"bold": True, "fontSize": 10},
                "horizontalAlignment": "CENTER"
            })
            
            # Заголовок "ВСЕ ТРУБКИ" (синий)
            worksheet.format('A3:J3', {
                "backgroundColor": {"red": 0.4, "green": 0.6, "blue": 0.9},
                "textFormat": {
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                    "bold": True,
                    "fontSize": 11
                },
                "horizontalAlignment": "CENTER"
            })
            
            # Заголовок "ПЕРЕЗВОНЫ" (зелёный)
            worksheet.format('L3:U3', {
                "backgroundColor": {"red": 0.3, "green": 0.7, "blue": 0.4},
                "textFormat": {
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                    "bold": True,
                    "fontSize": 11
                },
                "horizontalAlignment": "CENTER"
            })
            
            # Заголовок "ОБЩАЯ СТАТИСТИКА" (оранжевый)
            worksheet.format('W3:Y3', {
                "backgroundColor": {"red": 1, "green": 0.6, "blue": 0.2},
                "textFormat": {
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                    "bold": True,
                    "fontSize": 11
                },
                "horizontalAlignment": "CENTER"
            })
            
            # Заголовки колонок (светлые)
            worksheet.format('A4:J4', {
                "backgroundColor": {"red": 0.85, "green": 0.9, "blue": 1},
                "textFormat": {"bold": True, "fontSize": 9},
                "horizontalAlignment": "CENTER"
            })
            
            worksheet.format('L4:U4', {
                "backgroundColor": {"red": 0.85, "green": 1, "blue": 0.9},
                "textFormat": {"bold": True, "fontSize": 9},
                "horizontalAlignment": "CENTER"
            })
            
            # Заголовки статистики
            worksheet.format('W4:Y7', {
                "backgroundColor": {"red": 1, "green": 0.9, "blue": 0.7},
                "textFormat": {"bold": True, "fontSize": 9},
                "horizontalAlignment": "LEFT"
            })
            
            # ===== ШИРИНА КОЛОНОК =====
            body = {
                "requests": [
                    # ВСЕ ТРУБКИ
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 40}, "fields": "pixelSize"}},
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2}, "properties": {"pixelSize": 120}, "fields": "pixelSize"}},
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 8}, "properties": {"pixelSize": 45}, "fields": "pixelSize"}},
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 8, "endIndex": 9}, "properties": {"pixelSize": 60}, "fields": "pixelSize"}},
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 9, "endIndex": 10}, "properties": {"pixelSize": 50}, "fields": "pixelSize"}},
                    
                    # Пробел
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 10, "endIndex": 11}, "properties": {"pixelSize": 20}, "fields": "pixelSize"}},
                    
                    # ПЕРЕЗВОНЫ
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 11, "endIndex": 12}, "properties": {"pixelSize": 40}, "fields": "pixelSize"}},
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 12, "endIndex": 13}, "properties": {"pixelSize": 120}, "fields": "pixelSize"}},
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 13, "endIndex": 19}, "properties": {"pixelSize": 45}, "fields": "pixelSize"}},
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 19, "endIndex": 20}, "properties": {"pixelSize": 60}, "fields": "pixelSize"}},
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 20, "endIndex": 21}, "properties": {"pixelSize": 50}, "fields": "pixelSize"}},
                    
                    # Пробел
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 21, "endIndex": 22}, "properties": {"pixelSize": 20}, "fields": "pixelSize"}},
                    
                    # СТАТИСТИКА
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 22, "endIndex": 25}, "properties": {"pixelSize": 120}, "fields": "pixelSize"}},
                ]
            }
            self.spreadsheet.batch_update(body)
            
            logger.info("✅ Форматирование применено")
            
        except Exception as e:
            logger.error(f"❌ Ошибка форматирования: {e}")
    
    @retry(**API_RETRY_CONFIG)
    async def _get_week_stats_by_days(self, start_date: datetime, end_date: datetime) -> Tuple[Dict, Dict]:
        """
        ✅ ИСПРАВЛЕНО: Собирает данные только за ПРОШЕДШИЕ дни текущей недели
        
        Пропускает несуществующие листы БЕЗ ошибок.
        """
        try:
            all_tubes_by_days = {}
            recalls_by_days = {}
            
            # Инициализируем для всех менеджеров
            for manager_name in PAVLOGRAD_MANAGERS:
                all_tubes_by_days[manager_name] = {
                    "ПН": 0, "ВТ": 0, "СР": 0, "ЧТ": 0, "ПТ": 0, "СБ": 0
                }
                recalls_by_days[manager_name] = {
                    "ПН": 0, "ВТ": 0, "СР": 0, "ЧТ": 0, "ПТ": 0, "СБ": 0
                }
            
            # ✅ КРИТИЧНО: Обрабатываем ТОЛЬКО дни <= сегодня
            today = datetime.now(self.timezone).date()
            
            current_date = start_date
            day_names = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ"]
            
            while current_date <= end_date:
                # ✅ Пропускаем будущие дни
                if current_date.date() > today:
                    day_index = current_date.weekday()
                    day_name = day_names[day_index]
                    logger.info(f"⏭ Пропускаем {day_name} ({current_date.strftime('%d.%m')}) - будущая дата")
                    current_date += timedelta(days=1)
                    continue
                
                day_index = current_date.weekday()
                day_name = day_names[day_index]
                date_str = current_date.strftime('%d.%m')
                
                logger.info(f"📅 Обработка {day_name} ({date_str})")
                
                # Получаем данные за этот день
                raw_data = await self._fetch_managers_data_for_date(date_str)
                
                # ✅ Если лист не найден - пропускаем БЕЗ ошибки
                if raw_data is None:
                    logger.info(f"⏭ {day_name} ({date_str}): лист не найден, пропускаем")
                    current_date += timedelta(days=1)
                    continue
                
                # Обрабатываем данные этого дня
                stats_day = {}
                recalls_day = {}
                
                for row in raw_data:
                    manager = row.get("менеджер", "").strip()
                    color = row.get("цвет", "").strip()
                    
                    if not manager or not color:
                        continue
                    
                    manager_lower = manager.lower()
                    normalized_name = NAME_MAP.get(manager_lower, manager)
                    
                    # Пропускаем если менеджер не в списке
                    if normalized_name not in PAVLOGRAD_MANAGERS:
                        continue
                    
                    # ВСЕ ТРУБКИ
                    if normalized_name not in stats_day:
                        stats_day[normalized_name] = 0
                    stats_day[normalized_name] += 1
                    
                    # ПЕРЕЗВОНЫ (только зелёные)
                    if color == "ЗЕЛЕНЫЙ":
                        if normalized_name not in recalls_day:
                            recalls_day[normalized_name] = 0
                        recalls_day[normalized_name] += 1
                
                # Сохраняем данные этого дня
                for manager_name in PAVLOGRAD_MANAGERS:
                    if manager_name in stats_day:
                        all_tubes_by_days[manager_name][day_name] = stats_day[manager_name]
                    
                    if manager_name in recalls_day:
                        recalls_by_days[manager_name][day_name] = recalls_day[manager_name]
                
                logger.info(f"✅ {day_name}: трубок={sum(stats_day.values())}, перезвонов={sum(recalls_day.values())}")
                
                # Переходим к следующему дню
                current_date += timedelta(days=1)
            
            logger.info("✅ Статистика по дням собрана")
            return all_tubes_by_days, recalls_by_days
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики по дням: {e}")
            raise
    
    async def _fetch_managers_data_for_date(self, date_str: str) -> Optional[List[Dict]]:
        """
        ✅ ИСПРАВЛЕНО: Возвращает None если лист не найден (вместо Exception)
        
        Args:
            date_str: Дата в формате DD.MM (например "15.12")
            
        Returns:
            Список словарей с данными или None если лист не найден
        """
        url = settings.GOOGLE_APPS_SCRIPT_URL
        
        if not url:
            logger.error("❌ GOOGLE_APPS_SCRIPT_URL не установлен в .env")
            raise ValueError("GOOGLE_APPS_SCRIPT_URL не настроен")
        
        params = {
            'action': 'managers',
            'date': date_str
        }
        
        logger.debug(f"🔗 Запрос: {url}?action=managers&date={date_str}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    if response.status != 200:
                        logger.error(f"❌ HTTP ошибка: {response.status}")
                        raise Exception(f"HTTP {response.status}")
                    
                    content_type = response.headers.get('Content-Type', '')
                    
                    if 'text/html' in content_type:
                        html_text = await response.text()
                        logger.error(f"❌ Apps Script вернул HTML вместо JSON!")
                        raise ValueError("Apps Script вернул HTML вместо JSON")
                    
                    data = await response.json()
                    
                    # ✅ КРИТИЧНО: Если лист не найден - возвращаем None
                    if isinstance(data, dict) and 'error' in data:
                        if "не найден" in data['error']:
                            logger.debug(f"📭 Лист {date_str} не найден (это нормально для будущих дней)")
                            return None
                        else:
                            logger.error(f"❌ Ошибка от скрипта: {data['error']}")
                            raise Exception(data['error'])
                    
                    if not isinstance(data, list):
                        logger.error(f"❌ Неожиданный формат данных: {type(data)}")
                        raise ValueError("Apps Script вернул не список")
                    
                    logger.debug(f"✅ Получено {len(data)} записей за {date_str}")
                    return data
                    
        except aiohttp.ClientError as e:
            logger.error(f"❌ Ошибка HTTP запроса: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных: {e}")
            raise
    
    def _calculate_gradient_color(self, value: int, min_val: int, max_val: int) -> dict:
        """Расчёт цвета градиента"""
        if max_val == min_val or max_val == 0:
            return {"red": 1, "green": 1, "blue": 0.7}
        
        normalized = (value - min_val) / (max_val - min_val)
        
        if normalized >= 0.75:
            return {"red": 0.7, "green": 0.9, "blue": 0.7}
        elif normalized >= 0.25:
            return {"red": 1, "green": 1, "blue": 0.7}
        else:
            return {"red": 1, "green": 0.7, "blue": 0.7}
    
    @retry(**API_RETRY_CONFIG)
    async def update_stats(self):
        """
        ✅ ГЛАВНАЯ ФУНКЦИЯ: Обновить статистику
        """
        if not self.client or not self.spreadsheet:
            raise Exception("Google Sheets сервис не инициализирован")
        
        try:
            now = datetime.now(self.timezone)
            
            # Пропускаем воскресенье
            if now.weekday() == 6:
                logger.info("📅 Воскресенье - обновление статистики пропущено")
                return
            
            start, end = self._get_week_range(now)
            title = self._get_week_title(start, end)
            
            logger.info(f"🔄 Обновление дашборда: {title}")
            logger.info(f"📅 Период: {start.strftime('%d.%m')} - {end.strftime('%d.%m')}")
            
            # 1. Получение или создание листа
            try:
                worksheet = self.spreadsheet.worksheet(title)
            except WorksheetNotFound:
                worksheet = await self._create_weekly_sheet()
                if not worksheet:
                    raise Exception("Не удалось создать лист")
            
            # 2. Получение статистики ПО ДНЯМ
            all_tubes_by_days, recalls_by_days = await self._get_week_stats_by_days(start, end)
            
            # 3. Подсчёт итогов
            all_totals = {}
            recalls_totals = {}
            
            for manager_name in PAVLOGRAD_MANAGERS:
                all_totals[manager_name] = sum(all_tubes_by_days[manager_name].values())
                recalls_totals[manager_name] = sum(recalls_by_days[manager_name].values())
            
            # 4. Обновление данных
            await self._update_dashboard_data(
                worksheet, 
                all_tubes_by_days, 
                recalls_by_days,
                all_totals,
                recalls_totals,
                now
            )
            
            # 5. Применение границ и градиентов
            await self._apply_borders_and_formatting(worksheet, all_totals, recalls_totals)
            
            logger.info(f"✅ Дашборд обновлён успешно")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статистики: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    async def _update_dashboard_data(
        self,
        worksheet,
        all_tubes_by_days: Dict,
        recalls_by_days: Dict,
        all_totals: Dict,
        recalls_totals: Dict,
        now: datetime
    ):
        """
        Обновление всех данных дашборда (горизонтальный layout)
        """
        updates = []
        
        # ===== ОБЩАЯ СТАТИСТИКА (W4-X7) =====
        total_tubes = sum(all_totals.values())
        total_recalls = sum(recalls_totals.values())
        recall_percent = int((total_recalls / total_tubes * 100)) if total_tubes > 0 else 0
        plan_completed = sum(1 for total in all_totals.values() if total >= WEEKLY_PLAN)
        
        updates.append({
            'range': 'W4:X7',
            'values': [
                ["📞 Всего трубок", total_tubes],
                ["🟢 Перезвоны", total_recalls],
                ["📈 % Перезвонов", f"{recall_percent}%"],
                ["✓ План выполнен", f"{plan_completed}/{len(PAVLOGRAD_MANAGERS)}"]
            ]
        })
        
        # ===== ТАБЛИЦА 1: ВСЕ ТРУБКИ (A5-J) =====
        all_tubes_data = []
        for idx, manager_name in enumerate(PAVLOGRAD_MANAGERS, 1):
            days_data = all_tubes_by_days[manager_name]
            total = all_totals[manager_name]
            plan_status = "✓" if total >= WEEKLY_PLAN else "✗"
            
            row = [
                idx,
                manager_name,
                days_data["ПН"],
                days_data["ВТ"],
                days_data["СР"],
                days_data["ЧТ"],
                days_data["ПТ"],
                days_data["СБ"],
                total,
                plan_status
            ]
            all_tubes_data.append(row)
        
        start_row = 5
        end_row = start_row + len(all_tubes_data) - 1
        
        updates.append({
            'range': f'A{start_row}:J{end_row}',
            'values': all_tubes_data
        })
        
        # ===== ТАБЛИЦА 2: ПЕРЕЗВОНЫ (L5-U) =====
        recalls_data = []
        
        for idx, manager_name in enumerate(PAVLOGRAD_MANAGERS, 1):
            days_data = recalls_by_days[manager_name]
            total = recalls_totals[manager_name]
            total_tubes = all_totals[manager_name]
            percent = int((total / total_tubes * 100)) if total_tubes > 0 else 0
            
            row = [
                idx,
                manager_name,
                days_data["ПН"],
                days_data["ВТ"],
                days_data["СР"],
                days_data["ЧТ"],
                days_data["ПТ"],
                days_data["СБ"],
                total,
                f"{percent}%"
            ]
            recalls_data.append(row)
        
        recalls_start_row = 5
        recalls_end_row = recalls_start_row + len(recalls_data) - 1
        
        updates.append({
            'range': f'L{recalls_start_row}:U{recalls_end_row}',
            'values': recalls_data
        })
        
        # ===== ИТОГО =====
        total_row = end_row + 1
        recalls_total_row = recalls_end_row + 1
        
        # Итого для всех трубок
        updates.append({
            'range': f'A{total_row}:B{total_row}',
            'values': [["", "ИТОГО:"]]
        })
        
        for col_letter in ['C', 'D', 'E', 'F', 'G', 'H', 'I']:
            updates.append({
                'range': f'{col_letter}{total_row}',
                'values': [[f"=SUM({col_letter}{start_row}:{col_letter}{end_row})"]]
            })
        
        # Итого для перезвонов
        updates.append({
            'range': f'L{recalls_total_row}:M{recalls_total_row}',
            'values': [["", "ИТОГО:"]]
        })
        
        for col_letter in ['N', 'O', 'P', 'Q', 'R', 'S', 'T']:
            updates.append({
                'range': f'{col_letter}{recalls_total_row}',
                'values': [[f"=SUM({col_letter}{recalls_start_row}:{col_letter}{recalls_end_row})"]]
            })
        
        # ===== ВРЕМЯ ОБНОВЛЕНИЯ =====
        update_time = f"🔄 Обновлено: {now.strftime('%d.%m.%Y %H:%M')}"
        updates.append({
            'range': 'L1',
            'values': [[update_time]]
        })
        
        # Отправка всех обновлений
        logger.info(f"📤 Отправка {len(updates)} обновлений...")
        worksheet.batch_update(updates, value_input_option='USER_ENTERED')
    
    async def _apply_borders_and_formatting(
        self,
        worksheet,
        all_totals: Dict,
        recalls_totals: Dict
    ):
        """
        Применение границ всех ячеек + градиентное форматирование
        """
        try:
            sheet_id = worksheet.id
            
            tubes_values = [v for v in all_totals.values() if v > 0]
            recalls_values = [v for v in recalls_totals.values() if v > 0]
            
            if not tubes_values:
                return
            
            min_tubes = min(tubes_values)
            max_tubes = max(tubes_values)
            
            min_recalls = min(recalls_values) if recalls_values else 0
            max_recalls = max(recalls_values) if recalls_values else 0
            
            start_row = 4
            data_start_row = 5
            data_end_row = data_start_row + len(PAVLOGRAD_MANAGERS) - 1
            total_row = data_end_row + 1
            
            requests = []
            
            # ===== ГРАНИЦЫ ТАБЛИЦЫ 1 (ВСЕ ТРУБКИ A4:J) =====
            requests.append({
                "updateBorders": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": start_row - 1,
                        "endRowIndex": total_row,
                        "startColumnIndex": 0,
                        "endColumnIndex": 10
                    },
                    "top": {"style": "SOLID", "width": 2},
                    "bottom": {"style": "SOLID", "width": 2},
                    "left": {"style": "SOLID", "width": 2},
                    "right": {"style": "SOLID", "width": 2},
                    "innerHorizontal": {"style": "SOLID", "width": 1},
                    "innerVertical": {"style": "SOLID", "width": 1}
                }
            })
            
            # ===== ГРАНИЦЫ ТАБЛИЦЫ 2 (ПЕРЕЗВОНЫ L4:U) =====
            requests.append({
                "updateBorders": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": start_row - 1,
                        "endRowIndex": total_row,
                        "startColumnIndex": 11,
                        "endColumnIndex": 21
                    },
                    "top": {"style": "SOLID", "width": 2},
                    "bottom": {"style": "SOLID", "width": 2},
                    "left": {"style": "SOLID", "width": 2},
                    "right": {"style": "SOLID", "width": 2},
                    "innerHorizontal": {"style": "SOLID", "width": 1},
                    "innerVertical": {"style": "SOLID", "width": 1}
                }
            })
            
            # ===== ГРАНИЦЫ ОБЩЕЙ СТАТИСТИКИ (W3:X7) =====
            requests.append({
                "updateBorders": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 2,
                        "endRowIndex": 7,
                        "startColumnIndex": 22,
                        "endColumnIndex": 24
                    },
                    "top": {"style": "SOLID", "width": 2},
                    "bottom": {"style": "SOLID", "width": 2},
                    "left": {"style": "SOLID", "width": 2},
                    "right": {"style": "SOLID", "width": 2},
                    "innerHorizontal": {"style": "SOLID", "width": 1},
                    "innerVertical": {"style": "SOLID", "width": 1}
                }
            })
            
            # ===== ГРАДИЕНТЫ =====
            for idx, manager_name in enumerate(PAVLOGRAD_MANAGERS):
                row_idx = data_start_row + idx
                
                # Градиент для ИТОГО (все трубки) - колонка I
                total = all_totals[manager_name]
                if total > 0:
                    color = self._calculate_gradient_color(total, min_tubes, max_tubes)
                    requests.append({
                        "repeatCell": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": row_idx - 1,
                                "endRowIndex": row_idx,
                                "startColumnIndex": 8,
                                "endColumnIndex": 9
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "backgroundColor": color,
                                    "textFormat": {"bold": True}
                                }
                            },
                            "fields": "userEnteredFormat(backgroundColor,textFormat)"
                        }
                    })
                
                # Градиент для ИТОГО (перезвоны) - колонка T
                total_recalls = recalls_totals[manager_name]
                if total_recalls > 0 and recalls_values:
                    color = self._calculate_gradient_color(total_recalls, min_recalls, max_recalls)
                    requests.append({
                        "repeatCell": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": row_idx - 1,
                                "endRowIndex": row_idx,
                                "startColumnIndex": 19,
                                "endColumnIndex": 20
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "backgroundColor": color,
                                    "textFormat": {"bold": True}
                                }
                            },
                            "fields": "userEnteredFormat(backgroundColor,textFormat)"
                        }
                    })
            
            # Форматируем строки ИТОГО
            for row_idx in [total_row, total_row]:
                requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": row_idx - 1,
                            "endRowIndex": row_idx,
                            "startColumnIndex": 0,
                            "endColumnIndex": 10
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                                "textFormat": {"bold": True}
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat)"
                    }
                })
                
                requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": row_idx - 1,
                            "endRowIndex": row_idx,
                            "startColumnIndex": 11,
                            "endColumnIndex": 21
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                                "textFormat": {"bold": True}
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat)"
                    }
                })
            
            # Применяем все изменения
            body = {"requests": requests}
            self.spreadsheet.batch_update(body)
            
            logger.info("✅ Границы и градиенты применены")
            
        except Exception as e:
            logger.error(f"❌ Ошибка применения границ: {e}")
    
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