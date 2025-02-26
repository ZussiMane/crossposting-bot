# modules/settings.py
import os
import json
from pathlib import Path

class Settings:
    def __init__(self):
        # Базовые пути
        self.BASE_DIR = Path(__file__).parent.parent
        self.CONFIG_FILE = self.BASE_DIR / 'config.json'
        
        # Загрузка конфигурации из файла, если он существует
        self.config = self._load_config()
        
        # База данных
        self.DATABASE_URI = self.config.get('DATABASE_URI', 'sqlite:///crossposting.db')
        
        # Пути для сохранения файлов
        self.MEDIA_DIR = self.BASE_DIR / 'media'
        self.DOWNLOADS_DIR = self.BASE_DIR / 'downloads'
        self.LOGS_DIR = self.BASE_DIR / 'logs'
        
        # Создание необходимых директорий
        os.makedirs(self.MEDIA_DIR, exist_ok=True)
        os.makedirs(self.DOWNLOADS_DIR, exist_ok=True)
        os.makedirs(self.LOGS_DIR, exist_ok=True)
        
        # Настройки для размеров медиафайлов
        self.MAX_IMAGE_SIZE = self.config.get('MAX_IMAGE_SIZE', (1920, 1080))
        self.MAX_VIDEO_SIZE = self.config.get('MAX_VIDEO_SIZE', (1280, 720))
        self.MAX_FILE_SIZE = self.config.get('MAX_FILE_SIZE', 50 * 1024 * 1024)  # 50 MB
        
        # Настройки для водяных знаков
        self.WATERMARK_PATH = self.config.get('WATERMARK_PATH', self.BASE_DIR / 'media' / 'watermark.png')
        self.WATERMARK_OPACITY = self.config.get('WATERMARK_OPACITY', 0.7)
        
        # Таймауты и ограничения
        self.API_TIMEOUT = self.config.get('API_TIMEOUT', 30)
        self.RATE_LIMIT = self.config.get('RATE_LIMIT', 10)
        
        # Настройки аналитики
        self.ANALYTICS_INTERVAL = self.config.get('ANALYTICS_INTERVAL', 3600)  # Интервал обновления в секундах
        
    def _load_config(self):
        """Загрузка конфигурации из файла"""
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Ошибка загрузки конфигурации: {e}")
                return {}
        return {}
    
    def save_config(self, config):
        """Сохранение конфигурации в файл"""
        try:
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Ошибка сохранения конфигурации: {e}")
            return False
