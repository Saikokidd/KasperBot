"""
ФИНАЛЬНАЯ ВЕРСИЯ: services/scheduler_service.py
С уведомлениями админу при критических ошибках + статистика баз
"""
import asyncio
from datetime import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot

from utils.logger import logger
from utils.notifications import notification_service
from config.settings import settings


class SchedulerService:
    """Планировщик фоновых задач"""
    
    def __init__(self):
        """Инициализация планировщика"""
        self.scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Kiev'))
        self.timezone = pytz.timezone('Europe/Kiev')
        self._jobs_added = False
        self._last_update_success = None
        self._update_count = 0
        self._error_count = 0
        self._consecutive_errors = 0
        self._bot = None
    
    def set_bot(self, bot: Bot):
        """Установить экземпляр бота для отправки уведомлений"""
        self._bot = bot
        logger.info("✅ Бот установлен для отправки уведомлений")
    
    def _run_async_task(self, coro):
        """Запустить асинхронную задачу в синхронном контексте"""
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(coro)
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения задачи: {e}")
            raise
        finally:
            if loop is not None:
                try:
                    loop.close()
                except Exception as e:
                    logger.error(f"⚠️ Ошибка закрытия event loop: {e}")
    
    def _update_stats_job(self):
        """Задача обновления статистики менеджеров"""
        try:
            from services.google_sheets_service import google_sheets_service
            
            now = datetime.now(self.timezone)
            logger.info(f"⏰ Запуск обновления статистики менеджеров ({now.strftime('%H:%M')})")
            
            if not google_sheets_service.client or not google_sheets_service.spreadsheet:
                logger.error("❌ Google Sheets сервис не инициализирован!")
                self._error_count += 1
                self._consecutive_errors += 1
                
                if self._consecutive_errors >= 3 and self._bot:
                    self._send_critical_notification(
                        "Google Sheets не инициализирован",
                        f"{self._consecutive_errors} ошибок подряд при инициализации"
                    )
                return
            
            self._run_async_task(google_sheets_service.update_stats())
            
            if self._consecutive_errors >= 3:
                if self._bot:
                    self._send_recovery_notification("Google Sheets обновление")
            
            self._consecutive_errors = 0
            self._last_update_success = now
            self._update_count += 1
            
            logger.info(f"✅ Обновление статистики менеджеров завершено (всего: {self._update_count})")
            
        except Exception as e:
            self._error_count += 1
            self._consecutive_errors += 1
            
            error_msg = str(e)
            logger.error(f"❌ Ошибка обновления статистики менеджеров: {error_msg}")
            logger.error(f"⚠️ Ошибок подряд: {self._consecutive_errors}, всего: {self._error_count}")
            
            if self._consecutive_errors >= 3 and self._bot:
                additional_info = (
                    f"• Всего обновлений: {self._update_count}\n"
                    f"• Всего ошибок: {self._error_count}\n"
                    f"• Ошибок подряд: {self._consecutive_errors}"
                )
                
                self._send_critical_notification(
                    "Google Sheets обновление",
                    error_msg,
                    additional_info
                )
            
            if self._consecutive_errors >= 5:
                logger.warning(f"⚠️ КРИТИЧНО: {self._consecutive_errors} ошибок обновления подряд!")
    
    def _update_base_stats_job(self):
        """
        ✅ НОВАЯ ЗАДАЧА: Обновление статистики баз
        """
        try:
            from services.base_stats_service import base_stats_service
            
            now = datetime.now(self.timezone)
            logger.info(f"⏰ Запуск обновления статистики баз ({now.strftime('%H:%M')})")
            
            if not base_stats_service.client or not base_stats_service.spreadsheet:
                logger.error("❌ BaseStatsService не инициализирован!")
                logger.error("   Проверьте BASE_STATS_SHEET_ID в .env")
                return
            
            self._run_async_task(base_stats_service.update_stats())
            
            logger.info(f"✅ Обновление статистики баз завершено")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статистики баз: {e}")
            
            if self._bot:
                self._send_critical_notification(
                    "Статистика баз",
                    str(e)
                )
    
    def _create_weekly_sheet_job(self):
        """Задача создания нового листа"""
        try:
            from services.google_sheets_service import google_sheets_service
            
            now = datetime.now(self.timezone)
            logger.info(f"⏰ Запуск создания листа новой недели ({now.strftime('%Y-%m-%d %H:%M')})")
            
            if not google_sheets_service.client or not google_sheets_service.spreadsheet:
                logger.error("❌ Google Sheets сервис не инициализирован!")
                
                if self._bot:
                    self._send_critical_notification(
                        "Создание листа недели",
                        "Google Sheets сервис не инициализирован"
                    )
                return
            
            self._run_async_task(google_sheets_service.create_weekly_sheet_if_needed())
            
            logger.info("✅ Проверка/создание листа завершено")
            
        except Exception as e:
            logger.error(f"❌ Ошибка задачи создания листа: {e}")
            
            if self._bot:
                self._send_critical_notification(
                    "Создание листа недели",
                    str(e)
                )
    
    def _reset_sips_job(self):
        """Задача сброса SIP (каждое утро в 8:00)"""
        try:
            from database.models import db
            
            now = datetime.now(self.timezone)
            logger.info(f"⏰ Запуск сброса SIP ({now.strftime('%Y-%m-%d %H:%M')})")
            
            affected = db.reset_all_sips()
            
            if affected > 0:
                logger.info(f"✅ Сброшено {affected} SIP менеджеров")
            else:
                logger.info("ℹ️ SIP уже были сброшены ранее")
            
        except Exception as e:
            logger.error(f"❌ Ошибка задачи сброса SIP: {e}")
            
            if self._bot:
                self._send_critical_notification(
                    "Сброс SIP менеджеров",
                    str(e)
                )
    
    def _send_critical_notification(
        self,
        error_type: str,
        error_msg: str,
        additional_info: str = None
    ):
        """Отправить критическое уведомление админу"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                notification_service.notify_critical_error(
                    bot=self._bot,
                    error_type=error_type,
                    details=error_msg,
                    additional_info=additional_info
                )
            )
            loop.close()
        except Exception as e:
            logger.error(f"❌ Не удалось отправить уведомление: {e}")
    
    def _send_recovery_notification(self, service_name: str):
        """Отправить уведомление о восстановлении"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                notification_service.notify_recovery(
                    bot=self._bot,
                    service_name=service_name
                )
            )
            loop.close()
        except Exception as e:
            logger.error(f"❌ Не удалось отправить уведомление о восстановлении: {e}")
    
    def add_jobs(self):
        """Добавить задачи в планировщик"""
        if self._jobs_added:
            logger.warning("⚠️ Задачи уже добавлены в планировщик")
            return
        
        try:
            # ===== ЗАДАЧА 1: Обновление статистики менеджеров =====
            self.scheduler.add_job(
                func=self._update_stats_job,
                trigger=CronTrigger(
                    day_of_week='mon-sat',
                    hour='8-19',
                    minute=0,
                    timezone=self.timezone
                ),
                id='update_stats',
                name='Обновление статистики менеджеров',
                replace_existing=True,
                max_instances=1
            )
            
            # ===== ЗАДАЧА 2: Обновление статистики баз ✅ НОВОЕ =====
            self.scheduler.add_job(
                func=self._update_base_stats_job,
                trigger=CronTrigger(
                    day_of_week='mon-sat',
                    hour='8-19',
                    minute=0,
                    timezone=self.timezone
                ),
                id='update_base_stats',
                name='Обновление статистики баз',
                replace_existing=True,
                max_instances=1
            )
            
            # ===== ЗАДАЧА 3: Создание нового листа =====
            self.scheduler.add_job(
                func=self._create_weekly_sheet_job,
                trigger=CronTrigger(
                    day_of_week='mon',
                    hour=0,
                    minute=1,
                    timezone=self.timezone
                ),
                id='create_weekly_sheet',
                name='Создание листа новой недели',
                replace_existing=True,
                max_instances=1
            )
            
            # ===== ЗАДАЧА 4: Сброс SIP =====
            self.scheduler.add_job(
                func=self._reset_sips_job,
                trigger=CronTrigger(
                    day_of_week='mon-sat',
                    hour=8,
                    minute=0,
                    timezone=self.timezone
                ),
                id='reset_sips',
                name='Сброс SIP менеджеров',
                replace_existing=True,
                max_instances=1
            )
            
            self._jobs_added = True
            logger.info("✅ Все задачи добавлены в планировщик")
            logger.info("   • Статистика менеджеров: каждый час (8:00-19:00, ПН-СБ)")
            logger.info("   • Статистика баз: каждый час (8:00-19:00, ПН-СБ)")
            logger.info("   • Создание листа: понедельник 00:01")
            logger.info("   • Сброс SIP: 8:00 (ПН-СБ)")
        
            self._print_jobs_info()
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления задач: {e}")
    
    def _print_jobs_info(self):
        """Вывести информацию о запланированных задачах"""
        jobs = self.scheduler.get_jobs()
        logger.info(f"📋 Запланировано задач: {len(jobs)}")
        
        for job in jobs:
            try:
                if hasattr(job, 'next_run_time') and job.next_run_time:
                    next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
                    logger.info(f"  ⏰ {job.name}: {next_run}")
                else:
                    logger.info(f"  ⏰ {job.name}: (время неизвестно)")
            except Exception:
                logger.info(f"  ⏰ {job.name}: (ошибка получения времени)")
    
    def start(self):
        """Запустить планировщик"""
        try:
            if not self._jobs_added:
                self.add_jobs()
            
            if not self.scheduler.running:
                self.scheduler.start()
                logger.info("🚀 Планировщик задач запущен")
                logger.info("📊 Статистика менеджеров: каждый час (8:00-19:00, ПН-СБ)")
                logger.info("📊 Статистика баз: каждый час (8:00-19:00, ПН-СБ)")
                logger.info("📋 Новый лист: каждый понедельник в 00:01")
                logger.info("🔄 SIP: сброс каждое утро в 8:00 (ПН-СБ)")
                logger.info("📨 Критические ошибки → админам")
            else:
                logger.warning("⚠️ Планировщик уже запущен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска планировщика: {e}")
    
    def stop(self):
        """Остановить планировщик"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown()
                logger.info("⏹️ Планировщик задач остановлен")
            
                if self._update_count > 0:
                    logger.info(f"📊 Статистика работы:")
                    logger.info(f"  ✅ Успешных обновлений: {self._update_count}")
                    logger.info(f"  ❌ Всего ошибок: {self._error_count}")
                    if self._last_update_success:
                        logger.info(f"  ⏰ Последнее обновление: {self._last_update_success.strftime('%Y-%m-%d %H:%M')}")
        except Exception as e:
            logger.error(f"❌ Ошибка остановки планировщика: {e}")
    
    def run_update_now(self):
        """Запустить обновление статистики прямо сейчас (для тестирования)"""
        logger.info("🔄 Ручной запуск обновления статистики")
        self._update_stats_job()
    
    def run_base_stats_now(self):
        """
        ✅ НОВОЕ: Запустить обновление статистики баз прямо сейчас
        """
        logger.info("🔄 Ручной запуск обновления статистики баз")
        self._update_base_stats_job()
    
    def get_stats(self) -> dict:
        """Получить статистику работы планировщика"""
        return {
            'running': self.scheduler.running,
            'update_count': self._update_count,
            'error_count': self._error_count,
            'consecutive_errors': self._consecutive_errors,
            'last_update': self._last_update_success.strftime('%Y-%m-%d %H:%M') if self._last_update_success else None,
            'jobs_count': len(self.scheduler.get_jobs()) if self.scheduler else 0
        }
    
    def get_next_run_time(self, job_id: str) -> str:
        """Получить время следующего запуска задачи"""
        try:
            job = self.scheduler.get_job(job_id)
            if job and hasattr(job, 'next_run_time') and job.next_run_time:
                return job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            pass
        return None


# Глобальный экземпляр планировщика
scheduler_service = SchedulerService()