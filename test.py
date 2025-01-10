import boto3
import io
from pytubefix import YouTube
from pytubefix.cli import on_progress
import asyncio

BUCKET_NAME = "elr1ccloud"
ACCESS_KEY = "YCAJEWCBdEtl0jRBvNo2gNtUF"  
SECRET_KEY = "YCPdvq53hOPfTN0nGSpiOFIPCehpdGrFwtiaitnl"  
ENDPOINT = "https://storage.yandexcloud.net"

session = boto3.session.Session()
s3 = session.client(
    service_name='s3',
    endpoint_url=ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY
)

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
        print(f"Ошибка получения подписанной ссылки: {e}")
        return None

def upload_to_yandex(file_data, file_name):
    """Загрузка файла в Yandex Cloud и получение публичной ссылки"""
    try:
        # Загружаем файл в бакет
        s3.put_object(Bucket=BUCKET_NAME, Key=file_name, Body=file_data)

        # Получаем подписанную ссылку
        signed_url = get_presigned_url(file_name)

        return signed_url
    except Exception as e:
        print(f"Ошибка загрузки в Yandex.Cloud: {e}")
        return None

async def main():
    yt = YouTube('https://www.youtube.com/watch?v=HnPPMlCQVyE', on_progress_callback=on_progress)
    stream = yt.streams.get_highest_resolution()

    # Создаем буфер для потока данных
    buffer = io.BytesIO()

    # Скачиваем видео в память, записывая в буфер
    stream.stream_to_buffer(buffer)

    # Получаем данные из буфера
    buffer.seek(0)  # Перемещаемся в начало буфера, чтобы прочитать его содержимое

    # Загружаем файл в Yandex Cloud
    file_name = f"{stream.title}.mp4"  # Вы можете изменить имя файла
    public_url = upload_to_yandex(buffer, file_name)
    
    if public_url:
        print("Ссылка на файл после загрузки:", public_url)
    else:
        print("Произошла ошибка при загрузке файла в Yandex Cloud.")

if __name__ == "__main__":
    asyncio.run(main())
