#!/usr/bin/env python3
"""
Parallel TTS Processor для параллельной обработки чанков
Цель: TTS каждого чанка запускается немедленно, параллельно с генерацией следующих
"""

import asyncio
import time
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Any
import json

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
    
    def __init__(self, grpc_tts, ari_client):
        """
        Инициализация параллельного TTS процессора
        
        Args:
            grpc_tts: Экземпляр YandexGrpcTTS для синтеза
            ari_client: Клиент ARI для воспроизведения
        """
        self.grpc_tts = grpc_tts
        self.ari_client = ari_client
        
        # Управление очередями по каналам
        self.playback_queues: Dict[str, List[Dict]] = defaultdict(list)
        self.playback_busy: Dict[str, bool] = defaultdict(bool)
        self.tts_tasks: Dict[str, List[asyncio.Task]] = defaultdict(list)
        
        # Метрики производительности
        self.performance_metrics: Dict[str, Dict] = defaultdict(dict)
        
        logger.info("🔄 ParallelTTSProcessor инициализирован")
    
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
            # gRPC TTS (параллельно с другими чанками)
            audio_data = await self.grpc_tts.synthesize_chunk_fast(text)
            tts_time = time.time() - tts_start
            
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
        
        try:
            play_start = time.time()

            success = await self.ari_client.play_audio_data(channel_id, item["audio_data"])

            play_time = time.time() - play_start

            if success:
                logger.info(
                    f"🔊 Played chunk {item['chunk_num']}: {play_time:.2f}s - '{item['text'][:30]}...'"
                )
                return True
            else:
                logger.error(f"❌ Failed to play chunk {item['chunk_num']}")
                return False

        except Exception as e:
            logger.error(f"❌ Audio playback error: {e}")
            return False
    
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

