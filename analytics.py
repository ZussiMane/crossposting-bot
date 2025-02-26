# modules/analytics.py
import logging
import asyncio
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sqlalchemy import select, and_, or_, func, desc
import traceback

logger = logging.getLogger(__name__)

class AnalyticsManager:
    """Класс для управления аналитикой и статистикой"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.tracking_tasks = {}  # Словарь задач для отслеживания статистики
        self.update_interval = 3600  # Интервал обновления статистики (в секундах)
        self.reports_dir = 'reports'
        
        # Создаем директорию для отчетов
        os.makedirs(self.reports_dir, exist_ok=True)
    
    async def start_tracking(self, post_id: int, platforms: List[str]):
        """
        Начинает отслеживание статистики для поста
        
        Args:
            post_id: ID поста
            platforms: Список платформ для отслеживания
        """
        try:
            # Проверяем, есть ли уже задача для этого поста
            if post_id in self.tracking_tasks:
                # Отменяем существующую задачу
                self.tracking_tasks[post_id].cancel()
            
            # Создаем новую задачу
            task = asyncio.create_task(self._tracking_task(post_id, platforms))
            self.tracking_tasks[post_id] = task
            
            logger.info(f"Начато отслеживание статистики для поста #{post_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при запуске отслеживания статистики для поста #{post_id}: {e}")
            return False
    
    async def stop_tracking(self, post_id: int):
        """
        Останавливает отслеживание статистики для поста
        
        Args:
            post_id: ID поста
        """
        try:
            # Проверяем, есть ли задача для этого поста
            if post_id in self.tracking_tasks:
                # Отменяем задачу
                self.tracking_tasks[post_id].cancel()
                del self.tracking_tasks[post_id]
                logger.info(f"Отслеживание статистики для поста #{post_id} остановлено")
                return True
            
            logger.warning(f"Нет задачи отслеживания для поста #{post_id}")
            return False
        except Exception as e:
            logger.error(f"Ошибка при остановке отслеживания статистики для поста #{post_id}: {e}")
            return False
    
    async def _tracking_task(self, post_id: int, platforms: List[str]):
        """
        Фоновая задача для периодического обновления статистики
        
        Args:
            post_id: ID поста
            platforms: Список платформ для отслеживания
        """
        try:
            # Количество обновлений статистики
            updates_count = 0
            
            # Периодически обновляем статистику
            while True:
                # Обновляем статистику
                await self.update_post_statistics(post_id, platforms)
                
                # Увеличиваем счетчик обновлений
                updates_count += 1
                
                # Если пост старше 7 дней, увеличиваем интервал обновления
                post = await self.db_manager.get_post_by_id(post_id)
                
                if post and post.get('published_at'):
                    published_at = datetime.fromisoformat(post['published_at'])
                    days_since_publish = (datetime.utcnow() - published_at).days
                    
                    # Для постов старше 7 дней обновляем статистику реже
                    if days_since_publish > 7:
                        # Для постов старше 7 дней обновляем каждые 12 часов
                        await asyncio.sleep(12 * 3600)
                    # Для постов старше 3 дней обновляем каждые 6 часов
                    elif days_since_publish > 3:
                        await asyncio.sleep(6 * 3600)
                    # Для постов старше 1 дня обновляем каждые 3 часа
                    elif days_since_publish > 1:
                        await asyncio.sleep(3 * 3600)
                    else:
                        # Для свежих постов обновляем каждый час
                        await asyncio.sleep(self.update_interval)
                else:
                    # Если информация о публикации недоступна, используем стандартный интервал
                    await asyncio.sleep(self.update_interval)
                
                # Если статистика обновлялась более 30 раз и пост старше 7 дней, прекращаем отслеживание
                if updates_count > 30 and days_since_publish > 7:
                    logger.info(f"Автоматическое отслеживание статистики для поста #{post_id} завершено")
                    break
        except asyncio.CancelledError:
            # Задача была отменена, ничего не делаем
            pass
        except Exception as e:
            logger.error(f"Ошибка в задаче отслеживания статистики для поста #{post_id}: {e}")
            logger.error(traceback.format_exc())
        finally:
            # Удаляем задачу из словаря
            if post_id in self.tracking_tasks:
                del self.tracking_tasks[post_id]
    
    async def update_post_statistics(self, post_id: int, platforms: List[str] = None):
        """
        Обновляет статистику для поста
        
        Args:
            post_id: ID поста
            platforms: Список платформ для обновления (если None, используются все платформы из поста)
        """
        try:
            # Получаем информацию о посте
            post = await self.db_manager.get_post_by_id(post_id)
            
            if not post:
                logger.error(f"Пост #{post_id} не найден")
                return False
            
            # Если платформы не указаны, используем платформы из поста
            if not platforms:
                platforms = post.get('platforms', [])
            
            # Здесь будет логика обновления статистики для разных платформ
            # В полной реализации здесь будут вызовы API разных платформ для получения статистики
            # Для целей демонстрации создаем случайную статистику
            
            # Время последнего обновления статистики
            last_update = datetime.utcnow()
            
            # Для каждой платформы сохраняем статистику
            results = {}
            for platform in platforms:
                metrics = {}
                
                if platform == 'vk':
                    # Имитация статистики ВКонтакте
                    metrics = {
                        'views': np.random.randint(100, 1000),
                        'likes': np.random.randint(10, 100),
                        'reposts': np.random.randint(1, 20),
                        'comments': np.random.randint(1, 30),
                        'reach': np.random.randint(200, 2000),
                        'engagement': np.random.randint(5, 50) / 100.0,
                        'updated_at': last_update.isoformat()
                    }
                elif platform == 'telegram':
                    # Имитация статистики Telegram
                    metrics = {
                        'views': np.random.randint(50, 500),
                        'reactions': np.random.randint(5, 50),
                        'forwards': np.random.randint(1, 15),
                        'replies': np.random.randint(0, 10),
                        'reach': np.random.randint(100, 1000),
                        'engagement': np.random.randint(5, 60) / 100.0,
                        'updated_at': last_update.isoformat()
                    }
                elif platform == 'website':
                    # Имитация статистики сайта
                    metrics = {
                        'views': np.random.randint(30, 300),
                        'likes': np.random.randint(2, 20),
                        'comments': np.random.randint(0, 5),
                        'shares': np.random.randint(0, 10),
                        'reach': np.random.randint(50, 500),
                        'engagement': np.random.randint(3, 40) / 100.0,
                        'updated_at': last_update.isoformat()
                    }
                
                # Сохраняем статистику в базу данных
                await self.db_manager.add_statistics(post_id, platform, metrics)
                
                # Добавляем в результаты
                results[platform] = metrics
            
            logger.info(f"Статистика для поста #{post_id} обновлена")
            return results
        except Exception as e:
            logger.error(f"Ошибка при обновлении статистики для поста #{post_id}: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def get_post_statistics(self, post_id: int) -> Dict[str, Any]:
        """
        Получает статистику для поста
        
        Args:
            post_id: ID поста
            
        Returns:
            Словарь со статистикой
        """
        try:
            # Получаем статистику из базы данных
            stats_data = await self.db_manager.get_post_statistics(post_id)
            
            if not stats_data:
                # Если статистики нет, возвращаем пустой словарь
                return {}
            
            # Обрабатываем статистику
            result = {}
            total_reach = 0
            total_engagement = 0
            
            for platform, stats_list in stats_data.items():
                if not stats_list:
                    continue
                
                # Берем последнюю статистику для каждой платформы
                latest_stats = stats_list[-1]
                result[platform] = latest_stats
                
                # Суммируем показатели для общей статистики
                if 'reach' in latest_stats:
                    total_reach += latest_stats['reach']
                if 'engagement' in latest_stats:
                    total_engagement += latest_stats['engagement']
            
            # Добавляем общую статистику
            result['total'] = {
                'reach': total_reach,
                'engagement_rate': total_engagement / len(stats_data) if len(stats_data) > 0 else 0
            }
            
            return result
        except Exception as e:
            logger.error(f"Ошибка при получении статистики для поста #{post_id}: {e}")
            return {}
    
    async def get_general_statistics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Получает общую статистику по всем постам пользователя
        
        Args:
            user_id: ID пользователя (в Telegram)
            days: Количество дней для анализа
            
        Returns:
            Словарь с общей статистикой
        """
        try:
            # Получаем ID пользователя в базе данных
            user = await self.db_manager.get_user_by_telegram_id(user_id)
            if not user:
                logger.error(f"Пользователь с Telegram ID {user_id} не найден")
                return {}
            
            # Получаем все опубликованные посты пользователя за указанный период
            async with self.db_manager.async_session() as session:
                start_date = datetime.utcnow() - timedelta(days=days)
                
                query = select(self.db_manager.posts).where(
                    and_(
                        self.db_manager.posts.c.user_id == user['id'],
                        self.db_manager.posts.c.status == 'published',
                        self.db_manager.posts.c.published_at >= start_date
                    )
                )
                
                result = await session.execute(query)
                posts = result.fetchall()
                
                if not posts:
                    logger.info(f"Нет опубликованных постов за последние {days} дней")
                    return {
                        'total_posts': 0,
                        'total_reach': 0,
                        'avg_engagement': 0,
                        'best_time': 'Нет данных',
                        'best_platform': 'Нет данных'
                    }
                
                # Собираем статистику по всем постам
                total_reach = 0
                total_engagement = 0
                posts_with_stats = 0
                
                # Словари для анализа лучшего времени и платформы
                time_stats = {}  # Часы -> {sum_reach, count}
                platform_stats = {}  # Платформа -> {sum_reach, count}
                
                for post in posts:
                    post_dict = dict(post)
                    post_id = post_dict['id']
                    
                    # Получаем статистику поста
                    post_stats = await self.get_post_statistics(post_id)
                    
                    if not post_stats or 'total' not in post_stats:
                        continue
                    
                    # Суммируем показатели
                    total_reach += post_stats['total'].get('reach', 0)
                    total_engagement += post_stats['total'].get('engagement_rate', 0)
                    posts_with_stats += 1
                    
                    # Анализируем время публикации
                    if post_dict.get('published_at'):
                        published_at = datetime.fromisoformat(post_dict['published_at'])
                        hour = published_at.hour
                        
                        if hour not in time_stats:
                            time_stats[hour] = {'sum_reach': 0, 'count': 0}
                        
                        time_stats[hour]['sum_reach'] += post_stats['total'].get('reach', 0)
                        time_stats[hour]['count'] += 1
                    
                    # Анализируем платформы
                    for platform in post_dict.get('platforms', []):
                        if platform not in platform_stats:
                            platform_stats[platform] = {'sum_reach': 0, 'count': 0}
                        
                        if platform in post_stats:
                            platform_stats[platform]['sum_reach'] += post_stats[platform].get('reach', 0)
                            platform_stats[platform]['count'] += 1
                
                # Вычисляем средние показатели
                avg_engagement = total_engagement / posts_with_stats if posts_with_stats > 0 else 0
                
                # Находим лучшее время для публикации
                best_time = 'Нет данных'
                if time_stats:
                    best_hour = max(time_stats, key=lambda h: time_stats[h]['sum_reach'] / time_stats[h]['count'] if time_stats[h]['count'] > 0 else 0)
                    best_time = f"{best_hour}:00 - {best_hour}:59"
                
                # Находим лучшую платформу
                best_platform = 'Нет данных'
                if platform_stats:
                    best_platform = max(platform_stats, key=lambda p: platform_stats[p]['sum_reach'] / platform_stats[p]['count'] if platform_stats[p]['count'] > 0 else 0)
                    best_platform = best_platform.capitalize()
                
                return {
                    'total_posts': len(posts),
                    'total_reach': total_reach,
                    'avg_engagement': round(avg_engagement * 100, 2),
                    'best_time': best_time,
                    'best_platform': best_platform
                }
        except Exception as e:
            logger.error(f"Ошибка при получении общей статистики: {e}")
            logger.error(traceback.format_exc())
            return {}
    
    async def get_recommendations(self, user_id: int) -> Dict[str, str]:
        """
        Генерирует рекомендации на основе анализа статистики
        
        Args:
            user_id: ID пользователя (в Telegram)
            
        Returns:
            Словарь с рекомендациями
        """
        try:
            # Получаем общую статистику
            stats = await self.get_general_statistics(user_id)
            
            if not stats or stats.get('total_posts', 0) == 0:
                logger.info("Недостаточно данных для рекомендаций")
                return {}
            
            # Получаем ID пользователя в базе данных
            user = await self.db_manager.get_user_by_telegram_id(user_id)
            if not user:
                logger.error(f"Пользователь с Telegram ID {user_id} не найден")
                return {}
            
            # Получаем все посты пользователя
            async with self.db_manager.async_session() as session:
                query = select(self.db_manager.posts).where(
                    and_(
                        self.db_manager.posts.c.user_id == user['id'],
                        self.db_manager.posts.c.status == 'published'
                    )
                ).order_by(desc(self.db_manager.posts.c.published_at))
                
                result = await session.execute(query)
                posts = result.fetchall()
                
                if not posts:
                    return {}
                
                # Анализируем содержимое постов
                text_lengths = []
                media_counts = []
                platforms_used = {}
                
                for post in posts:
                    post_dict = dict(post)
                    
                    # Длина текста
                    text_length = len(post_dict.get('text', '')) if post_dict.get('text') else 0
                    text_lengths.append(text_length)
                    
                    # Количество медиафайлов
                    media_count = len(post_dict.get('media_files', [])) if post_dict.get('media_files') else 0
                    media_counts.append(media_count)
                    
                    # Используемые платформы
                    for platform in post_dict.get('platforms', []):
                        if platform not in platforms_used:
                            platforms_used[platform] = 0
                        platforms_used[platform] += 1
                
                # Генерируем рекомендации
                recommendations = {}
                
                # Рекомендации по времени публикации
                best_time = stats.get('best_time', 'Нет данных')
                if best_time != 'Нет данных':
                    recommendations['best_time'] = f"Оптимальное время публикации: {best_time}. Посты, опубликованные в это время, показывают наибольший охват."
                
                # Рекомендации по типу контента
                avg_text_length = sum(text_lengths) / len(text_lengths) if text_lengths else 0
                avg_media_count = sum(media_counts) / len(media_counts) if media_counts else 0
                
                content_recommendation = ""
                if avg_text_length > 500 and avg_media_count > 0:
                    content_recommendation = "Ваши посты с длинным текстом и медиафайлами показывают хорошие результаты. Рекомендуется продолжать создавать подробный контент с визуальным сопровождением."
                elif avg_text_length > 500:
                    content_recommendation = "Ваши текстовые посты показывают хорошие результаты. Рекомендуется добавить больше визуального контента для увеличения вовлеченности."
                elif avg_media_count > 0:
                    content_recommendation = "Ваши посты с медиафайлами показывают хорошие результаты. Рекомендуется добавить более содержательный текст для лучшего понимания контента."
                else:
                    content_recommendation = "Рекомендуется экспериментировать с разными форматами контента: добавлять медиафайлы и писать более содержательные тексты."
                
                recommendations['content_type'] = content_recommendation
                
                # Рекомендации по платформам
                best_platform = stats.get('best_platform', 'Нет данных')
                if best_platform != 'Нет данных':
                    if len(platforms_used) == 1:
                        recommendations['platform'] = f"Рекомендуется расширить присутствие на других платформах, например, добавить публикации в {best_platform if best_platform != list(platforms_used.keys())[0].capitalize() else 'других социальных сетях'}."
                    else:
                        recommendations['platform'] = f"Платформа {best_platform} показывает наилучшие результаты для ваших постов. Рекомендуется увеличить активность на этой платформе."
                
                return recommendations
        except Exception as e:
            logger.error(f"Ошибка при генерации рекомендаций: {e}")
            logger.error(traceback.format_exc())
            return {}
    
    async def generate_report(self, user_id: int, days: int = None) -> str:
        """
        Генерирует отчет со статистикой
        
        Args:
            user_id: ID пользователя (в Telegram)
            days: Количество дней для анализа (если None, то за все время)
            
        Returns:
            Путь к файлу отчета
        """
        try:
            # Получаем ID пользователя в базе данных
            user = await self.db_manager.get_user_by_telegram_id(user_id)
            if not user:
                logger.error(f"Пользователь с Telegram ID {user_id} не найден")
                return None
            
            # Получаем все опубликованные посты пользователя
            async with self.db_manager.async_session() as session:
                query = select(self.db_manager.posts).where(
                    and_(
                        self.db_manager.posts.c.user_id == user['id'],
                        self.db_manager.posts.c.status == 'published'
                    )
                )
                
                # Если указан период, добавляем условие
                if days is not None:
                    start_date = datetime.utcnow() - timedelta(days=days)
                    query = query.where(self.db_manager.posts.c.published_at >= start_date)
                
                query = query.order_by(desc(self.db_manager.posts.c.published_at))
                
                result = await session.execute(query)
                posts = result.fetchall()
                
                if not posts:
                    logger.info(f"Нет опубликованных постов")
                    return None
                
                # Создаем DataFrame для отчета
                data = []
                
                for post in posts:
                    post_dict = dict(post)
                    post_id = post_dict['id']
                    
                    # Получаем статистику поста
                    post_stats = await self.get_post_statistics(post_id)
                    
                    # Базовая информация о посте
                    post_data = {
                        'id': post_id,
                        'published_at': datetime.fromisoformat(post_dict['published_at']) if post_dict.get('published_at') else None,
                        'platforms': ', '.join(post_dict.get('platforms', [])),
                        'text_length': len(post_dict.get('text', '')) if post_dict.get('text') else 0,
                        'media_count': len(post_dict.get('media_files', [])) if post_dict.get('media_files') else 0
                    }
                    
                    # Добавляем статистику по каждой платформе
                    for platform in post_dict.get('platforms', []):
                        if platform in post_stats:
                            platform_stats = post_stats[platform]
                            for metric, value in platform_stats.items():
                                if metric != 'updated_at':
                                    post_data[f'{platform}_{metric}'] = value
                    
                    # Добавляем общую статистику
                    if 'total' in post_stats:
                        for metric, value in post_stats['total'].items():
                            post_data[f'total_{metric}'] = value
                    
                    data.append(post_data)
                
                # Создаем DataFrame
                df = pd.DataFrame(data)
                
                # Создаем уникальное имя файла для отчета
                report_name = f"report_{user['id']}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xlsx"
                report_path = os.path.join(self.reports_dir, report_name)
                
                # Создаем отчет в формате Excel
                with pd.ExcelWriter(report_path, engine='xlsxwriter') as writer:
                    # Лист с данными постов
                    df.to_excel(writer, sheet_name='Posts', index=False)
                    
                    # Создаем график охвата
                    if 'total_reach' in df.columns and 'published_at' in df.columns:
                        df_sorted = df.sort_values('published_at')
                        plt.figure(figsize=(10, 6))
                        plt.plot(df_sorted['published_at'], df_sorted['total_reach'], marker='o')
                        plt.title('Охват постов')
                        plt.xlabel('Дата публикации')
                        plt.ylabel('Охват')
                        plt.grid(True)
                        plt.tight_layout()
                        
                        # Сохраняем график
                        chart_path = os.path.join(self.reports_dir, f"chart_{user['id']}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.png")
                        plt.savefig(chart_path)
                        plt.close()
                        
                        # Добавляем лист с графиком
                        worksheet = writer.book.add_worksheet('Reach Chart')
                        worksheet.insert_image('B2', chart_path)
                        
                    # Создаем сводную таблицу
                    summary = pd.DataFrame({
                        'Всего постов': [len(df)],
                        'Средний охват': [df['total_reach'].mean() if 'total_reach' in df.columns else 0],
                        'Средняя вовлеченность': [df['total_engagement_rate'].mean() if 'total_engagement_rate' in df.columns else 0],
                        'Период': [f"{df['published_at'].min().strftime('%d.%m.%Y')} - {df['published_at'].max().strftime('%d.%m.%Y')}" if 'published_at' in df.columns and not df['published_at'].empty else 'Нет данных']
                    })
                    
                    # Добавляем сводку
                    summary.to_excel(writer, sheet_name='Summary', index=False)
                
                return report_path
        except Exception as e:
            logger.error(f"Ошибка при генерации отчета: {e}")
            logger.error(traceback.format_exc())
            return None
