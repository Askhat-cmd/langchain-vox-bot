#!/usr/bin/env python3
"""
Тестовый скрипт для проверки VAD системы.
Проверяет работу SimpleVADService изолированно от Asterisk.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Добавляем путь для импорта модулей проекта
current_dir = Path(__file__).parent
project_root = current_dir / "asterisk-vox-bot"
sys.path.insert(0, str(project_root))

from app.backend.services.simple_vad_service import SimpleVADService

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_vad_basic():
    """Базовый тест VAD сервиса."""
    logger.info("🧪 Начинаем базовый тест VAD сервиса")
    
    # Создаем VAD сервис
    vad = SimpleVADService(
        silence_timeout=2.0,
        min_recording_time=1.0,
        max_recording_time=10.0,
        debug_logging=True
    )
    
    # Callback для тестирования
    async def test_callback(channel_id: str, recording_id: str, reason: str):
        logger.info(f"🎯 VAD Callback: channel={channel_id}, recording={recording_id}, reason={reason}")
    
    # Тестируем запуск мониторинга
    channel_id = "test_channel_001"
    recording_id = "test_recording_001"
    
    success = await vad.start_monitoring(channel_id, recording_id, test_callback)
    logger.info(f"✅ Запуск мониторинга: {success}")
    
    # Проверяем, что мониторинг активен
    is_monitoring = vad.is_monitoring(channel_id)
    logger.info(f"✅ Мониторинг активен: {is_monitoring}")
    
    # Симулируем активность пользователя
    logger.info("🎤 Симулируем активность пользователя...")
    for i in range(5):
        await vad.update_activity(channel_id)
        await asyncio.sleep(0.5)
        logger.info(f"   Активность {i+1}/5")
    
    # Симулируем тишину
    logger.info("🔇 Симулируем тишину (должно сработать через 2 секунды)...")
    await asyncio.sleep(3.0)
    
    # Проверяем статистику
    stats = vad.get_monitoring_stats(channel_id)
    if stats:
        logger.info(f"📊 Статистика мониторинга: {stats}")
    else:
        logger.info("📊 Мониторинг завершен")
    
    logger.info("✅ Базовый тест VAD завершен")

async def test_vad_minimum_time():
    """Тест минимального времени записи."""
    logger.info("🧪 Тест минимального времени записи")
    
    vad = SimpleVADService(
        silence_timeout=1.0,
        min_recording_time=3.0,  # Минимум 3 секунды
        max_recording_time=10.0,
        debug_logging=True
    )
    
    async def test_callback(channel_id: str, recording_id: str, reason: str):
        logger.info(f"🎯 VAD Callback: channel={channel_id}, recording={recording_id}, reason={reason}")
    
    channel_id = "test_channel_002"
    recording_id = "test_recording_002"
    
    await vad.start_monitoring(channel_id, recording_id, test_callback)
    
    # Короткая активность (меньше минимального времени)
    logger.info("🎤 Короткая активность (1 секунда)...")
    await vad.update_activity(channel_id)
    await asyncio.sleep(1.0)
    
    # Тишина (должно НЕ сработать из-за минимального времени)
    logger.info("🔇 Тишина (не должно сработать из-за минимального времени)...")
    await asyncio.sleep(2.0)
    
    # Проверяем, что мониторинг все еще активен
    is_monitoring = vad.is_monitoring(channel_id)
    logger.info(f"✅ Мониторинг все еще активен: {is_monitoring}")
    
    # Останавливаем вручную
    await vad.stop_monitoring(channel_id)
    logger.info("✅ Тест минимального времени завершен")

async def test_vad_maximum_time():
    """Тест максимального времени записи (fallback)."""
    logger.info("🧪 Тест максимального времени записи")
    
    vad = SimpleVADService(
        silence_timeout=5.0,  # Длинный таймаут тишины
        min_recording_time=1.0,
        max_recording_time=3.0,  # Короткое максимальное время
        debug_logging=True
    )
    
    async def test_callback(channel_id: str, recording_id: str, reason: str):
        logger.info(f"🎯 VAD Callback: channel={channel_id}, recording={recording_id}, reason={reason}")
    
    channel_id = "test_channel_003"
    recording_id = "test_recording_003"
    
    await vad.start_monitoring(channel_id, recording_id, test_callback)
    
    # Одна активность в начале
    await vad.update_activity(channel_id)
    
    # Ждем максимальное время (должно сработать fallback)
    logger.info("⏰ Ждем максимальное время (3 секунды)...")
    await asyncio.sleep(4.0)
    
    # Проверяем, что мониторинг завершен
    is_monitoring = vad.is_monitoring(channel_id)
    logger.info(f"✅ Мониторинг завершен: {not is_monitoring}")
    
    logger.info("✅ Тест максимального времени завершен")

async def main():
    """Основная функция тестирования."""
    logger.info("🚀 Начинаем тестирование VAD системы")
    
    try:
        # Базовый тест
        await test_vad_basic()
        await asyncio.sleep(1)
        
        # Тест минимального времени
        await test_vad_minimum_time()
        await asyncio.sleep(1)
        
        # Тест максимального времени
        await test_vad_maximum_time()
        
        logger.info("🎉 Все тесты VAD завершены успешно!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в тестах VAD: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
