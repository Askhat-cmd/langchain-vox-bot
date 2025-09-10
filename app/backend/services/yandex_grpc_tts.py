"""
Yandex gRPC TTS Service - Оптимизированная реализация
Часть архитектуры TTSAdapter для достижения 1.1 секунды ответа
"""

import os
import sys
import grpc
import asyncio
import time
import logging
from typing import Optional

# Добавляем путь к gRPC файлам
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from yandex.cloud.ai.tts.v3 import tts_service_pb2_grpc
    from yandex.cloud.ai.tts.v3 import tts_pb2
    GRPC_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✅ gRPC модули для Yandex TTS загружены")
except ImportError as e:
    GRPC_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️ gRPC модули недоступны: {e}")

class YandexGrpcTTS:
    """
    Оптимизированный gRPC TTS сервис для минимальной латентности
    Цель: <250мс вместо 700мс HTTP TTS
    """
    
    def __init__(self):
        self.api_key = os.getenv("OAUTH_TOKEN")  # Используем OAUTH_TOKEN
        self.folder_id = os.getenv("YANDEX_FOLDER_ID")
        self.channel = None
        self.stub = None
        self.iam_token = None
        self.iam_token_expires = 0
        
        if not self.api_key or not self.folder_id:
            raise ValueError("Не найдены OAUTH_TOKEN или YANDEX_FOLDER_ID в .env")
        
        logger.info("🚀 YandexGrpcTTS инициализирован")
        
    async def initialize(self):
        """Инициализация gRPC соединения с оптимизированными настройками"""
        if not GRPC_AVAILABLE:
            raise RuntimeError("gRPC модули недоступны")
            
        try:
            credentials = grpc.ssl_channel_credentials()
            # Оптимизированный канал для минимальной латентности
            options = [
                ('grpc.keepalive_time_ms', 30000),      # Поддерживаем соединение
                ('grpc.keepalive_timeout_ms', 5000),    # Быстрый timeout
                ('grpc.http2.max_pings_without_data', 0), # Без ограничений ping
                ('grpc.http2.min_time_between_pings_ms', 10000),
                ('grpc.http2.min_ping_interval_without_data_ms', 300000),
                ('grpc.max_message_length', 4194304)    # 4MB буфер
            ]
            
            self.channel = grpc.aio.secure_channel(
                'tts.api.cloud.yandex.net:443', 
                credentials,
                options=options
            )
            self.stub = tts_service_pb2_grpc.SynthesizerStub(self.channel)
            logger.info("✅ gRPC TTS channel initialized")
            
        except Exception as e:
            logger.error(f"❌ gRPC TTS initialization failed: {e}")
            raise
    
    def _get_fresh_iam_token(self) -> str:
        """Получение свежего IAM токена с кешированием"""
        import requests
        
        # Проверяем, не истек ли токен (12 часов = 43200 сек, обновляем за час до истечения)
        if self.iam_token and time.time() < (self.iam_token_expires - 3600):
            return self.iam_token
        
        url = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
        headers = {"Content-Type": "application/json"}
        data = {"yandexPassportOauthToken": self.api_key}
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=5)
            response.raise_for_status()
            
            token_data = response.json()
            self.iam_token = token_data["iamToken"]
            
            # Токен действует 12 часов
            self.iam_token_expires = time.time() + 43200
            
            logger.info("🔑 IAM токен обновлен")
            return self.iam_token
        except Exception as e:
            logger.error(f"❌ Ошибка получения IAM токена: {e}")
            raise
    
    async def synthesize_chunk_fast(self, text: str) -> bytes:
        """
        Быстрый синтез чанка через gRPC.
        ЦЕЛЬ: <200мс вместо 700мс HTTP.
        """
        start_time = time.time()
        
        try:
            # Метаданные аутентификации
            metadata = [
                ('authorization', f'Bearer {self._get_fresh_iam_token()}'),
                ('x-folder-id', self.folder_id)
            ]
            
            # Запрос с оптимизацией для скорости
            request = tts_pb2.UtteranceSynthesisRequest(
                text=text,
                output_audio_spec=tts_pb2.AudioFormatOptions(
                    container_audio=tts_pb2.ContainerAudio(
                        container_audio_type=tts_pb2.ContainerAudio.ContainerAudioType.WAV
                    )
                ),
                # КРИТИЧНО: настройки для минимальной латентности
                hints=[
                    tts_pb2.Hints(voice="alena"),      # Быстрый голос (не "jane")
                    tts_pb2.Hints(speed=1.15),         # Немного ускорить
                    tts_pb2.Hints(role="neutral")      # Нейтральная эмоция
                ],
                loudness_normalization_type=tts_pb2.UtteranceSynthesisRequest.LoudnessNormalizationType.LUFS
            )
            
            # Потоковый вызов
            response_stream = self.stub.UtteranceSynthesis(request, metadata=metadata)
            
            # Собираем аудио чанки
            audio_chunks = []
            async for response in response_stream:
                if response.audio_chunk.data:
                    audio_chunks.append(response.audio_chunk.data)
            
            # Объединяем в финальный аудио
            audio_data = b''.join(audio_chunks)
            
            elapsed = time.time() - start_time
            logger.info(f"⚡ gRPC TTS: {elapsed:.2f}s for '{text[:30]}...'")
            
            # Алерт при превышении целевого времени
            if elapsed > 0.25:
                logger.warning(f"🐌 gRPC TTS slow: {elapsed:.2f}s > 0.25s target")
            
            return audio_data
            
        except Exception as e:
            logger.error(f"❌ gRPC TTS error: {e}")
            raise
    
    async def close(self):
        """Закрытие gRPC соединения"""
        if self.channel:
            await self.channel.close()
            logger.info("✅ gRPC TTS channel closed")

