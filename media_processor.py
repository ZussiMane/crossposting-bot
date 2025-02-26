# modules/media_processor.py
import os
import logging
import asyncio
import uuid
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path
import subprocess
import json

# Регистрируем поддержку форматов HEIF/HEIC
register_heif_opener()

logger = logging.getLogger(__name__)

class MediaProcessor:
    """Класс для обработки медиафайлов"""
    
    def __init__(self, output_dir: str = 'processed_media', watermark_path: str = None):
        self.output_dir = output_dir
        self.watermark_path = watermark_path
        
        # Создаем директорию для сохранения обработанных файлов
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def process_media(self, file_path: str, file_type: str) -> str:
        """
        Обрабатывает медиафайл в зависимости от его типа
        
        Args:
            file_path: Путь к файлу
            file_type: Тип файла (photo, video, animation, document)
            
        Returns:
            Путь к обработанному файлу
        """
        try:
            if file_type == 'photo':
                return await self.process_image(file_path)
            elif file_type == 'video':
                return await self.process_video(file_path)
            elif file_type == 'animation':
                return await self.process_animation(file_path)
            elif file_type == 'document':
                return await self.process_document(file_path)
            else:
                logger.warning(f"Неизвестный тип файла: {file_type}")
                return file_path
        except Exception as e:
            logger.error(f"Ошибка при обработке медиафайла {file_path}: {e}")
            return file_path
    
    async def process_image(self, image_path: str, resize: bool = True, 
                           optimize: bool = True, add_watermark: bool = False) -> str:
        """
        Обрабатывает изображение: изменяет размер, оптимизирует, добавляет водяной знак
        
        Args:
            image_path: Путь к исходному изображению
            resize: Нужно ли изменять размер
            optimize: Нужно ли оптимизировать
            add_watermark: Нужно ли добавлять водяной знак
            
        Returns:
            Путь к обработанному изображению
        """
        try:
            # Создаем уникальное имя файла
            file_name = os.path.basename(image_path)
            base_name, ext = os.path.splitext(file_name)
            
            # Для некоторых форматов изменяем расширение на .jpg
            if ext.lower() in ['.heic', '.heif', '.webp']:
                output_ext = '.jpg'
            else:
                output_ext = ext
            
            output_path = os.path.join(self.output_dir, f"{base_name}_{uuid.uuid4().hex[:8]}{output_ext}")
            
            # Открываем изображение
            img = Image.open(image_path)
            
            # Если изображение в формате RGBA (с прозрачностью), конвертируем в RGB
            if img.mode == 'RGBA':
                white_bg = Image.new('RGB', img.size, (255, 255, 255))
                white_bg.paste(img, mask=img.split()[3])  # Используем альфа-канал как маску
                img = white_bg
            
            # Изменяем размер, если нужно
            if resize:
                # Максимальные размеры для разных платформ
                max_width = 1920
                max_height = 1080
                
                # Получаем размеры изображения
                width, height = img.size
                
                # Проверяем, нужно ли изменять размер
                if width > max_width or height > max_height:
                    # Вычисляем новые размеры, сохраняя пропорции
                    if width > height:
                        new_width = max_width
                        new_height = int(height * (max_width / width))
                    else:
                        new_height = max_height
                        new_width = int(width * (max_height / height))
                    
                    # Изменяем размер
                    img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # Добавляем водяной знак, если нужно и есть путь к файлу
            if add_watermark and self.watermark_path and os.path.exists(self.watermark_path):
                watermark = Image.open(self.watermark_path)
                
                # Изменяем размер водяного знака относительно исходного изображения
                wm_width, wm_height = watermark.size
                img_width, img_height = img.size
                
                # Водяной знак должен быть не более 20% от исходного изображения
                max_wm_width = int(img_width * 0.2)
                max_wm_height = int(img_height * 0.2)
                
                if wm_width > max_wm_width or wm_height > max_wm_height:
                    # Вычисляем новые размеры, сохраняя пропорции
                    if wm_width > wm_height:
                        new_wm_width = max_wm_width
                        new_wm_height = int(wm_height * (max_wm_width / wm_width))
                    else:
                        new_wm_height = max_wm_height
                        new_wm_width = int(wm_width * (max_wm_height / wm_height))
                    
                    # Изменяем размер водяного знака
                    watermark = watermark.resize((new_wm_width, new_wm_height), Image.LANCZOS)
                
                # Вычисляем положение водяного знака (правый нижний угол)
                position = (img_width - new_wm_width - 10, img_height - new_wm_height - 10)
                
                # Если водяной знак имеет прозрачность (режим RGBA)
                if watermark.mode == 'RGBA':
                    # Создаем новый слой того же размера, что и исходное изображение
                    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
                    # Помещаем водяной знак на этот слой
                    layer.paste(watermark, position, watermark)
                    # Объединяем слои
                    img = Image.composite(layer, img.convert('RGBA'), layer)
                else:
                    # Если водяной знак не имеет прозрачности, просто размещаем его поверх изображения
                    img.paste(watermark, position)
            
            # Сохраняем результат
            if optimize:
                img.save(output_path, quality=85, optimize=True)
            else:
                img.save(output_path)
            
            return output_path
        except Exception as e:
            logger.error(f"Ошибка при обработке изображения {image_path}: {e}")
            return image_path
    
    async def process_video(self, video_path: str, resize: bool = True, 
                          create_preview: bool = True, add_watermark: bool = False) -> str:
        """
        Обрабатывает видео: изменяет размер, создает превью, добавляет водяной знак
        
        Args:
            video_path: Путь к исходному видео
            resize: Нужно ли изменять размер
            create_preview: Нужно ли создавать превью
            add_watermark: Нужно ли добавлять водяной знак
            
        Returns:
            Путь к обработанному видео
        """
        try:
            # Создаем уникальное имя файла
            file_name = os.path.basename(video_path)
            base_name, ext = os.path.splitext(file_name)
            
            output_path = os.path.join(self.output_dir, f"{base_name}_{uuid.uuid4().hex[:8]}{ext}")
            
            # Команда FFmpeg для обработки видео
            ffmpeg_cmd = ['ffmpeg', '-i', video_path]
            
            # Параметры для ffmpeg
            ffmpeg_params = []
            
            # Изменяем размер, если нужно
            if resize:
                # Максимальные размеры для разных платформ
                max_width = 1280
                max_height = 720
                
                ffmpeg_params.extend([
                    '-vf', f'scale=min({max_width},iw):min({max_height},ih):force_original_aspect_ratio=decrease'
                ])
            
            # Добавляем водяной знак, если нужно и есть путь к файлу
            if add_watermark and self.watermark_path and os.path.exists(self.watermark_path):
                overlay_filter = f"overlay=W-w-10:H-h-10"
                
                if resize:
                    # Если уже есть фильтр масштабирования, добавляем overlay через запятую
                    ffmpeg_params[-1] += f",movie={self.watermark_path}[watermark];[0][watermark]{overlay_filter}"
                else:
                    # Если фильтра нет, создаем новый
                    ffmpeg_params.extend([
                        '-vf', f"movie={self.watermark_path}[watermark];[0][watermark]{overlay_filter}"
                    ])
            
            # Устанавливаем кодек и качество
            ffmpeg_params.extend([
                '-c:v', 'libx264',
                '-crf', '23',
                '-preset', 'medium',
                '-c:a', 'aac',
                '-b:a', '128k'
            ])
            
            # Добавляем выходной файл
            ffmpeg_params.append(output_path)
            
            # Объединяем команду
            ffmpeg_cmd.extend(ffmpeg_params)
            
            # Запускаем FFmpeg
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Ждем завершения процесса
            await process.wait()
            
            # Проверяем результат
            if process.returncode != 0:
                logger.error(f"Ошибка FFmpeg при обработке видео {video_path}: {await process.stderr.read()}")
                return video_path
            
            # Создаем превью, если нужно
            if create_preview:
                preview_path = os.path.join(self.output_dir, f"{base_name}_{uuid.uuid4().hex[:8]}_preview.jpg")
                
                # Команда FFmpeg для создания превью из середины видео
                preview_cmd = [
                    'ffmpeg',
                    '-i', video_path,
                    '-ss', '00:00:01',
                    '-vframes', '1',
                    '-vf', 'scale=640:-1',
                    preview_path
                ]
                
                # Запускаем FFmpeg
                preview_process = await asyncio.create_subprocess_exec(
                    *preview_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # Ждем завершения процесса
                await preview_process.wait()
                
                # Проверяем результат
                if preview_process.returncode != 0:
                    logger.error(f"Ошибка FFmpeg при создании превью для видео {video_path}: {await preview_process.stderr.read()}")
                    preview_path = None
                
                # Если превью создано успешно, сохраняем информацию о нем в файл метаданных
                if preview_path and os.path.exists(preview_path):
                    metadata_path = os.path.join(self.output_dir, f"{base_name}_{uuid.uuid4().hex[:8]}_metadata.json")
                    
                    metadata = {
                        'original_path': video_path,
                        'processed_path': output_path,
                        'preview_path': preview_path
                    }
                    
                    with open(metadata_path, 'w') as f:
                        json.dump(metadata, f)
            
            return output_path
        except Exception as e:
            logger.error(f"Ошибка при обработке видео {video_path}: {e}")
            return video_path
    
    async def process_animation(self, animation_path: str, optimize: bool = True) -> str:
        """
        Обрабатывает анимацию (GIF)
        
        Args:
            animation_path: Путь к исходной анимации
            optimize: Нужно ли оптимизировать
            
        Returns:
            Путь к обработанной анимации
        """
        try:
            # Создаем уникальное имя файла
            file_name = os.path.basename(animation_path)
            base_name, ext = os.path.splitext(file_name)
            
            output_path = os.path.join(self.output_dir, f"{base_name}_{uuid.uuid4().hex[:8]}{ext}")
            
            # Если это не GIF, просто копируем файл
            if ext.lower() != '.gif':
                import shutil
                shutil.copy2(animation_path, output_path)
                return output_path
            
            # Для GIF используем gifsicle для оптимизации
            if optimize:
                # Команда для оптимизации GIF
                gifsicle_cmd = [
                    'gifsicle',
                    '-O3',
                    '--colors', '256',
                    animation_path,
                    '-o', output_path
                ]
                
                try:
                    # Запускаем gifsicle
                    process = await asyncio.create_subprocess_exec(
                        *gifsicle_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    
                    # Ждем завершения процесса
                    await process.wait()
                    
                    # Проверяем результат
                    if process.returncode != 0:
                        logger.error(f"Ошибка gifsicle при обработке анимации {animation_path}: {await process.stderr.read()}")
                        # Если произошла ошибка, просто копируем файл
                        import shutil
                        shutil.copy2(animation_path, output_path)
                except Exception as e:
                    logger.error(f"Ошибка при запуске gifsicle: {e}")
                    # Если произошла ошибка, просто копируем файл
                    import shutil
                    shutil.copy2(animation_path, output_path)
            else:
                # Просто копируем файл
                import shutil
                shutil.copy2(animation_path, output_path)
            
            return output_path
        except Exception as e:
            logger.error(f"Ошибка при обработке анимации {animation_path}: {e}")
            return animation_path
    
    async def process_document(self, document_path: str) -> str:
        """
        Обрабатывает документ (просто копирует его в выходную директорию)
        
        Args:
            document_path: Путь к исходному документу
            
        Returns:
            Путь к обработанному документу
        """
        try:
            # Создаем уникальное имя файла
            file_name = os.path.basename(document_path)
            base_name, ext = os.path.splitext(file_name)
            
            output_path = os.path.join(self.output_dir, f"{base_name}_{uuid.uuid4().hex[:8]}{ext}")
            
            # Просто копируем файл
            import shutil
            shutil.copy2(document_path, output_path)
            
            return output_path
        except Exception as e:
            logger.error(f"Ошибка при обработке документа {document_path}: {e}")
            return document_path
    
    async def crop_image(self, image_path: str, crop_type: str = 'square') -> str:
        """
        Обрезает изображение по заданному типу
        
        Args:
            image_path: Путь к исходному изображению
            crop_type: Тип обрезки (square, circle, portrait, landscape)
            
        Returns:
            Путь к обрезанному изображению
        """
        try:
            # Создаем уникальное имя файла
            file_name = os.path.basename(image_path)
            base_name, ext = os.path.splitext(file_name)
            
            output_path = os.path.join(self.output_dir, f"{base_name}_{crop_type}_{uuid.uuid4().hex[:8]}{ext}")
            
            # Открываем изображение
            img = Image.open(image_path)
            
            # Обрезаем в зависимости от типа
            if crop_type == 'square':
                # Для квадрата обрезаем до наименьшей стороны
                width, height = img.size
                size = min(width, height)
                
                # Вычисляем координаты для обрезки (центрируем)
                left = (width - size) // 2
                top = (height - size) // 2
                right = left + size
                bottom = top + size
                
                # Обрезаем
                img = img.crop((left, top, right, bottom))
            
            elif crop_type == 'circle':
                # Для круга сначала делаем квадрат
                width, height = img.size
                size = min(width, height)
                
                # Вычисляем координаты для обрезки (центрируем)
                left = (width - size) // 2
                top = (height - size) // 2
                right = left + size
                bottom = top + size
                
                # Обрезаем
                img = img.crop((left, top, right, bottom))
                
                # Создаем круглую маску
                mask = Image.new('L', (size, size), 0)
                mask_draw = ImageOps.Draw(mask)
                mask_draw.ellipse((0, 0, size, size), fill=255)
                
                # Создаем новое изображение с прозрачностью
                result = Image.new('RGBA', (size, size), (0, 0, 0, 0))
                
                # Конвертируем в RGBA, если необходимо
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                # Применяем маску
                result.paste(img, (0, 0), mask)
                img = result
            
            elif crop_type == 'portrait':
                # Для портретной ориентации обрезаем до соотношения 4:5
                width, height = img.size
                
                # Если ширина больше высоты * 0.8, обрезаем ширину
                if width > height * 0.8:
                    new_width = int(height * 0.8)
                    left = (width - new_width) // 2
                    top = 0
                    right = left + new_width
                    bottom = height
                    
                    # Обрезаем
                    img = img.crop((left, top, right, bottom))
            
            elif crop_type == 'landscape':
                # Для ландшафтной ориентации обрезаем до соотношения 16:9
                width, height = img.size
                
                # Если высота больше ширины * 0.5625, обрезаем высоту
                if height > width * 0.5625:
                    new_height = int(width * 0.5625)
                    left = 0
                    top = (height - new_height) // 2
                    right = width
                    bottom = top + new_height
                    
                    # Обрезаем
                    img = img.crop((left, top, right, bottom))
            
            # Сохраняем результат
            img.save(output_path)
            
            return output_path
        except Exception as e:
            logger.error(f"Ошибка при обрезке изображения {image_path}: {e}")
            return image_path
    
    async def add_watermark_to_image(self, image_path: str, watermark_path: str = None, 
                                   opacity: float = 0.7) -> str:
        """
        Добавляет водяной знак на изображение
        
        Args:
            image_path: Путь к исходному изображению
            watermark_path: Путь к файлу водяного знака (если None, используется self.watermark_path)
            opacity: Прозрачность водяного знака (0-1)
            
        Returns:
            Путь к изображению с водяным знаком
        """
        try:
            # Если путь к водяному знаку не указан, используем путь из конструктора
            if not watermark_path:
                watermark_path = self.watermark_path
            
            # Если путь к водяному знаку все еще None или файл не существует, возвращаем исходный файл
            if not watermark_path or not os.path.exists(watermark_path):
                logger.warning("Путь к водяному знаку не указан или файл не существует")
                return image_path
            
            # Создаем уникальное имя файла
            file_name = os.path.basename(image_path)
            base_name, ext = os.path.splitext(file_name)
            
            output_path = os.path.join(self.output_dir, f"{base_name}_watermarked_{uuid.uuid4().hex[:8]}{ext}")
            
            # Открываем изображение и водяной знак
            img = Image.open(image_path)
            watermark = Image.open(watermark_path)
            
            # Если изображение не в режиме RGBA, конвертируем его
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Изменяем размер водяного знака относительно исходного изображения
            wm_width, wm_height = watermark.size
            img_width, img_height = img.size
            
            # Водяной знак должен быть не более 20% от исходного изображения
            max_wm_width = int(img_width * 0.2)
            max_wm_height = int(img_height * 0.2)
            
            if wm_width > max_wm_width or wm_height > max_wm_height:
                # Вычисляем новые размеры, сохраняя пропорции
                if wm_width > wm_height:
                    new_wm_width = max_wm_width
                    new_wm_height = int(wm_height * (max_wm_width / wm_width))
                else:
                    new_wm_height = max_wm_height
                    new_wm_width = int(wm_width * (max_wm_height / wm_height))
                
                # Изменяем размер водяного знака
                watermark = watermark.resize((new_wm_width, new_wm_height), Image.LANCZOS)
            
            # Вычисляем положение водяного знака (правый нижний угол)
            position = (img_width - watermark.width - 10, img_height - watermark.height - 10)
            
            # Если водяной знак имеет прозрачность (режим RGBA)
            if watermark.mode == 'RGBA':
                # Создаем новый слой того же размера, что и исходное изображение
                layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
                
                # Если задана прозрачность, применяем ее
                if opacity < 1:
                    # Создаем копию водяного знака с измененной прозрачностью
                    watermark_with_opacity = watermark.copy()
                    alpha = watermark_with_opacity.split()[3]
                    alpha = alpha.point(lambda x: int(x * opacity))
                    watermark_with_opacity.putalpha(alpha)
                    
                    # Помещаем водяной знак на слой
                    layer.paste(watermark_with_opacity, position, watermark_with_opacity)
                else:
                    # Помещаем водяной знак на слой
                    layer.paste(watermark, position, watermark)
                
                # Объединяем слои
                img = Image.composite(layer, img, layer)
            else:
                # Если водяной знак не имеет прозрачности, просто размещаем его поверх изображения
                img.paste(watermark, position)
            
            # Сохраняем результат
            img.save(output_path)
            
            return output_path
        except Exception as e:
            logger.error(f"Ошибка при добавлении водяного знака на изображение {image_path}: {e}")
            return image_path
    
    async def create_video_preview(self, video_path: str) -> str:
        """
        Создает превью для видео
        
        Args:
            video_path: Путь к видео
            
        Returns:
            Путь к созданному превью
        """
        try:
            # Создаем уникальное имя файла
            file_name = os.path.basename(video_path)
            base_name, ext = os.path.splitext(file_name)
            
            output_path = os.path.join(self.output_dir, f"{base_name}_preview_{uuid.uuid4().hex[:8]}.jpg")
            
            # Команда FFmpeg для создания превью из середины видео
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', video_path,
                '-ss', '00:00:01',
                '-vframes', '1',
                '-vf', 'scale=640:-1',
                output_path
            ]
            
            # Запускаем FFmpeg
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Ждем завершения процесса
            await process.wait()
            
            # Проверяем результат
            if process.returncode != 0:
                logger.error(f"Ошибка FFmpeg при создании превью для видео {video_path}: {await process.stderr.read()}")
                return None
            
            return output_path
        except Exception as e:
            logger.error(f"Ошибка при создании превью для видео {video_path}: {e}")
            return None
    
    async def get_media_info(self, file_path: str) -> Dict[str, Any]:
        """
        Получает информацию о медиафайле
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Словарь с информацией о файле
        """
        try:
            # Получаем информацию о файле
            file_info = {}
            file_info['path'] = file_path
            file_info['name'] = os.path.basename(file_path)
            file_info['size'] = os.path.getsize(file_path)
            file_info['extension'] = os.path.splitext(file_path)[1].lower()
            
            # Определяем тип файла
            if file_info['extension'] in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.heic', '.heif']:
                file_info['type'] = 'image'
                
                # Получаем размеры изображения
                with Image.open(file_path) as img:
                    file_info['width'] = img.width
                    file_info['height'] = img.height
            
            elif file_info['extension'] in ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv']:
                file_info['type'] = 'video'
                
                # Используем FFmpeg для получения информации о видео
                ffprobe_cmd = [
                    'ffprobe',
                    '-v', 'error',
                    '-show_entries', 'stream=width,height,duration,codec_name',
                    '-of', 'json',
                    file_path
                ]
                
                # Запускаем ffprobe
                process = await asyncio.create_subprocess_exec(
                    *ffprobe_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # Получаем вывод процесса
                stdout, stderr = await process.communicate()
                
                # Проверяем результат
                if process.returncode != 0:
                    logger.error(f"Ошибка FFprobe при получении информации о видео {file_path}: {stderr.decode()}")
                else:
                    # Парсим JSON
                    try:
                        video_info = json.loads(stdout.decode())
                        
                        # Получаем информацию из первого видеопотока
                        for stream in video_info.get('streams', []):
                            if stream.get('codec_type') == 'video':
                                file_info['width'] = stream.get('width', 0)
                                file_info['height'] = stream.get('height', 0)
                                file_info['duration'] = float(stream.get('duration', 0))
                                file_info['codec'] = stream.get('codec_name', '')
                                break
                    except Exception as e:
                        logger.error(f"Ошибка при парсинге JSON с информацией о видео {file_path}: {e}")
            
            else:
                file_info['type'] = 'document'
            
            return file_info
        except Exception as e:
            logger.error(f"Ошибка при получении информации о файле {file_path}: {e}")
            return {'path': file_path, 'name': os.path.basename(file_path)}
