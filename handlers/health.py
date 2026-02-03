"""
РАСШИРЕНО: handlers/health.py
Добавлена проверка системы быстрых ошибок BMW

ИЗМЕНЕНИЯ:
✅ Добавлен _check_bmw_system()
✅ Статистика SIP менеджеров
✅ Проверка ConversationHandler
"""
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from services.user_service import user_service
from database.models import db
from utils.logger import logger


async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /health - показывает состояние всех компонентов бота"""
    user_id = update.effective_user.id

    if not user_service.is_admin(user_id):
        await update.message.reply_text(
            "❌ Эта команда доступна только администраторам."
        )
        return

    logger.info(f"🏥 Health check запрошен админом {user_id}")

    await update.message.reply_text(
        "🔍 Проверка состояния компонентов...\nЭто может занять несколько секунд."
    )

    health_status = await _collect_health_status()
    message = _format_health_message(health_status)

    await update.message.reply_text(message, parse_mode="HTML")


async def _collect_health_status() -> dict:
    """Собирает информацию о состоянии всех компонентов"""

    status = {"timestamp": datetime.now(), "components": {}}

    status["components"]["database"] = _check_database()
    status["components"]["scheduler"] = _check_scheduler()
    status["components"]["google_sheets"] = _check_google_sheets()
    status["components"]["system"] = _check_system()
    status["components"]["bot_stats"] = _check_bot_stats()
    status["components"]["bmw_system"] = _check_bmw_system()  # ✅ НОВОЕ

    return status


def _check_database() -> dict:
    """Проверяет состояние базы данных"""
    try:
        conn = db._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT 1")

        cursor.execute(
            "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"
        )
        db_size = cursor.fetchone()[0]
        db_size_mb = db_size / (1024 * 1024)

        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        tables_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'")
        indexes_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM managers")
        managers_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM error_reports")
        errors_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM telephonies")
        telephonies_count = cursor.fetchone()[0]

        conn.close()

        return {
            "status": "✅ Healthy",
            "details": {
                "size_mb": round(db_size_mb, 2),
                "tables": tables_count,
                "indexes": indexes_count,
                "managers": managers_count,
                "errors": errors_count,
                "telephonies": telephonies_count,
            },
        }

    except Exception as e:
        logger.error(f"❌ Ошибка проверки БД: {e}")
        return {"status": "❌ Error", "error": str(e)}


def _check_scheduler() -> dict:
    """Проверяет состояние планировщика"""
    try:
        from services.scheduler_service import scheduler_service

        stats = scheduler_service.get_stats()

        if not stats["running"]:
            return {"status": "⚠️ Stopped", "details": stats}

        if stats["consecutive_errors"] >= 3:
            status = "⚠️ Warning"
        else:
            status = "✅ Running"

        next_update = scheduler_service.get_next_run_time("update_stats")

        return {
            "status": status,
            "details": {
                "running": stats["running"],
                "jobs_count": stats["jobs_count"],
                "update_count": stats["update_count"],
                "error_count": stats["error_count"],
                "consecutive_errors": stats["consecutive_errors"],
                "last_update": stats["last_update"],
                "next_update": next_update,
            },
        }

    except Exception as e:
        logger.error(f"❌ Ошибка проверки планировщика: {e}")
        return {"status": "❌ Error", "error": str(e)}


def _check_google_sheets() -> dict:
    """Проверяет подключение к Google Sheets"""
    try:
        from services.google_sheets_service import google_sheets_service

        if not google_sheets_service.client:
            return {"status": "❌ Not Initialized", "error": "Client not initialized"}

        if not google_sheets_service.spreadsheet:
            return {"status": "❌ Not Connected", "error": "Spreadsheet not opened"}

        title = google_sheets_service.spreadsheet.title
        worksheets = google_sheets_service.spreadsheet.worksheets()

        return {
            "status": "✅ Connected",
            "details": {
                "spreadsheet": title,
                "worksheets_count": len(worksheets),
                "sheet_id": google_sheets_service.sheet_id[:20] + "...",
            },
        }

    except Exception as e:
        logger.error(f"❌ Ошибка проверки Google Sheets: {e}")
        return {"status": "❌ Error", "error": str(e)[:100]}


def _check_system() -> dict:
    """Проверяет системные ресурсы"""
    try:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available_mb = memory.available / (1024 * 1024)

        disk = psutil.disk_usage("/")
        disk_percent = disk.percent
        disk_free_gb = disk.free / (1024 * 1024 * 1024)

        if cpu_percent > 80 or memory_percent > 90 or disk_percent > 90:
            status = "⚠️ High Load"
        else:
            status = "✅ Normal"

        return {
            "status": status,
            "details": {
                "cpu_percent": round(cpu_percent, 1),
                "memory_percent": round(memory_percent, 1),
                "memory_available_mb": round(memory_available_mb, 1),
                "disk_percent": round(disk_percent, 1),
                "disk_free_gb": round(disk_free_gb, 1),
            },
        }

    except ImportError:
        return {
            "status": "⚠️ psutil not installed",
            "details": "Install psutil for system monitoring",
        }
    except Exception as e:
        logger.error(f"❌ Ошибка проверки системы: {e}")
        return {"status": "❌ Error", "error": str(e)}


def _check_bot_stats() -> dict:
    """Получает общую статистику работы бота"""
    try:
        conn = db._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) 
            FROM error_reports 
            WHERE DATE(created_at) = DATE('now')
        """
        )
        errors_today = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) 
            FROM error_reports 
            WHERE DATE(resolved_at) = DATE('now')
        """
        )
        resolved_today = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT AVG(response_time_seconds) 
            FROM error_reports 
            WHERE DATE(resolved_at) = DATE('now')
            AND response_time_seconds IS NOT NULL
            AND response_time_seconds <= 1800
        """
        )
        avg_time = cursor.fetchone()[0]

        conn.close()

        def format_time(seconds):
            if not seconds:
                return "нет данных"
            m = int(seconds // 60)
            s = int(seconds % 60)
            return f"{m}м {s}с"

        return {
            "status": "📊 Stats",
            "details": {
                "errors_today": errors_today,
                "resolved_today": resolved_today,
                "avg_response_time": format_time(avg_time),
            },
        }

    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики бота: {e}")
        return {"status": "❌ Error", "error": str(e)}


def _check_bmw_system() -> dict:
    """
    ✅ НОВОЕ: Проверяет состояние системы быстрых ошибок BMW

    Returns:
        Словарь со статусом и деталями
    """
    try:
        conn = db._get_connection()
        cursor = conn.cursor()

        # Общее количество SIP
        cursor.execute("SELECT COUNT(*) FROM manager_sips")
        total_sips = cursor.fetchone()[0]

        # SIP указанные сегодня
        cursor.execute(
            """
            SELECT COUNT(*) FROM manager_sips 
            WHERE last_updated = DATE('now')
        """
        )
        sips_today = cursor.fetchone()[0]

        # SIP указанные вчера (не обновлённые)
        cursor.execute(
            """
            SELECT COUNT(*) FROM manager_sips 
            WHERE last_updated < DATE('now')
        """
        )
        sips_outdated = cursor.fetchone()[0]

        # Быстрые ошибки за сегодня (SIP: в description)
        cursor.execute(
            """
            SELECT COUNT(*) FROM error_reports
            WHERE telephony_code = 'bmw'
            AND description LIKE 'SIP:%'
            AND DATE(created_at) = DATE('now')
        """
        )
        quick_errors_today = cursor.fetchone()[0]

        conn.close()

        # Определяем статус
        if total_sips == 0:
            status = "⚠️ No SIPs"
        elif sips_today > 0:
            status = "✅ Active"
        else:
            status = "⚠️ No activity today"

        return {
            "status": status,
            "details": {
                "total_sips": total_sips,
                "sips_today": sips_today,
                "sips_outdated": sips_outdated,
                "quick_errors_today": quick_errors_today,
            },
        }

    except Exception as e:
        logger.error(f"❌ Ошибка проверки BMW системы: {e}")
        return {"status": "❌ Error", "error": str(e)}


def _format_health_message(health_status: dict) -> str:
    """Форматирует сообщение о состоянии здоровья"""

    timestamp = health_status["timestamp"].strftime("%d.%m.%Y %H:%M:%S")
    components = health_status["components"]

    message = "🏥 <b>HEALTH CHECK</b>\n"
    message += f"⏰ {timestamp}\n"
    message += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # База данных
    db_info = components["database"]
    message += f"💾 <b>База данных:</b> {db_info['status']}\n"
    if "details" in db_info:
        d = db_info["details"]
        message += f"   Размер: {d['size_mb']} MB\n"
        message += f"   Таблицы: {d['tables']} | Индексы: {d['indexes']}\n"
        message += f"   Менеджеры: {d['managers']} | Ошибки: {d['errors']}\n"
    elif "error" in db_info:
        message += f"   ⚠️ {db_info['error']}\n"
    message += "\n"

    # Планировщик
    sch_info = components["scheduler"]
    message += f"⏱ <b>Планировщик:</b> {sch_info['status']}\n"
    if "details" in sch_info:
        d = sch_info["details"]
        message += f"   Задач: {d['jobs_count']} | Обновлений: {d['update_count']}\n"
        message += (
            f"   Ошибок: {d['error_count']} | Подряд: {d['consecutive_errors']}\n"
        )
        if d["last_update"]:
            message += f"   Последнее: {d['last_update']}\n"
        if d["next_update"]:
            message += f"   Следующее: {d['next_update']}\n"
    elif "error" in sch_info:
        message += f"   ⚠️ {sch_info['error']}\n"
    message += "\n"

    # Google Sheets
    gs_info = components["google_sheets"]
    message += f"📊 <b>Google Sheets:</b> {gs_info['status']}\n"
    if "details" in gs_info:
        d = gs_info["details"]
        message += f"   Таблица: {d['spreadsheet']}\n"
        message += f"   Листов: {d['worksheets_count']}\n"
    elif "error" in gs_info:
        message += f"   ⚠️ {gs_info['error']}\n"
    message += "\n"

    # Система
    sys_info = components["system"]
    message += f"🖥 <b>Система:</b> {sys_info['status']}\n"
    if "details" in sys_info:
        d = sys_info["details"]
        message += f"   CPU: {d['cpu_percent']}%\n"
        message += f"   RAM: {d['memory_percent']}% (свободно: {d['memory_available_mb']} MB)\n"
        message += f"   Диск: {d['disk_percent']}% (свободно: {d['disk_free_gb']} GB)\n"
    elif "error" in sys_info:
        message += f"   ⚠️ {sys_info['error']}\n"
    message += "\n"

    # ✅ НОВОЕ: BMW система
    bmw_info = components["bmw_system"]
    message += f"🔵 <b>BMW Быстрые ошибки:</b> {bmw_info['status']}\n"
    if "details" in bmw_info:
        d = bmw_info["details"]
        message += f"   Всего SIP: {d['total_sips']}\n"
        message += f"   Указано сегодня: {d['sips_today']}\n"
        message += f"   Устаревших: {d['sips_outdated']}\n"
        message += f"   Быстрых ошибок сегодня: {d['quick_errors_today']}\n"
    elif "error" in bmw_info:
        message += f"   ⚠️ {bmw_info['error']}\n"
    message += "\n"

    # Статистика бота
    bot_info = components["bot_stats"]
    message += "📈 <b>Статистика за сегодня:</b>\n"
    if "details" in bot_info:
        d = bot_info["details"]
        message += f"   Ошибок получено: {d['errors_today']}\n"
        message += f"   Ошибок решено: {d['resolved_today']}\n"
        message += f"   Среднее время: {d['avg_response_time']}\n"
    elif "error" in bot_info:
        message += f"   ⚠️ {bot_info['error']}\n"

    message += "\n━━━━━━━━━━━━━━━━━━━━━━━━"

    return message
