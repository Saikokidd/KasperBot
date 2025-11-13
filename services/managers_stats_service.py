"""
Сервис для работы со статистикой менеджеров из Google Sheets
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
            Форматированная строка со статистикой
        """
        try:
            # Получаем данные из таблицы
            data = await self._fetch_managers_data()
            
            # Группируем по менеджерам
            stats_by_manager = self._group_by_manager(data)
            
            # Форматируем результат
            result = self._format_stats(stats_by_manager)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики менеджеров: {e}", exc_info=True)
            return "⚠️ Ошибка получения статистики менеджеров"
    
    async def _fetch_managers_data(self) -> List[Dict]:
        """
        Получает данные менеджеров из Google Sheets
        
        Returns:
            Список словарей с данными
        """
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
        """
        Группирует данные по менеджерам и цветам
        
        Args:
            data: Данные из Google Sheets
            
        Returns:
            Словарь {менеджер: {цвет: количество}}
        """
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
    
    def _format_stats(self, stats: Dict[str, Dict[str, int]]) -> str:
        """
        Форматирует статистику в текст
        
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
        
        result = f"👥 <b>Статистика менеджеров (Павлоград) на {current_time}</b>\n"
        result += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        # Сортируем по общему количеству (больше → меньше)
        sorted_managers = sorted(
            stats.items(),
            key=lambda x: sum(x[1].values()),
            reverse=True
        )
        
        for manager, colors in sorted_managers:
            total = sum(colors.values())
            
            if total == 0:
                continue
            
            green = colors["ЗЕЛЕНЫЙ"]
            purple = colors["ФИОЛЕТОВЫЙ"]
            yellow = colors["ЖЕЛТЫЙ"]
            
            green_pct = int((green / total) * 100) if total > 0 else 0
            purple_pct = int((purple / total) * 100) if total > 0 else 0
            yellow_pct = int((yellow / total) * 100) if total > 0 else 0
            
            result += f"<b>{manager}:</b> {total}\n"
            
            # Показываем только цвета которые есть
            colors_to_show = []
            if green > 0:
                colors_to_show.append(f"{green}{COLOR_EMOJI['ЗЕЛЕНЫЙ']}({green_pct}%)")
            if purple > 0:
                colors_to_show.append(f"{purple}{COLOR_EMOJI['ФИОЛЕТОВЫЙ']}({purple_pct}%)")
            if yellow > 0:
                colors_to_show.append(f"{yellow}{COLOR_EMOJI['ЖЕЛТЫЙ']}({yellow_pct}%)")
            
            result += " ".join(colors_to_show) + "\n"
            result += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        return result


# Глобальный экземпляр сервиса
managers_stats_service = ManagersStatsService()