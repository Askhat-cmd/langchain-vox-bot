"""
ASR (Automatic Speech Recognition) сервис для распознавания речи.
Использует OpenAI Whisper API для преобразования аудио в текст.
"""
import os
import logging
import aiohttp
import aiofiles
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class ASRService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY не установлен в переменных окружения")
        
        self.model = os.getenv("ASR_MODEL", "whisper-1")
        self.language = os.getenv("ASR_LANGUAGE", "ru")  # Язык для распознавания
        
        logger.info(f"ASR Service инициализирован: model={self.model}, language={self.language}")

    async def speech_to_text(self, audio_path: str, prompt: Optional[str] = None) -> str:
        """
        Преобразует аудио файл в текст.
        
        Args:
            audio_path: Путь к аудио файлу
            prompt: Дополнительный промпт для улучшения качества распознавания
            
        Returns:
            str: Распознанный текст
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Аудио файл не найден: {audio_path}")
        
        try:
            url = "https://api.openai.com/v1/audio/transcriptions"
            
            # Подготавливаем данные для multipart/form-data
            data = aiohttp.FormData()
            data.add_field('model', self.model)
            data.add_field('language', self.language)
            
            if prompt:
                data.add_field('prompt', prompt)
            
            # Добавляем аудио файл
            async with aiofiles.open(audio_path, 'rb') as f:
                audio_data = await f.read()
                data.add_field('file', audio_data, filename=os.path.basename(audio_path))
            
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            
            logger.info(f"Распознаем речь из файла: {audio_path}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        text = result.get('text', '').strip()
                        
                        logger.info(f"✅ Речь распознана: '{text}'")
                        return text
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Ошибка ASR API: {response.status} - {error_text}")
                        raise Exception(f"ASR API error: {response.status} - {error_text}")
                        
        except Exception as e:
            logger.error(f"❌ Ошибка при распознавании речи: {e}", exc_info=True)
            raise

    async def speech_to_text_with_translation(self, audio_path: str) -> str:
        """
        Преобразует аудио файл в текст с переводом на английский.
        Полезно для многоязычных аудио.
        
        Args:
            audio_path: Путь к аудио файлу
            
        Returns:
            str: Переведенный текст на английском
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Аудио файл не найден: {audio_path}")
        
        try:
            url = "https://api.openai.com/v1/audio/translations"
            
            # Подготавливаем данные для multipart/form-data
            data = aiohttp.FormData()
            data.add_field('model', self.model)
            
            # Добавляем аудио файл
            async with aiofiles.open(audio_path, 'rb') as f:
                audio_data = await f.read()
                data.add_field('file', audio_data, filename=os.path.basename(audio_path))
            
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            
            logger.info(f"Переводим речь из файла: {audio_path}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        text = result.get('text', '').strip()
                        
                        logger.info(f"✅ Речь переведена: '{text}'")
                        return text
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Ошибка перевода ASR API: {response.status} - {error_text}")
                        raise Exception(f"ASR translation API error: {response.status} - {error_text}")
                        
        except Exception as e:
            logger.error(f"❌ Ошибка при переводе речи: {e}", exc_info=True)
            raise

# Глобальный экземпляр сервиса
asr_service = None

def get_asr_service() -> ASRService:
    """Возвращает глобальный экземпляр ASR сервиса."""
    global asr_service
    if asr_service is None:
        asr_service = ASRService()
    return asr_service

# Тестирование
if __name__ == "__main__":
    import asyncio
    
    async def test_asr():
        service = ASRService()
        
        # Для тестирования нужен реальный аудио файл
        test_audio = "data/audio/test_greeting.wav"
        
        if os.path.exists(test_audio):
            try:
                text = await service.speech_to_text(test_audio)
                print(f"✅ Тест пройден! Распознанный текст: '{text}'")
            except Exception as e:
                print(f"❌ Тест не пройден: {e}")
        else:
            print(f"⚠️ Тестовый аудио файл не найден: {test_audio}")
    
    asyncio.run(test_asr())

