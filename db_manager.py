# modules/db_manager.py
import json
import logging
import asyncio
from datetime import datetime
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, JSON, Boolean, ForeignKey, Text
from sqlalchemy.sql import select, update, delete, insert
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, database_uri):
        # Преобразование URI для асинхронности, если необходимо
        if database_uri.startswith('sqlite:///'):
            self.async_uri = database_uri.replace('sqlite:///', 'sqlite+aiosqlite:///')
        else:
            self.async_uri = database_uri
        
        # Создание асинхронного движка
        self.engine = create_async_engine(self.async_uri, echo=False)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        
        # Инициализация метаданных и таблиц
        self.metadata = MetaData()
        self._init_tables()
    
    def _init_tables(self):
        """Инициализация структуры таблиц"""
        # Таблица пользователей
        self.users = Table(
            'users',
            self.metadata,
            Column('id', Integer, primary_key=True),
            Column('telegram_id', Integer, unique=True, nullable=False),
            Column('username', String(100)),
            Column('full_name', String(200)),
            Column('is_admin', Boolean, default=False),
            Column('settings', JSON, default={}),
            Column('created_at', DateTime, default=datetime.utcnow),
            Column('last_activity', DateTime, default=datetime.utcnow)
        )
        
        # Таблица постов
        self.posts = Table(
            'posts',
            self.metadata,
            Column('id', Integer, primary_key=True),
            Column('user_id', Integer, ForeignKey('users.id')),
            Column('text', Text),
            Column('media_files', JSON, default=[]),
            Column('platforms', JSON, default=[]),
            Column('schedule_time', DateTime, nullable=True),
            Column('status', String(20), default='draft'),  # draft, scheduled, publishing, published, failed
            Column('results', JSON, default={}),
            Column('created_at', DateTime, default=datetime.utcnow),
            Column('published_at', DateTime, nullable=True),
            Column('updated_at', DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        )
        
        # Таблица статистики
        self.statistics = Table(
            'statistics',
            self.metadata,
            Column('id', Integer, primary_key=True),
            Column('post_id', Integer, ForeignKey('posts.id')),
            Column('platform', String(20)),
            Column('metrics', JSON, default={}),
            Column('collected_at', DateTime, default=datetime.utcnow)
        )
        
        # Таблица активностей пользователей
        self.user_activities = Table(
            'user_activities',
            self.metadata,
            Column('id', Integer, primary_key=True),
            Column('user_id', Integer, ForeignKey('users.id')),
            Column('action', String(100)),
            Column('details', JSON, default={}),
            Column('created_at', DateTime, default=datetime.utcnow)
        )
    
    async def init_db(self):
        """Инициализация базы данных и создание таблиц"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(self.metadata.create_all)
            logger.info("База данных инициализирована успешно")
            return True
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            return False
    
    async def get_session(self):
        """Получение сессии базы данных"""
        return self.async_session()
    
    # Методы для работы с пользователями
    async def register_user(self, user_id, username=None, full_name=None, is_admin=False):
        """Регистрация нового пользователя"""
        try:
            async with self.async_session() as session:
                # Проверяем, существует ли пользователь
                query = select(self.users).where(self.users.c.telegram_id == user_id)
                result = await session.execute(query)
                user = result.fetchone()
                
                if user:
                    # Пользователь уже существует, обновляем информацию
                    query = update(self.users).where(
                        self.users.c.telegram_id == user_id
                    ).values(
                        username=username,
                        full_name=full_name,
                        last_activity=datetime.utcnow()
                    )
                    await session.execute(query)
                else:
                    # Создаем нового пользователя
                    query = insert(self.users).values(
                        telegram_id=user_id,
                        username=username,
                        full_name=full_name,
                        is_admin=is_admin,
                        settings={},
                        created_at=datetime.utcnow(),
                        last_activity=datetime.utcnow()
                    )
                    await session.execute(query)
                
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка регистрации пользователя: {e}")
            return False
    
    async def user_exists(self, user_id):
        """Проверка существования пользователя"""
        try:
            async with self.async_session() as session:
                query = select(self.users).where(self.users.c.telegram_id == user_id)
                result = await session.execute(query)
                return result.fetchone() is not None
        except Exception as e:
            logger.error(f"Ошибка проверки существования пользователя: {e}")
            return False
    
    async def get_user_by_telegram_id(self, telegram_id):
        """Получение пользователя по ID Telegram"""
        try:
            async with self.async_session() as session:
                query = select(self.users).where(self.users.c.telegram_id == telegram_id)
                result = await session.execute(query)
                user = result.fetchone()
                return dict(user) if user else None
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {e}")
            return None
    
    async def get_all_users(self, limit=100, offset=0):
        """Получение списка всех пользователей"""
        try:
            async with self.async_session() as session:
                query = select(self.users).limit(limit).offset(offset)
                result = await session.execute(query)
                users = result.fetchall()
                return [dict(user) for user in users]
        except Exception as e:
            logger.error(f"Ошибка получения списка пользователей: {e}")
            return []
    
    # Методы для работы с постами
    async def create_post(self, user_id, text=None, media_files=None, platforms=None, schedule_time=None, status='draft'):
        """Создание нового поста"""
        try:
            # Получаем ID пользователя из базы данных по Telegram ID
            user = await self.get_user_by_telegram_id(user_id)
            if not user:
                logger.error(f"Пользователь с ID {user_id} не найден")
                return None
            
            # Подготовка данных для вставки
            post_data = {
                'user_id': user['id'],
                'text': text,
                'media_files': media_files or [],
                'platforms': platforms or [],
                'status': status,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            # Добавляем время публикации, если оно указано
            if schedule_time:
                post_data['schedule_time'] = schedule_time
                post_data['status'] = 'scheduled'
            
            async with self.async_session() as session:
                query = insert(self.posts).values(**post_data)
                result = await session.execute(query)
                post_id = result.inserted_primary_key[0]
                await session.commit()
                
                # Логирование действия пользователя
                await self.log_user_activity(
                    user_id=user['id'],
                    action=f"post_created_{status}",
                    details={"post_id": post_id}
                )
                
                return post_id
        except Exception as e:
            logger.error(f"Ошибка создания поста: {e}")
            return None
    
    async def update_post(self, post_id, **kwargs):
        """Обновление информации о посте"""
        try:
            async with self.async_session() as session:
                # Добавляем время обновления
                kwargs['updated_at'] = datetime.utcnow()
                
                # Если статус меняется на 'published', добавляем время публикации
                if kwargs.get('status') == 'published' and 'published_at' not in kwargs:
                    kwargs['published_at'] = datetime.utcnow()
                
                query = update(self.posts).where(self.posts.c.id == post_id).values(**kwargs)
                await session.execute(query)
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления поста: {e}")
            return False
    
    async def get_post_by_id(self, post_id):
        """Получение поста по ID"""
        try:
            async with self.async_session() as session:
                query = select(self.posts).where(self.posts.c.id == post_id)
                result = await session.execute(query)
                post = result.fetchone()
                return dict(post) if post else None
        except Exception as e:
            logger.error(f"Ошибка получения поста: {e}")
            return None
    
    async def get_posts_by_status(self, user_id, status, limit=10, offset=0):
        """Получение постов по статусу"""
        try:
            # Получаем ID пользователя из базы данных по Telegram ID
            user = await self.get_user_by_telegram_id(user_id)
            if not user:
                logger.error(f"Пользователь с ID {user_id} не найден")
                return []
            
            async with self.async_session() as session:
                query = select(self.posts).where(
                    (self.posts.c.user_id == user['id']) & 
                    (self.posts.c.status == status)
                ).order_by(self.posts.c.created_at.desc()).limit(limit).offset(offset)
                
                result = await session.execute(query)
                posts = result.fetchall()
                return [dict(post) for post in posts]
        except Exception as e:
            logger.error(f"Ошибка получения постов: {e}")
            return []
    
    async def delete_post(self, post_id):
        """Удаление поста"""
        try:
            async with self.async_session() as session:
                # Получаем информацию о посте для логирования
                query = select(self.posts).where(self.posts.c.id == post_id)
                result = await session.execute(query)
                post = result.fetchone()
                
                if post:
                    # Удаляем связанную статистику
                    delete_stats = delete(self.statistics).where(self.statistics.c.post_id == post_id)
                    await session.execute(delete_stats)
                    
                    # Удаляем пост
                    delete_post = delete(self.posts).where(self.posts.c.id == post_id)
                    await session.execute(delete_post)
                    
                    # Логирование действия
                    await self.log_user_activity(
                        user_id=post['user_id'],
                        action="post_deleted",
                        details={"post_id": post_id}
                    )
                    
                    await session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Ошибка удаления поста: {e}")
            return False
    
    # Методы для работы со статистикой
    async def add_statistics(self, post_id, platform, metrics):
        """Добавление статистики для поста"""
        try:
            async with self.async_session() as session:
                query = insert(self.statistics).values(
                    post_id=post_id,
                    platform=platform,
                    metrics=metrics,
                    collected_at=datetime.utcnow()
                )
                await session.execute(query)
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка добавления статистики: {e}")
            return False
    
    async def get_post_statistics(self, post_id):
        """Получение статистики для конкретного поста"""
        try:
            async with self.async_session() as session:
                query = select(self.statistics).where(self.statistics.c.post_id == post_id)
                result = await session.execute(query)
                stats = result.fetchall()
                
                # Группировка статистики по платформам
                statistics = {}
                for stat in stats:
                    stat_dict = dict(stat)
                    platform = stat_dict['platform']
                    if platform not in statistics:
                        statistics[platform] = []
                    statistics[platform].append(stat_dict['metrics'])
                
                return statistics
        except Exception as e:
            logger.error(f"Ошибка получения статистики поста: {e}")
            return {}
    
    # Логирование действий пользователей
    async def log_user_activity(self, user_id, action, details=None):
        """Логирование действий пользователя"""
        try:
            async with self.async_session() as session:
                query = insert(self.user_activities).values(
                    user_id=user_id,
                    action=action,
                    details=details or {},
                    created_at=datetime.utcnow()
                )
                await session.execute(query)
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка логирования действия пользователя: {e}")
            return False
    
    async def get_user_activities(self, user_id, limit=50, offset=0):
        """Получение истории действий пользователя"""
        try:
            # Получаем ID пользователя из базы данных по Telegram ID, если передан Telegram ID
            if isinstance(user_id, int) and user_id > 1000000000:  # Предполагаем, что это Telegram ID
                user = await self.get_user_by_telegram_id(user_id)
                if not user:
                    logger.error(f"Пользователь с Telegram ID {user_id} не найден")
                    return []
                user_id = user['id']
            
            async with self.async_session() as session:
                query = select(self.user_activities).where(
                    self.user_activities.c.user_id == user_id
                ).order_by(self.user_activities.c.created_at.desc()).limit(limit).offset(offset)
                
                result = await session.execute(query)
                activities = result.fetchall()
                return [dict(activity) for activity in activities]
        except Exception as e:
            logger.error(f"Ошибка получения активности пользователя: {e}")
            return []
