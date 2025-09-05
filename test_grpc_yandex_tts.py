#!/usr/bin/env python3
"""
Тест сверхбыстрого Yandex TTS с gRPC streaming
"""

import asyncio
import sys
import os
import time
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv('/root/Asterisk_bot/asterisk-vox-bot/.env')

# Добавляем путь к проекту
sys.path.insert(0, '/root/Asterisk_bot/asterisk-vox-bot')

from app.backend.services.yandex_tts_service import get_yandex_tts_service

async def test_grpc_tts():
    """Тестируем скорость gRPC TTS vs HTTP TTS"""
    
    print("🚀 Тестируем СВЕРХБЫСТРЫЙ Yandex TTS с gRPC streaming...")
    
    # Проверяем переменные окружения
    oauth_token = os.getenv("OAUTH_TOKEN")
    folder_id = os.getenv("YANDEX_FOLDER_ID")
    
    print(f"📋 OAUTH_TOKEN: {'✅ найден' if oauth_token else '❌ не найден'}")
    print(f"📋 YANDEX_FOLDER_ID: {'✅ найден' if folder_id else '❌ не найден'}")
    
    if not oauth_token or not folder_id:
        print("❌ Не найдены необходимые переменные окружения!")
        return
    
    # Получаем сервис
    tts_service = get_yandex_tts_service()
    
    # Тестовые фразы
    test_phrases = [
        "Привет! Это тест сверхбыстрого Yandex TTS.",
        "Сейчас мы проверяем скорость синтеза речи через gRPC.",
        "Ожидаемая задержка должна быть 1-1.5 секунды!"
    ]
    
    for i, phrase in enumerate(test_phrases):
        print(f"\n📝 Тест {i+1}: '{phrase}'")
        
        # Засекаем время
        start_time = time.time()
        
        try:
            # Вызываем TTS
            result = await tts_service.text_to_speech(phrase, f"grpc_test_{i+1}")
            
            end_time = time.time()
            duration = end_time - start_time
            
            if result:
                print(f"✅ TTS готов за {duration:.2f} секунд")
                print(f"📁 Файл: {result}")
                
                # Проверяем, что файл существует
                full_path = f"/usr/share/asterisk/sounds/ru/{result}.wav"
                if os.path.exists(full_path):
                    file_size = os.path.getsize(full_path)
                    print(f"📊 Размер файла: {file_size} байт")
                else:
                    print(f"❌ Файл не найден: {full_path}")
            else:
                print(f"❌ TTS неудачен за {duration:.2f} секунд")
                
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            print(f"❌ Ошибка за {duration:.2f} секунд: {e}")
    
    print("\n🎯 Тест завершен!")

if __name__ == "__main__":
    asyncio.run(test_grpc_tts())
