"""
ИСПРАВЛЕННЫЙ ФАЙЛ: services/scheduler_service.py
Планировщик задач для автоматического обновления Google Sheets

ИЗМЕНЕНИЯ:
✅ Заменен _run_async_task на использование asyncio.run() (более эффективно)
"""
import asyncio
from datetime import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from utils.logger import logger


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
    
    def _run_async_task(self, coro):
        """
        Запустить асинхронную задачу в синхронном контексте
        
        ✅ ИСПРАВЛЕНО: Используется asyncio.run() вместо создания нового event loop
        
        Args:
            coro: Корутина для запуска
        """
        try:
            asyncio.run(coro)
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения задачи: {e}")
            raise
    
    def _update_stats_job(self):
        """Задача обновления статистики"""
        try:
            from services.google_sheets_service import google_sheets_service
            
            now = datetime.now(self.timezone)
            logger.info(f"⏰ Запуск обновления статистики по расписанию ({now.strftime('%H:%M')})")
            
            # Проверка что сервис инициализирован
            if not google_sheets_service.client or not google_sheets_service.spreadsheet:
                logger.error("❌ Google Sheets сервис не инициализирован!")
                self._error_count += 1
                return
            
            # Выполнение обновления
            self._run_async_task(google_sheets_service.update_stats())
            
            # Обновление статистики успеха
            self._last_update_success = now
            self._update_count += 1
            
            logger.info(f"✅ Обновление завершено успешно (всего обновлений: {self._update_count})")
            
        except Exception as e:
            self._error_count += 1
            logger.error(f"❌ Ошибка задачи обновления статистики: {e}")
            logger.error(f"⚠️ Всего ошибок: {self._error_count}")
            
            # Если слишком много ошибок подряд - уведомление
            if self._error_count >= 3:
                logger.warning(f"⚠️ ВНИМАНИЕ: {self._error_count} ошибок обновления подряд!")
    
    def _create_weekly_sheet_job(self):
        """Задача создания нового листа"""
        try:
            from services.google_sheets_service import google_sheets_service
            
            now = datetime.now(self.timezone)
            logger.info(f"⏰ Запуск создания листа новой недели ({now.strftime('%Y-%m-%d %H:%M')})")
            
            if not google_sheets_service.client or not google_sheets_service.spreadsheet:
                logger.error("❌ Google Sheets сервис не инициализирован!")
                return
            
            self._run_async_task(google_sheets_service.create_weekly_sheet_if_needed())
            
            logger.info("✅ Проверка/создание листа завершено")
            
        except Exception as e:
            logger.error(f"❌ Ошибка задачи создания листа: {e}")
    
    def _reset_sips_job(self):
        """Задача сброса SIP (каждое утро в 8:00)"""
        try:
            from database.models import db
            
            now = datetime.now(self.timezone)
            logger.info(f"⏰ Запуск сброса SIP ({now.strftime('%Y-%m-%d %H:%M')})")
            
            db.reset_all_sips()
            
            logger.info("✅ SIP всех менеджеров сброшены")
            
        except Exception as e:
            logger.error(f"❌ Ошибка задачи сброса SIP: {e}")
    
    def add_jobs(self):
        """Добавить задачи в планировщик"""
        if self._jobs_added:
            logger.warning("⚠️ Задачи уже добавлены в планировщик")
            return
        
        try:
            # ===== ЗАДАЧА 1: Обновление статистики =====
            # Каждый час с 8:00 до 19:00, ПН-СБ
            self.scheduler.add_job(
                func=self._update_stats_job,
                trigger=CronTrigger(
                    day_of_week='mon-sat',  # Понедельник-Суббота
                    hour='8-19',            # С 8 утра до 19 вечера
                    minute=0,               # В начале часа
                    timezone=self.timezone
                ),
                id='update_stats',
                name='Обновление статистики в Google Sheets',
                replace_existing=True,
                max_instances=1  # Не запускать новую задачу, если предыдущая ещё работает
            )
            
            # ===== ЗАДАЧА 2: Создание нового листа =====
            # Каждый понедельник в 00:01
            self.scheduler.add_job(
                func=self._create_weekly_sheet_job,
                trigger=CronTrigger(
                    day_of_week='mon',      # Понедельник
                    hour=0,                 # 00 часов
                    minute=1,               # 01 минута
                    timezone=self.timezone
                ),
                id='create_weekly_sheet',
                name='Создание листа новой недели',
                replace_existing=True,
                max_instances=1
            )
            
            # ===== ЗАДАЧА 3: Сброс SIP =====
            # Каждое утро в 8:00 (ПН-СБ)
            self.scheduler.add_job(
                func=self._reset_sips_job,
                trigger=CronTrigger(
                    day_of_week='mon-sat',  # Понедельник-Суббота
                    hour=8,                 # 8 утра
                    minute=0,
                    timezone=self.timezone
                ),
                id='reset_sips',
                name='Сброс SIP менеджеров',
                replace_existing=True,
                max_instances=1
            )
            
            self._jobs_added = True
            logger.info("✅ Задачи добавлены в планировщик")
            logger.info("✅ Задача сброса SIP добавлена (8:00, ПН-СБ)")
            
            # Вывод информации о задачах
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
                logger.info("📊 Статистика будет обновляться каждый час (8:00-19:00, ПН-СБ)")
                logger.info("📋 Новый лист будет создаваться каждый понедельник в 00:01")
                logger.info("🔄 SIP будут сбрасываться каждое утро в 8:00 (ПН-СБ)")
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
                
                # Вывод финальной статистики
                if self._update_count > 0:
                    logger.info(f"📊 Статистика работы:")
                    logger.info(f"  ✅ Успешных обновлений: {self._update_count}")
                    logger.info(f"  ❌ Ошибок: {self._error_count}")
                    if self._last_update_success:
                        logger.info(f"  ⏰ Последнее обновление: {self._last_update_success.strftime('%Y-%m-%d %H:%M')}")
        except Exception as e:
            logger.error(f"❌ Ошибка остановки планировщика: {e}")
    
    def run_update_now(self):
        """Запустить обновление статистики прямо сейчас (для тестирования)"""
        logger.info("🔄 Ручной запуск обновления статистики")
        self._update_stats_job()
    
    def get_stats(self) -> dict:
        """
        Получить статистику работы планировщика
        
        Returns:
            Словарь со статистикой
        """
        return {
            'running': self.scheduler.running,
            'update_count': self._update_count,
            'error_count': self._error_count,
            'last_update': self._last_update_success.strftime('%Y-%m-%d %H:%M') if self._last_update_success else None,
            'jobs_count': len(self.scheduler.get_jobs()) if self.scheduler else 0
        }
    
    def get_next_run_time(self, job_id: str) -> str:
        """
        Получить время следующего запуска задачи
        
        Args:
            job_id: ID задачи ('update_stats' или 'create_weekly_sheet')
            
        Returns:
            Строка с временем или None
        """
        try:
            job = self.scheduler.get_job(job_id)
            if job and hasattr(job, 'next_run_time') and job.next_run_time:
                return job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            pass
        return None


# Глобальный экземпляр планировщика
scheduler_service = SchedulerService()

# НЕ запускаем автоматически - запуск только через main.py