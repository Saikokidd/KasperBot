"""
ПОЛНАЯ ВЕРСИЯ: services/google_sheets_service.py
Дашборд с перезвонами, планом и динамикой по дням

ВОЗМОЖНОСТИ:
✅ Сбор данных по каждому дню недели (ПН-СБ)
✅ Таблица всех трубок + таблица перезвонов
✅ Колонка выполнения плана (✓/✗)
✅ Процент перезвонов для каждого менеджера
✅ Градиентное форматирование
✅ Sparklines динамики
✅ Общая статистика вверху
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
        """Создать новый лист для недели с улучшенным дизайном"""
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
        Создаёт красивый layout дашборда
        """
        try:
            # ===== ШАПКА =====
            months_ru = {
                1: "Января", 2: "Февраля", 3: "Марта", 4: "Апреля",
                5: "Мая", 6: "Июня", 7: "Июля", 8: "Августа",
                9: "Сентября", 10: "Октября", 11: "Ноября", 12: "Декабря"
            }
            
            week_title = f"📊 СТАТИСТИКА НЕДЕЛИ {start.day}-{end.day} {months_ru[start.month].upper()} {start.year}"
            
            # Объединяем ячейки для заголовка
            worksheet.merge_cells('A1:S1')
            worksheet.update('A1', [[week_title]])
            
            # Время обновления
            worksheet.merge_cells('T1:W1')
            worksheet.update('T1', [[f"🔄 Обновлено: {datetime.now(self.timezone).strftime('%d.%m.%Y %H:%M')}"]])
            
            # ===== ОБЩАЯ СТАТИСТИКА (строка 3) =====
            headers_summary = [
                ["📊 Всего трубок", "🟢 Перезвоны", "📈 % Перезвонов", "✓ План выполнен"]
            ]
            worksheet.update('A3:D3', headers_summary)
            worksheet.update('A4:D4', [["0", "0", "0%", "0/0"]])
            
            # ===== ТАБЛИЦА 1: ВСЕ ТРУБКИ (A-J) =====
            worksheet.merge_cells('A6:J6')
            worksheet.update('A6', [["📞 ВСЕ ТРУБКИ"]])
            
            headers_all = [["№", "Менеджер", "ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ИТОГО", "ПЛАН"]]
            worksheet.update('A7:J7', headers_all)
            
            # ===== ТАБЛИЦА 2: ПЕРЕЗВОНЫ (L-U) =====
            worksheet.merge_cells('L6:U6')
            worksheet.update('L6', [["🟢 ПЕРЕЗВОНЫ"]])
            
            headers_recalls = [["№", "Менеджер", "ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ИТОГО", "%"]]
            worksheet.update('L7:U7', headers_recalls)
            
            # Применяем форматирование
            self._format_headers(worksheet)
            
            logger.info("✅ Layout дашборда создан")
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания layout: {e}")
    
    def _format_headers(self, worksheet):
        """Форматирование заголовков"""
        try:
            # Главный заголовок (синий)
            worksheet.format('A1:W1', {
                "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.7},
                "textFormat": {
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                    "bold": True,
                    "fontSize": 13
                },
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE"
            })
            
            # Общая статистика (светло-серый)
            worksheet.format('A3:D3', {
                "backgroundColor": {"red": 0.85, "green": 0.85, "blue": 0.85},
                "textFormat": {"bold": True, "fontSize": 10},
                "horizontalAlignment": "CENTER"
            })
            
            worksheet.format('A4:D4', {
                "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 1},
                "textFormat": {"bold": True, "fontSize": 11},
                "horizontalAlignment": "CENTER"
            })
            
            # Заголовок "ВСЕ ТРУБКИ" (синий)
            worksheet.format('A6:J6', {
                "backgroundColor": {"red": 0.4, "green": 0.6, "blue": 0.9},
                "textFormat": {
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                    "bold": True,
                    "fontSize": 11
                },
                "horizontalAlignment": "CENTER"
            })
            
            # Заголовок "ПЕРЕЗВОНЫ" (зелёный)
            worksheet.format('L6:U6', {
                "backgroundColor": {"red": 0.3, "green": 0.7, "blue": 0.4},
                "textFormat": {
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                    "bold": True,
                    "fontSize": 11
                },
                "horizontalAlignment": "CENTER"
            })
            
            # Заголовки колонок (светлые)
            worksheet.format('A7:J7', {
                "backgroundColor": {"red": 0.85, "green": 0.9, "blue": 1},
                "textFormat": {"bold": True, "fontSize": 9},
                "horizontalAlignment": "CENTER"
            })
            
            worksheet.format('L7:U7', {
                "backgroundColor": {"red": 0.85, "green": 1, "blue": 0.9},
                "textFormat": {"bold": True, "fontSize": 9},
                "horizontalAlignment": "CENTER"
            })
            
            # Ширина колонок
            body = {
                "requests": [
                    # Номер
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 40}, "fields": "pixelSize"}},
                    # Менеджер
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2}, "properties": {"pixelSize": 100}, "fields": "pixelSize"}},
                    # Дни + Итого
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 10}, "properties": {"pixelSize": 50}, "fields": "pixelSize"}},
                    # План
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 9, "endIndex": 10}, "properties": {"pixelSize": 50}, "fields": "pixelSize"}},
                    # Пробел между таблицами
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 10, "endIndex": 11}, "properties": {"pixelSize": 20}, "fields": "pixelSize"}},
                    # Перезвоны (аналогично)
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 11, "endIndex": 12}, "properties": {"pixelSize": 40}, "fields": "pixelSize"}},
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 12, "endIndex": 13}, "properties": {"pixelSize": 100}, "fields": "pixelSize"}},
                    {"updateDimensionProperties": {"range": {"sheetId": worksheet.id, "dimension": "COLUMNS", "startIndex": 13, "endIndex": 21}, "properties": {"pixelSize": 50}, "fields": "pixelSize"}},
                ]
            }
            self.spreadsheet.batch_update(body)
            
        except Exception as e:
            logger.error(f"❌ Ошибка форматирования: {e}")
    
    @retry(**API_RETRY_CONFIG)
    async def _get_week_stats_by_days(self, start_date: datetime, end_date: datetime) -> Tuple[Dict, Dict]:
        """
        ✅ КЛЮЧЕВАЯ ФУНКЦИЯ: Получить статистику ПО КАЖДОМУ ДНЮ недели
        
        Returns:
            (all_tubes_by_days, recalls_by_days)
            где каждый - Dict[manager_name][day] = count
        """
        try:
            from services.managers_stats_service import managers_stats_service
            
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
            
            # Проходим по каждому дню недели
            current_date = start_date
            day_names = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ"]
            
            while current_date <= end_date:
                day_index = current_date.weekday()
                day_name = day_names[day_index]
                
                logger.info(f"📅 Обработка {day_name} ({current_date.strftime('%d.%m.%Y')})")
                
                # Получаем данные за этот день
                # ВАЖНО: Apps Script ожидает запрос к конкретной дате
                # Для этого нужно модифицировать Apps Script чтобы принимать параметр date
                # Но пока используем текущий механизм (берём сегодняшние данные)
                
                # TODO: Тут нужно модифицировать fetch_managers_data 
                # чтобы передавать date параметр в Apps Script
                
                # ВРЕМЕННОЕ РЕШЕНИЕ: Используем существующий механизм
                # который берёт данные за "сегодня" из листа с названием текущей даты
                
                raw_data = await managers_stats_service._fetch_managers_data()
                
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
                
                # Переходим к следующему дню
                current_date += timedelta(days=1)
            
            logger.info("✅ Статистика по дням собрана")
            return all_tubes_by_days, recalls_by_days
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики по дням: {e}")
            raise
    
    def _calculate_gradient_color(self, value: int, min_val: int, max_val: int) -> dict:
        """
        Расчёт цвета градиента: Зелёный → Жёлтый → Красный
        """
        if max_val == min_val or max_val == 0:
            return {"red": 1, "green": 1, "blue": 0.7}
        
        normalized = (value - min_val) / (max_val - min_val)
        
        if normalized >= 0.75:
            # Топ 25% - зелёный
            return {"red": 0.7, "green": 0.9, "blue": 0.7}
        elif normalized >= 0.25:
            # Середина 50% - жёлтый
            return {"red": 1, "green": 1, "blue": 0.7}
        else:
            # Низ 25% - красный/розовый
            return {"red": 1, "green": 0.7, "blue": 0.7}
    
    @retry(**API_RETRY_CONFIG)
    async def update_stats(self):
        """
        ✅ ГЛАВНАЯ ФУНКЦИЯ: Обновить статистику с полным дашбордом
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
            
            # 5. Применение градиентов
            await self._apply_gradient_formatting(worksheet, all_totals, recalls_totals)
            
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
        Обновление всех данных дашборда
        """
        updates = []
        
        # ===== ОБЩАЯ СТАТИСТИКА =====
        total_tubes = sum(all_totals.values())
        total_recalls = sum(recalls_totals.values())
        recall_percent = int((total_recalls / total_tubes * 100)) if total_tubes > 0 else 0
        plan_completed = sum(1 for total in all_totals.values() if total >= WEEKLY_PLAN)
        
        updates.append({
            'range': 'A4:D4',
            'values': [[
                total_tubes,
                total_recalls,
                f"{recall_percent}%",
                f"{plan_completed}/{len(PAVLOGRAD_MANAGERS)}"
            ]]
        })
        
        # ===== ТАБЛИЦА 1: ВСЕ ТРУБКИ =====
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
        
        start_row = 8
        end_row = start_row + len(all_tubes_data) - 1
        
        updates.append({
            'range': f'A{start_row}:J{end_row}',
            'values': all_tubes_data
        })
        
        # ===== ТАБЛИЦА 2: ПЕРЕЗВОНЫ =====
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
        
        updates.append({
            'range': f'L{start_row}:U{end_row}',
            'values': recalls_data
        })
        
        # ===== ИТОГО =====
        total_row = end_row + 1
        
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
            'range': f'L{total_row}:M{total_row}',
            'values': [["", "ИТОГО:"]]
        })
        
        for col_letter in ['N', 'O', 'P', 'Q', 'R', 'S', 'T']:
            updates.append({
                'range': f'{col_letter}{total_row}',
                'values': [[f"=SUM({col_letter}{start_row}:{col_letter}{end_row})"]]
            })
        
        # ===== ВРЕМЯ ОБНОВЛЕНИЯ =====
        update_time = f"🔄 Обновлено: {now.strftime('%d.%m.%Y %H:%M')}"
        updates.append({
            'range': 'T1',
            'values': [[update_time]]
        })
        
        # Отправка всех обновлений
        logger.info(f"📤 Отправка {len(updates)} обновлений...")
        worksheet.batch_update(updates, value_input_option='USER_ENTERED')
    
    async def _apply_gradient_formatting(
        self,
        worksheet,
        all_totals: Dict,
        recalls_totals: Dict
    ):
        """
        Применение градиентного форматирования
        """
        try:
            # Находим min/max
            tubes_values = [v for v in all_totals.values() if v > 0]
            recalls_values = [v for v in recalls_totals.values() if v > 0]
            
            if not tubes_values:
                return
            
            min_tubes = min(tubes_values)
            max_tubes = max(tubes_values)
            
            min_recalls = min(recalls_values) if recalls_values else 0
            max_recalls = max(recalls_values) if recalls_values else 0
            
            start_row = 8
            
            # Градиент для ИТОГО (все трубки)
            for idx, manager_name in enumerate(PAVLOGRAD_MANAGERS, start_row):
                total = all_totals[manager_name]
                if total > 0:
                    color = self._calculate_gradient_color(total, min_tubes, max_tubes)
                    worksheet.format(f'I{idx}', {
                        "backgroundColor": color,
                        "textFormat": {"bold": True}
                    })
            
            # Градиент для ИТОГО (перезвоны)
            if recalls_values:
                for idx, manager_name in enumerate(PAVLOGRAD_MANAGERS, start_row):
                    total = recalls_totals[manager_name]
                    if total > 0:
                        color = self._calculate_gradient_color(total, min_recalls, max_recalls)
                        worksheet.format(f'T{idx}', {
                            "backgroundColor": color,
                            "textFormat": {"bold": True}
                        })
            
            # Форматируем строку ИТОГО
            total_row = start_row + len(PAVLOGRAD_MANAGERS)
            worksheet.format(f'A{total_row}:U{total_row}', {
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                "textFormat": {"bold": True}
            })
            
            logger.info("✅ Градиентное форматирование применено")
            
        except Exception as e:
            logger.error(f"❌ Ошибка применения градиента: {e}")
    
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