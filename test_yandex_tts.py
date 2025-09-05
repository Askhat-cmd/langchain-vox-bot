#!/usr/bin/env python3
"""
Тестовый скрипт для проверки Yandex TTS
БЕЗОПАСНЫЙ ТЕСТ - не влияет на основную систему
"""
import asyncio
import sys
import os
from pathlib import Path

# Добавляем путь к модулям проекта
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.backend.services.yandex_tts_service import get_yandex_tts_service
from dotenv import load_dotenv

async def test_yandex_tts():
    """Тестируем Yandex TTS отдельно от основной системы."""
    
    # Загружаем переменные окружения
    load_dotenv()
    
    print("🧪 Тестируем Yandex TTS...")
    
    # Проверяем переменные окружения
    oauth_token = os.getenv("OAUTH_TOKEN")
    folder_id = os.getenv("YANDEX_FOLDER_ID")
    
    if not oauth_token:
        print("❌ OAUTH_TOKEN не найден в .env")
        return False
    
    if not folder_id:
        print("❌ YANDEX_FOLDER_ID не найден в .env")
        return False
    
    print(f"✅ OAuth токен: {oauth_token[:20]}...")
    print(f"✅ Folder ID: {folder_id}")
    
    # Инициализируем TTS сервис
    tts = get_yandex_tts_service()
    
    # Тестовый текст
    test_text = "Привет! Это тест Яндекс синтеза речи."
    test_filename = "yandex_test"
    
    print(f"🔊 Тестируем синтез: '{test_text}'")
    
    try:
        # Выполняем синтез
        result = await tts.text_to_speech(test_text, test_filename)
        
        if result:
            print(f"✅ Yandex TTS успешно! Файл: {result}.wav")
            
            # Проверяем, что файл создан
            wav_path = f"/usr/share/asterisk/sounds/ru/{result}.wav"
            if os.path.exists(wav_path):
                file_size = os.path.getsize(wav_path)
                print(f"✅ Файл создан: {wav_path} ({file_size} байт)")
                return True
            else:
                print(f"❌ Файл не найден: {wav_path}")
                return False
        else:
            print("❌ Yandex TTS вернул None")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_yandex_tts())
    if success:
        print("\n🎉 Yandex TTS готов к использованию!")
    else:
        print("\n💥 Yandex TTS требует доработки")
    
    sys.exit(0 if success else 1)
