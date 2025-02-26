# modules/user_manager.py
import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from sqlalchemy import select, update, and_, or_

logger = logging.getLogger(__name__)

class UserManager:
    """Класс для управления пользователями и их настройками"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
    
    async def register_user(self, user_id: int, username: str = None, full_name: str = None, is_admin: bool = False) -> bool:
        """
        Регистрирует нового пользователя
        
        Args:
            user_id: ID пользователя в Telegram
            username: Имя пользователя
            full_name: Полное имя пользователя
            is_admin: Флаг администратора
            
        Returns:
            True, если регистрация прошла успешно, иначе False
        """
        return await self.db_manager.register_user(user_id, username, full_name, is_admin)
    
    async def user_exists(self, user_id: int) -> bool:
        """
        Проверяет, существует ли пользователь
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            True, если пользователь существует, иначе False
        """
        return await self.db_manager.user_exists(user_id)
    
    async def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        """
        Получает настройки пользователя
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            Словарь с настройками пользователя
        """
        try:
            # Получаем информацию о пользователе
            user = await self.db_manager.get_user_by_telegram_id(user_id)
            
            if not user:
                logger.error(f"Пользователь с ID {user_id} не найден")
                return {}
            
            # Возвращаем настройки пользователя
            return user.get('settings', {})
        except Exception as e:
            logger.error(f"Ошибка при получении настроек пользователя {user_id}: {e}")
            return {}
    
    async def update_user_settings(self, user_id: int, settings: Dict[str, Any]) -> bool:
        """
        Обновляет настройки пользователя
        
        Args:
            user_id: ID пользователя в Telegram
            settings: Новые настройки
            
        Returns:
            True, если обновление прошло успешно, иначе False
        """
        try:
            # Получаем информацию о пользователе
            user = await self.db_manager.get_user_by_telegram_id(user_id)
            
            if not user:
                logger.error(f"Пользователь с ID {user_id} не найден")
                return False
            
            # Обновляем настройки в базе данных
            async with self.db_manager.async_session() as session:
                query = update(self.db_manager.users).where(
                    self.db_manager.users.c.id == user['id']
                ).values(
                    settings=settings,
                    last_activity=datetime.utcnow()
                )
                
                await session.execute(query)
                await session.commit()
                
                # Логируем действие
                await self.db_manager.log_user_activity(
                    user_id=user['id'],
                    action="settings_updated",
                    details={"settings": settings}
                )
                
                return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении настроек пользователя {user_id}: {e}")
            return False
    async def get_connected_accounts(self, user_id: int) -> Dict[str, Any]:
        """
        Получает список подключенных аккаунтов пользователя
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            Словарь с информацией о подключенных аккаунтах
        """
        try:
            # Получаем настройки пользователя
            user_settings = await self.get_user_settings(user_id)
            
            # Возвращаем информацию о подключенных аккаунтах
            return user_settings.get('connected_accounts', {})
        except Exception as e:
            logger.error(f"Ошибка при получении подключенных аккаунтов пользователя {user_id}: {e}")
            return {}
    
    async def connect_account(self, user_id: int, platform: str, account_data: Dict[str, Any]) -> bool:
        """
        Подключает аккаунт к пользователю
        
        Args:
            user_id: ID пользователя в Telegram
            platform: Название платформы (vk, telegram, website)
            account_data: Данные аккаунта
            
        Returns:
            True, если подключение прошло успешно, иначе False
        """
        try:
            # Получаем настройки пользователя
            user_settings = await self.get_user_settings(user_id)
            
            # Инициализируем структуру, если она отсутствует
            if 'connected_accounts' not in user_settings:
                user_settings['connected_accounts'] = {}
            
            # Добавляем информацию об аккаунте
            user_settings['connected_accounts'][platform] = account_data
            
            # Обновляем настройки пользователя
            return await self.update_user_settings(user_id, user_settings)
        except Exception as e:
            logger.error(f"Ошибка при подключении аккаунта {platform} для пользователя {user_id}: {e}")
            return False
    
    async def disconnect_account(self, user_id: int, platform: str) -> bool:
        """
        Отключает аккаунт от пользователя
        
        Args:
            user_id: ID пользователя в Telegram
            platform: Название платформы (vk, telegram, website)
            
        Returns:
            True, если отключение прошло успешно, иначе False
        """
        try:
            # Получаем настройки пользователя
            user_settings = await self.get_user_settings(user_id)
            
            # Проверяем, есть ли подключенные аккаунты
            if 'connected_accounts' not in user_settings:
                return True
            
            # Удаляем информацию об аккаунте
            if platform in user_settings['connected_accounts']:
                del user_settings['connected_accounts'][platform]
            
            # Обновляем настройки пользователя
            return await self.update_user_settings(user_id, user_settings)
        except Exception as e:
            logger.error(f"Ошибка при отключении аккаунта {platform} для пользователя {user_id}: {e}")
            return False
    
    async def check_admin_rights(self, user_id: int) -> bool:
        """
        Проверяет, имеет ли пользователь права администратора
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            True, если пользователь является администратором, иначе False
        """
        try:
            # Получаем информацию о пользователе
            user = await self.db_manager.get_user_by_telegram_id(user_id)
            
            if not user:
                logger.error(f"Пользователь с ID {user_id} не найден")
                return False
            
            # Проверяем флаг администратора
            return user.get('is_admin', False)
        except Exception as e:
            logger.error(f"Ошибка при проверке прав администратора для пользователя {user_id}: {e}")
            return False
    
    async def set_admin_rights(self, user_id: int, is_admin: bool) -> bool:
        """
        Устанавливает права администратора для пользователя
        
        Args:
            user_id: ID пользователя в Telegram
            is_admin: Флаг администратора
            
        Returns:
            True, если обновление прошло успешно, иначе False
        """
        try:
            # Получаем информацию о пользователе
            user = await self.db_manager.get_user_by_telegram_id(user_id)
            
            if not user:
                logger.error(f"Пользователь с ID {user_id} не найден")
                return False
            
            # Обновляем права администратора в базе данных
            async with self.db_manager.async_session() as session:
                query = update(self.db_manager.users).where(
                    self.db_manager.users.c.id == user['id']
                ).values(
                    is_admin=is_admin,
                    last_activity=datetime.utcnow()
                )
                
                await session.execute(query)
                await session.commit()
                
                # Логируем действие
                await self.db_manager.log_user_activity(
                    user_id=user['id'],
                    action="admin_rights_updated",
                    details={"is_admin": is_admin}
                )
                
                return True
        except Exception as e:
            logger.error(f"Ошибка при установке прав администратора для пользователя {user_id}: {e}")
            return False
    
    async def get_user_activity(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Получает историю активности пользователя
        
        Args:
            user_id: ID пользователя в Telegram
            limit: Максимальное количество записей
            
        Returns:
            Список с историей активности
        """
        try:
            return await self.db_manager.get_user_activities(user_id, limit)
        except Exception as e:
            logger.error(f"Ошибка при получении истории активности пользователя {user_id}: {e}")
            return []
    
    async def update_last_activity(self, user_id: int) -> bool:
        """
        Обновляет время последней активности пользователя
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            True, если обновление прошло успешно, иначе False
        """
        try:
            # Получаем информацию о пользователе
            user = await self.db_manager.get_user_by_telegram_id(user_id)
            
            if not user:
                logger.error(f"Пользователь с ID {user_id} не найден")
                return False
            
            # Обновляем время последней активности в базе данных
            async with self.db_manager.async_session() as session:
                query = update(self.db_manager.users).where(
                    self.db_manager.users.c.id == user['id']
                ).values(
                    last_activity=datetime.utcnow()
                )
                
                await session.execute(query)
                await session.commit()
                
                return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении времени последней активности пользователя {user_id}: {e}")
            return False
    
    async def get_all_users(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Получает список всех пользователей
        
        Args:
            limit: Максимальное количество записей
            offset: Смещение
            
        Returns:
            Список пользователей
        """
        try:
            return await self.db_manager.get_all_users(limit, offset)
        except Exception as e:
            logger.error(f"Ошибка при получении списка пользователей: {e}")
            return []
    
    async def delete_user(self, user_id: int) -> bool:
        """
        Удаляет пользователя
        
        Args:
            user_id: ID пользователя в Telegram
            
        Returns:
            True, если удаление прошло успешно, иначе False
        """
        try:
            # Получаем информацию о пользователе
            user = await self.db_manager.get_user_by_telegram_id(user_id)
            
            if not user:
                logger.error(f"Пользователь с ID {user_id} не найден")
                return False
            
            # Удаляем пользователя из базы данных
            async with self.db_manager.async_session() as session:
                # Удаляем связанные записи
                from sqlalchemy import delete
                
                # Удаляем записи активности
                query = delete(self.db_manager.user_activities).where(
                    self.db_manager.user_activities.c.user_id == user['id']
                )
                await session.execute(query)
                
                # Удаляем записи постов
                query = delete(self.db_manager.posts).where(
                    self.db_manager.posts.c.user_id == user['id']
                )
                await session.execute(query)
                
                # Удаляем пользователя
                query = delete(self.db_manager.users).where(
                    self.db_manager.users.c.id == user['id']
                )
                await session.execute(query)
                
                await session.commit()
                
                return True
        except Exception as e:
            logger.error(f"Ошибка при удалении пользователя {user_id}: {e}")
            return False
