# modules/scheduler.py
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
import aiocron
import traceback

logger = logging.getLogger(__name__)

class SchedulerManager:
    """Класс для управления запланированными публикациями"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.jobs = {}  # Словарь запланированных задач
        self.running = False
        self.check_interval = 60  # Интервал проверки в секундах
    
    async def start(self):
        """Запускает планировщик"""
        if not self.running:
            self.running = True
            logger.info("Планировщик запущен")
            
            # Запускаем фоновую задачу для периодической проверки запланированных постов
            asyncio.create_task(self._check_scheduled_posts())
            
            # Загружаем и планируем существующие посты
            await self._load_scheduled_posts()
    
    async def stop(self):
        """Останавливает планировщик"""
        if self.running:
            self.running = False
            
            # Отменяем все запланированные задачи
            for job_id, job in self.jobs.items():
                job.cancel()
            
            self.jobs = {}
            logger.info("Планировщик остановлен")
    
    async def _load_scheduled_posts(self):
        """Загружает все запланированные посты из базы данных и планирует их публикацию"""
        try:
            async with self.db_manager.async_session() as session:
                # Получаем все посты со статусом 'scheduled'
                from sqlalchemy import select
                from sqlalchemy.sql import and_
                
                query = select(self.db_manager.posts).where(
                    and_(
                        self.db_manager.posts.c.status == 'scheduled',
                        self.db_manager.posts.c.schedule_time > datetime.utcnow()
                    )
                )
                
                result = await session.execute(query)
                scheduled_posts = result.fetchall()
                
                if not scheduled_posts:
                    logger.info("Нет запланированных постов для загрузки")
                    return
                
                # Планируем публикацию для каждого поста
                for post in scheduled_posts:
                    post_dict = dict(post)
                    post_id = post_dict['id']
                    schedule_time = post_dict['schedule_time']
                    
                    # Планируем задачу только если время публикации в будущем
                    if schedule_time > datetime.utcnow():
                        await self.schedule_post(post_id, schedule_time)
                        logger.info(f"Запланирована публикация поста #{post_id} на {schedule_time}")
        except Exception as e:
            logger.error(f"Ошибка при загрузке запланированных постов: {e}")
    
    async def _check_scheduled_posts(self):
        """Периодически проверяет запланированные посты"""
        while self.running:
            try:
                # Получаем все посты, которые должны быть опубликованы в ближайшее время
                now = datetime.utcnow()
                future = now + timedelta(seconds=self.check_interval)
                
                async with self.db_manager.async_session() as session:
                    from sqlalchemy import select
                    from sqlalchemy.sql import and_
                    
                    query = select(self.db_manager.posts).where(
                        and_(
                            self.db_manager.posts.c.status == 'scheduled',
                            self.db_manager.posts.c.schedule_time.between(now, future)
                        )
                    )
                    
                    result = await session.execute(query)
                    posts_to_publish = result.fetchall()
                    
                    for post in posts_to_publish:
                        post_dict = dict(post)
                        post_id = post_dict['id']
                        
                        # Проверяем, есть ли уже запланированная задача для этого поста
                        if post_id not in self.jobs:
                            await self.schedule_post(post_id, post_dict['schedule_time'])
                
                # Ждем указанное время перед следующей проверкой
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Ошибка при проверке запланированных постов: {e}")
                
                # Ждем некоторое время перед повторной попыткой
                await asyncio.sleep(10)
    
    async def schedule_post(self, post_id: int, schedule_time: datetime):
        """
        Планирует публикацию поста
        
        Args:
            post_id: ID поста для публикации
            schedule_time: Время публикации
        """
        try:
            # Проверяем, есть ли уже запланированная задача для этого поста
            if post_id in self.jobs:
                # Отменяем существующую задачу
                self.jobs[post_id].cancel()
                del self.jobs[post_id]
            
            # Вычисляем задержку до публикации
            now = datetime.utcnow()
            delay = (schedule_time - now).total_seconds()
            
            # Если время публикации уже прошло, публикуем сразу
            if delay <= 0:
                asyncio.create_task(self._publish_post(post_id))
                return
            
            # Планируем задачу
            job = asyncio.create_task(self._schedule_task(post_id, delay))
            self.jobs[post_id] = job
            
            logger.info(f"Запланирована публикация поста #{post_id} через {delay:.2f} секунд")
            return True
        except Exception as e:
            logger.error(f"Ошибка при планировании публикации поста #{post_id}: {e}")
            return False
    
    async def _schedule_task(self, post_id: int, delay: float):
        """
        Фоновая задача для ожидания и публикации поста
        
        Args:
            post_id: ID поста для публикации
            delay: Задержка в секундах
        """
        try:
            # Ждем указанное время
            await asyncio.sleep(delay)
            
            # Публикуем пост
            await self._publish_post(post_id)
        except asyncio.CancelledError:
            # Задача была отменена, ничего не делаем
            pass
        except Exception as e:
            logger.error(f"Ошибка в задаче планирования поста #{post_id}: {e}")
            logger.error(traceback.format_exc())
        finally:
            # Удаляем задачу из словаря
            if post_id in self.jobs:
                del self.jobs[post_id]
    
    async def _publish_post(self, post_id: int):
        """
        Публикует запланированный пост
        
        Args:
            post_id: ID поста для публикации
        """
        try:
            # Получаем информацию о посте
            post = await self.db_manager.get_post_by_id(post_id)
            
            if not post:
                logger.error(f"Пост #{post_id} не найден")
                return
            
            # Проверяем статус поста
            if post['status'] != 'scheduled':
                logger.warning(f"Пост #{post_id} имеет неверный статус: {post['status']}")
                return
            
            # Обновляем статус поста
            await self.db_manager.update_post(
                post_id=post_id,
                status='publishing'
            )
            
            # Здесь будет логика публикации поста
            # В полной реализации здесь будет вызов других модулей для публикации на разных платформах
            logger.info(f"Публикация поста #{post_id}")
            
            # Для целей демонстрации просто обновляем статус
            await self.db_manager.update_post(
                post_id=post_id,
                status='published',
                published_at=datetime.utcnow()
            )
            
            logger.info(f"Пост #{post_id} успешно опубликован")
        except Exception as e:
            logger.error(f"Ошибка при публикации поста #{post_id}: {e}")
            logger.error(traceback.format_exc())
            
            # Обновляем статус поста в случае ошибки
            try:
                await self.db_manager.update_post(
                    post_id=post_id,
                    status='failed',
                    results={'error': str(e)}
                )
            except Exception as update_error:
                logger.error(f"Ошибка при обновлении статуса поста #{post_id}: {update_error}")
    
    async def cancel_scheduled_post(self, post_id: int):
        """
        Отменяет запланированную публикацию поста
        
        Args:
            post_id: ID поста для отмены
        """
        try:
            # Проверяем, есть ли запланированная задача для этого поста
            if post_id in self.jobs:
                # Отменяем задачу
                self.jobs[post_id].cancel()
                del self.jobs[post_id]
                logger.info(f"Публикация поста #{post_id} отменена")
                return True
            
            logger.warning(f"Нет запланированной задачи для поста #{post_id}")
            return False
        except Exception as e:
            logger.error(f"Ошибка при отмене публикации поста #{post_id}: {e}")
            return False
    
    async def reschedule_post(self, post_id: int, new_schedule_time: datetime):
        """
        Изменяет время публикации поста
        
        Args:
            post_id: ID поста
            new_schedule_time: Новое время публикации
        """
        try:
            # Обновляем время публикации в базе данных
            await self.db_manager.update_post(
                post_id=post_id,
                schedule_time=new_schedule_time
            )
            
            # Перепланируем публикацию
            return await self.schedule_post(post_id, new_schedule_time)
        except Exception as e:
            logger.error(f"Ошибка при изменении времени публикации поста #{post_id}: {e}")
            return False
