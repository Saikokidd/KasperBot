"""
services/base_stats_service.py
Сервис для автоматизации таблицы "Статистика баз"

ФУНКЦИОНАЛ:
✅ Парсинг данных поставщиков из рабочей таблицы
✅ Подсчёт трубок и перезвонов по каждому поставщику
✅ Автоматическое заполнение недельных листов
✅ Форматирование и раскраска ячеек
"""

import re
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
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)
import logging

load_dotenv()

# ===== КОНСТАНТЫ =====

# Retry для Google Sheets API
API_RETRY_CONFIG = {
    'stop': stop_after_attempt(3),
    'wait': wait_exponential(min=2, max=10),
    'retry': retry_if_exception_type((APIError,)),
    'before_sleep': before_sleep_log(logger, logging.WARNING)
}


class ProviderInfo:
    """Класс для хранения информации о поставщике"""
    
    def __init__(self, raw_text: str):
        self.raw_text = raw_text
        self.date: Optional[str] = None          # "15.12"
        self.quantity: Optional[int] = None      # 1000, 3000, 500
        self.provider_text: Optional[str] = None # ВСЁ после даты (нормализованное)
        
        self._parse()
    
    def _parse(self):
        """
        Парсит строку поставщика
        
        ✅ ИСПРАВЛЕНО: Дата может быть в начале или в конце!
        
        Примеры:
        "15.12 тест" → дата="15.12", кол=None, текст="тест"
        "1к Микс регионов_XX_15.12" → дата="15.12", кол=1000, текст="1к Микс регионов_XX"
        "15.12 3к_МСК_helphub-3" → дата="15.12", кол=3000, текст="3к_МСК_helphub-3"
        """
        text = self.raw_text.strip()
        
        if not text:
            return
        
        # ===== ШАГ 1: Извлечь дату (может быть в начале ИЛИ в конце!) =====
        date_matches = list(re.finditer(r'(\d{1,2}\.\d{1,2})', text))
        
        if date_matches:
            # Берём первую найденную дату
            date_match = date_matches[0]
            self.date = date_match.group(1)
            
            # Удаляем дату из текста
            text = text.replace(date_match.group(0), '').strip()
            
            # Удаляем лишние пробелы/подчёркивания в начале/конце
            text = text.strip('_ ')
        
        # ===== ШАГ 2: Извлечь количество =====
        # Паттерны: 1к, 3к, 0.5к, 1.5к (с пробелом или без)
        quantity_match = re.search(r'(\d+\.?\d*)\s*к', text, re.IGNORECASE)
        if quantity_match:
            quantity_str = quantity_match.group(1)
            self.quantity = int(float(quantity_str) * 1000)
        
        # ===== ШАГ 3: Нормализовать текст поставщика =====
        # Убираем лишние пробелы, заменяем множественные на одинарные
        text = re.sub(r'\s+', ' ', text).strip()
        
        self.provider_text = text if text else self.raw_text
        
        logger.debug(
            f"Парсинг: '{self.raw_text}' → "
            f"дата={self.date}, кол={self.quantity}, "
            f"текст='{self.provider_text}'"
        )
    
    def __str__(self):
        return self.provider_text or self.raw_text
    
    def __repr__(self):
        return f"ProviderInfo('{self.raw_text}')"


