# modules/telegram_module.py
import os
import logging
import asyncio
from typing import List, Dict, Any, Optional, Union
from telethon import TelegramClient
from telethon.tl.types import InputMediaPhoto, InputMediaDocument, InputMediaGeoPoint
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeAnimated
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.functions.channels import GetFullChannelRequest

logger = logging.getLogger(__name__)

class TelegramManager:
    """Класс для работы с Telegram API через Telethon"""
    
    def __init__(self, api_id: str, api_hash: str, session_name: str = 'crosspost_bot'):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client = None
    
    async def start(self):
        """Запускает клиент Telegram"""
        if not self.client:
            try:
                self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
                await self.client.start()
                logger.info("Клиент Telegram успешно запущен")
                return True
            except Exception as e:
                logger.error(f"Ошибка запуска клиента Telegram: {e}")
                return False
        return True
    
    async def stop(self):
        """Останавливает клиент Telegram"""
        if self.client:
            try:
                await self.client.disconnect()
                self.client = None
                logger.info("Клиент Telegram остановлен")
                return True
            except Exception as e:
                logger.error(f"Ошибка остановки клиента Telegram: {e}")
                return False
        return True
    
    async def get_client(self) -> TelegramClient:
        """Возвращает клиент Telegram, запуская его при необходимости"""
        if not self.client:
            await self.start()
        return self.client
    
    async def get_me(self) -> Dict[str, Any]:
        """Получает информацию о текущем пользователе"""
        client = await self.get_client()
        try:
            me = await client.get_me()
            return {
                'id': me.id,
                'first_name': me.first_name,
                'last_name': me.last_name,
                'username': me.username,
                'phone': me.phone
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации о пользователе: {e}")
            return {}
    
    async def get_dialogs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Получает список диалогов (чатов и каналов)"""
        client = await self.get_client()
        try:
            dialogs = []
            async for dialog in client.iter_dialogs(limit=limit):
                entity = dialog.entity
                
                dialog_info = {
                    'id': entity.id,
                    'title': getattr(entity, 'title', None) or f"{getattr(entity, 'first_name', '')} {getattr(entity, 'last_name', '')}".strip(),
                    'type': 'channel' if hasattr(entity, 'broadcast') and entity.broadcast else 
                           'group' if hasattr(entity, 'megagroup') and entity.megagroup else 
                           'user' if hasattr(entity, 'first_name') else 'unknown',
                    'username': getattr(entity, 'username', None)
                }
                
                dialogs.append(dialog_info)
            
            return dialogs
        except Exception as e:
            logger.error(f"Ошибка получения списка диалогов: {e}")
            return []
    
    async def get_channel_info(self, channel_id: Union[int, str]) -> Dict[str, Any]:
        """Получает информацию о канале"""
        client = await self.get_client()
        try:
            # Если передана строка (username канала), получаем его ID
            if isinstance(channel_id, str):
                entity = await client.get_entity(channel_id)
                channel_id = entity.id
            
            # Получаем полную информацию о канале
            channel = await client(GetFullChannelRequest(channel=channel_id))
            
            return {
                'id': channel.full_chat.id,
                'title': channel.chats[0].title,
                'username': getattr(channel.chats[0], 'username', None),
                'description': channel.full_chat.about,
                'members_count': channel.full_chat.participants_count,
                'photo': bool(channel.full_chat.chat_photo)
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации о канале: {e}")
            return {}
    
    async def send_message(self, chat_id: Union[int, str], text: str) -> int:
        """Отправляет текстовое сообщение"""
        client = await self.get_client()
        try:
            message = await client.send_message(chat_id, text, parse_mode='md')
            return message.id
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            raise
    
    async def send_photo(self, chat_id: Union[int, str], photo_path: str, caption: str = None) -> int:
        """Отправляет фото"""
        client = await self.get_client()
        try:
            message = await client.send_file(
                chat_id,
                photo_path,
                caption=caption,
                parse_mode='md'
            )
            return message.id
        except Exception as e:
            logger.error(f"Ошибка отправки фото: {e}")
            raise
    
    async def send_video(self, chat_id: Union[int, str], video_path: str, caption: str = None,
                       thumb: str = None, duration: int = None, width: int = None, 
                       height: int = None) -> int:
        """Отправляет видео"""
        client = await self.get_client()
        try:
            # Если указан путь к превью видео
            thumb_file = open(thumb, 'rb') if thumb and os.path.exists(thumb) else None
            
            # Создаем атрибуты видео
            attributes = []
            if duration or width or height:
                attributes.append(DocumentAttributeVideo(
                    duration=duration or 0,
                    w=width or 0,
                    h=height or 0
                ))
            
            message = await client.send_file(
                chat_id,
                video_path,
                caption=caption,
                thumb=thumb_file,
                attributes=attributes,
                parse_mode='md'
            )
            
            # Закрываем файл превью, если он был открыт
            if thumb_file:
                thumb_file.close()
            
            return message.id
        except Exception as e:
            logger.error(f"Ошибка отправки видео: {e}")
            raise
    
    async def send_document(self, chat_id: Union[int, str], document_path: str, 
                          caption: str = None, thumb: str = None) -> int:
        """Отправляет документ (файл)"""
        client = await self.get_client()
        try:
            # Если указан путь к превью документа
            thumb_file = open(thumb, 'rb') if thumb and os.path.exists(thumb) else None
            
            message = await client.send_file(
                chat_id,
                document_path,
                caption=caption,
                thumb=thumb_file,
                parse_mode='md',
                force_document=True
            )
            
            # Закрываем файл превью, если он был открыт
            if thumb_file:
                thumb_file.close()
            
            return message.id
        except Exception as e:
            logger.error(f"Ошибка отправки документа: {e}")
            raise
    
    async def send_animation(self, chat_id: Union[int, str], animation_path: str,
                           caption: str = None, thumb: str = None) -> int:
        """Отправляет анимацию (GIF)"""
        client = await self.get_client()
        try:
            # Если указан путь к превью анимации
            thumb_file = open(thumb, 'rb') if thumb and os.path.exists(thumb) else None
            
            # Создаем атрибуты анимации
            attributes = [DocumentAttributeAnimated()]
            
            message = await client.send_file(
                chat_id,
                animation_path,
                caption=caption,
                thumb=thumb_file,
                attributes=attributes,
                parse_mode='md'
            )
            
            # Закрываем файл превью, если он был открыт
            if thumb_file:
                thumb_file.close()
            
            return message.id
        except Exception as e:
            logger.error(f"Ошибка отправки анимации: {e}")
            raise
    
    async def get_message_stats(self, chat_id: Union[int, str], message_id: int) -> Dict[str, Any]:
        """Получает статистику сообщения (количество просмотров, репостов и т.д.)"""
        client = await self.get_client()
        try:
            # Получаем сообщение
            message = await client.get_messages(chat_id, ids=message_id)
            
            if not message:
                logger.warning(f"Сообщение с ID {message_id} не найдено")
                return {}
            
            # Собираем статистику
            stats = {
                'views': getattr(message, 'views', 0),
                'forwards': getattr(message, 'forwards', 0),
                'replies': getattr(message, 'replies', 0) if hasattr(message, 'replies') else 0,
                'reactions': len(message.reactions.results) if hasattr(message, 'reactions') and message.reactions else 0
            }
            
            return stats
        except Exception as e:
            logger.error(f"Ошибка получения статистики сообщения: {e}")
            return {}
    
    async def publish_post(self, text: str, media_files: List[Dict[str, Any]], 
                         chat_ids: List[Union[int, str]] = None) -> Dict[str, List[int]]:
        """Публикует пост в один или несколько чатов/каналов"""
        # Если не указаны ID чатов, пытаемся получить список каналов пользователя
        if not chat_ids:
            dialogs = await self.get_dialogs()
            chat_ids = [dialog['id'] for dialog in dialogs if dialog['type'] == 'channel']
        
        # Если нет медиафайлов, отправляем только текст
        if not media_files:
            results = {}
            for chat_id in chat_ids:
                try:
                    message_id = await self.send_message(chat_id, text)
                    if chat_id not in results:
                        results[chat_id] = []
                    results[chat_id].append(message_id)
                except Exception as e:
                    logger.error(f"Ошибка публикации текста в чат {chat_id}: {e}")
            return results
        
        # Если есть медиафайлы, отправляем их с текстом
        results = {}
        for chat_id in chat_ids:
            sent_message_ids = []
            
            # Отправляем каждый медиафайл отдельно
            # В первом сообщении отправляем текст как подпись
            is_first = True
            
            for media_file in media_files:
                file_type = media_file.get('file_type')
                file_path = media_file.get('file_path')
                
                if not file_path or not os.path.exists(file_path):
                    logger.warning(f"Файл не найден: {file_path}")
                    continue
                
                try:
                    # Подпись только для первого медиафайла
                    caption = text if is_first else None
                    
                    if file_type == 'photo':
                        message_id = await self.send_photo(chat_id, file_path, caption)
                    elif file_type == 'video':
                        message_id = await self.send_video(chat_id, file_path, caption)
                    elif file_type == 'animation':
                        message_id = await self.send_animation(chat_id, file_path, caption)
                    elif file_type == 'document':
                        message_id = await self.send_document(chat_id, file_path, caption)
                    else:
                        logger.warning(f"Неизвестный тип файла: {file_type}")
                        continue
                    
                    sent_message_ids.append(message_id)
                    is_first = False
                except Exception as e:
                    logger.error(f"Ошибка публикации медиафайла {file_path} в чат {chat_id}: {e}")
            
            # Если не удалось отправить ни одного медиафайла, пытаемся отправить текст
            if not sent_message_ids and text:
                try:
                    message_id = await self.send_message(chat_id, text)
                    sent_message_ids.append(message_id)
                except Exception as e:
                    logger.error(f"Ошибка публикации текста в чат {chat_id}: {e}")
            
            if sent_message_ids:
                results[chat_id] = sent_message_ids
        
        return results
