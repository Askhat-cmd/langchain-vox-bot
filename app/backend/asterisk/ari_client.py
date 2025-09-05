import aiohttp
import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class AsteriskARIClient:
    def __init__(self, host="localhost", port=8088, username="asterisk", password="asterisk123"):
        self.base_url = f"http://{host}:{port}/ari"
        self.auth = aiohttp.BasicAuth(username, password)
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(auth=self.auth)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def answer_channel(self, channel_id):
        try:
            url = f"{self.base_url}/channels/{channel_id}/answer"
            async with self.session.post(url) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"Error answering channel {channel_id}: {e}")
            return False
    
    async def play_sound(self, channel_id, sound_id, lang: Optional[str] = None):
        """
        Проигрывает звуковой файл на канале.

        Args:
            channel_id: ID канала
            sound_id: Имя звукового файла (без расширения)
            lang: Язык (папка в sounds/). ``None`` — использовать язык канала
        """
        try:
            url = f"{self.base_url}/channels/{channel_id}/play"
            # Формат: sound:<lang>/filename или sound:filename если язык не указан
            media = f"sound:{lang}/{sound_id}" if lang else f"sound:{sound_id}"
            data = {"media": media}
            
            logger.info(f"Проигрываем звук: {media} на канале {channel_id}")
            
            async with self.session.post(url, json=data) as response:
                # ARI может возвращать 200 OK или 201 Created/202 Accepted при успешном создании playback
                if response.status in (200, 201, 202):
                    try:
                        result = await response.json()
                        playback_id = result.get('id')
                    except Exception:
                        playback_id = None
                    logger.info(f"✅ Проигрывание принято ARI (status={response.status}), playback_id={playback_id}")
                    return playback_id or True
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Ошибка проигрывания: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Ошибка при проигрывании звука: {e}")
            return None

    async def start_recording(self, channel_id, filename, max_duration=15):
        """
        Запускает запись с канала.
        
        Args:
            channel_id: ID канала
            filename: Имя файла для записи (без расширения)
            max_duration: Максимальная длительность в секундах
        """
        try:
            url = f"{self.base_url}/channels/{channel_id}/record"
            data = {
                "name": filename,
                "format": "wav",
                "maxDurationSeconds": max_duration,
                "beep": False,
                "terminateOn": "#",  # Завершить запись по нажатию #
                "ifExists": "overwrite"
            }
            
            logger.info(f"Запускаем запись: {filename} на канале {channel_id}")
            
            async with self.session.post(url, json=data) as response:
                # ARI может возвращать 200 OK или 201 Created при успешном создании записи
                if response.status in (200, 201):
                    result = await response.json()
                    recording_id = result.get('name')
                    logger.info(f"✅ Запись запущена: {recording_id}")
                    return recording_id
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Ошибка запуска записи: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Ошибка при запуске записи: {e}")
            return None

    async def stop_recording(self, recording_id):
        """Останавливает запись."""
        try:
            url = f"{self.base_url}/recordings/live/{recording_id}/stop"
            async with self.session.post(url) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"❌ Ошибка остановки записи: {e}")
            return False

    async def hold_channel(self, channel_id):
        """Удерживает канал - пользователь не может повесить трубку."""
        try:
            url = f"{self.base_url}/channels/{channel_id}/hold"
            async with self.session.post(url) as response:
                if response.status in (200, 201):
                    logger.info(f"✅ Канал {channel_id} удержан")
                    return True
                else:
                    error_text = await response.text()
                    logger.warning(f"⚠️ Не удалось удержать канал {channel_id}: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"❌ Ошибка удержания канала {channel_id}: {e}")
            return False

    async def hangup_channel(self, channel_id):
        """Завершает звонок."""
        try:
            url = f"{self.base_url}/channels/{channel_id}"
            async with self.session.delete(url) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"❌ Ошибка завершения звонка: {e}")
            return False

if __name__ == "__main__":
    async def test():
        async with AsteriskARIClient() as ari:
            url = f"{ari.base_url}/asterisk/info"
            async with ari.session.get(url) as response:
                if response.status == 200:
                    print("ARI connection successful!")
                else:
                    print(f"ARI connection failed: {response.status}")
    
    asyncio.run(test())