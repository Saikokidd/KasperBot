"""
services/base_stats_service.py
ПЕРЕРАБОТАННЫЙ сервис для статистики баз

НОВАЯ АРХИТЕКТУРА:
✅ BaseStatsConfig - конфигурация цветов и структуры
✅ BaseStatsDataCollector - сбор данных из Apps Script
✅ BaseStatsSheetManager - управление листами Google Sheets
✅ BaseStatsFormatter - форматирование и дизайн
✅ BaseStatsService - главный класс, координирующий все

ПРОФЕССИОНАЛЬНЫЙ ДИЗАЙН:
✅ Чёрный текст на всех ячейках
✅ Цветовая кодировка по колонкам
✅ Автоматическое объединение и форматирование
✅ Graceful error handling
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
import pytz
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from gspread.exceptions import WorksheetNotFound, APIError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging
import aiohttp

from utils.logger import logger
from config.settings import settings

load_dotenv()

# ===== КОНСТАНТЫ =====
API_RETRY_CONFIG = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(min=2, max=10),
    "retry": retry_if_exception_type((APIError,)),
    "before_sleep": before_sleep_log(logger, logging.WARNING),
}


class BaseStatsConfig:
    """Конфигурация цветов и структуры таблицы статистики баз"""

    # Цвета фона (RGB значения для Google Sheets)
    COLORS = {
        "header_bg": {"red": 0.9, "green": 0.9, "blue": 0.9},  # Серый для заголовков
        "date_bg": {"red": 1, "green": 0.65, "blue": 0.3},  # Оранжевый для дат
        "provider_bg": {
            "red": 0.9,
            "green": 0.8,
            "blue": 1.0,
        },  # Фиолетовый для поставщиков
        "calls_bg": {"red": 1, "green": 1, "blue": 0.4},  # Жёлтый для количества
        "bomzh_bg": {"red": 1, "green": 0.75, "blue": 0.8},  # Розовый для бомжей
        "recalls_bg": {
            "red": 0.7,
            "green": 0.95,
            "blue": 0.7,
        },  # Зелёный для перезвонов
        "manual_bg": {
            "red": 1,
            "green": 0.8,
            "blue": 1.0,
        },  # Фиолетовый для ручных полей
        "day_total_bg": {
            "red": 0.5,
            "green": 0.8,
            "blue": 1.0,
        },  # Голубой для итогов дня
        "week_total_bg": {
            "red": 0.2,
            "green": 0.5,
            "blue": 0.8,
        },  # Тёмно-голубой для итогов недели
        "percent_bg": {"red": 0.95, "green": 0.95, "blue": 0.95},  # Серый для процентов
    }

    # Структура колонок
    COLUMNS = [
        {"name": "Дата", "width": 100},
        {"name": "Поставщик", "width": 250},
        {"name": "Кол-во", "width": 120},
        {"name": "Бомж", "width": 120},
        {"name": "Перезвоны", "width": 120},
        {"name": "Пошло в работу", "width": 120},
        {"name": "Закрыто", "width": 120},
    ]

    # Форматирование текста (всегда чёрный)
    TEXT_FORMAT = {"foregroundColor": {"red": 0, "green": 0, "blue": 0}, "fontSize": 11}

    HEADER_FORMAT = {**TEXT_FORMAT, "bold": True, "fontSize": 12}


class BaseStatsDataCollector:
    """Сбор данных поставщиков из Google Apps Script"""

    def __init__(self):
        self.url = settings.GOOGLE_APPS_SCRIPT_URL
        if not self.url:
            raise ValueError("GOOGLE_APPS_SCRIPT_URL не настроен")

    @retry(**API_RETRY_CONFIG)
    async def fetch_provider_data(self, date_str: str) -> List[Dict]:
        """Получить данные поставщиков за дату"""
        params = {"action": "providers", "date": date_str}

        logger.debug(f"🔗 Запрос данных поставщиков за {date_str}")

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15)
        ) as session:
            async with session.get(self.url, params=params) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")

                data = await response.json()

                if isinstance(data, dict) and "error" in data:
                    if "не найден" in data["error"]:
                        logger.debug(f"📭 Лист {date_str} не найден")
                        return []
                    raise Exception(data["error"])

                if not isinstance(data, list):
                    raise ValueError("Apps Script вернул не список")

                logger.debug(
                    f"✅ Получено {len(data)} записей поставщиков за {date_str}"
                )
                return data

    @staticmethod
    def calculate_provider_stats(raw_data: List[Dict]) -> Dict[str, Dict[str, int]]:
        """Подсчитать статистику по поставщикам"""
        if not raw_data:
            return {}

        stats = {}

        for row in raw_data:
            provider = row.get("поставщик", "").strip()
            if not provider:
                continue

            if provider not in stats:
                stats[provider] = {"calls": 0, "recalls": 0, "bomzh": 0}

            stats[provider]["calls"] += 1

            # Определяем тип по цвету (поддерживаем оба ключа: 'цвет' и 'итог_цвет')
            color = (row.get("цвет") or row.get("итог_цвет") or "").strip().upper()
            if color == "РОЗОВЫЙ":
                stats[provider]["bomzh"] += 1
            elif color == "ЗЕЛЕНЫЙ":
                stats[provider]["recalls"] += 1

        # Логируем результаты
        if stats:
            total_calls = sum(s["calls"] for s in stats.values())
            total_bomzh = sum(s["bomzh"] for s in stats.values())
            total_recalls = sum(s["recalls"] for s in stats.values())

            logger.info(
                f"📊 Статистика поставщиков: {len(stats)} поставщиков, "
                f"{total_calls} трубок, бомжей: {total_bomzh}, перезвонов: {total_recalls}"
            )

        return stats


class BaseStatsSheetManager:
    """Управление листами Google Sheets"""

    def __init__(self, client, spreadsheet):
        self.client = client
        self.spreadsheet = spreadsheet

    def _get_week_range(self, date: datetime) -> Tuple[datetime, datetime]:
        """Получить диапазон недели (ПН-СБ)"""
        if date.weekday() == 6:  # Воскресенье
            start = date + timedelta(days=1)
        else:
            start = date - timedelta(days=date.weekday())
        end = start + timedelta(days=5)
        return start, end

    def _get_week_title(self, start: datetime, end: datetime) -> str:
        """Создать название листа недели"""
        months = {
            1: "Января",
            2: "Февраля",
            3: "Марта",
            4: "Апреля",
            5: "Мая",
            6: "Июня",
            7: "Июля",
            8: "Августа",
            9: "Сентября",
            10: "Октября",
            11: "Ноября",
            12: "Декабря",
        }
        month_name = months[start.month]
        return f"Неделя {start.day}-{end.day} {month_name} {start.year}"

    async def get_or_create_week_sheet(self, timezone: pytz.timezone) -> Optional[Any]:
        """Получить или создать лист для текущей недели"""
        now = datetime.now(timezone)

        if now.weekday() == 6:  # Воскресенье
            logger.info("📅 Воскресенье - создание листа пропущено")
            return None

        start, end = self._get_week_range(now)
        title = self._get_week_title(start, end)

        try:
            worksheet = self.spreadsheet.worksheet(title)
            logger.info(f"📋 Лист '{title}' уже существует")
            return worksheet
        except WorksheetNotFound:
            pass

        # Создаём новый лист
        worksheet = self.spreadsheet.add_worksheet(title=title, rows=200, cols=10)
        logger.info(f"✅ Создан новый лист: {title}")

        # Настраиваем layout
        await self._setup_sheet_layout(worksheet, start, end)
        return worksheet

    async def _setup_sheet_layout(self, worksheet, start: datetime, end: datetime):
        """Создать layout листа с профессиональным дизайном"""
        config = BaseStatsConfig()

        # Заголовок
        title = f"📊 СТАТИСТИКА БАЗ ПАВЛОГРАД - {start.strftime('%d.%m')} - {end.strftime('%d.%m.%Y')}"
        worksheet.merge_cells("A1:H1")
        worksheet.update("A1", [[title]])

        # Заголовки колонок
        headers = [[col["name"] for col in config.COLUMNS]]
        worksheet.update("A2:H2", headers)

        # Форматирование заголовка
        worksheet.format(
            "A1:H1",
            {
                "backgroundColor": config.COLORS["header_bg"],
                "textFormat": config.HEADER_FORMAT,
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
            },
        )

        # Форматирование заголовков колонок
        worksheet.format(
            "A2:H2",
            {
                "backgroundColor": config.COLORS["header_bg"],
                "textFormat": config.HEADER_FORMAT,
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "borders": {
                    "top": {"style": "SOLID", "width": 2},
                    "bottom": {"style": "SOLID", "width": 2},
                    "left": {"style": "SOLID", "width": 1},
                    "right": {"style": "SOLID", "width": 1},
                },
            },
        )

        # Ширина колонок
        sheet_id = worksheet.id
        body = {
            "requests": [
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": i,
                            "endIndex": i + 1,
                        },
                        "properties": {"pixelSize": col["width"]},
                        "fields": "pixelSize",
                    }
                }
                for i, col in enumerate(config.COLUMNS)
            ]
        }
        self.spreadsheet.batch_update(body)

        logger.info("✅ Layout листа создан")


class BaseStatsFormatter:
    """Форматирование данных и дизайна таблицы"""

    def __init__(self, spreadsheet):
        self.spreadsheet = spreadsheet
        self.config = BaseStatsConfig()

    def format_provider_row(self, sheet_id: int, row: int) -> List[Dict]:
        """Форматирование строки поставщика"""
        requests = []

        # Поставщик (фиолетовый)
        requests.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row - 1,
                        "endRowIndex": row,
                        "startColumnIndex": 1,
                        "endColumnIndex": 2,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": self.config.COLORS["provider_bg"],
                            "textFormat": self.config.TEXT_FORMAT,
                            "horizontalAlignment": "LEFT",
                        }
                    },
                    "fields": "userEnteredFormat",
                }
            }
        )

        # Кол-во (жёлтый)
        requests.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row - 1,
                        "endRowIndex": row,
                        "startColumnIndex": 2,
                        "endColumnIndex": 3,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": self.config.COLORS["calls_bg"],
                            "textFormat": {**self.config.TEXT_FORMAT, "bold": True},
                            "horizontalAlignment": "CENTER",
                        }
                    },
                    "fields": "userEnteredFormat",
                }
            }
        )

        # Бомж (розовый)
        requests.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row - 1,
                        "endRowIndex": row,
                        "startColumnIndex": 3,
                        "endColumnIndex": 4,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": self.config.COLORS["bomzh_bg"],
                            "textFormat": {**self.config.TEXT_FORMAT, "bold": True},
                            "horizontalAlignment": "CENTER",
                        }
                    },
                    "fields": "userEnteredFormat",
                }
            }
        )

        # Перезвоны (зелёный)
        requests.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row - 1,
                        "endRowIndex": row,
                        "startColumnIndex": 4,
                        "endColumnIndex": 5,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": self.config.COLORS["recalls_bg"],
                            "textFormat": {**self.config.TEXT_FORMAT, "bold": True},
                            "horizontalAlignment": "CENTER",
                        }
                    },
                    "fields": "userEnteredFormat",
                }
            }
        )

        # Ручные поля (фиолетовый)
        for col_idx in [5, 6]:  # Пошло в работу, Закрыто
            requests.append(
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": row - 1,
                            "endRowIndex": row,
                            "startColumnIndex": col_idx,
                            "endColumnIndex": col_idx + 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": self.config.COLORS["manual_bg"],
                                "textFormat": self.config.TEXT_FORMAT,
                                "horizontalAlignment": "CENTER",
                            }
                        },
                        "fields": "userEnteredFormat",
                    }
                }
            )

        return requests

    def format_date_merge(self, sheet_id: int, start_row: int, end_row: int) -> Dict:
        """Форматирование объединённой ячейки даты"""
        return {
            "mergeCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": start_row,
                    "endRowIndex": end_row,
                    "startColumnIndex": 0,
                    "endColumnIndex": 1,
                },
                "mergeType": "MERGE_ALL",
            }
        }

    def format_date_cell(self, sheet_id: int, start_row: int, end_row: int) -> Dict:
        """Форматирование ячейки даты (оранжевый)"""
        return {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": start_row,
                    "endRowIndex": end_row,
                    "startColumnIndex": 0,
                    "endColumnIndex": 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": self.config.COLORS["date_bg"],
                        "textFormat": {**self.config.TEXT_FORMAT, "bold": True},
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat",
            }
        }

    def format_day_total(self, sheet_id: int, row: int) -> Dict:
        """Форматирование итоговой строки дня (голубой)"""
        return {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row - 1,
                    "endRowIndex": row,
                    "startColumnIndex": 0,
                    "endColumnIndex": 8,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": self.config.COLORS["day_total_bg"],
                        "textFormat": {**self.config.TEXT_FORMAT, "bold": True},
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat",
            }
        }

    def format_week_total(self, sheet_id: int, row: int) -> Dict:
        """Форматирование итоговой строки недели (тёмно-голубой)"""
        return {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row - 1,
                    "endRowIndex": row,
                    "startColumnIndex": 0,
                    "endColumnIndex": 8,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": self.config.COLORS["week_total_bg"],
                        "textFormat": {
                            **self.config.HEADER_FORMAT,
                            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                        },
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat",
            }
        }

    def apply_borders(self, sheet_id: int, last_row: int) -> Dict:
        """Применить границы к таблице"""
        return {
            "updateBorders": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "endRowIndex": last_row,
                    "startColumnIndex": 0,
                    "endColumnIndex": 7,
                },
                "top": {
                    "style": "SOLID",
                    "width": 2,
                    "color": {"red": 0, "green": 0, "blue": 0},
                },
                "bottom": {
                    "style": "SOLID",
                    "width": 2,
                    "color": {"red": 0, "green": 0, "blue": 0},
                },
                "left": {
                    "style": "SOLID",
                    "width": 2,
                    "color": {"red": 0, "green": 0, "blue": 0},
                },
                "right": {
                    "style": "SOLID",
                    "width": 2,
                    "color": {"red": 0, "green": 0, "blue": 0},
                },
                "innerHorizontal": {
                    "style": "SOLID",
                    "width": 1,
                    "color": {"red": 0, "green": 0, "blue": 0},
                },
                "innerVertical": {
                    "style": "SOLID",
                    "width": 1,
                    "color": {"red": 0, "green": 0, "blue": 0},
                },
            }
        }


class BaseStatsService:
    """Главный сервис для работы с таблицей 'Статистика баз'"""

    def __init__(self):
        self.timezone = pytz.timezone("Europe/Kiev")
        self.sheet_id = os.getenv("BASE_STATS_SHEET_ID")
        self.credentials_file = os.getenv(
            "GOOGLE_CREDENTIALS_FILE", "google_credentials.json"
        )

        self.client = None
        self.spreadsheet = None
        self.collector = None
        # Всегда создаём экземпляр sheet_manager (client/spreadsheet могут быть None)
        self.sheet_manager = BaseStatsSheetManager(self.client, self.spreadsheet)
        self.formatter = None

        if not self.sheet_id:
            logger.warning(
                "⚠️ BASE_STATS_SHEET_ID не найден - статистика баз недоступна"
            )
            return

        if not self._authorize():
            logger.error("❌ Не удалось авторизоваться в Google Sheets")
            return

        self.collector = BaseStatsDataCollector()
        self.sheet_manager = BaseStatsSheetManager(self.client, self.spreadsheet)
        self.formatter = BaseStatsFormatter(self.spreadsheet)

        logger.info("✅ BaseStatsService инициализирован")

    def calculate_provider_stats(
        self, raw_data: List[Dict]
    ) -> Dict[str, Dict[str, int]]:
        """Подсчитать статистику по поставщикам для совместимости с тестами"""
        return BaseStatsDataCollector.calculate_provider_stats(raw_data)

    def _authorize(self) -> bool:
        """Авторизация в Google Sheets"""
        try:
            if not os.path.exists(self.credentials_file):
                logger.error(f"❌ Файл {self.credentials_file} не найден!")
                return False

            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
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

    def get_week_range(self, date: datetime) -> Tuple[datetime, datetime]:
        """Получить диапазон недели (ПН-СБ) для совместимости с тестами"""
        return self.sheet_manager._get_week_range(date)

    async def count_calls_by_provider(self, date_str: str) -> Dict[str, Dict[str, int]]:
        """Подсчитать звонки по поставщикам для совместимости с тестами"""
        raw_data = await self.fetch_provider_data(date_str)
        return self.calculate_provider_stats(raw_data)

    @retry(**API_RETRY_CONFIG)
    async def update_stats(self):
        """Главная функция обновления статистики"""
        if not all(
            [
                self.client,
                self.spreadsheet,
                self.collector,
                self.sheet_manager,
                self.formatter,
            ]
        ):
            raise Exception("BaseStatsService не инициализирован")

        now = datetime.now(self.timezone)

        if now.weekday() == 6:  # Воскресенье
            logger.info("📅 Воскресенье - обновление пропущено")
            return

        logger.info("🔄 Обновление статистики баз")

        # 1. Получить или создать лист недели
        worksheet = await self.sheet_manager.get_or_create_week_sheet(self.timezone)
        if not worksheet:
            return

        # 2. Собрать данные за неделю
        week_start, week_end = self.sheet_manager._get_week_range(now)
        all_stats = await self._collect_week_data(week_start, week_end)

        # 3. Обновить данные на листе
        await self._update_sheet_data(worksheet, all_stats, week_start)

        logger.info("✅ Статистика баз обновлена")

    async def _collect_week_data(
        self, week_start: datetime, week_end: datetime
    ) -> Dict[str, Dict[str, Dict[str, int]]]:
        """Собрать данные за всю неделю"""
        all_stats = {}
        today = datetime.now(self.timezone).date()

        current_date = week_start
        while current_date <= week_end:
            if current_date.date() > today:
                current_date += timedelta(days=1)
                continue

            date_str = current_date.strftime("%d.%m")
            logger.info(f"📅 Обработка {date_str}")

            try:
                raw_data = await self.collector.fetch_provider_data(date_str)
                stats = BaseStatsDataCollector.calculate_provider_stats(raw_data)
                all_stats[date_str] = stats
            except Exception as e:
                logger.error(f"❌ Ошибка получения данных за {date_str}: {e}")
                all_stats[date_str] = {}  # Пустые данные для этой даты

            current_date += timedelta(days=1)

        return all_stats

    async def _update_sheet_data(
        self,
        worksheet,
        all_stats: Dict[str, Dict[str, Dict[str, int]]],
        week_start: datetime,
    ):
        """Обновить данные на листе с форматированием"""
        updates = []
        merge_requests = []
        format_requests = []
        sheet_id = worksheet.id

        row = 3  # Начинаем с 3-й строки
        weekly_stats = {"total_calls": 0, "total_bomzh": 0, "total_recalls": 0}

        # Проходим по дням недели
        for day_offset in range(6):  # ПН-СБ
            current_date = week_start + timedelta(days=day_offset)
            date_str = current_date.strftime("%d.%m")
            date_full = current_date.strftime("%d.%m.%Y")

            stats = all_stats.get(date_str, {})

            if not stats:
                continue

            first_row = row
            day_total_calls = sum(s["calls"] for s in stats.values())
            day_total_bomzh = sum(s["bomzh"] for s in stats.values())
            day_total_recalls = sum(s["recalls"] for s in stats.values())

            weekly_stats["total_calls"] += day_total_calls
            weekly_stats["total_bomzh"] += day_total_bomzh
            weekly_stats["total_recalls"] += day_total_recalls

            # Строки поставщиков
            for provider, data in sorted(stats.items()):
                _pct_recalls = (
                    (data["recalls"] / data["calls"] * 100) if data["calls"] > 0 else 0
                )

                updates.append(
                    {
                        "range": f"A{row}:G{row}",
                        "values": [
                            [
                                date_full,
                                provider,
                                data["calls"],
                                data["bomzh"],
                                data["recalls"],
                                f"{_pct_recalls:.1f}%",
                                "",
                            ]
                        ],
                    }
                )

                format_requests.extend(
                    self.formatter.format_provider_row(sheet_id, row)
                )
                row += 1

            last_row = row - 1

            # Объединение даты
            if last_row >= first_row:
                merge_requests.append(
                    self.formatter.format_date_merge(sheet_id, first_row - 1, last_row)
                )
                format_requests.append(
                    self.formatter.format_date_cell(sheet_id, first_row - 1, last_row)
                )

            # Итоговая строка дня
            _day_pct_recalls = (
                (day_total_recalls / day_total_calls * 100)
                if day_total_calls > 0
                else 0
            )

            updates.append(
                {
                    "range": f"A{row}:H{row}",
                    "values": [
                        [
                            "ИТОГО",
                            "ИТОГО",
                            day_total_calls,
                            day_total_bomzh,
                            day_total_recalls,
                            f"{_day_pct_recalls:.1f}%",
                            "",
                        ]
                    ],
                }
            )

            format_requests.append(self.formatter.format_day_total(sheet_id, row))
            row += 2  # Отступ

        # Итоговая строка недели
        if weekly_stats["total_calls"] > 0:
            _weekly_pct = (
                weekly_stats["total_recalls"] / weekly_stats["total_calls"] * 100
            )

            updates.append(
                {
                    "range": f"A{row}:G{row}",
                    "values": [
                        [
                            "НЕДЕЛЯ",
                            "ИТОГО",
                            weekly_stats["total_calls"],
                            weekly_stats["total_bomzh"],
                            weekly_stats["total_recalls"],
                            f"{_weekly_pct:.1f}%",
                            "",
                        ]
                    ],
                }
            )

            format_requests.append(self.formatter.format_week_total(sheet_id, row))

        # Применяем обновления
        if updates:
            logger.info(f"📤 Отправка {len(updates)} обновлений")
            worksheet.batch_update(updates, value_input_option="USER_ENTERED")

        # Применяем объединение и форматирование
        if merge_requests or format_requests:
            body = {"requests": merge_requests + format_requests}
            self.spreadsheet.batch_update(body)
            logger.info("✅ Форматирование и объединение применены")

        # Границы
        body = {"requests": [self.formatter.apply_borders(sheet_id, row)]}
        self.spreadsheet.batch_update(body)
        logger.info("✅ Границы применены")


# Глобальный экземпляр сервиса
base_stats_service = BaseStatsService()
