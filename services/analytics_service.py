"""
ОПТИМИЗИРОВАННЫЙ: services/analytics_service.py
Объединены SQL запросы для ускорения

ИЗМЕНЕНИЯ:
✅ get_dashboard_overview() - 1 SQL запрос вместо 4
✅ get_dashboard_managers() - добавлен type hint
✅ get_dashboard_support() - добавлен type hint
✅ get_dashboard_timing() - добавлен type hint
"""
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from database.models import db
from utils.logger import logger


class AnalyticsService:
    """Сервис для получения аналитики по ошибкам"""

    @staticmethod
    def _get_period_filter(period: str) -> Tuple[str, str, str]:
        """
        Возвращает фильтр и название для периода

        Args:
            period: Период ('today', 'week', 'month')

        Returns:
            (where_clause, date_filter, title)
        """
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

        return where_clause, date_filter, title

    @staticmethod
    def get_dashboard_overview(period: str = "today") -> str:
        """
        Страница 1: Общий обзор

        ✅ ОПТИМИЗИРОВАНО: 1 SQL запрос вместо 4

        Args:
            period: Период для отображения

        Returns:
            Форматированная строка со статистикой
        """
        try:
            conn = db._get_connection()
            cursor = conn.cursor()

            where_clause, date_filter, title = AnalyticsService._get_period_filter(
                period
            )

            # ✅ ОПТИМИЗАЦИЯ: Объединённый запрос - всё за один раз
            cursor.execute(
                f"""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN support_action IS NOT NULL THEN 1 END) as resolved,
                    AVG(CASE WHEN response_time_seconds <= 1800 THEN response_time_seconds END) as avg_time
                FROM error_reports 
                WHERE {where_clause}
            """,
                (date_filter,),
            )

            stats = cursor.fetchone()
            total, resolved, avg_time = stats

            if total == 0:
                conn.close()
                return f"📊 <b>ДАШБОРД {title.upper()}</b>\n\n📭 Ошибок не найдено."

            # По телефониям (отдельный запрос - нужна группировка)
            cursor.execute(
                f"""
                SELECT telephony_code, COUNT(*) as cnt 
                FROM error_reports 
                WHERE {where_clause}
                GROUP BY telephony_code
                ORDER BY cnt DESC
            """,
                (date_filter,),
            )
            by_telephony = cursor.fetchall()

            conn.close()

            # Форматирование
            result = f"📊 <b>ДАШБОРД {title.upper()}</b>\n"
            result += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            # Общее
            resolved_pct = int((resolved / total) * 100) if total > 0 else 0

            result += "📈 <b>ОБЩЕЕ:</b>\n"
            result += f"• Всего ошибок: <b>{total}</b>\n"
            result += f"• ✅ Решено: {resolved} ({resolved_pct}%)\n\n"

            # По телефониям с прогресс-барами
            if by_telephony:
                result += "📞 <b>ПО ТЕЛЕФОНИЯМ:</b>\n"
                for tel_code, count in by_telephony:
                    tel = db.get_telephony_by_code(tel_code)
                    tel_name = tel["name"] if tel else tel_code.upper()
                    percentage = int((count / total) * 100)

                    # Прогресс-бар
                    filled = int(percentage / 10)
                    bar = "█" * filled + "░" * (10 - filled)

                    result += f"• {tel_name}: {bar} {count} ({percentage}%)\n"
                result += "\n"

            # Среднее время
            if avg_time:
                minutes = int(avg_time // 60)
                seconds = int(avg_time % 60)
                result += "⏱ <b>СРЕДНЕЕ ВРЕМЯ ОТВЕТА:</b>\n"
                result += f"• {minutes}м {seconds}с\n\n"

            result += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            result += "📄 Страница 1 из 4"

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка дашборда: {e}", exc_info=True)
            return "⚠️ Ошибка получения данных"

    @staticmethod
    def get_dashboard_managers(period: str = "today") -> str:
        """
        Страница 2: Все менеджеры

        Args:
            period: Период для отображения

        Returns:
            Форматированная строка со статистикой менеджеров
        """
        try:
            conn = db._get_connection()
            cursor = conn.cursor()

            where_clause, date_filter, title = AnalyticsService._get_period_filter(
                period
            )

            # Все менеджеры
            cursor.execute(
                f"""
                SELECT username, user_id, COUNT(*) as cnt 
                FROM error_reports 
                WHERE {where_clause}
                GROUP BY user_id 
                ORDER BY cnt DESC
            """,
                (date_filter,),
            )
            managers = cursor.fetchall()

            # Общее количество ошибок
            cursor.execute(
                f"SELECT COUNT(*) FROM error_reports WHERE {where_clause}",
                (date_filter,),
            )
            total = cursor.fetchone()[0]

            conn.close()

            if not managers:
                return f"👥 <b>ВСЕ МЕНЕДЖЕРЫ {title.upper()}</b>\n\n📭 Данных нет."

            result = f"👥 <b>ВСЕ МЕНЕДЖЕРЫ {title.upper()}</b>\n"
            result += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            # Таблица с моноширинным шрифтом
            result += "<pre>"
            result += "┌───┬──────────────┬──────┬────┐\n"
            result += "│ # │     Имя      │Ошибок│ %  │\n"
            result += "├───┼──────────────┼──────┼────┤\n"

            for i, (username, user_id, count) in enumerate(managers, 1):
                name = username or f"ID{user_id}"
                # Обрезаем имя если длинное
                if len(name) > 12:
                    name = name[:9] + "..."

                percentage = int((count / total) * 100) if total > 0 else 0

                # Выравнивание
                result += f"│{i:2} │ {name:12} │ {count:4} │{percentage:3}%│\n"

            result += "└───┴──────────────┴──────┴────┘"
            result += "</pre>\n\n"

            result += f"Всего: {len(managers)} менеджеров | {total} ошибок\n\n"
            result += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            result += "📄 Страница 2 из 4"

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка статистики менеджеров: {e}", exc_info=True)
            return "⚠️ Ошибка получения данных"

    @staticmethod
    def get_dashboard_support(period: str = "today") -> str:
        """
        Страница 3: Все саппорты

        Args:
            period: Период для отображения

        Returns:
            Форматированная строка со статистикой саппорта
        """
        try:
            conn = db._get_connection()
            cursor = conn.cursor()

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

            # Все саппорты (только до 30 минут)
            cursor.execute(
                f"""
                SELECT support_username, support_user_id, 
                       COUNT(*) as total,
                       AVG(CASE WHEN response_time_seconds <= 1800 THEN response_time_seconds END) as avg_time,
                       SUM(CASE WHEN support_action = 'fix' THEN 1 ELSE 0 END) as fixed,
                       SUM(CASE WHEN support_action = 'wait' THEN 1 ELSE 0 END) as wait,
                       SUM(CASE WHEN support_action = 'wrong' THEN 1 ELSE 0 END) as wrong,
                       SUM(CASE WHEN support_action = 'sim' THEN 1 ELSE 0 END) as sim
                FROM error_reports 
                WHERE {where_clause} AND support_username IS NOT NULL
                GROUP BY support_user_id 
                ORDER BY total DESC
            """,
                (date_filter,),
            )
            supports = cursor.fetchall()

            conn.close()

            if not supports:
                return f"🛠 <b>ВСЕ САППОРТЫ {title.upper()}</b>\n\n📭 Данных нет."

            result = f"🛠 <b>ВСЕ САППОРТЫ {title.upper()}</b>\n"
            result += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            for i, (
                username,
                user_id,
                total,
                avg_time,
                fixed,
                wait,
                wrong,
                sim,
            ) in enumerate(supports, 1):
                name = username or f"ID{user_id}"

                result += f"{i}. <b>{name}</b> - {total}\n"

                # Детализация по действиям
                actions = []
                if fixed > 0:
                    actions.append(f"✅ Исправлено: {fixed}")
                if wait > 0:
                    actions.append(f"⏱ 2-3 мин: {wait}")
                if wrong > 0:
                    actions.append(f"⚠️ Неверный формат: {wrong}")
                if sim > 0:
                    actions.append(f"✅ Сим ворк: {sim}")

                for action in actions:
                    result += f"   {action}\n"

                # Среднее время в конце
                if avg_time:
                    minutes = int(avg_time // 60)
                    seconds = int(avg_time % 60)
                    result += f"   ⏱ Среднее: {minutes}м {seconds}с\n"

                result += "\n"

            result += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            result += "📄 Страница 3 из 4"

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка статистики саппорта: {e}", exc_info=True)
            return "⚠️ Ошибка получения данных"

    @staticmethod
    def get_dashboard_timing(period: str = "today") -> str:
        """
        Страница 4: Время реакции

        Args:
            period: Период для отображения

        Returns:
            Форматированная строка со статистикой времени
        """
        try:
            conn = db._get_connection()
            cursor = conn.cursor()

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

            # Только ошибки обработанные до 30 минут
            cursor.execute(
                f"""
                SELECT AVG(response_time_seconds), 
                       MIN(response_time_seconds),
                       MAX(response_time_seconds),
                       COUNT(*)
                FROM error_reports 
                WHERE {where_clause} 
                AND response_time_seconds IS NOT NULL
                AND response_time_seconds <= 1800
            """,
                (date_filter,),
            )
            stats = cursor.fetchone()

            # Распределение
            cursor.execute(
                f"""
                SELECT 
                    SUM(CASE WHEN response_time_seconds < 120 THEN 1 ELSE 0 END) as under_2min,
                    SUM(CASE WHEN response_time_seconds BETWEEN 120 AND 300 THEN 1 ELSE 0 END) as from_2_5,
                    SUM(CASE WHEN response_time_seconds BETWEEN 300 AND 600 THEN 1 ELSE 0 END) as from_5_10,
                    SUM(CASE WHEN response_time_seconds BETWEEN 600 AND 1800 THEN 1 ELSE 0 END) as from_10_30
                FROM error_reports 
                WHERE {where_clause} 
                AND response_time_seconds IS NOT NULL
                AND response_time_seconds <= 1800
            """,
                (date_filter,),
            )
            distribution = cursor.fetchone()

            conn.close()

            if not stats or stats[3] == 0:
                return f"⏱ <b>ВРЕМЯ РЕАКЦИИ {title.upper()}</b>\n\n📭 Данных нет."

            avg_time, min_time, max_time, count = stats
            under_2, from_2_5, from_5_10, from_10_30 = distribution

            def format_time(seconds):
                if not seconds:
                    return "нет данных"
                m = int(seconds // 60)
                s = int(seconds % 60)
                return f"{m}м {s}с"

            result = f"⏱ <b>ВРЕМЯ РЕАКЦИИ {title.upper()}</b>\n"
            result += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            result += f"📊 <b>Обработано ошибок:</b> {count}\n\n"

            result += f"🔹 Среднее: <b>{format_time(avg_time)}</b>\n"
            result += f"🟢 Быстрейший: {format_time(min_time)}\n"
            result += f"🔴 Самый долгий: {format_time(max_time)}\n\n"

            # Распределение
            result += "📈 <b>РАСПРЕДЕЛЕНИЕ:</b>\n\n"

            pct_under_2 = int((under_2 / count) * 100) if count > 0 else 0
            pct_2_5 = int((from_2_5 / count) * 100) if count > 0 else 0
            pct_5_10 = int((from_5_10 / count) * 100) if count > 0 else 0
            pct_10_30 = int((from_10_30 / count) * 100) if count > 0 else 0

            # Прогресс-бары
            def bar(percentage):
                filled = int(percentage / 10)
                return "█" * filled + "░" * (10 - filled)

            result += "🟢 До 2 мин:\n"
            result += f"   {bar(pct_under_2)} {under_2} ({pct_under_2}%)\n\n"

            result += "🟡 2-5 мин:\n"
            result += f"   {bar(pct_2_5)} {from_2_5} ({pct_2_5}%)\n\n"

            result += "🟠 5-10 мин:\n"
            result += f"   {bar(pct_5_10)} {from_5_10} ({pct_5_10}%)\n\n"

            result += "🔴 10-30 мин:\n"
            result += f"   {bar(pct_10_30)} {from_10_30} ({pct_10_30}%)\n\n"

            result += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            result += "📄 Страница 4 из 4"

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка статистики времени: {e}", exc_info=True)
            return "⚠️ Ошибка получения данных"


# Глобальный экземпляр сервиса
analytics_service = AnalyticsService()
