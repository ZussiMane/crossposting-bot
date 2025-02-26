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
        """Останав