class BaseStatsService:
    """Сервис для работы с таблицей 'Статистика баз'"""
    
    def __init__(self):
        """Инициализация сервиса"""
        self.client = None
        self.spreadsheet = None
        self.sheet_id = os.getenv("BASE_STATS_SHEET_ID")  # НОВАЯ переменная
        self.credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")
        self.timezone = pytz.timezone('Europe/Kiev')
        
        # ID рабочей таблицы (откуда берём данные)
        self.source_sheet_id = os.getenv("GOOGLE_SHEETS_ID")
        
        if not self.sheet_id:
            logger.warning("⚠️ BASE_STATS_SHEET_ID не найден - статистика баз недоступна")
            return
        
        if not self._authorize():
            logger.error("❌ Не удалось авторизоваться в Google Sheets")
            return
        
        logger.info("✅ BaseStatsService инициализирован")
    
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
            
            logger.info(f"✅ Подключение к таблице: {self.spreadsheet.title}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка авторизации: {e}")
            return False
    
    def _get_week_range(self, date: datetime) -> Tuple[datetime, datetime]:
        """Получить диапазон текущей недели (ПН-СБ)"""
        # Если воскресенье → следующий понедельник
        if date.weekday() == 6:
            start = date + timedelta(days=1)
        else:
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
    
    @retry(**API_RETRY_CONFIG)
    async def _fetch_provider_data_for_date(self, date_str: str) -> List[Dict]:
        """
        Получить данные из рабочей таблицы за конкретную дату
        
        Args:
            date_str: Дата в формате DD.MM (например "15.12")
            
        Returns:
            Список строк с данными (включая колонку "Поставщик")
        """
        url = settings.GOOGLE_APPS_SCRIPT_URL
        
        if not url:
            logger.error("❌ GOOGLE_APPS_SCRIPT_URL не установлен")
            raise ValueError("GOOGLE_APPS_SCRIPT_URL не настроен")
        
        params = {
            'action': 'providers',  # Новый endpoint в Apps Script
            'date': date_str
        }
        
        logger.debug(f"🔗 Запрос данных поставщиков за {date_str}")
        
        import aiohttp
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    if response.status != 200:
                        logger.error(f"❌ HTTP {response.status}")
                        raise Exception(f"HTTP {response.status}")
                    
                    data = await response.json()
                    
                    if isinstance(data, dict) and 'error' in data:
                        if "не найден" in data['error']:
                            logger.debug(f"📭 Лист {date_str} не найден")
                            return []
                        else:
                            raise Exception(data['error'])
                    
                    if not isinstance(data, list):
                        raise ValueError("Apps Script вернул не список")
                    
                    logger.debug(f"✅ Получено {len(data)} записей за {date_str}")
                    return data
                    
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных: {e}")
            raise
    
    async def _count_calls_by_provider(
        self, 
        date_str: str
    ) -> Dict[str, Dict[str, int]]:
        """
        Подсчитать трубки и перезвоны по каждому поставщику за день
        
        ✅ ИСПРАВЛЕНО: Группировка одинаковых поставщиков
        
        Args:
            date_str: Дата в формате DD.MM
            
        Returns:
            Словарь: {
                "тест": {
                    "calls": 20, 
                    "recalls": 5,
                    "rows": 0
                },
                "3к_МСК_helphub-3": {
                    "calls": 18, 
                    "recalls": 6,
                    "rows": 3000
                }
            }
        """
        raw_data = await self._fetch_provider_data_for_date(date_str)
        
        if not raw_data:
            return {}
        
        stats = {}
        
        for row in raw_data:
            # Получаем информацию о поставщике
            provider_raw = row.get("поставщик", "").strip()
            
            if not provider_raw:
                continue
            
            # Парсим информацию о поставщике
            provider_info = ProviderInfo(provider_raw)
            
            # ✅ ИСПОЛЬЗУЕМ provider_text БЕЗ ИЗМЕНЕНИЙ
            provider_key = provider_info.provider_text
            
            if not provider_key:
                continue
            
            # ✅ ГРУППИРОВКА: Если поставщик уже есть - суммируем
            if provider_key not in stats:
                stats[provider_key] = {
                    "calls": 0,
                    "recalls": 0,
                    "rows": provider_info.quantity or 0  # Берём из ПЕРВОЙ строки
                }
            
            # Считаем трубки (всегда +1)
            stats[provider_key]["calls"] += 1
            
            # Считаем перезвоны (если цвет зелёный)
            color = row.get("цвет", "").strip().upper()
            if color == "ЗЕЛЕНЫЙ":
                stats[provider_key]["recalls"] += 1
        
        logger.info(
            f"📊 Статистика за {date_str}: "
            f"{len(stats)} уникальных поставщиков, "
            f"{sum(s['calls'] for s in stats.values())} трубок"
        )
        
        return stats
    
    async def _create_weekly_sheet(self) -> Optional[object]:
        """Создать новый лист для недели"""
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
                cols=20
            )
            
            logger.info(f"✅ Создан новый лист: {title}")
            
            # Применяем layout
            await self._setup_sheet_layout(worksheet, start, end)
            
            return worksheet
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания листа: {e}")
            return None
    
    async def _setup_sheet_layout(self, worksheet, start: datetime, end: datetime):
        """Создать layout листа (как на скрине 1)"""
        try:
            # ===== ШАПКА =====
            title = f"📊 СТАТИСТИКА БАЗ - {start.strftime('%d.%m')} - {end.strftime('%d.%m.%Y')}"
            
            worksheet.merge_cells('A1:H1')
            worksheet.update('A1', [[title]])
            
            # ===== ЗАГОЛОВКИ =====
            headers = [[
                "Дата", "Поставщик", "Строки", "Кол-во", "Бомж", 
                "перезвоны", "Пошло в работу", "Закрыто"
            ]]
            worksheet.update('A2:H2', headers)
            
            # ===== ФОРМАТИРОВАНИЕ =====
            sheet_id = worksheet.id
            
            # Шапка (синяя)
            worksheet.format('A1:H1', {
                "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.7},
                "textFormat": {
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                    "bold": True,
                    "fontSize": 12
                },
                "horizontalAlignment": "CENTER"
            })
            
            # Заголовки (светло-голубые)
            worksheet.format('A2:H2', {
                "backgroundColor": {"red": 0.85, "green": 0.9, "blue": 1},
                "textFormat": {"bold": True, "fontSize": 10},
                "horizontalAlignment": "CENTER"
            })
            
            # Ширина колонок
            body = {
                "requests": [
                    {"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 90}, "fields": "pixelSize"}},   # Дата
                    {"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2}, "properties": {"pixelSize": 200}, "fields": "pixelSize"}},  # Поставщик
                    {"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 3}, "properties": {"pixelSize": 80}, "fields": "pixelSize"}},   # Строки
                    {"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 3, "endIndex": 8}, "properties": {"pixelSize": 100}, "fields": "pixelSize"}},  # Остальные
                ]
            }
            self.spreadsheet.batch_update(body)
            
            logger.info("✅ Layout листа создан")
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания layout: {e}")
    
    @retry(**API_RETRY_CONFIG)
    async def update_stats(self):
        """
        Главная функция обновления статистики
        """
        if not self.client or not self.spreadsheet:
            raise Exception("BaseStatsService не инициализирован")
        
        try:
            now = datetime.now(self.timezone)
            
            # Пропускаем воскресенье
            if now.weekday() == 6:
                logger.info("📅 Воскресенье - обновление пропущено")
                return
            
            start, end = self._get_week_range(now)
            title = self._get_week_title(start, end)
            
            logger.info(f"🔄 Обновление статистики баз: {title}")
            
            # 1. Получить или создать лист
            try:
                worksheet = self.spreadsheet.worksheet(title)
            except WorksheetNotFound:
                worksheet = await self._create_weekly_sheet()
                if not worksheet:
                    raise Exception("Не удалось создать лист")
            
            # 2. Собираем данные за каждый день недели
            all_stats = {}  # {date_str: {provider: {calls, recalls}}}
            
            current_date = start
            today = datetime.now(self.timezone).date()
            
            while current_date <= end:
                # Пропускаем будущие дни
                if current_date.date() > today:
                    current_date += timedelta(days=1)
                    continue
                
                date_str = current_date.strftime('%d.%m')
                logger.info(f"📅 Обработка {date_str}")
                
                stats = await self._count_calls_by_provider(date_str)
                all_stats[date_str] = stats
                
                current_date += timedelta(days=1)
            
            # 3. Обновляем лист
            await self._update_sheet_data(worksheet, all_stats, start)
            
            logger.info("✅ Статистика баз обновлена")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статистики баз: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    async def _update_sheet_data(
        self,
        worksheet,
        all_stats: Dict[str, Dict[str, Dict[str, int]]],
        week_start: datetime
    ):
        """Обновить данные на листе"""
        updates = []
        
        row = 3  # Начинаем с 3-й строки (после заголовков)
        
        # Проходим по дням недели
        for day_offset in range(6):  # ПН-СБ
            current_date = week_start + timedelta(days=day_offset)
            date_str = current_date.strftime('%d.%m')
            
            stats = all_stats.get(date_str, {})
            
            if not stats:
                # Пустой день
                continue
            
            # Добавляем строку для каждого поставщика
            for provider, data in sorted(stats.items()):
                updates.append({
                    'range': f'A{row}:H{row}',
                    'values': [[
                        date_str,
                        provider,                # ✅ Полный текст БЕЗ ИЗМЕНЕНИЙ
                        data.get('rows', 0),     # ✅ НОВОЕ: Количество строк
                        data['calls'],           # Кол-во трубок
                        "",                      # Бомж (заполняется вручную)
                        data['recalls'],         # Перезвоны
                        "",                      # Пошло в работу (вручную)
                        ""                       # Закрыто (вручную)
                    ]]
                })
                row += 1
            
            # Добавляем пустую строку между днями
            row += 1
        
        # Отправляем все обновления
        if updates:
            logger.info(f"📤 Отправка {len(updates)} обновлений")
            worksheet.batch_update(updates, value_input_option='USER_ENTERED')
            
            # Применяем границы
            await self._apply_borders(worksheet, row - 1)
    
    async def _apply_borders(self, worksheet, last_row: int):
        """Применить границы к таблице"""
        try:
            sheet_id = worksheet.id
            
            requests = [{
                "updateBorders": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,  # Со 2-й строки (заголовки)
                        "endRowIndex": last_row,
                        "startColumnIndex": 0,
                        "endColumnIndex": 8  # ✅ Изменено с 7 на 8
                    },
                    "top": {"style": "SOLID", "width": 2},
                    "bottom": {"style": "SOLID", "width": 2},
                    "left": {"style": "SOLID", "width": 2},
                    "right": {"style": "SOLID", "width": 2},
                    "innerHorizontal": {"style": "SOLID", "width": 1},
                    "innerVertical": {"style": "SOLID", "width": 1}
                }
            }]
            
            body = {"requests": requests}
            self.spreadsheet.batch_update(body)
            
            logger.info("✅ Границы применены")
            
        except Exception as e:
            logger.error(f"❌ Ошибка применения границ: {e}")


# Глобальный экземпляр сервиса
base_stats_service = BaseStatsService()