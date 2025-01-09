import asyncio
import logging
import os
import re


from aiogram import types, Router
from aiogram.filters.command import Command
from aiogram.types import FSInputFile, CallbackQuery
from pytubefix import YouTube
from pytubefix.cli import on_progress
from aiogram_dialog import Dialog, DialogManager, StartMode, Window
from aiogram.filters.state import State, StatesGroup
from aiogram_dialog.widgets.kbd import Button, Row
from aiogram_dialog.widgets.text import Const
from aiogram_dialog import setup_dialogs

from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import Row
from aiogram_dialog.widgets.text import Const
from admin.core import log_download

# from media_converter.audio_converter import convert_audio
from media_converter.async_audio_converter import async_convert_audio
from media_converter.async_movie_editor import video_size_reducer_async


# from youtube_downloader.download_media import download_media


os.environ['PYDEVD_WARN_SLOW_RESOLVE_TIMEOUT'] = '15'

MAX_FILE_SIZE = 30 * 1000 * 1000  # 50 МБ

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MySG(StatesGroup):
    choose_action = State()
    choose_media_type = State()  # Новый стейт для выбора медиа типа

download_router = Router()
setup_dialogs(download_router)


# Регулярка для проверки ссылок
url_pattern = re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be|tiktok\.com|instagram\.com)/[\w\-\.]+")


# Хэндлер для обработки текстового сообщения с ссылкой на видео
@download_router.message(lambda message: url_pattern.match(message.text))
async def download_video_handler(message: types.Message, dialog_manager: DialogManager):
    url = message.text
    if 'youtube.com' in url or 'youtu.be' in url:
        try:
            yt = YouTube(url, on_progress_callback=on_progress)
            logger.info(f"Получаем информацию о видео: {yt.title}, видео id: {yt.video_id}")


            await dialog_manager.start(MySG.choose_media_type, mode=StartMode.RESET_STACK, data={"url": url, "title": yt.title})
        except Exception as e:
            logger.error(f"Ошибка при обработке видео по URL {url}: {e}")
            await message.reply(f"Произошла ошибка: {str(e)}")
    else:
        logger.warning(f"Неправильная ссылка от пользователя {message.from_user.id}: {url}")
        await message.reply("Пожалуйста, отправьте действующую ссылку на YouTube.")

# Функция для скачивания и отправки видео
async def download_and_send_video(message: types.Message, stream):
    try:
        logger.info(f"Начинается загрузка видео {stream.default_filename}.")
        filepath = await asyncio.to_thread(stream.download, filename=stream.default_filename.replace('/', '').replace('*', ''))
        logger.info(f"Видео {stream.default_filename} успешно загружено.")

        await video_size_reducer_async(filepath, MAX_FILE_SIZE)
        
        input_file = FSInputFile(filepath)
        print(f"input_file: {input_file}")
        # await message.bot
        await message.bot.send_document(message.chat.id, input_file)
        os.remove(filepath)  # Удаляем файл после отправки
        logger.info(f"Видео {stream.default_filename} отправлено и удалено с диска.")

    except Exception as e:
        logger.error(f"Ошибка при загрузке или отправке видео: {e}")
        await message.reply(f"Произошла ошибка при отправке видео: {str(e)}")

# Функция для скачивания и отправки аудио
async def download_and_send_audio(message: types.Message, stream):
    try:
        logger.info(f"Начинается загрузка аудио {stream.default_filename}.")
        filepath = await asyncio.to_thread(stream.download, filename=stream.default_filename.replace('/', '').replace('*', ''))
        logger.info(f"Аудио {stream.default_filename} успешно загружено.")

        # Меняем расширение с mp4 на mp3
        # new_filepath = os.path.splitext(filepath)[0] + ".mp3"

        new_filepath = await async_convert_audio(filepath, 'mp3')
        # Переименовываем файл
        # os.rename(filepath, new_filepath)
        
        input_file = FSInputFile(new_filepath)
        await message.bot.send_document(message.chat.id, input_file)
        os.remove(new_filepath)  # Удаляем файл после отправки
        logger.info(f"Аудио {stream.default_filename} отправлено и удалено с диска.")

    except Exception as e:
        logger.error(f"Ошибка при загрузке или отправке аудио: {e}")
        await message.reply(f"Произошла ошибка при отправке аудио: {str(e)}")

# Хэндлер для выбора видео
async def on_choose_video(c: CallbackQuery, button: Button, dialog_manager: DialogManager):
    url = dialog_manager.start_data["url"]
    user_id = c.from_user.id
    username = c.from_user.username
    dialog_manager.dialog_data['media_type'] = 'video'

    logger.info(f"Видео получено в обработку")

    try:
        yt = YouTube(url, on_progress_callback=on_progress)
        stream = yt.streams.get_highest_resolution()

        logger.info(log_download(user_id=user_id, username=username, media_type='video', url=url, title=yt.title, filesize=stream.filesize))

        logger.info(f"Видео {stream.default_filename} обрабатывается")
        if stream.filesize > MAX_FILE_SIZE:
            # await dialog_manager.start(MySG.choose_action, data={"url": url, "title": yt.title})
            await dialog_manager.switch_to(MySG.choose_action)
        else:
            await download_and_send_video(c.message, stream)
    except Exception as e:
        logger.error(f"Ошибка при обработке видео: {e}")
        await c.message.reply(f"Произошла ошибка при скачивании видео: {str(e)}")
    await dialog_manager.done()

# Хэндлер для выбора аудио
async def on_choose_audio(c: CallbackQuery, button: Button, dialog_manager: DialogManager):
    url = dialog_manager.start_data["url"]
    user_id = c.from_user.id
    username = c.from_user.username

    logger.info(f"Аудио получено в обработку")
    try:
        yt = YouTube(url, on_progress_callback=on_progress)
        stream = yt.streams.get_audio_only()

        logger.info(log_download(user_id=user_id, username=username, media_type='audio', url=url, title=yt.title, filesize=stream.filesize))

        await download_and_send_audio(c.message, stream)
    except Exception as e:
        logger.error(f"Ошибка при обработке аудио: {e}")
        await c.message.reply(f"Произошла ошибка при скачивании аудио: {str(e)}")
    await dialog_manager.done()

# Хэндлер для выбора действия при большом файле
async def on_choose_lower_quality(c: CallbackQuery, button: Button, dialog_manager: DialogManager):
    url = dialog_manager.start_data["url"]
    user_id = c.from_user.id
    username = c.from_user.username
    yt = YouTube(url, on_progress_callback=on_progress)
    stream = yt.streams.get_by_resolution(360)
    
    logger.info(log_download(user_id=user_id, username=username, media_type='video_low', url=url, title=yt.title, filesize=stream.filesize))

    await download_and_send_video(c.message, stream)
    await dialog_manager.done()


dialog = Dialog(
    Window(
        Const("Что вы хотите скачать?"),
        Row(
            Button(Const("Видео"), id="video", on_click=on_choose_video),
            Button(Const("Аудио"), id="audio", on_click=on_choose_audio),
        ),
        state=MySG.choose_media_type,
    ),
    Window(
        Const("Видео слишком большое для отправки. Что вы хотите сделать?"),
        Row(
            Button(Const("Снизить качество"), id="lower_quality", on_click=on_choose_lower_quality),
            Button(Const("Только аудио"), id="audio", on_click=on_choose_audio),
        ),
        state=MySG.choose_action,
    ),
)

download_router.include_router(dialog)
setup_dialogs(download_router)