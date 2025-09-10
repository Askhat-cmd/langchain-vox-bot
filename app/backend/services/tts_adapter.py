"""
TTS Adapter - Умный адаптер с автоматическим fallback
Архитектурное решение для достижения 1.1 секунды ответа
"""

import asyncio
import time
import logging
from typing import Optional, Dict, Any

from .yandex_grpc_tts import YandexGrpcTTS
from .yandex_tts_service import YandexTTSService

logger = logging.getLogger(__name__)

class TTSAdapter:
    """
    Умный TTS адаптер с автоматическим fallback
    - Primary: gRPC TTS (быстрый, <250мс)
    - Fallback: HTTP TTS (надежный, 700мс)
    """
    
    def __init__(self):
        self.grpc_tts = YandexGrpcTTS()
        self.http_tts = YandexTTSService()  # Существующий HTTP TTS
        self.grpc_healthy = True
        self.fallback_count = 0
        self.success_count = 0
        
        # Метрики для мониторинга
        self.metrics = {
            "grpc_success_count": 0,
            "grpc_error_count": 0,
            "http_fallback_count": 0,
            "grpc_latency_sum": 0,
            "grpc_latency_count": 0
        }
        
        logger.info("🚀 TTSAdapter инициализирован с gRPC + HTTP fallback")
        
    async def initialize(self):
        """Инициализация обоих TTS сервисов"""
        try:
            await self.grpc_tts.initialize()
            logger.info("✅ TTSAdapter initialized with gRPC + HTTP fallback")
        except Exception as e:
            logger.error(f"❌ gRPC TTS init failed: {e}")
            self.grpc_healthy = False
            logger.info("🔄 TTSAdapter будет использовать только HTTP TTS")
        
    async def synthesize(self, text: str) -> bytes:
        """
        Умный синтез с автоматическим fallback
        """
        if self.grpc_healthy:
            try:
                start_time = time.time()
                audio_data = await self.grpc_tts.synthesize_chunk_fast(text)
                elapsed = time.time() - start_time
                
                # Обновляем метрики
                self.metrics["grpc_success_count"] += 1
                self.metrics["grpc_latency_sum"] += elapsed
                self.metrics["grpc_latency_count"] += 1
                self.success_count += 1
                
                # Периодически проверяем здоровье gRPC
                if self.success_count % 10 == 0:
                    await self._check_grpc_health()
                
                logger.info(f"✅ gRPC TTS success: {elapsed:.2f}s")
                return audio_data
                
            except Exception as e:
                logger.warning(f"gRPC TTS failed: {e}, falling back to HTTP")
                self.grpc_healthy = False
                self.metrics["grpc_error_count"] += 1
                self.fallback_count += 1
                self.metrics["http_fallback_count"] += 1
                
                # Fallback на HTTP TTS
                return await self._http_fallback(text)
        else:
            # Используем HTTP TTS
            return await self._http_fallback(text)
    
    async def _http_fallback(self, text: str) -> bytes:
        """Fallback на HTTP TTS"""
        import os

        temp_dir = os.path.join(self.http_tts.asterisk_sounds_dir, "fallback_tmp")
        os.makedirs(temp_dir, exist_ok=True)

        original_dir = self.http_tts.asterisk_sounds_dir
        self.http_tts.asterisk_sounds_dir = temp_dir

        try:
            result = await self.http_tts.text_to_speech(text, "fallback")
            if result:
                wav_path = os.path.join(temp_dir, f"{result}.wav")
                if os.path.exists(wav_path):
                    try:
                        with open(wav_path, 'rb') as f:
                            audio_data = f.read()
                    except Exception as e:
                        logger.error(f"❌ Не удалось прочитать файл {wav_path}: {e}")
                        return b""

                    try:
                        os.remove(wav_path)
                    except Exception as e:
                        logger.error(f"❌ Не удалось удалить временный файл {wav_path}: {e}")
                    else:
                        if os.path.exists(wav_path):
                            logger.warning(f"⚠️ Временный файл не удалён: {wav_path}")
                    return audio_data
                else:
                    logger.error(f"❌ Сгенерированный файл не найден: {wav_path}")
            else:
                logger.error("❌ HTTP TTS не вернул результат")
            return b""
        except Exception as e:
            logger.error(f"❌ HTTP TTS fallback error: {e}")
            return b""
        finally:
            self.http_tts.asterisk_sounds_dir = original_dir
    
    async def _check_grpc_health(self):
        """Проверка здоровья gRPC соединения"""
        try:
            # Простой тест соединения
            test_audio = await self.grpc_tts.synthesize_chunk_fast("тест")
            if len(test_audio) > 0:
                self.grpc_healthy = True
                logger.info("✅ gRPC TTS health check passed")
        except Exception as e:
            logger.warning(f"gRPC TTS health check failed: {e}")
            self.grpc_healthy = False
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получение метрик производительности"""
        total_requests = (self.metrics["grpc_success_count"] + 
                         self.metrics["grpc_error_count"] + 
                         self.metrics["http_fallback_count"])
        
        grpc_success_rate = (self.metrics["grpc_success_count"] / total_requests 
                           if total_requests > 0 else 0)
        
        avg_grpc_latency = (self.metrics["grpc_latency_sum"] / self.metrics["grpc_latency_count"] 
                          if self.metrics["grpc_latency_count"] > 0 else 0)
        
        fallback_rate = (self.metrics["http_fallback_count"] / total_requests 
                        if total_requests > 0 else 0)
        
        return {
            "grpc_success_rate": grpc_success_rate,
            "avg_grpc_latency": avg_grpc_latency,
            "fallback_rate": fallback_rate,
            "grpc_healthy": self.grpc_healthy,
            "total_requests": total_requests
        }
    
    async def close(self):
        """Закрытие всех соединений"""
        if self.grpc_tts:
            await self.grpc_tts.close()
        logger.info("✅ TTSAdapter closed")

# Глобальный экземпляр адаптера
_tts_adapter = None

async def get_tts_adapter() -> TTSAdapter:
    """Фабрика для создания TTS адаптера"""
    global _tts_adapter
    if _tts_adapter is None:
        _tts_adapter = TTSAdapter()
        await _tts_adapter.initialize()
    return _tts_adapter

