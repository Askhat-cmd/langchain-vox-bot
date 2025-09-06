#!/usr/bin/env python3
"""
Тест ARI playback для проверки исправлений
"""

import asyncio
import aiohttp
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_ari_playback():
    """Тестирует ARI playback с существующим звуком"""
    
    # Подключаемся к ARI
    base_url = "http://localhost:8088/ari"
    auth = aiohttp.BasicAuth("asterisk", "asterisk123")
    
    async with aiohttp.ClientSession(auth=auth) as session:
        try:
            # 1. Получаем список активных каналов
            logger.info("🔍 Проверяем активные каналы...")
            async with session.get(f"{base_url}/channels") as response:
                channels = await response.json()
                logger.info(f"📞 Активных каналов: {len(channels)}")
                
                if not channels:
                    logger.warning("⚠️ Нет активных каналов для тестирования")
                    return
                
                # Берем первый канал
                channel_id = channels[0]['id']
                logger.info(f"🎯 Тестируем на канале: {channel_id}")
            
            # 2. Тестируем проигрывание существующего звука
            logger.info("🔊 Тестируем проигрывание demo-congrats...")
            url = f"{base_url}/channels/{channel_id}/play"
            data = {"media": "sound:demo-congrats"}
            
            async with session.post(url, json=data) as response:
                response_text = await response.text()
                logger.info(f"🔍 ARI Response: status={response.status}, body={response_text}")
                
                if response.status in (200, 201, 202):
                    logger.info("✅ Проигрывание запущено успешно!")
                    
                    # Ждем немного и проверяем статус
                    await asyncio.sleep(2)
                    
                    # Получаем информацию о канале
                    async with session.get(f"{base_url}/channels/{channel_id}") as response:
                        channel_info = await response.json()
                        logger.info(f"📊 Статус канала: {channel_info.get('state')}")
                        
                else:
                    logger.error(f"❌ Ошибка проигрывания: {response.status} - {response_text}")
            
            # 3. Тестируем проигрывание с новым форматом (без ru/)
            logger.info("🔊 Тестируем новый формат media URI...")
            data = {"media": "sound:demo-congrats"}  # Без ru/
            
            async with session.post(url, json=data) as response:
                response_text = await response.text()
                logger.info(f"🔍 ARI Response (новый формат): status={response.status}, body={response_text}")
                
                if response.status in (200, 201, 202):
                    logger.info("✅ Новый формат работает!")
                else:
                    logger.error(f"❌ Новый формат не работает: {response.status} - {response_text}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка тестирования: {e}")

if __name__ == "__main__":
    asyncio.run(test_ari_playback())