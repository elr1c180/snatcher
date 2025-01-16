import asyncio
import logging
import os
import re
import io

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

from yandexcloud import SDK
import boto3

BUCKET_NAME = "elr1ccloud"
ACCESS_KEY = "YCAJEWCBdEtl0jRBvNo2gNtUF"  # Ваш новый Access Key
SECRET_KEY = "YCPdvq53hOPfTN0nGSpiOFIPCehpdGrFwtiaitnl"  # Ваш новый Secret Key
ENDPOINT = "https://storage.yandexcloud.net"
# from youtube_downloader.download_media import download_media

session = boto3.session.Session()
s3 = session.client(
    service_name='s3',
    endpoint_url=ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY
)

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

def get_presigned_url(file_name):
    """Получение подписанной ссылки на объект в бакете."""
    try:
        # Получение подписанной ссылки на объект
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': file_name},
            ExpiresIn=3600  # Время действия ссылки в секундах
        )
        return url
    except Exception as e:
        logger.error(f"Ошибка получения подписанной ссылки: {e}")
        return None

# Функция для загрузки в Яндекс Облако
async def upload_to_yandex(buffer, file_name):
    try:
        # Перемещаемся в начало буфера перед отправкой
        buffer.seek(0)

        # Загружаем файл в бакет с использованием boto3
        s3.put_object(Bucket=BUCKET_NAME, Key=file_name, Body=buffer)

        # Формируем публичную ссылку
        public_url = get_presigned_url(file_name)
        
        if not public_url:
            logger.error(f"Не удалось получить подписанную ссылку для файла: {file_name}")
            return None
        
        return public_url
    except Exception as e:
        logger.error(f"Ошибка при загрузке в Яндекс Облако: {e}")
        return None
    
async def download_and_send_video(message: types.Message, yt_stream):
    try:
        # Создаем буфер для потока данных
        buffer = io.BytesIO()

        # Скачиваем видео в память, записывая в буфер
        yt_stream.stream_to_buffer(buffer)

        # Загружаем файл в Яндекс Cloud
        file_name = f"{yt_stream.title}.mp4"  # Можно изменить имя файла
        public_url = await upload_to_yandex(buffer, file_name)
        
        if public_url:
            await message.reply(f"Ваше видео доступно по ссылке: {public_url}")
        else:
            await message.reply("Произошла ошибка при загрузке файла в облако.")
    except Exception as e:
        logger.error(f"Произошла ошибка при обработке видео: {str(e)}")
        await message.reply(f"Произошла ошибка при обработке видео: {str(e)}")



# Функция для скачивания и отправки аудио
async def download_and_send_audio(message, url):
    try:
        yt = YouTube(url, on_progress_callback=on_progress)
        stream = yt.streams.get_highest_resolution()

        # Создаем буфер для потока данных
        buffer = io.BytesIO()

        # Скачиваем видео в память, записывая в буфер
        stream.stream_to_buffer(buffer)

        # Получаем данные из буфера
        buffer.seek(0)  # Перемещаемся в начало буфера, чтобы прочитать его содержимое

        # Загружаем файл в Yandex Cloud
        file_name = f"{stream.title}.mp3"  # Можно изменить имя файла
        public_url = upload_to_yandex(buffer, file_name)
        
        if public_url:
            await message.reply(f"Ваше видео доступно по ссылке: {public_url}")
        else:
            await message.reply("Произошла ошибка при загрузке файла в облако.")
    except Exception as e:
        await message.reply(f"Произошла ошибка при обработке аудио: {str(e)}")

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
        # if stream.filesize > MAX_FILE_SIZE:
        #     # await dialog_manager.start(MySG.choose_action, data={"url": url, "title": yt.title})
        #     print('123123123123 оч много')
        #     await dialog_manager.switch_to(MySG.choose_action)
        # else:

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