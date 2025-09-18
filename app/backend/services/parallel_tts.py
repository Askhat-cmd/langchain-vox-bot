#!/usr/bin/env python3
"""
Parallel TTS Processor для параллельной обработки чанков
Цель: TTS каждого чанка запускается немедленно, параллельно с генерацией следующих
"""

import asyncio
import time
import logging
import os
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

from app.backend.asterisk.ari_client import AsteriskARIClient

logger = logging.getLogger(__name__)

class ParallelTTSProcessor:
    """
    Параллельный TTS процессор для обработки chunked ответов
    
    Принцип работы:
    1. TTS каждого чанка запускается немедленно (не ждем предыдущие)
    2. Готовые аудио складываются в очередь воспроизведения
    3. Воспроизведение происходит последовательно в правильном порядке
    4. Barge-in очищает все очереди и отменяет задачи
    """
    
    def __init__(self, grpc_tts, ari_client_factory: Optional[Callable[[], AsteriskARIClient]] = None):
        """
        Инициализация параллельного TTS процессора
        
        Args:
            grpc_tts: Экземпляр YandexGrpcTTS для синтеза
            ari_client: Клиент ARI для воспроизведения
        """
        self.grpc_tts = grpc_tts

        if ari_client_factory is None:
            self.ari_client_factory: Callable[[], AsteriskARIClient] = lambda: AsteriskARIClient()
        elif callable(ari_client_factory):
            self.ari_client_factory = ari_client_factory
        else:
            logger.warning(
                "⚠️ Передан объект ARI без фабрики, повторное использование может быть небезопасным."
            )
            self.ari_client_factory = lambda: ari_client_factory
        
        # Конфигурация из .env
        self.tts_workers = int(os.getenv("TTS_PARALLEL_WORKERS", "3"))
        self.audio_buffer_size = int(os.getenv("AUDIO_BUFFER_SIZE", "2"))
        
        # ThreadPoolExecutor для параллельных TTS запросов
        self.tts_pool = ThreadPoolExecutor(max_workers=self.tts_workers)
        
        # Управление очередями по каналам
        self.playback_queues: Dict[str, List[Dict]] = defaultdict(list)
        self.playback_busy: Dict[str, bool] = defaultdict(bool)
        self.tts_tasks: Dict[str, List[asyncio.Task]] = defaultdict(list)
        
        # Метрики производительности
        self.performance_metrics: Dict[str, Dict] = defaultdict(dict)
        
        logger.info(f"🔄 ParallelTTSProcessor инициализирован с {self.tts_workers} TTS workers")
    
    async def process_chunk_immediate(self, channel_id: str, chunk_data: Dict[str, Any]):
        """
        Обрабатывает чанк НЕМЕДЛЕННО, параллельно с генерацией следующих.
        
        Ключевая логика:
        1. Запускаем gRPC TTS сразу (не ждем)
        2. Добавляем в очередь воспроизведения  
        3. Воспроизводим последовательно готовые чанки
        
        Args:
            channel_id: ID канала для воспроизведения
            chunk_data: Данные чанка с текстом и метаданными
        """
        chunk_num = chunk_data.get("chunk_number", 0)
        text = chunk_data.get("text", "")
        is_first = chunk_data.get("is_first", False)
        
        logger.info(f"🚀 Processing chunk {chunk_num} immediately: '{text[:30]}...'")
        
        try:
            # Запускаем TTS ПАРАЛЛЕЛЬНО (не блокируем)
            tts_task = asyncio.create_task(
                self._synthesize_chunk_async(channel_id, chunk_num, text, is_first)
            )
            
            self.tts_tasks[channel_id].append(tts_task)
            
            # Не ждем завершения TTS - обрабатываем следующий чанк
            
        except Exception as e:
            logger.error(f"❌ Immediate processing error chunk {chunk_num}: {e}")
    
    async def _synthesize_chunk_async(self, channel_id: str, chunk_num: int, text: str, is_first: bool):
        """Async TTS + добавление в очередь воспроизведения"""
        
        tts_start = time.time()
        
        try:
            # КРИТИЧНО: Проверяем канал перед TTS
            if not await self._channel_exists(channel_id):
                logger.warning(f"⚠️ Канал {channel_id} не существует, пропускаем TTS chunk {chunk_num}")
                return

            # gRPC TTS (параллельно с другими чанками)
            audio_data = await self.grpc_tts.synthesize_chunk_fast(text)
            if not audio_data:
                logger.error(f"❌ gRPC TTS вернул пустой результат для chunk {chunk_num}")
                return

            tts_time = time.time() - tts_start

            # Повторная проверка канала после TTS
            if not await self._channel_exists(channel_id):
                logger.warning(f"⚠️ Канал {channel_id} закрылся во время TTS, пропускаем chunk {chunk_num}")
                return
            
            logger.info(f"✅ TTS done for chunk {chunk_num}: {tts_time:.2f}s")
            
            # Добавляем готовый аудио в очередь воспроизведения
            playback_item = {
                "chunk_num": chunk_num,
                "audio_data": audio_data,
                "text": text,
                "tts_time": tts_time,
                "is_first": is_first,
                "ready_time": time.time()
            }
            
            await self._enqueue_playback(channel_id, playback_item)
            
        except Exception as e:
            logger.error(f"❌ Async TTS error chunk {chunk_num}: {e}")
    
    async def _enqueue_playback(self, channel_id: str, playback_item: Dict[str, Any]):
        """Добавляет готовый аудио в очередь воспроизведения"""
        
        self.playback_queues[channel_id].append(playback_item)
        
        # Сортируем по номеру чанка для правильного порядка
        self.playback_queues[channel_id].sort(key=lambda x: x["chunk_num"])
        
        logger.debug(f"📋 Playback queue for {channel_id}: {len(self.playback_queues[channel_id])} items")
        
        # Запускаем обработку очереди если не занят
        if not self.playback_busy[channel_id]:
            await self._process_playback_queue(channel_id)
    
    async def _process_playback_queue(self, channel_id: str):
        """Последовательно воспроизводит готовые чанки"""
        
        if self.playback_busy[channel_id]:
            return
            
        self.playback_busy[channel_id] = True
        
        try:
            while self.playback_queues[channel_id]:
                # Проверяем barge-in
                if self._check_barge_in(channel_id):
                    logger.info("🚫 Barge-in detected - clearing playback queue")
                    self.playback_queues[channel_id] = []
                    break
                
                # Берем следующий готовый чанк
                item = self.playback_queues[channel_id].pop(0)
                
                # Воспроизводим через ARI
                success = await self._play_audio_chunk(channel_id, item)
                
                # Логируем критическую метрику для первого чанка
                if item["is_first"]:
                    logger.info(f"🎯 FIRST AUDIO PLAYED for {channel_id}")
                    self._log_first_audio_metric(channel_id, item)
                
                if not success:
                    logger.warning("⚠️ Playback failed, stopping queue processing")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Playback queue error: {e}")
        finally:
            self.playback_busy[channel_id] = False
    
    async def _play_audio_chunk(self, channel_id: str, item: Dict[str, Any]) -> bool:
        """Воспроизводит аудио чанк через ARI"""

        temp_path: Optional[str] = None

        try:
            play_start = time.time()
            audio_data = item.get("audio_data")

            if not audio_data:
                logger.warning(f"⚠️ Пустые аудио данные для chunk {item.get('chunk_num')}")
                return False

            # Сохраняем аудио данные во временный файл
            timestamp = datetime.now().strftime('%H%M%S%f')[:-3]
            temp_filename = f"chunk_{channel_id}_{item['chunk_num']}_{timestamp}.wav"
            temp_path = os.path.join("/var/lib/asterisk/sounds", temp_filename)
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)

            header = audio_data[:12]
            if header.startswith(b"RIFF") and b"WAVE" in header:
                with open(temp_path, "wb") as temp_file:
                    temp_file.write(audio_data)
            else:
                await self._convert_lpcm_to_wav(audio_data, temp_path)

            playback_id = None
            try:
                client = self.ari_client_factory()
            except Exception as factory_error:
                logger.error(f"❌ Не удалось создать ARI клиент: {factory_error}")
                return False

            if not hasattr(client, "__aenter__"):
                logger.error("❌ ARI клиент не поддерживает async context manager")
                return False

            try:
                async with client as ari:
                    playback_id = await ari.play_sound(channel_id, temp_filename[:-4], lang=None)
            except Exception as playback_error:
                logger.error(
                    f"❌ Ошибка запуска ARI playback для chunk {item['chunk_num']}: {playback_error}"
                )
                playback_id = None

            play_time = time.time() - play_start

            if playback_id:
                logger.info(
                    f"🔊 Played chunk {item['chunk_num']}: {play_time:.2f}s - '{item['text'][:30]}...'"
                )
                return True

            logger.error(f"❌ Не удалось воспроизвести chunk {item['chunk_num']}")
            return False

        except Exception as e:
            logger.error(f"❌ Audio playback error chunk {item.get('chunk_num')}: {e}")
            return False
        finally:
            if temp_path and os.path.exists(temp_path):
                asyncio.create_task(self._cleanup_temp_file(temp_path, delay=10.0))
    
    async def _channel_exists(self, channel_id: str) -> bool:
        """Проверяет наличие канала через ARI"""

        try:
            client = self.ari_client_factory()
        except Exception as factory_error:
            logger.error(f"❌ Не удалось создать ARI клиент для проверки канала: {factory_error}")
            return False

        if not hasattr(client, "__aenter__"):
            logger.error("❌ ARI клиент не поддерживает async context manager")
            return False

        try:
            async with client as ari:
                return await ari.channel_exists(channel_id)
        except Exception as error:
            logger.error(f"❌ Ошибка проверки канала {channel_id}: {error}")
            return False

    async def _convert_lpcm_to_wav(self, lpcm_data: bytes, output_path: str):
        """Конвертирует raw LPCM в WAV файл"""

        try:
            import wave

            sample_rate = 8000
            channels = 1
            sample_width = 2

            with wave.open(output_path, "wb") as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(lpcm_data)

            logger.debug(f"🔄 LPCM конвертирован в WAV: {output_path}")

        except Exception as e:
            logger.error(f"❌ Ошибка конвертации LPCM→WAV: {e}")
            with open(output_path, "wb") as fallback_file:
                fallback_file.write(lpcm_data)

    async def _cleanup_temp_file(self, file_path: str, delay: float = 10.0):
        """Удаляет временный файл после задержки"""

        try:
            await asyncio.sleep(delay)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"🗑️ Удален временный файл: {file_path}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось удалить временный файл {file_path}: {e}")

    def _check_barge_in(self, channel_id: str) -> bool:
        """
        Проверяет не прервал ли пользователь
        
        В реальной реализации здесь будет интеграция с системой active_calls
        """
        # ЗАГЛУШКА: Всегда возвращаем False для тестирования
        return False
    
    def _log_first_audio_metric(self, channel_id: str, item: Dict[str, Any]):
        """Логирует критическую метрику первого аудио"""
        
        if channel_id not in self.performance_metrics:
            self.performance_metrics[channel_id] = {}
        
        self.performance_metrics[channel_id]["first_audio_time"] = item["ready_time"]
        self.performance_metrics[channel_id]["first_chunk_tts_time"] = item["tts_time"]
        
        logger.info(f"📊 First audio metrics for {channel_id}: TTS={item['tts_time']:.2f}s")
    
    async def clear_all_queues(self, channel_id: str):
        """
        Очищает все очереди и отменяет задачи для канала
        
        Используется при barge-in для полной остановки обработки
        """
        try:
            # Очищаем очередь воспроизведения
            self.playback_queues[channel_id] = []
            
            # Отменяем все активные TTS задачи
            for task in self.tts_tasks[channel_id]:
                if not task.done():
                    task.cancel()
            
            self.tts_tasks[channel_id] = []
            
            # Сбрасываем флаг занятости
            self.playback_busy[channel_id] = False
            
            logger.info(f"🧹 Cleared all queues for channel {channel_id}")
            
        except Exception as e:
            logger.error(f"❌ Error clearing queues for {channel_id}: {e}")
    
    def get_performance_metrics(self, channel_id: str) -> Dict[str, Any]:
        """Возвращает метрики производительности для канала"""
        return self.performance_metrics.get(channel_id, {})
    
    def get_queue_status(self, channel_id: str) -> Dict[str, Any]:
        """Возвращает статус очередей для канала"""
        return {
            "playback_queue_size": len(self.playback_queues[channel_id]),
            "active_tts_tasks": len(self.tts_tasks[channel_id]),
            "playback_busy": self.playback_busy[channel_id],
            "queued_chunks": [item["chunk_num"] for item in self.playback_queues[channel_id]]
        }

