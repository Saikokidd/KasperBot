"""
Сервис аналитики ошибок телефонии
"""
from datetime import datetime, timedelta
from typing import Dict, List
from database.models import db
from utils.logger import logger


class AnalyticsService:
    """Сервис для получения аналитики по ошибкам"""
    
    @staticmethod
    def get_general_stats(period: str = "today") -> str:
        """
        Общая статистика ошибок
        
        Args:
            period: 'today', 'week', 'month'
            
        Returns:
            Форматированная строка со статистикой
        """
        try:
            conn = db._get_connection()
            cursor = conn.cursor()
            
            # Определяем период
            if period == "today":
                date_filter = datetime.now().strftime("%Y-%m-%d")
                title = "за сегодня"
                where_clause = "DATE(created_at) = ?"
            elif period == "week":
                date_filter = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                title = "за неделю"
                where_clause = "DATE(created_at) >= ?"
            else:  # month
                date_filter = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
                title = "за месяц"
                where_clause = "DATE(created_at) >= ?"
            
            # Общее количество
            cursor.execute(
                f"SELECT COUNT(*) FROM error_reports WHERE {where_clause}",
                (date_filter,)
            )
            total = cursor.fetchone()[0]
            
            if total == 0:
                conn.close()
                return f"📊 <b>Общая статистика {title}</b>\n\n📭 Ошибок не найдено."
            
            # По телефониям
            cursor.execute(
                f"""
                SELECT telephony_code, COUNT(*) as cnt 
                FROM error_reports 
                WHERE {where_clause}
                GROUP BY telephony_code
                ORDER BY cnt DESC
                """,
                (date_filter,)
            )
            by_telephony = cursor.fetchall()
            
            # По статусам
            cursor.execute(
                f"""
                SELECT status, COUNT(*) as cnt 
                FROM error_reports 
                WHERE {where_clause}
                GROUP BY status
                """,
                (date_filter,)
            )
            by_status = cursor.fetchall()
            
            conn.close()
            
            # Форматирование
            result = f"📊 <b>Общая статистика {title}</b>\n\n"
            result += f"📈 Всего ошибок: <b>{total}</b>\n\n"
            
            if by_telephony:
                result += "📞 <b>По телефониям:</b>\n"
                for tel_code, count in by_telephony:
                    percentage = int((count / total) * 100) if total > 0 else 0
                    # Получаем название телефонии
                    tel = db.get_telephony_by_code(tel_code)
                    tel_name = tel['name'] if tel else tel_code.upper()
                    result += f"• {tel_name}: {count} ({percentage}%)\n"
                result += "\n"
            
            if by_status:
                result += "🔄 <b>По статусам:</b>\n"
                status_names = {
                    'new': '🆕 Новые',
                    'resolved': '✅ Решены'
                }
                for status, count in by_status:
                    status_name = status_names.get(status, status)
                    percentage = int((count / total) * 100) if total > 0 else 0
                    result += f"• {status_name}: {count} ({percentage}%)\n"
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения общей статистики: {e}", exc_info=True)
            return "⚠️ Ошибка получения статистики"
    
    @staticmethod
    def get_managers_stats(period: str = "today", limit: int = 10) -> str:
        """
        Статистика по менеджерам (кто сколько ошибок отправил)
        
        Args:
            period: 'today', 'week', 'month'
            limit: Количество топ менеджеров
            
        Returns:
            Форматированная строка
        """
        try:
            conn = db._get_connection()
            cursor = conn.cursor()
            
            # Определяем период
            if period == "today":
                date_filter = datetime.now().strftime("%Y-%m-%d")
                title = "за сегодня"
                where_clause = "DATE(created_at) = ?"
            elif period == "week":
                date_filter = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                title = "за неделю"
                where_clause = "DATE(created_at) >= ?"
            else:
                date_filter = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
                title = "за месяц"
                where_clause = "DATE(created_at) >= ?"
            
            # Топ менеджеров по количеству ошибок
            cursor.execute(
                f"""
                SELECT username, COUNT(*) as cnt 
                FROM error_reports 
                WHERE {where_clause}
                GROUP BY user_id 
                ORDER BY cnt DESC 
                LIMIT ?
                """,
                (date_filter, limit)
            )
            top_managers = cursor.fetchall()
            
            conn.close()
            
            if not top_managers:
                return f"👤 <b>Статистика менеджеров {title}</b>\n\n📭 Ошибок не найдено."
            
            result = f"👤 <b>Топ-{limit} менеджеров {title}</b>\n\n"
            
            for i, (username, count) in enumerate(top_managers, 1):
                name = username or "Неизвестно"
                medal = ""
                if i == 1:
                    medal = "🥇 "
                elif i == 2:
                    medal = "🥈 "
                elif i == 3:
                    medal = "🥉 "
                
                result += f"{medal}{i}. <b>{name}</b> - {count} ошибок\n"
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики менеджеров: {e}", exc_info=True)
            return "⚠️ Ошибка получения статистики"
    
    @staticmethod
    def get_support_stats(period: str = "today", limit: int = 10) -> str:
        """
        Статистика по саппорту (кто сколько обработал)
        
        Args:
            period: 'today', 'week', 'month'
            limit: Количество топ саппортов
            
        Returns:
            Форматированная строка
        """
        try:
            conn = db._get_connection()
            cursor = conn.cursor()
            
            # Определяем период
            if period == "today":
                date_filter = datetime.now().strftime("%Y-%m-%d")
                title = "за сегодня"
                where_clause = "DATE(resolved_at) = ?"
            elif period == "week":
                date_filter = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                title = "за неделю"
                where_clause = "DATE(resolved_at) >= ?"
            else:
                date_filter = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
                title = "за месяц"
                where_clause = "DATE(resolved_at) >= ?"
            
            # Топ саппортов
            cursor.execute(
                f"""
                SELECT support_username, COUNT(*) as cnt,
                       AVG(response_time_seconds) as avg_time
                FROM error_reports 
                WHERE {where_clause} AND support_username IS NOT NULL
                GROUP BY support_user_id 
                ORDER BY cnt DESC 
                LIMIT ?
                """,
                (date_filter, limit)
            )
            top_support = cursor.fetchall()
            
            conn.close()
            
            if not top_support:
                return f"🛠 <b>Статистика саппорта {title}</b>\n\n�� Обработанных ошибок не найдено."
            
            result = f"🛠 <b>Топ-{limit} саппортов {title}</b>\n\n"
            
            for i, (username, count, avg_time) in enumerate(top_support, 1):
                name = username or "Неизвестно"
                medal = ""
                if i == 1:
                    medal = "🥇 "
                elif i == 2:
                    medal = "🥈 "
                elif i == 3:
                    medal = "🥉 "
                
                # Форматируем среднее время
                if avg_time:
                    minutes = int(avg_time // 60)
                    seconds = int(avg_time % 60)
                    time_str = f"⏱ {minutes}м {seconds}с"
                else:
                    time_str = "⏱ нет данных"
                
                result += f"{medal}{i}. <b>{name}</b> - {count} ошибок ({time_str})\n"
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики саппорта: {e}", exc_info=True)
            return "⚠️ Ошибка получения статистики"
    
    @staticmethod
    def get_response_time_stats(period: str = "today") -> str:
        """
        Статистика времени реакции саппорта
        
        Args:
            period: 'today', 'week', 'month'
            
        Returns:
            Форматированная строка
        """
        try:
            conn = db._get_connection()
            cursor = conn.cursor()
            
            # Определяем период
            if period == "today":
                date_filter = datetime.now().strftime("%Y-%m-%d")
                title = "за сегодня"
                where_clause = "DATE(resolved_at) = ?"
            elif period == "week":
                date_filter = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                title = "за неделю"
                where_clause = "DATE(resolved_at) >= ?"
            else:
                date_filter = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
                title = "за месяц"
                where_clause = "DATE(resolved_at) >= ?"
            
            # Среднее время
            cursor.execute(
                f"""
                SELECT AVG(response_time_seconds), 
                       MIN(response_time_seconds),
                       MAX(response_time_seconds),
                       COUNT(*)
                FROM error_reports 
                WHERE {where_clause} AND response_time_seconds IS NOT NULL
                """,
                (date_filter,)
            )
            stats = cursor.fetchone()
            
            conn.close()
            
            if not stats or stats[3] == 0:
                return f"⏱ <b>Время реакции {title}</b>\n\n📭 Данных нет."
            
            avg_time, min_time, max_time, count = stats
            
            # Форматируем
            def format_time(seconds):
                if not seconds:
                    return "нет данных"
                m = int(seconds // 60)
                s = int(seconds % 60)
                return f"{m}м {s}с"
            
            result = f"⏱ <b>Время реакции саппорта {title}</b>\n\n"
            result += f"📊 Обработано ошибок: {count}\n\n"
            result += f"🔹 Среднее время: <b>{format_time(avg_time)}</b>\n"
            result += f"🟢 Быстрейший: {format_time(min_time)}\n"
            result += f"🔴 Самый долгий: {format_time(max_time)}\n"
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики времени: {e}", exc_info=True)
            return "⚠️ Ошибка получения статистики"


# Глобальный экземпляр сервиса
analytics_service = AnalyticsService()
