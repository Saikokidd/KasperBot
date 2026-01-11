"""
services/base_stats_service.py
Сервис для автоматизации таблицы "Статистика баз"

СТРУКТУРА ТАБЛИЦЫ (как на скрине):
✅ Дата в первой колонке (объединённая ячейка)
✅ Строки поставщиков под датой
✅ Итоговая строка (голубая) после каждой даты
✅ Автозаполнение: Дата, Поставщик, Кол-во, Перезвоны
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
API_RETRY_CONFIG = {
    'stop': stop_after_attempt(3),
    'wait': wait_exponential(min=2, max=10),
    'retry': retry_if_exception_type((APIError,)),
    'before_sleep': before_sleep_log(logger, logging.WARNING)
}


class BaseStatsService:
    """Сервис для работы с таблицей 'Статистика баз'"""
    
    def __init__(self):
        """Инициализация сервиса"""
        self.client = None
        self.spreadsheet = None
        self.sheet_id = os.getenv("BASE_STATS_SHEET_ID")
        self.credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")
        self.timezone = pytz.timezone('Europe/Kiev')
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
        if date.weekday() == 6:
            start = date + timedelta(days=1)
        else:
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
    
    @retry(**API_RETRY_CONFIG)
    async def _fetch_provider_data_for_date(self, date_str: str) -> List[Dict]:
        """Получить данные поставщиков за конкретную дату"""
        url = settings.GOOGLE_APPS_SCRIPT_URL
        
        if not url:
            logger.error("❌ GOOGLE_APPS_SCRIPT_URL не установлен")
            raise ValueError("GOOGLE_APPS_SCRIPT_URL не настроен")
        
        params = {
            'action': 'providers',
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
    
    def _count_calls_from_raw_data(self, raw_data: List[Dict]) -> Dict[str, Dict[str, int]]:
        """
        Подсчитать метрики по каждому поставщику (для тестирования)
        
        Returns:
            Словарь: {
                "3к_МСК_helphub": {
                    "calls": 12,        # Общее кол-во
                    "recalls": 4,       # Зелёные (перезвоны)
                    "bomzh": 2          # Розовые (бомжи)
                }
            }
        """
        if not raw_data:
            return {}
        
        stats = {}
        
        for row in raw_data:
            provider = row.get("поставщик", "").strip()
            
            if not provider:
                continue
            
            if provider not in stats:
                stats[provider] = {
                    "calls": 0,
                    "recalls": 0,
                    "bomzh": 0
                }
            
            stats[provider]["calls"] += 1
            
            # Определяем тип трубки по цвету в графе "итог"
            itog_color = row.get("итог_цвет", "").strip().upper()
            
            if itog_color == "РОЗОВЫЙ":
                stats[provider]["bomzh"] += 1
            elif itog_color == "ЗЕЛЕНЫЙ":
                stats[provider]["recalls"] += 1
        
        return stats
    
    async def _count_calls_by_provider(self, date_str: str) -> Dict[str, Dict[str, int]]:
        """
        Подсчитать метрики по каждому поставщику за день
        
        Returns:
            Словарь: {
                "3к_МСК_helphub": {
                    "calls": 12,        # Общее кол-во
                    "recalls": 4,       # Зелёные (перезвоны)
                    "bomzh": 2          # Розовые (бомжи)
                }
            }
        """
        raw_data = await self._fetch_provider_data_for_date(date_str)
        
        stats = self._count_calls_from_raw_data(raw_data)
        
        if stats:
            logger.info(
                f"📊 Статистика за {date_str}: "
                f"{len(stats)} поставщиков, "
                f"{sum(s['calls'] for s in stats.values())} трубок, "
                f"бомжей: {sum(s['bomzh'] for s in stats.values())}, "
                f"перезвонов: {sum(s['recalls'] for s in stats.values())}"
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
            
            worksheet = self.spreadsheet.add_worksheet(
                title=title,
                rows=200,
                cols=10
            )
            
            logger.info(f"✅ Создан новый лист: {title}")
            
            await self._setup_sheet_layout(worksheet, start, end)
            
            return worksheet
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания листа: {e}")
            return None
    
    async def _setup_sheet_layout(self, worksheet, start: datetime, end: datetime):
        """Создать layout листа с профессиональным дизайном"""
        try:
            # ===== ШАПКА =====
            title = f"📊 СТАТИСТИКА БАЗ ПАВЛОГРАД - {start.strftime('%d.%m')} - {end.strftime('%d.%m.%Y')}"
            
            worksheet.merge_cells('A1:H1')
            worksheet.update('A1', [[title]])
            
            # ===== ЗАГОЛОВКИ =====
            headers = [[
                "Дата", "Поставщик", "Кол-во", "Бомж", 
                "Перезвоны", "Пошло в работу", "Закрыто", "% перезвонов"
            ]]
            worksheet.update('A2:H2', headers)
            
            # ===== ФОРМАТИРОВАНИЕ ШАПКИ =====
            worksheet.format('A1:H1', {
                "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.7},
                "textFormat": {
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                    "bold": True,
                    "fontSize": 14
                },
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE"
            })
            
            # ===== ФОРМАТИРОВАНИЕ ЗАГОЛОВКОВ =====
            worksheet.format('A2:H2', {
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                "textFormat": {"bold": True, "fontSize": 11},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "borders": {
                    "top": {"style": "SOLID", "width": 2},
                    "bottom": {"style": "SOLID", "width": 2},
                    "left": {"style": "SOLID", "width": 1},
                    "right": {"style": "SOLID", "width": 1}
                }
            })
            
            # ===== ШИРИНА КОЛОНОК =====
            sheet_id = worksheet.id
            body = {
                "requests": [
                    {"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 100}, "fields": "pixelSize"}},
                    {"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2}, "properties": {"pixelSize": 250}, "fields": "pixelSize"}},
                    {"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 8}, "properties": {"pixelSize": 120}, "fields": "pixelSize"}},
                ]
            }
            self.spreadsheet.batch_update(body)
            
            logger.info("✅ Layout листа создан")
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания layout: {e}")
    
    @retry(**API_RETRY_CONFIG)
    async def update_stats(self):
        """Главная функция обновления статистики"""
        if not self.client or not self.spreadsheet:
            raise Exception("BaseStatsService не инициализирован")
        
        try:
            now = datetime.now(self.timezone)
            
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
            all_stats = {}
            
            current_date = start
            today = datetime.now(self.timezone).date()
            
            while current_date <= end:
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
        """
        Обновить данные на листе с профессиональным дизайном
        
        ✅ СТРУКТУРА:
        | Дата       | Поставщик      | Кол-во | Бомж | Перезвоны | Пошло | Закрыто | % перезвонов |
        | 15.12.2025 | 3к_МСК_helphub | 12     | 2    | 4         |       |         | 33%          |
        | 15.12.2025 | 1к_регл_Анон   | 16     | 1    | 9         |       |         | 56%          |
        |------------|----------------|--------|------|-----------|-------|---------|--------------|
        | ИТОГО      | ИТОГО          | 45     | 3    | 16        |       |         | 36%          | ← Голубая
        """
        updates = []
        merge_requests = []
        format_requests = []
        sheet_id = worksheet.id
        
        row = 3  # Начинаем с 3-й строки
        weekly_stats = {
            "total_calls": 0,
            "total_bomzh": 0,
            "total_recalls": 0
        }
        
        # Проходим по дням недели
        for day_offset in range(6):  # ПН-СБ
            current_date = week_start + timedelta(days=day_offset)
            date_str = current_date.strftime('%d.%m')
            date_full = current_date.strftime('%d.%m.%Y')
            
            stats = all_stats.get(date_str, {})
            
            if not stats:
                continue
            
            first_row = row  # Запоминаем первую строку для объединения
            day_total_calls = sum(s['calls'] for s in stats.values())
            day_total_bomzh = sum(s['bomzh'] for s in stats.values())
            day_total_recalls = sum(s['recalls'] for s in stats.values())
            
            # Обновляем итоги за неделю
            weekly_stats["total_calls"] += day_total_calls
            weekly_stats["total_bomzh"] += day_total_bomzh
            weekly_stats["total_recalls"] += day_total_recalls
            
            # ===== СТРОКИ ПОСТАВЩИКОВ =====
            for provider, data in sorted(stats.items()):
                # Расчет процента перезвонов
                pct_recalls = (data['recalls'] / data['calls'] * 100) if data['calls'] > 0 else 0
                
                updates.append({
                    'range': f'A{row}:H{row}',
                    'values': [[
                        date_full,                    # Дата полная (DD.MM.YYYY)
                        provider,                     # Поставщик
                        data['calls'],               # Кол-во
                        data['bomzh'],               # Бомж
                        data['recalls'],             # Перезвоны
                        "",                          # Пошло в работу (заполнять вручную)
                        "",                          # Закрыто (заполнять вручную)
                        f"{pct_recalls:.0f}%"       # % перезвонов
                    ]]
                })
                
                # Форматирование строк поставщиков
                format_requests.extend(self._get_provider_row_format(sheet_id, row, pct_recalls))
                
                row += 1
            
            last_row = row - 1
            
            # ===== ОБЪЕДИНЕНИЕ ЯЧЕЕК ДАТЫ (оранжевая) =====
            if last_row >= first_row:
                merge_requests.append({
                    "mergeCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": first_row - 1,
                            "endRowIndex": last_row,
                            "startColumnIndex": 0,
                            "endColumnIndex": 1
                        },
                        "mergeType": "MERGE_ALL"
                    }
                })
                
                # Форматирование даты (оранжевая)
                format_requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": first_row - 1,
                            "endRowIndex": last_row,
                            "startColumnIndex": 0,
                            "endColumnIndex": 1
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {"red": 1, "green": 0.65, "blue": 0.3},
                                "textFormat": {"bold": True, "fontSize": 11},
                                "horizontalAlignment": "CENTER",
                                "verticalAlignment": "MIDDLE"
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)"
                    }
                })
            
            # ===== ИТОГОВАЯ СТРОКА ЗА ДЕНЬ (голубая) =====
            day_pct_recalls = (day_total_recalls / day_total_calls * 100) if day_total_calls > 0 else 0
            
            updates.append({
                'range': f'A{row}:H{row}',
                'values': [[
                    "ИТОГО",
                    "ИТОГО",
                    day_total_calls,
                    day_total_bomzh,
                    day_total_recalls,
                    "",
                    "",
                    f"{day_pct_recalls:.0f}%"
                ]]
            })
            
            # Форматирование итоговой строки (голубая)
            format_requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row - 1,
                        "endRowIndex": row,
                        "startColumnIndex": 0,
                        "endColumnIndex": 8
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.5, "green": 0.8, "blue": 1.0},
                            "textFormat": {"bold": True, "fontSize": 11},
                            "horizontalAlignment": "CENTER",
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
                }
            })
            
            row += 2  # Отступ между днями
        
        # ===== ИТОГОВАЯ СТРОКА ЗА НЕДЕЛЮ (тёмно-голубая) =====
        if weekly_stats["total_calls"] > 0:
            weekly_pct = (weekly_stats["total_recalls"] / weekly_stats["total_calls"] * 100)
            
            updates.append({
                'range': f'A{row}:H{row}',
                'values': [[
                    "НЕДЕЛЯ",
                    "ИТОГО",
                    weekly_stats["total_calls"],
                    weekly_stats["total_bomzh"],
                    weekly_stats["total_recalls"],
                    "",
                    "",
                    f"{weekly_pct:.0f}%"
                ]]
            })
            
            format_requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row - 1,
                        "endRowIndex": row,
                        "startColumnIndex": 0,
                        "endColumnIndex": 8
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.2, "green": 0.5, "blue": 0.8},
                            "textFormat": {"bold": True, "fontSize": 12, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                            "horizontalAlignment": "CENTER",
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
                }
            })
        
        # Отправляем обновления
        if updates:
            logger.info(f"📤 Отправка {len(updates)} обновлений")
            worksheet.batch_update(updates, value_input_option='USER_ENTERED')
        
        # Применяем объединение и форматирование
        if merge_requests or format_requests:
            body = {"requests": merge_requests + format_requests}
            self.spreadsheet.batch_update(body)
            logger.info("✅ Форматирование и объединение применены")
        
        # Границы
        await self._apply_borders(worksheet, row)
    
    def _get_provider_row_format(self, sheet_id: int, row: int, pct_recalls: float) -> List[Dict]:
        """Форматирование строки поставщика с правильными цветами"""
        return [
            # Поставщик (фиолетовая)
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row - 1,
                        "endRowIndex": row,
                        "startColumnIndex": 1,
                        "endColumnIndex": 2
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.9, "green": 0.8, "blue": 1.0},
                            "horizontalAlignment": "CENTER"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,horizontalAlignment)"
                }
            },
            # Кол-во (жёлтая)
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row - 1,
                        "endRowIndex": row,
                        "startColumnIndex": 2,
                        "endColumnIndex": 3
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 1, "green": 1, "blue": 0.4},
                            "textFormat": {"bold": True},
                            "horizontalAlignment": "CENTER"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
                }
            },
            # Бомж (розовая)
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row - 1,
                        "endRowIndex": row,
                        "startColumnIndex": 3,
                        "endColumnIndex": 4
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 1, "green": 0.75, "blue": 0.8},
                            "textFormat": {"bold": True},
                            "horizontalAlignment": "CENTER"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
                }
            },
            # Перезвоны (зелёная)
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row - 1,
                        "endRowIndex": row,
                        "startColumnIndex": 4,
                        "endColumnIndex": 5
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.7, "green": 0.95, "blue": 0.7},
                            "textFormat": {"bold": True},
                            "horizontalAlignment": "CENTER"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
                }
            },
            # Пошло в работу (фиолетовая)
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row - 1,
                        "endRowIndex": row,
                        "startColumnIndex": 5,
                        "endColumnIndex": 6
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 1, "green": 0.8, "blue": 1.0},
                            "horizontalAlignment": "CENTER"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,horizontalAlignment)"
                }
            },
            # Закрыто (голубая)
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row - 1,
                        "endRowIndex": row,
                        "startColumnIndex": 6,
                        "endColumnIndex": 7
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.7, "green": 0.9, "blue": 1.0},
                            "horizontalAlignment": "CENTER"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,horizontalAlignment)"
                }
            },
            # % перезвонов (серая с условным цветом)
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row - 1,
                        "endRowIndex": row,
                        "startColumnIndex": 7,
                        "endColumnIndex": 8
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
                            "textFormat": {"bold": True},
                            "horizontalAlignment": "CENTER"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
                }
            }
        ]
    
    async def _apply_borders(self, worksheet, last_row: int):
        """Применить границы к таблице"""
        try:
            sheet_id = worksheet.id
            
            requests = [{
                "updateBorders": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": last_row,
                        "startColumnIndex": 0,
                        "endColumnIndex": 7
                    },
                    "top": {"style": "SOLID", "width": 2, "color": {"red": 0, "green": 0, "blue": 0}},
                    "bottom": {"style": "SOLID", "width": 2, "color": {"red": 0, "green": 0, "blue": 0}},
                    "left": {"style": "SOLID", "width": 2, "color": {"red": 0, "green": 0, "blue": 0}},
                    "right": {"style": "SOLID", "width": 2, "color": {"red": 0, "green": 0, "blue": 0}},
                    "innerHorizontal": {"style": "SOLID", "width": 1, "color": {"red": 0, "green": 0, "blue": 0}},
                    "innerVertical": {"style": "SOLID", "width": 1, "color": {"red": 0, "green": 0, "blue": 0}}
                }
            }]
            
            body = {"requests": requests}
            self.spreadsheet.batch_update(body)
            
            logger.info("✅ Границы применены")
            
        except Exception as e:
            logger.error(f"❌ Ошибка применения границ: {e}")


# Глобальный экземпляр сервиса
base_stats_service = BaseStatsService()