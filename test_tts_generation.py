#!/usr/bin/env python3
"""
Тест генерации TTS файлов с новым ulaw форматом
"""

import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv('/root/Asterisk_bot/asterisk-vox-bot/.env')

# Добавляем путь к проекту
sys.path.insert(0, '/root/Asterisk_bot/asterisk-vox-bot')

from app.backend.services.yandex_tts_service import get_yandex_tts_service

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_tts_generation():
    """Тестирует генерацию TTS файлов с новым ulaw форматом"""
    
    try:
        # Инициализируем TTS сервис
        logger.info("🚀 Инициализируем Yandex TTS сервис...")
        tts_service = get_yandex_tts_service()
        
        # Тестовый текст
        test_text = "Привет! Это тест нового формата звука."
        logger.info(f"🎤 Генерируем TTS для текста: '{test_text}'")
        
        # Генерируем TTS
        filename = await tts_service.text_to_speech(test_text, "test_ulaw")
        
        if filename:
            logger.info(f"✅ TTS файл создан: {filename}")
            
            # Проверяем, что файл существует
            full_path = f"/var/lib/asterisk/sounds/ru/{filename}.ulaw"
            if os.path.exists(full_path):
                logger.info(f"✅ ulaw файл найден: {full_path}")
                
                # Проверяем права доступа
                import stat
                file_stat = os.stat(full_path)
                logger.info(f"📊 Права доступа: {stat.filemode(file_stat.st_mode)}")
                logger.info(f"📊 Владелец: {file_stat.st_uid}:{file_stat.st_gid}")
                
                # Проверяем размер файла
                file_size = os.path.getsize(full_path)
                logger.info(f"📊 Размер файла: {file_size} байт")
                
                return True
            else:
                logger.error(f"❌ ulaw файл не найден: {full_path}")
                return False
        else:
            logger.error("❌ Не удалось создать TTS файл")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования TTS: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_tts_generation())
    if success:
        print("🎉 Тест TTS генерации прошел успешно!")
    else:
        print("❌ Тест TTS генерации не прошел!")
