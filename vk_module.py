# modules/vk_module.py
import os
import logging
import aiohttp
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

class VKManager:
    """Класс для работы с API ВКонтакте"""
    
    def __init__(self, token: str = None, api_version: str = '5.131'):
        self.token = token
        self.api_version = api_version
        self.api_url = 'https://api.vk.com/method/'
        self.upload_url = 'https://api.vk.com/upload'
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Возвращает сессию aiohttp, создавая новую при необходимости"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close_session(self):
        """Закрывает сессию aiohttp"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def _make_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Выполняет запрос к API ВКонтакте"""
        session = await self._get_session()
        url = f"{self.api_url}{method}"
        
        # Добавляем токен и версию API к параметрам
        params['access_token'] = self.token
        params['v'] = self.api_version
        
        try:
            async with session.post(url, data=params) as response:
                result = await response.json()
                
                if 'error' in result:
                    logger.error(f"ВКонтакте API ошибка: {result['error']}")
                    raise Exception(f"VK API Error: {result['error'].get('error_msg', 'Unknown error')}")
                
                return result.get('response', {})
        except Exception as e:
            logger.error(f"Ошибка запроса к ВКонтакте API: {e}")
            raise
    
    async def get_user_info(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Получает информацию о пользователе"""
        params = {'fields': 'photo_max,screen_name'}
        if user_id:
            params['user_ids'] = str(user_id)
        
        result = await self._make_request('users.get', params)
        return result[0] if result else {}
    
    async def get_groups(self) -> List[Dict[str, Any]]:
        """Получает список групп пользователя, где он является администратором"""
        params = {
            'filter': 'admin',
            'extended': 1,
            'fields': 'name,screen_name,photo_200'
        }
        
        result = await self._make_request('groups.get', params)
        return result.get('items', [])
    
    async def get_upload_server(self, upload_type: str, peer_id: Optional[int] = None) -> str:
        """Получает URL сервера для загрузки медиафайлов"""
        params = {}
        method = ''
        
        if upload_type == 'photo':
            method = 'photos.getWallUploadServer'
        elif upload_type == 'video':
            method = 'video.save'
        elif upload_type == 'doc':
            method = 'docs.getWallUploadServer'
        
        if peer_id:
            params['peer_id'] = peer_id
        
        result = await self._make_request(method, params)
        return result.get('upload_url', '')
    
    async def upload_file(self, upload_url: str, file_path: str, file_type: str) -> Dict[str, Any]:
        """Загружает файл на сервер ВКонтакте"""
        session = await self._get_session()
        
        try:
            with open(file_path, 'rb') as file:
                if file_type == 'photo':
                    form_data = aiohttp.FormData()
                    form_data.add_field('photo', file, filename=os.path.basename(file_path))
                    
                    async with session.post(upload_url, data=form_data) as response:
                        return await response.json()
                
                elif file_type == 'video':
                    form_data = aiohttp.FormData()
                    form_data.add_field('video_file', file, filename=os.path.basename(file_path))
                    
                    async with session.post(upload_url, data=form_data) as response:
                        return await response.json()
                
                elif file_type == 'doc':
                    form_data = aiohttp.FormData()
                    form_data.add_field('file', file, filename=os.path.basename(file_path))
                    
                    async with session.post(upload_url, data=form_data) as response:
                        return await response.json()
        except Exception as e:
            logger.error(f"Ошибка загрузки файла в ВКонтакте: {e}")
            raise
    
    async def save_wall_photo(self, server: str, photo: str, hash_value: str) -> Dict[str, Any]:
        """Сохраняет фото после загрузки на сервер"""
        params = {
            'server': server,
            'photo': photo,
            'hash': hash_value
        }
        
        result = await self._make_request('photos.saveWallPhoto', params)
        return result[0] if result else {}
    
    async def save_document(self, file: str, title: str = None) -> Dict[str, Any]:
        """Сохраняет документ после загрузки на сервер"""
        params = {
            'file': file
        }
        
        if title:
            params['title'] = title
        
        result = await self._make_request('docs.save', params)
        return result.get('doc', {})
    
    async def upload_photo(self, file_path: str) -> Dict[str, Any]:
        """Полный процесс загрузки фото"""
        # Получаем URL для загрузки
        upload_url = await self.get_upload_server('photo')
        
        # Загружаем файл
        upload_result = await self.upload_file(upload_url, file_path, 'photo')
        
        # Сохраняем фото
        photo_info = await self.save_wall_photo(
            server=upload_result.get('server', ''),
            photo=upload_result.get('photo', ''),
            hash_value=upload_result.get('hash', '')
        )
        
        return photo_info
    
    async def upload_document(self, file_path: str, title: str = None) -> Dict[str, Any]:
        """Полный процесс загрузки документа"""
        # Получаем URL для загрузки
        upload_url = await self.get_upload_server('doc')
        
        # Загружаем файл
        upload_result = await self.upload_file(upload_url, file_path, 'doc')
        
        # Сохраняем документ
        doc_info = await self.save_document(
            file=upload_result.get('file', ''),
            title=title or os.path.basename(file_path)
        )
        
        return doc_info
    
    async def upload_video(self, file_path: str, title: str = None, description: str = None) -> Dict[str, Any]:
        """Полный процесс загрузки видео"""
        # Параметры для запроса save
        params = {}
        if title:
            params['name'] = title
        if description:
            params['description'] = description
        
        # Получаем данные для загрузки
        upload_data = await self._make_request('video.save', params)
        upload_url = upload_data.get('upload_url', '')
        
        # Загружаем файл
        session = await self._get_session()
        
        try:
            with open(file_path, 'rb') as file:
                form_data = aiohttp.FormData()
                form_data.add_field('video_file', file, filename=os.path.basename(file_path))
                
                async with session.post(upload_url, data=form_data) as response:
                    response_text = await response.text()
                    # ВКонтакте может вернуть HTML или JSON при загрузке видео
                    # Если загрузка прошла успешно, мы получаем просто 'ok'
                    if response_text.strip() == 'ok':
                        return upload_data
                    else:
                        logger.error(f"Ошибка загрузки видео в ВКонтакте: {response_text}")
                        raise Exception("Error uploading video to VK")
        except Exception as e:
            logger.error(f"Ошибка загрузки видео в ВКонтакте: {e}")
            raise
    
    async def publish_post(self, text: str, media_files: List[Dict[str, Any]], 
                          owner_id: Optional[int] = None) -> int:
        """Публикует пост на стене ВКонтакте"""
        # Подготовка медиа-вложений
        attachments = []
        
        for media_file in media_files:
            file_type = media_file.get('file_type')
            file_path = media_file.get('file_path')
            
            if not file_path or not os.path.exists(file_path):
                logger.warning(f"Файл не найден: {file_path}")
                continue
            
            try:
                if file_type == 'photo':
                    photo_info = await self.upload_photo(file_path)
                    attachments.append(f"photo{photo_info.get('owner_id')}_{photo_info.get('id')}")
                
                elif file_type == 'video':
                    video_info = await self.upload_video(file_path)
                    attachments.append(f"video{video_info.get('owner_id')}_{video_info.get('video_id')}")
                
                elif file_type in ['document', 'animation']:
                    doc_info = await self.upload_document(file_path)
                    attachments.append(f"doc{doc_info.get('owner_id')}_{doc_info.get('id')}")
            except Exception as e:
                logger.error(f"Ошибка при подготовке вложения {file_path}: {e}")
                continue
        
        # Параметры для публикации
        params = {
            'message': text,
            'attachments': ','.join(attachments)
        }
        
        if owner_id:
            params['owner_id'] = owner_id
        
        # Публикация поста
        result = await self._make_request('wall.post', params)
        return result.get('post_id', 0)
    
    async def get_post_stats(self, post_id: int, owner_id: Optional[int] = None) -> Dict[str, Any]:
        """Получает статистику поста"""
        params = {
            'posts': f"{owner_id or ''}_{post_id}"
        }
        
        result = await self._make_request('stats.getPostReach', params)
        return result[0] if result else {}
