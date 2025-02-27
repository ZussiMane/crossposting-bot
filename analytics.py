# main.py
import os
import logging
import asyncio
import datetime
from pathlib import Path
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile, ParseMode
from aiogram.utils import executor

# Модули бота
from modules.vk_module import VKManager
from modules.telegram_module import TelegramManager
from modules.media_processor import MediaProcessor
from modules.scheduler import SchedulerManager
from modules.analytics import AnalyticsManager
from modules.user_manager import UserManager
from modules.db_manager import DatabaseManager
from modules.settings import Settings

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler("bot_logs.log"),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)

# Инициализация бота
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
bot = Bot(token=TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Инициализация менеджеров
settings = Settings()
db_manager = DatabaseManager(settings.DATABASE_URI)
vk_manager = VKManager(os.getenv('VK_TOKEN'))
telegram_manager = TelegramManager(os.getenv('TELEGRAM_API_ID'), os.getenv('TELEGRAM_API_HASH'))
media_processor = MediaProcessor()
scheduler_manager = SchedulerManager(db_manager)
analytics_manager = AnalyticsManager(db_manager)
user_manager = UserManager(db_manager)

# Определение состояний бота
class BotStates(StatesGroup):
    # Общие состояния
    main_menu = State()

    # Создание поста
    create_post = State()
    add_text = State()
    add_media = State()
    choose_platforms = State()
    schedule_post = State()

    # Управление медиа
    media_menu = State()
    crop_image = State()
    add_watermark = State()

    # Планирование
    schedule_menu = State()
    set_time = State()

    # Аналитика
    analytics_menu = State()

    # Настройки пользователя
    user_settings = State()

    # Административные функции
    admin_menu = State()
    manage_users = State()

# Вспомогательные функции
async def is_admin(user_id):
    return await user_manager.check_admin_rights(user_id)

# Функция для генерации главного меню
async def get_main_menu(user_id):
    keyboard = InlineKeyboardMarkup(row_width=2)

    # Основные кнопки для всех пользователей
    keyboard.add(InlineKeyboardButton('📝 Создать пост', callback_data='create_post'))
    keyboard.add(InlineKeyboardButton('📅 Планирование', callback_data='schedule'))
    keyboard.add(InlineKeyboardButton('📊 Аналитика', callback_data='analytics'))
    keyboard.add(InlineKeyboardButton('⚙️ Настройки', callback_data='settings'))

    # Дополнительные кнопки для администраторов
    if await is_admin(user_id):
        keyboard.add(InlineKeyboardButton('👥 Управление пользователями', callback_data='manage_users'))

    return keyboard

# Обработчики команд
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id

    # Проверяем, зарегистрирован ли пользователь
    if not await user_manager.user_exists(user_id):
        # Делаем первого пользователя администратором (замените YOUR_TELEGRAM_ID на ваш ID)
        is_admin = user_id == 1641227678
        await user_manager.register_user(
            user_id=user_id,
            username=message.from_user.username,
            full_name=f"{message.from_user.first_name} {message.from_user.last_name if message.from_user.last_name else ''}",
            is_admin=is_admin
        )

    welcome_text = (
        "👋 Приветствую в боте для кросс-постинга!\n\n"
        "С моей помощью вы можете публиковать контент в ВКонтакте, Telegram и на ваш сайт.\n\n"
        "Выберите действие из меню ниже:"
    )

    await message.answer(welcome_text, reply_markup=await get_main_menu(user_id))
    await BotStates.main_menu.set()

@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    help_text = (
        "📚 *Инструкция по использованию бота*\n\n"
        "*/start* - Перезапустить бота и вернуться в главное меню\n"
        "*/help* - Показать эту справку\n"
        "*/post* - Быстрое создание нового поста\n"
        "*/schedule* - Управление запланированными постами\n"
        "*/analytics* - Просмотр статистики\n"
        "*/settings* - Настройки пользователя\n\n"
        "Для публикации контента выберите пункт 'Создать пост' в главном меню и следуйте инструкциям."
    )

    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)

