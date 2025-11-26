"""
Сервис для работы со статистикой менеджеров из Google Sheets - улучшенная визуализация
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import aiohttp
from config.settings import settings
from utils.logger import logger


class ManagersStatsService:
    """Сервис для получения статистики менеджеров Павлограда"""
    
    async def get_managers_stats(self) -> str:
        """
        Получает статистику менеджеров за сегодня
        
        Returns:
            Форматированная строка со статистикой в стиле дашборда
        """
        try:
            # Получаем данные из таблицы
            data = await self._fetch_managers_data()
            
            # Группируем по менеджерам
            stats_by_manager = self._group_by_manager(data)
            
            # Форматируем результат в новом стиле
            result = self._format_stats_dashboard(stats_by_manager)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики менеджеров: {e}", exc_info=True)
            return "⚠️ Ошибка получения статистики менеджеров"
    
    async def _fetch_managers_data(self) -> List[Dict]:
        """Получает данные менеджеров из Google Sheets"""
        url = settings.GOOGLE_APPS_SCRIPT_URL
        
        if not url:
            raise ValueError("GOOGLE_APPS_SCRIPT_URL не настроен")
        
        # Добавляем параметр action=managers
        if '?' in url:
            url += '&action=managers'
        else:
            url += '?action=managers'
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 200:
                        logger.error(f"❌ HTTP ошибка: {response.status}")
                        raise Exception(f"HTTP {response.status}")
                    
                    data = await response.json()
                    
                    if isinstance(data, dict) and 'error' in data:
                        logger.error(f"❌ Ошибка от скрипта: {data['error']}")
                        raise Exception(data['error'])
                    
                    logger.info(f"✅ Получено {len(data)} записей менеджеров")
                    return data
                    
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных менеджеров: {e}", exc_info=True)
            raise
    
    def _group_by_manager(self, data: List[Dict]) -> Dict[str, Dict[str, int]]:
        """Группирует данные по менеджерам и цветам"""
        stats = {}
        
        for row in data:
            manager = row.get("менеджер", "").strip()
            color = row.get("цвет", "").strip()
            
            if not manager or not color:
                continue
            
            if manager not in stats:
                stats[manager] = {
                    "ЖЕЛТЫЙ": 0,
                    "ЗЕЛЕНЫЙ": 0,
                    "ФИОЛЕТОВЫЙ": 0
                }
            
            if color in stats[manager]:
                stats[manager][color] += 1
        
        return stats
    
    def _format_stats_dashboard(self, stats: Dict[str, Dict[str, int]]) -> str:
        """
        Форматирует статистику в стиле дашборда ошибок
        
        Args:
            stats: Статистика по менеджерам
            
        Returns:
            Форматированная строка
        """
        kiev_tz = timezone(timedelta(hours=2))
        current_time = datetime.now(kiev_tz).strftime("%H:%M")
        
        COLOR_EMOJI = {
            "ЖЕЛТЫЙ": "🟨",
            "ЗЕЛЕНЫЙ": "🟩",
            "ФИОЛЕТОВЫЙ": "🟪"
        }
        
        if not stats:
            return f"👥 <b>МЕНЕДЖЕРЫ (ПАВЛОГРАД) на {current_time}</b>\n\n📭 Данных нет."
        
        # Сортируем по общему количеству (больше → меньше)
        sorted_managers = sorted(
            stats.items(),
            key=lambda x: sum(x[1].values()),
            reverse=True
        )
        
        # Считаем общее
        total_calls = sum(sum(colors.values()) for colors in stats.values())
        
        result = f"👥 <b>МЕНЕДЖЕРЫ (ПАВЛОГРАД) на {current_time}</b>\n"
        result += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        result += f"📊 <b>ОБЩЕЕ:</b>\n"
        result += f"• Всего трубок: <b>{total_calls}</b>\n"
        result += f"• Менеджеров: {len(stats)}\n\n"
        
        result += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, (manager, colors) in enumerate(sorted_managers, 1):
            total = sum(colors.values())
            
            if total == 0:
                continue
            
            green = colors["ЗЕЛЕНЫЙ"]
            yellow = colors["ЖЕЛТЫЙ"]
            purple = colors["ФИОЛЕТОВЫЙ"]
            
            # Процент от общего количества
            percentage = int((total / total_calls) * 100) if total_calls > 0 else 0
            
            # Прогресс-бар
            filled = int(percentage / 10) if percentage <= 100 else 10
            bar = "█" * filled + "░" * (10 - filled)
            
            result += f"<b>{i}. {manager}</b> - {total} трубок\n"
            result += f"{bar} {percentage}%\n"
            
            # Детализация по цветам (только если есть)
            colors_line = []
            if green > 0:
                green_pct = int((green / total) * 100)
                colors_line.append(f"{COLOR_EMOJI['ЗЕЛЕНЫЙ']} {green} ({green_pct}%)")
            if yellow > 0:
                yellow_pct = int((yellow / total) * 100)
                colors_line.append(f"{COLOR_EMOJI['ЖЕЛТЫЙ']} {yellow} ({yellow_pct}%)")
            if purple > 0:
                purple_pct = int((purple / total) * 100)
                colors_line.append(f"{COLOR_EMOJI['ФИОЛЕТОВЫЙ']} {purple} ({purple_pct}%)")
            
            if colors_line:
                result += "• " + " | ".join(colors_line) + "\n"
            
            result += "\n"
        
        # Итоги по цветам
        result += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        total_green = sum(m["ЗЕЛЕНЫЙ"] for m in stats.values())
        total_yellow = sum(m["ЖЕЛТЫЙ"] for m in stats.values())
        total_purple = sum(m["ФИОЛЕТОВЫЙ"] for m in stats.values())
        
        result += f"🎨 <b>ИТОГО ПО ЦВЕТАМ:</b>\n"
        
        if total_green > 0:
            green_pct = int((total_green / total_calls) * 100)
            result += f"{COLOR_EMOJI['ЗЕЛЕНЫЙ']} Зелёные: {total_green} ({green_pct}%)\n"
        
        if total_yellow > 0:
            yellow_pct = int((total_yellow / total_calls) * 100)
            result += f"{COLOR_EMOJI['ЖЕЛТЫЙ']} Жёлтые: {total_yellow} ({yellow_pct}%)\n"
        
        if total_purple > 0:
            purple_pct = int((total_purple / total_calls) * 100)
            result += f"{COLOR_EMOJI['ФИОЛЕТОВЫЙ']} Фиолетовые: {total_purple} ({purple_pct}%)\n"
        
        return result


# Глобальный экземпляр сервиса
managers_stats_service = ManagersStatsService()