# Обработчики создания постов
@dp.callback_query_handler(lambda c: c.data == 'create_post', state='*')
async def process_create_post(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    # Очищаем предыдущие данные
    await state.update_data(post_text="", media_files=[], platforms=[], schedule_time=None)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Добавить текст', callback_data='add_text'))
    keyboard.add(InlineKeyboardButton('Добавить медиа', callback_data='add_media'))
    keyboard.add(InlineKeyboardButton('Выбрать платформы', callback_data='choose_platforms'))
    keyboard.add(InlineKeyboardButton('Запланировать публикацию', callback_data='schedule_post'))
    keyboard.add(InlineKeyboardButton('Опубликовать сейчас', callback_data='publish_now'))
    keyboard.add(InlineKeyboardButton('Сохранить как черновик', callback_data='save_draft'))
    keyboard.add(InlineKeyboardButton('Назад', callback_data='back_to_main'))

    await bot.edit_message_text(
        "📝 *Создание нового поста*\n\n"
        "Выберите действие для создания поста:",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    await BotStates.create_post.set()

@dp.callback_query_handler(lambda c: c.data == 'add_text', state=BotStates.create_post)
async def process_add_text(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Отмена', callback_data='cancel_add_text'))

    await bot.edit_message_text(
        "📝 *Добавление текста*\n\n"
        "Отправьте текст вашего поста в ответном сообщении. Вы можете использовать базовое форматирование Markdown.\n\n"
        "Примеры форматирования:\n"
        "- *жирный текст* между звездочками\n"
        "- _курсив_ между подчеркиваниями\n"
        "- [текст ссылки](https://example.com)",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    await BotStates.add_text.set()

@dp.message_handler(state=BotStates.add_text)
async def process_text_input(message: types.Message, state: FSMContext):
    post_text = message.text

    # Сохраняем текст в состоянии
    await state.update_data(post_text=post_text)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Добавить текст', callback_data='add_text'))
    keyboard.add(InlineKeyboardButton('Добавить медиа', callback_data='add_media'))
    keyboard.add(InlineKeyboardButton('Выбрать платформы', callback_data='choose_platforms'))
    keyboard.add(InlineKeyboardButton('Запланировать публикацию', callback_data='schedule_post'))
    keyboard.add(InlineKeyboardButton('Опубликовать сейчас', callback_data='publish_now'))
    keyboard.add(InlineKeyboardButton('Сохранить как черновик', callback_data='save_draft'))
    keyboard.add(InlineKeyboardButton('Назад', callback_data='back_to_main'))

    await message.answer(
        "✅ Текст добавлен успешно!\n\n"
        f"Текст поста:\n{post_text[:200]}{'...' if len(post_text) > 200 else ''}\n\n"
        "Выберите следующее действие:",
        reply_markup=keyboard
    )

    await BotStates.create_post.set()

@dp.callback_query_handler(lambda c: c.data == 'add_media', state=BotStates.create_post)
async def process_add_media(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Отмена', callback_data='cancel_add_media'))

    await bot.edit_message_text(
        "📎 *Добавление медиафайлов*\n\n"
        "Отправьте фото, видео, GIF или документы, которые вы хотите добавить к посту.\n"
        "Вы можете отправить несколько файлов в одном сообщении или по отдельности.\n\n"
        "Поддерживаемые форматы:\n"
        "- Изображения: JPG, PNG, GIF\n"
        "- Видео: MP4, AVI, MOV\n"
        "- Документы: PDF, DOC, DOCX",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    await BotStates.add_media.set()

@dp.message_handler(content_types=[types.ContentType.PHOTO, types.ContentType.VIDEO,
                                  types.ContentType.DOCUMENT, types.ContentType.ANIMATION],
                    state=BotStates.add_media)
async def process_media_input(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    media_files = user_data.get('media_files', [])

    # Получаем файл и определяем его тип
    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = 'photo'
    elif message.video:
        file_id = message.video.file_id
        file_type = 'video'
    elif message.animation:
        file_id = message.animation.file_id
        file_type = 'animation'  # GIF
    elif message.document:
        file_id = message.document.file_id
        file_type = 'document'
    else:
        await message.answer("❌ Неподдерживаемый тип файла. Пожалуйста, отправьте фото, видео, GIF или документ.")
        return

    # Скачиваем файл
    file_info = await bot.get_file(file_id)
    file_path = file_info.file_path
    file_name = f"{file_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Создаем директорию, если ее нет
    os.makedirs('downloads', exist_ok=True)

    # Полный путь для сохранения файла
    download_path = os.path.join('downloads', file_name)

    # Скачиваем файл
    await bot.download_file(file_path, download_path)

    # Обрабатываем медиафайл
    processed_path = await media_processor.process_media(download_path, file_type)

    # Добавляем информацию о файле в состояние
    media_files.append({
        'file_id': file_id,
        'file_type': file_type,
        'file_path': processed_path,
        'original_path': download_path
    })

    await state.update_data(media_files=media_files)

    # Отправляем подтверждение
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Добавить еще медиа', callback_data='add_media'))
    keyboard.add(InlineKeyboardButton('Назад к созданию поста', callback_data='back_to_create'))

    await message.answer(
        f"✅ Медиафайл успешно добавлен! Всего файлов: {len(media_files)}\n\n"
        "Выберите следующее действие:",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data == 'back_to_create', state=BotStates.add_media)
async def back_to_create_post(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Добавить текст', callback_data='add_text'))
    keyboard.add(InlineKeyboardButton('Добавить медиа', callback_data='add_media'))
    keyboard.add(InlineKeyboardButton('Выбрать платформы', callback_data='choose_platforms'))
    keyboard.add(InlineKeyboardButton('Запланировать публикацию', callback_data='schedule_post'))
    keyboard.add(InlineKeyboardButton('Опубликовать сейчас', callback_data='publish_now'))
    keyboard.add(InlineKeyboardButton('Сохранить как черновик', callback_data='save_draft'))
    keyboard.add(InlineKeyboardButton('Назад', callback_data='back_to_main'))

    user_data = await state.get_data()
    media_count = len(user_data.get('media_files', []))
    post_text = user_data.get('post_text', '')

    status_text = "📝 *Создание нового поста*\n\n"

    if post_text:
        status_text += f"✅ Текст: {post_text[:100]}{'...' if len(post_text) > 100 else ''}\n"
    else:
        status_text += "❌ Текст: не добавлен\n"

    status_text += f"📎 Медиафайлы: {media_count}\n\n"
    status_text += "Выберите действие:"

    await bot.edit_message_text(
        status_text,
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    await BotStates.create_post.set()

@dp.callback_query_handler(lambda c: c.data == 'choose_platforms', state=BotStates.create_post)
async def process_choose_platforms(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    user_data = await state.get_data()
    selected_platforms = user_data.get('platforms', [])

    # Создаем клавиатуру с выбором платформ
    keyboard = InlineKeyboardMarkup()
    vk_selected = '✅' if 'vk' in selected_platforms else '❌'
    telegram_selected = '✅' if 'telegram' in selected_platforms else '❌'
    website_selected = '✅' if 'website' in selected_platforms else '❌'

    keyboard.add(InlineKeyboardButton(f'{vk_selected} ВКонтакте', callback_data='toggle_vk'))
    keyboard.add(InlineKeyboardButton(f'{telegram_selected} Telegram', callback_data='toggle_telegram'))
    keyboard.add(InlineKeyboardButton(f'{website_selected} Сайт (недоступно)', callback_data='toggle_website'))
    keyboard.add(InlineKeyboardButton('Готово', callback_data='platforms_selected'))
    keyboard.add(InlineKeyboardButton('Отмена', callback_data='back_to_create'))

    await bot.edit_message_text(
        "🌐 *Выбор платформ для публикации*\n\n"
        "Выберите платформы, на которых хотите опубликовать пост:",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    await BotStates.choose_platforms.set()

@dp.callback_query_handler(lambda c: c.data.startswith('toggle_'), state=BotStates.choose_platforms)
async def toggle_platform(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    platform = callback_query.data.replace('toggle_', '')

    # Если это веб-сайт, отображаем сообщение о недоступности
    if platform == 'website':
        await bot.answer_callback_query(
            callback_query.id,
            "Публикация на сайте временно недоступна",
            show_alert=True
        )
        return

    # Получаем текущий список выбранных платформ
    user_data = await state.get_data()
    selected_platforms = user_data.get('platforms', [])

    # Переключаем состояние выбранной платформы
    if platform in selected_platforms:
        selected_platforms.remove(platform)
    else:
        selected_platforms.append(platform)

    # Обновляем данные
    await state.update_data(platforms=selected_platforms)

    # Обновляем клавиатуру
    keyboard = InlineKeyboardMarkup()
    vk_selected = '✅' if 'vk' in selected_platforms else '❌'
    telegram_selected = '✅' if 'telegram' in selected_platforms else '❌'
    website_selected = '✅' if 'website' in selected_platforms else '❌'

    keyboard.add(InlineKeyboardButton(f'{vk_selected} ВКонтакте', callback_data='toggle_vk'))
    keyboard.add(InlineKeyboardButton(f'{telegram_selected} Telegram', callback_data='toggle_telegram'))
    keyboard.add(InlineKeyboardButton(f'{website_selected} Сайт (недоступно)', callback_data='toggle_website'))
    keyboard.add(InlineKeyboardButton('Готово', callback_data='platforms_selected'))
    keyboard.add(InlineKeyboardButton('Отмена', callback_data='back_to_create'))

    await bot.edit_message_text(
        "🌐 *Выбор платформ для публикации*\n\n"
        "Выберите платформы, на которых хотите опубликовать пост:",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

@dp.callback_query_handler(lambda c: c.data == 'platforms_selected', state=BotStates.choose_platforms)
async def platforms_selected(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    user_data = await state.get_data()
    selected_platforms = user_data.get('platforms', [])

    if not selected_platforms:
        await bot.answer_callback_query(
            callback_query.id,
            "Выберите хотя бы одну платформу для публикации",
            show_alert=True
        )
        return

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Добавить текст', callback_data='add_text'))
    keyboard.add(InlineKeyboardButton('Добавить медиа', callback_data='add_media'))
    keyboard.add(InlineKeyboardButton('Выбрать платформы', callback_data='choose_platforms'))
    keyboard.add(InlineKeyboardButton('Запланировать публикацию', callback_data='schedule_post'))
    keyboard.add(InlineKeyboardButton('Опубликовать сейчас', callback_data='publish_now'))
    keyboard.add(InlineKeyboardButton('Сохранить как черновик', callback_data='save_draft'))
    keyboard.add(InlineKeyboardButton('Назад', callback_data='back_to_main'))

    platforms_text = ', '.join([p.capitalize() for p in selected_platforms])

    user_data = await state.get_data()
    media_count = len(user_data.get('media_files', []))
    post_text = user_data.get('post_text', '')

    status_text = "📝 *Создание нового поста*\n\n"

    if post_text:
        status_text += f"✅ Текст: {post_text[:100]}{'...' if len(post_text) > 100 else ''}\n"
    else:
        status_text += "❌ Текст: не добавлен\n"

    status_text += f"📎 Медиафайлы: {media_count}\n"
    status_text += f"🌐 Платформы: {platforms_text}\n\n"
    status_text += "Выберите действие:"

    await bot.edit_message_text(
        status_text,
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    await BotStates.create_post.set()

@dp.callback_query_handler(lambda c: c.data == 'schedule_post', state=BotStates.create_post)
async def schedule_post(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Сегодня', callback_data='schedule_today'))
    keyboard.add(InlineKeyboardButton('Завтра', callback_data='schedule_tomorrow'))
    keyboard.add(InlineKeyboardButton('Выбрать дату', callback_data='schedule_custom'))
    keyboard.add(InlineKeyboardButton('Отмена', callback_data='back_to_create'))

    await bot.edit_message_text(
        "📅 *Планирование публикации*\n\n"
        "Выберите дату публикации:",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    await BotStates.schedule_post.set()

@dp.callback_query_handler(lambda c: c.data.startswith('schedule_'), state=BotStates.schedule_post)
async def set_schedule_date(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    schedule_option = callback_query.data.replace('schedule_', '')

    if schedule_option == 'today':
        date = datetime.datetime.now().date()
    elif schedule_option == 'tomorrow':
        date = (datetime.datetime.now() + datetime.timedelta(days=1)).date()
    elif schedule_option == 'custom':
        # Здесь можно реализовать выбор произвольной даты через календарь
        # Для простоты примера используем текущую дату
        date = datetime.datetime.now().date()
    else:
        # Возвращаемся к созданию поста
        await back_to_create_post(callback_query, state)
        return

    # Сохраняем дату в состоянии
    await state.update_data(schedule_date=date.strftime('%Y-%m-%d'))

    # Предлагаем выбрать время
    keyboard = InlineKeyboardMarkup(row_width=3)

    # Добавляем варианты времени с 10:00 до 21:00
    for hour in range(10, 22):
        keyboard.insert(InlineKeyboardButton(f"{hour}:00", callback_data=f"time_{hour}_00"))

    for hour in range(10, 22):
        keyboard.insert(InlineKeyboardButton(f"{hour}:30", callback_data=f"time_{hour}_30"))

    keyboard.add(InlineKeyboardButton('Отмена', callback_data='back_to_create'))

    await bot.edit_message_text(
        f"🕒 *Выбор времени публикации*\n\n"
        f"Дата: {date.strftime('%d.%m.%Y')}\n\n"
        f"Выберите время публикации:",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    await BotStates.set_time.set()

@dp.callback_query_handler(lambda c: c.data.startswith('time_'), state=BotStates.set_time)
async def set_schedule_time(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    time_parts = callback_query.data.replace('time_', '').split('_')
    hour = int(time_parts[0])
    minute = int(time_parts[1])

    user_data = await state.get_data()
    date_str = user_data.get('schedule_date')

    # Создаем полную дату со временем
    date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
    scheduled_time = date.replace(hour=hour, minute=minute)

    # Проверяем, не пытается ли пользователь запланировать пост на прошлое
    if scheduled_time < datetime.datetime.now():
        await bot.answer_callback_query(
            callback_query.id,
            "Нельзя запланировать публикацию на прошедшее время. Пожалуйста, выберите другое время.",
            show_alert=True
        )
        return

    # Сохраняем полную дату и время в состоянии
    await state.update_data(schedule_time=scheduled_time.strftime('%Y-%m-%d %H:%M:%S'))

    # Возвращаемся к созданию поста с обновленной информацией
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Добавить текст', callback_data='add_text'))
    keyboard.add(InlineKeyboardButton('Добавить медиа', callback_data='add_media'))
    keyboard.add(InlineKeyboardButton('Выбрать платформы', callback_data='choose_platforms'))
    keyboard.add(InlineKeyboardButton('Изменить время публикации', callback_data='schedule_post'))
    keyboard.add(InlineKeyboardButton('Запланировать пост', callback_data='confirm_schedule'))
    keyboard.add(InlineKeyboardButton('Опубликовать сейчас', callback_data='publish_now'))
    keyboard.add(InlineKeyboardButton('Сохранить как черновик', callback_data='save_draft'))
    keyboard.add(InlineKeyboardButton('Назад', callback_data='back_to_main'))

    user_data = await state.get_data()
    media_count = len(user_data.get('media_files', []))
    post_text = user_data.get('post_text', '')
    platforms = user_data.get('platforms', [])
    platforms_text = ', '.join([p.capitalize() for p in platforms])

    status_text = "📝 *Создание нового поста*\n\n"

    if post_text:
        status_text += f"✅ Текст: {post_text[:100]}{'...' if len(post_text) > 100 else ''}\n"
    else:
        status_text += "❌ Текст: не добавлен\n"

    status_text += f"📎 Медиафайлы: {media_count}\n"
    status_text += f"🌐 Платформы: {platforms_text}\n"
    status_text += f"📅 Запланировано на: {scheduled_time.strftime('%d.%m.%Y %H:%M')}\n\n"
    status_text += "Выберите действие:"

    await bot.edit_message_text(
        status_text,
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    await BotStates.create_post.set()

@dp.callback_query_handler(lambda c: c.data == 'confirm_schedule', state=BotStates.create_post)
async def confirm_schedule_post(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    user_data = await state.get_data()
    post_text = user_data.get('post_text', '')
    media_files = user_data.get('media_files', [])
    platforms = user_data.get('platforms', [])
    schedule_time_str = user_data.get('schedule_time')

    # Проверка наличия необходимых данных
    if not post_text and not media_files:
        await bot.answer_callback_query(
            callback_query.id,
            "Пост должен содержать текст или медиафайлы. Пожалуйста, добавьте содержимое.",
            show_alert=True
        )
        return

    if not platforms:
        await bot.answer_callback_query(
            callback_query.id,
            "Выберите хотя бы одну платформу для публикации.",
            show_alert=True
        )
        return

    # Преобразование строки времени в объект datetime
    schedule_time = datetime.datetime.strptime(schedule_time_str, '%Y-%m-%d %H:%M:%S')

    # Создание записи о посте в базе данных
    post_id = await db_manager.create_post(
        user_id=callback_query.from_user.id,
        text=post_text,
        media_files=media_files,
        platforms=platforms,
        schedule_time=schedule_time
    )

    # Добавление задачи в планировщик
    await scheduler_manager.schedule_post(post_id, schedule_time)

    # Отправка подтверждения пользователю
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Главное меню', callback_data='back_to_main'))
    keyboard.add(InlineKeyboardButton('Создать новый пост', callback_data='create_post'))
    keyboard.add(InlineKeyboardButton('Управление запланированными постами', callback_data='schedule'))

    platforms_text = ', '.join([p.capitalize() for p in platforms])

    await bot.edit_message_text(
        f"✅ *Пост успешно запланирован!*\n\n"
        f"📅 Дата и время публикации: {schedule_time.strftime('%d.%m.%Y %H:%M')}\n"
        f"🌐 Платформы: {platforms_text}\n\n"
        f"Ваш пост будет автоматически опубликован в указанное время.",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    await BotStates.main_menu.set()

@dp.callback_query_handler(lambda c: c.data == 'publish_now', state=BotStates.create_post)
async def publish_post_now(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    user_data = await state.get_data()
    post_text = user_data.get('post_text', '')
    media_files = user_data.get('media_files', [])
    platforms = user_data.get('platforms', [])

    # Проверка наличия необходимых данных
    if not post_text and not media_files:
        await bot.answer_callback_query(
            callback_query.id,
            "Пост должен содержать текст или медиафайлы. Пожалуйста, добавьте содержимое.",
            show_alert=True
        )
        return

    if not platforms:
        await bot.answer_callback_query(
            callback_query.id,
            "Выберите хотя бы одну платформу для публикации.",
            show_alert=True
        )
        return

    # Отправляем сообщение о начале публикации
    await bot.edit_message_text(
        "🔄 *Публикация поста...*\n\n"
        "Пожалуйста, подождите, пост публикуется на выбранных платформах.",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        parse_mode=ParseMode.MARKDOWN
    )

    # Создание записи о посте в базе данных
    post_id = await db_manager.create_post(
        user_id=callback_query.from_user.id,
        text=post_text,
        media_files=media_files,
        platforms=platforms,
        schedule_time=None,  # Пост публикуется сразу
        status='publishing'
    )

    # Публикация поста на разных платформах
    results = {}

    # Публикация в ВКонтакте
    if 'vk' in platforms:
        try:
            vk_post_id = await vk_manager.publish_post(post_text, media_files)
            results['vk'] = {'success': True, 'post_id': vk_post_id}
        except Exception as e:
            results['vk'] = {'success': False, 'error': str(e)}
            logger.error(f"Error publishing to VK: {e}")

    # Публикация в Telegram
    if 'telegram' in platforms:
        try:
            tg_message_ids = await telegram_manager.publish_post(post_text, media_files)
            results['telegram'] = {'success': True, 'message_ids': tg_message_ids}
        except Exception as e:
            results['telegram'] = {'success': False, 'error': str(e)}
            logger.error(f"Error publishing to Telegram: {e}")

    # Публикация на сайт (закомментированная функциональность)
    """
    if 'website' in platforms:
        try:
            website_post_id = await website_manager.publish_post(post_text, media_files)
            results['website'] = {'success': True, 'post_id': website_post_id}
        except Exception as e:
            results['website'] = {'success': False, 'error': str(e)}
            logger.error(f"Error publishing to Website: {e}")
    """

    # Обновляем статус поста в базе данных
    success_count = sum(1 for platform in results if results[platform]['success'])
    status = 'published' if success_count > 0 else 'failed'

    await db_manager.update_post(
        post_id=post_id,
        status=status,
        results=results
    )

    # Начинаем отслеживание статистики
    if success_count > 0:
        await analytics_manager.start_tracking(post_id, platforms)

    # Формируем результаты для отображения
    results_text = ""
    for platform in results:
        if results[platform]['success']:
            results_text += f"✅ {platform.capitalize()}: Опубликовано успешно\n"
        else:
            results_text += f"❌ {platform.capitalize()}: Ошибка публикации\n"

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Главное меню', callback_data='back_to_main'))
    keyboard.add(InlineKeyboardButton('Создать новый пост', callback_data='create_post'))
    keyboard.add(InlineKeyboardButton('Просмотреть статистику', callback_data='post_stats_' + str(post_id)))

    await bot.edit_message_text(
        f"📤 *Результаты публикации*\n\n"
        f"{results_text}\n"
        f"Пост {'опубликован успешно' if success_count > 0 else 'не удалось опубликовать'}.",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    await BotStates.main_menu.set()

@dp.callback_query_handler(lambda c: c.data == 'save_draft', state=BotStates.create_post)
async def save_post_draft(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    user_data = await state.get_data()
    post_text = user_data.get('post_text', '')
    media_files = user_data.get('media_files', [])
    platforms = user_data.get('platforms', [])

    # Проверка наличия данных для сохранения
    if not post_text and not media_files:
        await bot.answer_callback_query(
            callback_query.id,
            "Черновик должен содержать текст или медиафайлы. Пожалуйста, добавьте содержимое.",
            show_alert=True
        )
        return

    # Сохранение черновика в базе данных
    draft_id = await db_manager.create_post(
        user_id=callback_query.from_user.id,
        text=post_text,
        media_files=media_files,
        platforms=platforms,
        schedule_time=None,
        status='draft'
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Главное меню', callback_data='back_to_main'))
    keyboard.add(InlineKeyboardButton('Создать новый пост', callback_data='create_post'))
    keyboard.add(InlineKeyboardButton('Управление черновиками', callback_data='drafts'))

    await bot.edit_message_text(
        "✅ *Черновик успешно сохранен!*\n\n"
        "Вы можете найти его в разделе 'Управление черновиками'.",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    await BotStates.main_menu.set()

# Планирование публикаций
@dp.callback_query_handler(lambda c: c.data == 'schedule', state='*')
async def schedule_menu(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Запланированные посты', callback_data='scheduled_posts'))
    keyboard.add(InlineKeyboardButton('Черновики', callback_data='drafts'))
    keyboard.add(InlineKeyboardButton('Опубликованные посты', callback_data='published_posts'))
    keyboard.add(InlineKeyboardButton('Календарь публикаций', callback_data='calendar'))
    keyboard.add(InlineKeyboardButton('Назад', callback_data='back_to_main'))

    await bot.edit_message_text(
        "📅 *Управление публикациями*\n\n"
        "Выберите раздел для управления вашими публикациями:",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    await BotStates.schedule_menu.set()

@dp.callback_query_handler(lambda c: c.data == 'scheduled_posts', state=BotStates.schedule_menu)
async def view_scheduled_posts(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    # Получение запланированных постов из базы данных
    scheduled_posts = await db_manager.get_posts_by_status(
        user_id=callback_query.from_user.id,
        status='scheduled',
        limit=10
    )

    if not scheduled_posts:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton('Создать пост', callback_data='create_post'))
        keyboard.add(InlineKeyboardButton('Назад', callback_data='schedule'))

        await bot.edit_message_text(
            "📭 *У вас нет запланированных постов*\n\n"
            "Создайте новый пост и запланируйте его публикацию.",
            callback_query.message.chat.id,
            callback_query.message.message_id,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Формирование списка постов
    posts_text = ""
    for post in scheduled_posts:
        schedule_time = datetime.datetime.fromisoformat(post['schedule_time'])
        platforms = ', '.join([p.capitalize() for p in post['platforms']])
        text_preview = post['text'][:50] + '...' if post['text'] and len(post['text']) > 50 else post['text'] or '[Нет текста]'

        posts_text += (
            f"📝 *Пост #{post['id']}*\n"
            f"⏰ {schedule_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"🌐 {platforms}\n"
            f"📄 {text_preview}\n\n"
        )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Управление постами', callback_data='manage_scheduled'))
    keyboard.add(InlineKeyboardButton('Создать новый пост', callback_data='create_post'))
    keyboard.add(InlineKeyboardButton('Назад', callback_data='schedule'))

    await bot.edit_message_text(
        f"📅 *Запланированные посты*\n\n"
        f"{posts_text}"
        f"Всего запланированных постов: {len(scheduled_posts)}",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

@dp.callback_query_handler(lambda c: c.data == 'manage_scheduled', state=BotStates.schedule_menu)
async def manage_scheduled_posts(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    # Получение запланированных постов из базы данных
    scheduled_posts = await db_manager.get_posts_by_status(
        user_id=callback_query.from_user.id,
        status='scheduled',
        limit=10
    )

    keyboard = InlineKeyboardMarkup()

    for post in scheduled_posts:
        schedule_time = datetime.datetime.fromisoformat(post['schedule_time'])
        text_preview = post['text'][:20] + '...' if post['text'] and len(post['text']) > 20 else post['text'] or '[Нет текста]'
        button_text = f"#{post['id']} | {schedule_time.strftime('%d.%m %H:%M')} | {text_preview}"
        keyboard.add(InlineKeyboardButton(button_text, callback_data=f"manage_post_{post['id']}"))

    keyboard.add(InlineKeyboardButton('Назад', callback_data='scheduled_posts'))

    await bot.edit_message_text(
        "🔄 *Управление запланированными постами*\n\n"
        "Выберите пост для управления:",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

@dp.callback_query_handler(lambda c: c.data.startswith('manage_post_'), state=BotStates.schedule_menu)
async def manage_specific_post(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    post_id = int(callback_query.data.replace('manage_post_', ''))

    # Получение информации о посте
    post = await db_manager.get_post_by_id(post_id)

    if not post:
        await bot.answer_callback_query(
            callback_query.id,
            "Пост не найден. Возможно, он был удален.",
            show_alert=True
        )
        await manage_scheduled_posts(callback_query, state)
        return

    # Формирование информации о посте
    schedule_time = datetime.datetime.fromisoformat(post['schedule_time'])
    platforms = ', '.join([p.capitalize() for p in post['platforms']])
    media_count = len(post['media_files']) if post['media_files'] else 0

    post_info = (
        f"📝 *Пост #{post['id']}*\n\n"
        f"📅 Дата публикации: {schedule_time.strftime('%d.%m.%Y %H:%M')}\n"
        f"🌐 Платформы: {platforms}\n"
        f"📎 Медиафайлы: {media_count}\n\n"
        f"📄 Текст поста:\n{post['text'] or '[Нет текста]'}"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Редактировать пост', callback_data=f"edit_post_{post_id}"))
    keyboard.add(InlineKeyboardButton('Изменить время публикации', callback_data=f"reschedule_post_{post_id}"))
    keyboard.add(InlineKeyboardButton('Опубликовать сейчас', callback_data=f"publish_now_{post_id}"))
    keyboard.add(InlineKeyboardButton('Удалить пост', callback_data=f"delete_post_{post_id}"))
    keyboard.add(InlineKeyboardButton('Назад', callback_data="manage_scheduled"))

    await bot.edit_message_text(
        post_info,
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

@dp.callback_query_handler(lambda c: c.data.startswith('delete_post_'), state=BotStates.schedule_menu)
async def confirm_delete_post(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    post_id = int(callback_query.data.replace('delete_post_', ''))

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Да, удалить пост', callback_data=f"confirm_delete_{post_id}"))
    keyboard.add(InlineKeyboardButton('Нет, отменить', callback_data=f"manage_post_{post_id}"))

    await bot.edit_message_text(
        "❓ *Подтверждение удаления*\n\n"
        f"Вы уверены, что хотите удалить пост #{post_id}?\n"
        "Это действие нельзя отменить.",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

@dp.callback_query_handler(lambda c: c.data.startswith('confirm_delete_'), state=BotStates.schedule_menu)
async def delete_post(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    post_id = int(callback_query.data.replace('confirm_delete_', ''))

    # Удаление поста из базы данных и отмена запланированной задачи
    await db_manager.delete_post(post_id)
    await scheduler_manager.cancel_scheduled_post(post_id)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Назад к запланированным постам', callback_data="scheduled_posts"))
    keyboard.add(InlineKeyboardButton('Главное меню', callback_data="back_to_main"))

    await bot.edit_message_text(
        "✅ *Пост успешно удален!*",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

# Аналитика
@dp.callback_query_handler(lambda c: c.data == 'analytics', state='*')
async def analytics_menu(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Статистика постов', callback_data='posts_stats'))
    keyboard.add(InlineKeyboardButton('Общая аналитика', callback_data='general_stats'))
    keyboard.add(InlineKeyboardButton('Рекомендации', callback_data='recommendations'))
    keyboard.add(InlineKeyboardButton('Экспорт отчетов', callback_data='export_reports'))
    keyboard.add(InlineKeyboardButton('Назад', callback_data='back_to_main'))

    await bot.edit_message_text(
        "📊 *Аналитика и статистика*\n\n"
        "Выберите раздел для просмотра аналитики:",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    await BotStates.analytics_menu.set()

@dp.callback_query_handler(lambda c: c.data == 'posts_stats', state=BotStates.analytics_menu)
async def view_posts_stats(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    # Получение опубликованных постов из базы данных
    published_posts = await db_manager.get_posts_by_status(
        user_id=callback_query.from_user.id,
        status='published',
        limit=10
    )

    if not published_posts:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton('Создать пост', callback_data='create_post'))
        keyboard.add(InlineKeyboardButton('Назад', callback_data='analytics'))

        await bot.edit_message_text(
            "📭 *У вас нет опубликованных постов*\n\n"
            "Опубликуйте пост, чтобы начать отслеживать статистику.",
            callback_query.message.chat.id,
            callback_query.message.message_id,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Формирование списка постов
    keyboard = InlineKeyboardMarkup()

    for post in published_posts:
    # Безопасное преобразование даты публикации
        try:
            if isinstance(post['published_at'], str):
                publish_date = datetime.datetime.fromisoformat(post['published_at'])
            else:
                publish_date = post['published_at']
        except (TypeError, ValueError):
            publish_date = datetime.datetime.utcnow()
            text_preview = post['text'][:20] + '...' if post['text'] and len(post['text']) > 20 else post['text'] or '[Нет текста]'
            button_text = f"#{post['id']} | {publish_date.strftime('%d.%m %H:%M')} | {text_preview}"
            keyboard.add(InlineKeyboardButton(button_text, callback_data=f"post_stats_{post['id']}"))

    keyboard.add(InlineKeyboardButton('Назад', callback_data='analytics'))

    await bot.edit_message_text(
        "📊 *Статистика постов*\n\n"
        "Выберите пост для просмотра детальной статистики:",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

@dp.callback_query_handler(lambda c: c.data.startswith('post_stats_'), state='*')
async def view_post_statistics(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    post_id = int(callback_query.data.replace('post_stats_', ''))

    # Получение информации о посте
    post = await db_manager.get_post_by_id(post_id)

    if not post:
        await bot.answer_callback_query(
            callback_query.id,
            "Пост не найден. Возможно, он был удален.",
            show_alert=True
        )
        await view_posts_stats(callback_query, state)
        return

    # Получение статистики поста
    stats = await analytics_manager.get_post_statistics(post_id)

    # Формирование данных для отображения
    platforms = post['platforms']
    publish_date = datetime.datetime.fromisoformat(post['published_at'])

    stats_text = f"📊 *Статистика поста #{post_id}*\n\n"
    stats_text += f"📅 Опубликован: {publish_date.strftime('%d.%m.%Y %H:%M')}\n\n"

    # Статистика по платформам
    for platform in platforms:
        platform_stats = stats.get(platform, {})

        if platform == 'vk':
            stats_text += "*ВКонтакте:*\n"
            stats_text += f"👁 Просмотры: {platform_stats.get('views', 0)}\n"
            stats_text += f"👍 Лайки: {platform_stats.get('likes', 0)}\n"
            stats_text += f"🔄 Репосты: {platform_stats.get('reposts', 0)}\n"
            stats_text += f"💬 Комментарии: {platform_stats.get('comments', 0)}\n\n"

        elif platform == 'telegram':
            stats_text += "*Telegram:*\n"
            stats_text += f"👁 Просмотры: {platform_stats.get('views', 0)}\n"
            stats_text += f"👍 Реакции: {platform_stats.get('reactions', 0)}\n"
            stats_text += f"📢 Пересылки: {platform_stats.get('forwards', 0)}\n\n"

        # Статистика для сайта (закомментированный код)
        """
        elif platform == 'website':
            stats_text += "*Сайт:*\n"
            stats_text += f"👁 Просмотры: {platform_stats.get('views', 0)}\n"
            stats_text += f"👍 Лайки: {platform_stats.get('likes', 0)}\n"
            stats_text += f"💬 Комментарии: {platform_stats.get('comments', 0)}\n\n"
        """

    # Общая статистика
    stats_text += "*Общая статистика:*\n"
    stats_text += f"👁 Общий охват: {stats.get('total', {}).get('reach', 0)}\n"
    stats_text += f"👥 Вовлеченность: {stats.get('total', {}).get('engagement_rate', 0)}%\n"

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Обновить статистику', callback_data=f"refresh_stats_{post_id}"))
    keyboard.add(InlineKeyboardButton('Назад к списку постов', callback_data="posts_stats"))
    keyboard.add(InlineKeyboardButton('Экспорт данных', callback_data=f"export_stats_{post_id}"))
    keyboard.add(InlineKeyboardButton('Назад в меню аналитики', callback_data='analytics'))

    await bot.edit_message_text(
        stats_text,
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

@dp.callback_query_handler(lambda c: c.data.startswith('refresh_stats_'), state='*')
async def refresh_post_statistics(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id, "Статистика обновляется...")

    post_id = int(callback_query.data.replace('refresh_stats_', ''))

    # Обновление статистики
    await analytics_manager.update_post_statistics(post_id)

    # Повторный показ статистики
    await view_post_statistics(callback_query, state)

@dp.callback_query_handler(lambda c: c.data == 'general_stats', state=BotStates.analytics_menu)
async def view_general_statistics(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    # Получение общей статистики
    stats = await analytics_manager.get_general_statistics(user_id=callback_query.from_user.id)

    # Форматирование данных для отображения
    total_posts = stats.get('total_posts', 0)
    total_reach = stats.get('total_reach', 0)
    avg_engagement = stats.get('avg_engagement', 0)
    best_time = stats.get('best_time', 'Нет данных')
    best_platform = stats.get('best_platform', 'Нет данных')

    stats_text = (
        "📊 *Общая статистика*\n\n"
        f"📝 Всего опубликовано постов: {total_posts}\n"
        f"👁 Общий охват: {total_reach}\n"
        f"👥 Средняя вовлеченность: {avg_engagement}%\n\n"
        f"⏰ Лучшее время для публикаций: {best_time}\n"
        f"🌐 Наиболее эффективная платформа: {best_platform}\n\n"
        f"Статистика за последние 30 дней."
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Экспорт полной статистики', callback_data='export_full_stats'))
    keyboard.add(InlineKeyboardButton('Рекомендации', callback_data='recommendations'))
    keyboard.add(InlineKeyboardButton('Назад', callback_data='analytics'))

    await bot.edit_message_text(
        stats_text,
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

@dp.callback_query_handler(lambda c: c.data == 'recommendations', state=BotStates.analytics_menu)
async def view_recommendations(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    # Получение рекомендаций на основе анализа данных
    recommendations = await analytics_manager.get_recommendations(user_id=callback_query.from_user.id)

    if not recommendations:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton('Назад', callback_data='analytics'))

        await bot.edit_message_text(
            "❓ *Недостаточно данных для рекомендаций*\n\n"
            "Опубликуйте больше постов, чтобы получить персонализированные рекомендации для улучшения показателей.",
            callback_query.message.chat.id,
            callback_query.message.message_id,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Формирование рекомендаций для отображения
    time_recom = recommendations.get('best_time', 'Недостаточно данных')
    content_recom = recommendations.get('content_type', 'Недостаточно данных')
    platform_recom = recommendations.get('platform', 'Недостаточно данных')

    recom_text = (
        "💡 *Рекомендации для улучшения показателей*\n\n"
        f"⏰ *Оптимальное время публикации:*\n{time_recom}\n\n"
        f"📝 *Рекомендуемый тип контента:*\n{content_recom}\n\n"
        f"🌐 *Приоритетные платформы:*\n{platform_recom}\n\n"
        "Рекомендации основаны на анализе ваших предыдущих публикаций и статистики вовлеченности аудитории."
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Новый пост с учетом рекомендаций', callback_data='create_recommended_post'))
    keyboard.add(InlineKeyboardButton('Назад', callback_data='analytics'))

    await bot.edit_message_text(
        recom_text,
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

@dp.callback_query_handler(lambda c: c.data == 'export_reports', state=BotStates.analytics_menu)
async def export_reports_menu(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Отчет за последнюю неделю', callback_data='export_week'))
    keyboard.add(InlineKeyboardButton('Отчет за последний месяц', callback_data='export_month'))
    keyboard.add(InlineKeyboardButton('Полный отчет', callback_data='export_full'))
    keyboard.add(InlineKeyboardButton('Назад', callback_data='analytics'))

    await bot.edit_message_text(
        "📊 *Экспорт отчетов*\n\n"
        "Выберите период для экспорта статистики:",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

@dp.callback_query_handler(lambda c: c.data.startswith('export_'), state=BotStates.analytics_menu)
async def export_report(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    period = callback_query.data.replace('export_', '')

    if period == 'week':
        period_name = "последняя неделя"
        days = 7
    elif period == 'month':
        period_name = "последний месяц"
        days = 30
    else:  # full
        period_name = "все время"
        days = None

    # Генерация отчета
    report_path = await analytics_manager.generate_report(
        user_id=callback_query.from_user.id,
        days=days
    )

    # Отправка файла отчета пользователю
    with open(report_path, 'rb') as report_file:
        await bot.send_document(
            chat_id=callback_query.message.chat.id,
            document=InputFile(report_file, filename=f"report_{period}.xlsx"),
            caption=f"📊 Отчет по статистике за {period_name}"
        )

    # Удаление временного файла
    os.remove(report_path)

    # Возвращаемся в меню аналитики
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Назад в меню аналитики', callback_data='analytics'))

    await bot.send_message(
        callback_query.message.chat.id,
        "✅ Отчет успешно экспортирован!",
        reply_markup=keyboard
    )

# Настройки пользователя
@dp.callback_query_handler(lambda c: c.data == 'settings', state='*')
async def user_settings_menu(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    # Получение текущих настроек пользователя
    user_id = callback_query.from_user.id
    user_settings = await user_manager.get_user_settings(user_id)

    # Формирование текста с настройками
    notifications_status = "Включены" if user_settings.get('notifications', True) else "Отключены"
    lang = user_settings.get('language', 'Русский')

    settings_text = (
        "⚙️ *Настройки пользователя*\n\n"
        f"🔔 Уведомления: {notifications_status}\n"
        f"🌐 Язык: {lang}\n\n"
        "Выберите настройку для изменения:"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Управление уведомлениями', callback_data='manage_notifications'))
    keyboard.add(InlineKeyboardButton('Изменить язык', callback_data='change_language'))
    keyboard.add(InlineKeyboardButton('Подключение аккаунтов', callback_data='manage_accounts'))
    keyboard.add(InlineKeyboardButton('Настройки медиа', callback_data='media_settings'))
    keyboard.add(InlineKeyboardButton('Назад', callback_data='back_to_main'))

    await bot.edit_message_text(
        settings_text,
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    await BotStates.user_settings.set()

@dp.callback_query_handler(lambda c: c.data == 'manage_notifications', state=BotStates.user_settings)
async def manage_notifications(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    # Получение текущих настроек уведомлений
    user_id = callback_query.from_user.id
    user_settings = await user_manager.get_user_settings(user_id)

    notifications = user_settings.get('notifications', {})
    post_published = notifications.get('post_published', True)
    analytics_update = notifications.get('analytics_update', True)
    scheduled_reminder = notifications.get('scheduled_reminder', True)

    notification_text = (
        "🔔 *Управление уведомлениями*\n\n"
        "Настройте типы уведомлений, которые вы хотите получать:"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(
        f"{'✅' if post_published else '❌'} Публикация постов",
        callback_data='toggle_notif_published'
    ))
    keyboard.add(InlineKeyboardButton(
        f"{'✅' if analytics_update else '❌'} Обновление аналитики",
        callback_data='toggle_notif_analytics'
    ))
    keyboard.add(InlineKeyboardButton(
        f"{'✅' if scheduled_reminder else '❌'} Напоминания о запланированных постах",
        callback_data='toggle_notif_scheduled'
    ))
    keyboard.add(InlineKeyboardButton('Отключить все уведомления', callback_data='disable_all_notif'))
    keyboard.add(InlineKeyboardButton('Включить все уведомления', callback_data='enable_all_notif'))
    keyboard.add(InlineKeyboardButton('Назад', callback_data='settings'))

    await bot.edit_message_text(
        notification_text,
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

@dp.callback_query_handler(lambda c: c.data.startswith('toggle_notif_'), state=BotStates.user_settings)
async def toggle_notification(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    notif_type = callback_query.data.replace('toggle_notif_', '')

    # Получение текущих настроек уведомлений
    user_id = callback_query.from_user.id
    user_settings = await user_manager.get_user_settings(user_id)

    # Инициализация структуры, если она отсутствует
    if 'notifications' not in user_settings:
        user_settings['notifications'] = {}

    # Переключение состояния конкретного типа уведомлений
    current_value = user_settings['notifications'].get(notif_type, True)
    user_settings['notifications'][notif_type] = not current_value

    # Сохранение обновленных настроек
    await user_manager.update_user_settings(user_id, user_settings)

    # Обновление меню уведомлений
    await manage_notifications(callback_query, state)

@dp.callback_query_handler(lambda c: c.data == 'disable_all_notif', state=BotStates.user_settings)
async def disable_all_notifications(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    # Получение текущих настроек
    user_id = callback_query.from_user.id
    user_settings = await user_manager.get_user_settings(user_id)

    # Отключение всех уведомлений
    user_settings['notifications'] = {
        'post_published': False,
        'analytics_update': False,
        'scheduled_reminder': False
    }

    # Сохранение обновленных настроек
    await user_manager.update_user_settings(user_id, user_settings)

    # Обновление меню уведомлений
    await manage_notifications(callback_query, state)

@dp.callback_query_handler(lambda c: c.data == 'enable_all_notif', state=BotStates.user_settings)
async def enable_all_notifications(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    # Получение текущих настроек
    user_id = callback_query.from_user.id
    user_settings = await user_manager.get_user_settings(user_id)

    # Включение всех уведомлений
    user_settings['notifications'] = {
        'post_published': True,
        'analytics_update': True,
        'scheduled_reminder': True
    }

    # Сохранение обновленных настроек
    await user_manager.update_user_settings(user_id, user_settings)

    # Обновление меню уведомлений
    await manage_notifications(callback_query, state)

@dp.callback_query_handler(lambda c: c.data == 'manage_accounts', state=BotStates.user_settings)
async def manage_accounts(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    # Получение подключенных аккаунтов пользователя
    user_id = callback_query.from_user.id
    accounts = await user_manager.get_connected_accounts(user_id)

    vk_status = "✅ Подключен" if accounts.get('vk') else "❌ Не подключен"
    telegram_status = "✅ Подключен" if accounts.get('telegram') else "❌ Не подключен"
    website_status = "❌ Недоступно"

    accounts_text = (
        "🔗 *Управление подключенными аккаунтами*\n\n"
        f"ВКонтакте: {vk_status}\n"
        f"Telegram: {telegram_status}\n"
        f"Сайт: {website_status}\n\n"
        "Выберите платформу для настройки:"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Настройка ВКонтакте', callback_data='setup_vk'))
    keyboard.add(InlineKeyboardButton('Настройка Telegram', callback_data='setup_telegram'))
    keyboard.add(InlineKeyboardButton('Назад', callback_data='settings'))

    await bot.edit_message_text(
        accounts_text,
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

@dp.callback_query_handler(lambda c: c.data == 'setup_vk', state=BotStates.user_settings)
async def setup_vk_account(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Получить токен ВКонтакте', url='https://vk.com/dev/implicit_flow_user'))
    keyboard.add(InlineKeyboardButton('Ввести токен', callback_data='enter_vk_token'))
    keyboard.add(InlineKeyboardButton('Назад', callback_data='manage_accounts'))

    await bot.edit_message_text(
        "🔑 *Настройка аккаунта ВКонтакте*\n\n"
        "Для публикации постов в ВКонтакте необходимо получить токен доступа API.\n\n"
        "1. Нажмите кнопку 'Получить токен ВКонтакте'\n"
        "2. Авторизуйтесь в ВКонтакте, если потребуется\n"
        "3. Разрешите доступ приложению\n"
        "4. Скопируйте токен из адресной строки (параметр access_token)\n"
        "5. Вернитесь в бот и нажмите 'Ввести токен'\n\n"
        "⚠️ Токен должен иметь права на доступ к wall, photos, video и docs",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

# Функции для административного меню (управление пользователями)
@dp.callback_query_handler(lambda c: c.data == 'manage_users', state='*')
async def admin_manage_users(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    # Проверка прав администратора
    if not await is_admin(callback_query.from_user.id):
        await bot.answer_callback_query(
            callback_query.id,
            "У вас нет прав для доступа к этому разделу.",
            show_alert=True
        )
        return

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Список пользователей', callback_data='list_users'))
    keyboard.add(InlineKeyboardButton('Добавить администратора', callback_data='add_admin'))
    keyboard.add(InlineKeyboardButton('Журнал действий', callback_data='action_log'))
    keyboard.add(InlineKeyboardButton('Настройки доступа', callback_data='access_settings'))
    keyboard.add(InlineKeyboardButton('Назад', callback_data='back_to_main'))

    await bot.edit_message_text(
        "👥 *Управление пользователями*\n\n"
        "Выберите действие для управления пользователями бота:",
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    await BotStates.admin_menu.set()

@dp.callback_query_handler(lambda c: c.data == 'list_users', state=BotStates.admin_menu)
async def list_users(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    # Получение списка пользователей
    users = await user_manager.get_all_users(limit=20)

    if not users:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton('Назад', callback_data='manage_users'))

        await bot.edit_message_text(
            "👥 *Список пользователей*\n\n"
            "В системе еще нет зарегистрированных пользователей.",
            callback_query.message.chat.id,
            callback_query.message.message_id,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Формирование списка пользователей
    users_text = "👥 *Список пользователей*\n\n"

    for user in users:
        admin_mark = "👑 " if user.get('is_admin') else ""
        users_text += f"{admin_mark}ID: {user['id']} | {user.get('username', 'Нет имени')} | {user.get('created_at')}\n"

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('Управление правами', callback_data='manage_permissions'))
    keyboard.add(InlineKeyboardButton('Назад', callback_data='manage_users'))

    await bot.edit_message_text(
        users_text,
        callback_query.message.chat.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

# Обработчик для возврата в главное меню
@dp.callback_query_handler(lambda c: c.data == 'back_to_main', state='*')
async def back_to_main_menu(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)

    # Очистка состояния и возврат в главное меню
    await state.finish()
    await BotStates.main_menu.set()

    # Отображение главного меню
    welcome_text = (
        "👋 Добро пожаловать в бот для кросс-постинга!\n\n"
        "С моей помощью вы можете публиковать контент в ВКонтакте, Telegram и на ваш сайт.\n\n"
        "Выберите действие из меню ниже:"
    )

    try:
        keyboard = await get_main_menu(callback_query.from_user.id)
        await bot.edit_message_text(
            welcome_text,
            callback_query.message.chat.id,
            callback_query.message.message_id,
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при отображении главного меню: {e}")
        # В случае ошибки, отправляем новое сообщение
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton('📝 Создать пост', callback_data='create_post'))
        keyboard.add(InlineKeyboardButton('📅 Планирование', callback_data='schedule'))
        keyboard.add(InlineKeyboardButton('📊 Аналитика', callback_data='analytics'))
        keyboard.add(InlineKeyboardButton('⚙️ Настройки', callback_data='settings'))

        await bot.send_message(
            callback_query.message.chat.id,
            welcome_text,
            reply_markup=keyboard
        )

# Запуск бота
if __name__ == '__main__':
    # Инициализация базы данных
    loop = asyncio.get_event_loop()
    loop.run_until_complete(db_manager.init_db())

    # Запуск планировщика
    loop.run_until_complete(scheduler_manager.start())

    # Запуск бота
    executor.start_polling(dp, skip_updates=True)
