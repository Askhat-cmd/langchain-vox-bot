
#!/usr/bin/env python3
"""
Оптимизированный StasisHandler с интеграцией всех компонентов оптимизации
Цель: 1.1 секунды от ASR до первого звука
"""

import asyncio
import json
import logging
import websockets
import uuid
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Добавляем путь для импорта модулей проекта
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent.parent
sys.path.insert(0, str(project_root))

from app.backend.asterisk.ari_client import AsteriskARIClient
from app.backend.rag.agent import Agent
from app.backend.services.yandex_tts_service import get_yandex_tts_service
from app.backend.services.asr_service import get_asr_service
from app.backend.utils.text_normalizer import normalize as normalize_text
from app.backend.services.log_storage import insert_log

# НОВЫЕ КОМПОНЕНТЫ ОПТИМИЗАЦИИ
from app.backend.services.yandex_grpc_tts import YandexGrpcTTS
from app.backend.services.tts_adapter import TTSAdapter
from app.backend.services.filler_tts import InstantFillerTTS
from app.backend.services.parallel_tts import ParallelTTSProcessor

logger = logging.getLogger(__name__)

class OptimizedAsteriskAIHandler:
    """
    Оптимизированный обработчик Asterisk с интеграцией всех компонентов
    
    Компоненты:
    1. Yandex gRPC TTS - быстрый синтез речи
    2. Chunked Response Generator - streaming AI ответы
    3. Filler Words - мгновенные психологические реакции
    4. Parallel TTS Processor - параллельная обработка чанков
    """
    
    def __init__(self):
        self.ws_url = "ws://localhost:8088/ari/events?app=asterisk-bot&api_key=asterisk:asterisk123"
        
        # Инициализируем AI Agent
        try:
            self.agent = Agent()
            logger.info("✅ AI Agent успешно инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации AI Agent: {e}")
            self.agent = None
        
        # Инициализируем ASR сервис
        try:
            self.asr = get_asr_service()
            logger.info("✅ ASR сервис инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации ASR: {e}")
            self.asr = None
        
        # НОВЫЕ КОМПОНЕНТЫ ОПТИМИЗАЦИИ
        self.grpc_tts = None
        self.tts_adapter = None
        self.filler_tts = None
        self.parallel_tts = None
        
        # Активные звонки с оптимизированными данными
        self.active_calls = {}
        
        # Константы оптимизации
        self.SPEECH_END_TIMEOUT = 0.2
        self.BARGE_IN_GUARD_MS = 1500  # Увеличено для Asterisk
        self.INPUT_DEBOUNCE_MS = 1200
        
        # Метрики производительности
        self.performance_metrics = {}
        
        logger.info("🚀 OptimizedAsteriskAIHandler инициализирован")
    
    async def initialize_optimization_services(self):
        """Инициализация всех сервисов оптимизации"""
        try:
            logger.info("🔄 Инициализация сервисов оптимизации...")
            
            # 1. Yandex gRPC TTS
            self.grpc_tts = YandexGrpcTTS()
            await self.grpc_tts.initialize()
            
            # 2. TTS Adapter (gRPC + HTTP fallback)
            self.tts_adapter = TTSAdapter()
            await self.tts_adapter.initialize()
            
            # 3. Filler TTS
            self.filler_tts = InstantFillerTTS()
            await self.filler_tts.initialize()
            
            # 4. Parallel TTS Processor
            ari_client = AsteriskARIClient()
            self.parallel_tts = ParallelTTSProcessor(self.tts_adapter, ari_client)
            
            logger.info("✅ Все сервисы оптимизации инициализированы")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации сервисов оптимизации: {e}")
            # Fallback на старые сервисы
            self.tts = get_yandex_tts_service()
            logger.warning("⚠️ Используем fallback TTS сервис")
    
    async def handle_stasis_start(self, event):
        """Обрабатывает начало звонка с оптимизированной инициализацией"""
        channel_id = event.get('channel', {}).get('id')
        caller_id = event.get('channel', {}).get('caller', {}).get('number', 'Unknown')
        
        logger.info(f"🔔 Новый звонок: Channel={channel_id}, Caller={caller_id}")
        
        # Создаем сессию звонка с оптимизированными данными
        session_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)

        self.active_calls[channel_id] = {
            "session_id": session_id,
            "caller_id": caller_id,
            "start_time": start_time.isoformat(),
            "transcript": [],
            "status": "Started",
            
            # Оптимизированные данные
            "response_buffer": "",
            "buffer_timer": None,
            "tts_queue": [],
            "is_recording": False,
            "tts_busy": False,
            "current_playback": None,
            "last_speak_started_at": 0,
            "is_speaking": False,
            "preload_cache": {},
            
            # Новые метрики производительности
            "performance_start": time.time(),
            "asr_complete_time": None,
            "first_chunk_time": None,
            "first_audio_time": None,
            "user_interrupted": False
        }
        
        # Канал уже принят в dialplan
        async with AsteriskARIClient() as ari:
            logger.info(f"✅ Звонок уже принят в dialplan: {channel_id}")
            
            # Получаем приветствие от AI Agent
            if self.agent:
                greeting = self.agent.prompts.get("greeting", "Здравствуйте! Чем могу помочь?")
            else:
                greeting = "Здравствуйте! Система временно недоступна."

            # Добавляем в транскрипт
            self.active_calls[channel_id]["transcript"].append({
                "speaker": "bot",
                "text": greeting,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            # Оптимизированное приветствие через TTS Adapter
            if self.tts_adapter:
                await self.speak_optimized(channel_id, greeting)
            else:
                # Fallback на старый метод
                await self.speak_queued(channel_id, greeting)
            
            logger.info(f"🎤 Готов к приему речи от {caller_id}")

    async def process_user_speech_optimized(self, channel_id: str, audio_path: str):
        """
        ОПТИМИЗИРОВАННАЯ обработка речи пользователя
        ЦЕЛЬ: 1.1 секунды от ASR до первого звука
        """
        if channel_id not in self.active_calls:
            logger.warning(f"Канал {channel_id} не найден в активных звонках")
            return

        call_data = self.active_calls[channel_id]
        session_id = call_data["session_id"]
        overall_start = time.time()

        # Проверяем, что канал еще активен
        if call_data.get("status") == "Completed":
            logger.info(f"🚫 Канал {channel_id} уже завершен, пропускаем обработку речи")
            return

        try:
            logger.info(f"🎯 ОПТИМИЗИРОВАННАЯ обработка речи для канала {channel_id}")
            
            # ЭТАП 1.2: Проверка размера аудио файла перед ASR
            if not os.path.exists(audio_path):
                logger.warning(f"⚠️ Аудио файл не найден: {audio_path}")
                return
                
            file_size = os.path.getsize(audio_path)
            if file_size < 1000:  # Минимальный размер 1KB
                logger.warning(f"⚠️ Аудио файл слишком короткий: {file_size} bytes, пропускаем ASR")
                return
                
            logger.info(f"✅ Аудио файл проверен: {file_size} bytes")
            
            # 1. ASR: Преобразуем речь в текст
            if self.asr:
                logger.info(f"🎤 Запускаем ASR для файла: {audio_path}")
                user_text = await self.asr.speech_to_text(audio_path)
                normalized_text = normalize_text(user_text)
                
                asr_complete_time = time.time()
                call_data["asr_complete_time"] = asr_complete_time
                
                logger.info(f"🎤 Пользователь сказал: '{user_text}' → '{normalized_text}'")

                # Добавляем в транскрипт
                call_data["transcript"].append({
                    "speaker": "user",
                    "text": normalized_text,
                    "raw": user_text,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            else:
                logger.warning("ASR сервис недоступен")
                normalized_text = "Извините, система распознавания речи недоступна"

            # 2. Останавливаем TTS при barge-in
            await self.stop_tts_on_barge_in_optimized(channel_id, "UserSpeech")

            # 3. ОПТИМИЗИРОВАННАЯ AI обработка с chunking
            if self.agent and normalized_text:
                logger.info(f"🤖 Запрашиваем ОПТИМИЗИРОВАННЫЙ ответ от AI агента")
                
                try:
                    # Запускаем filler word НЕМЕДЛЕННО
                    filler_task = asyncio.create_task(
                        self._play_instant_filler(channel_id, normalized_text)
                    )
                    
                    # ВРЕМЕННО: Используем оригинальный метод для тестирования
                    # TODO: Вернуться к chunked generator после исправления
                    logger.info("🔄 ВРЕМЕННО: Используем оригинальный AI response для тестирования")
                    
                    # Получаем обычный response generator от AI Agent
                    response_generator = self.agent.get_response_generator(normalized_text, session_id)
                    
                    # Обрабатываем AI ответы через оригинальный метод
                    await self.process_ai_response_streaming(channel_id, response_generator)
                    
                    # Ждем завершения filler
                    await filler_task
                    
                    total_time = time.time() - overall_start
                    logger.info(f"✅ ОПТИМИЗИРОВАННАЯ обработка завершена: {total_time:.2f}s")
                    
                    # Логируем метрики
                    self._log_performance_metrics(channel_id, total_time)
                    
                except Exception as ai_error:
                    logger.error(f"❌ Ошибка оптимизированного AI: {ai_error}", exc_info=True)
                    # Fallback на старую систему
                    await self._fallback_to_old_system(channel_id, normalized_text)
            else:
                logger.warning("AI Agent недоступен или текст пустой")
                await self.speak_optimized(channel_id, "Извините, система ИИ временно недоступна")

        except Exception as e:
            logger.error(f"❌ Ошибка оптимизированной обработки речи: {e}", exc_info=True)

    async def _play_instant_filler(self, channel_id: str, user_text: str):
        """Воспроизводит мгновенный filler word"""
        try:
            if not self.filler_tts:
                return
                
            filler_start = time.time()
            
            # Получаем мгновенный filler
            filler_audio = await self.filler_tts.get_instant_filler(user_text)
            
            if filler_audio:
                # Воспроизводим немедленно
                await self._play_audio_data(channel_id, filler_audio)
                
                filler_time = time.time() - filler_start
                logger.info(f"⚡ Filler played: {filler_time:.2f}s")
                
                # Логируем метрику
                call_data = self.active_calls.get(channel_id, {})
                call_data["filler_time"] = filler_time
            
        except Exception as e:
            logger.error(f"❌ Filler playback error: {e}")

    async def process_chunked_ai_response(self, channel_id: str, chunked_generator):
        """Обрабатывает chunked AI ответы через Parallel TTS Processor"""
        try:
            if not self.parallel_tts:
                logger.warning("Parallel TTS Processor недоступен")
                return
            
            # Итерируем chunked generator
            async for chunk_data in chunked_generator:
                # Запускаем TTS каждого чанка НЕМЕДЛЕННО (параллельно)
                await self.parallel_tts.process_chunk_immediate(channel_id, chunk_data)
                
                # Логируем критическую метрику
                if chunk_data.get("is_first"):
                    first_chunk_time = time.time() - self.active_calls[channel_id]["performance_start"]
                    logger.info(f"🎯 FIRST CHUNK GENERATED: {first_chunk_time:.2f}s")
                    self.active_calls[channel_id]["first_chunk_time"] = first_chunk_time
                    
        except Exception as e:
            logger.error(f"❌ Chunked AI response error: {e}")

    async def process_ai_response_streaming(self, channel_id: str, response_generator):
        """Потоковая обработка ответа AI с разделителями | (из оригинальной версии)."""
        import time
        stasis_start = time.time()
        logger.info(f"⏱️ ПРОФИЛИРОВАНИЕ STASIS: Начинаем обработку AI response для канала {channel_id}")
        
        if channel_id not in self.active_calls:
            return
        
        call_data = self.active_calls[channel_id]
        
        # Накапливаем chunks от AI Agent
        first_chunk = True
        chunk_count = 0
        
        for chunk in response_generator:
            if first_chunk:
                first_chunk_time = time.time() - stasis_start
                logger.info(f"⏱️ ПРОФИЛИРОВАНИЕ STASIS: Первый чанк получен через {first_chunk_time:.3f}с")
                first_chunk = False
            
            if chunk:
                chunk_count += 1
                call_data["response_buffer"] += chunk
                
                # Проигрываем каждое завершённое предложение по | (как в Voximplant)
                while "|" in call_data["response_buffer"]:
                    idx = call_data["response_buffer"].index("|")
                    sentence = self.clean_text(call_data["response_buffer"][:idx])
                    call_data["response_buffer"] = call_data["response_buffer"][idx + 1:]
                    
                    if sentence:
                        await self.speak_optimized(channel_id, sentence)
                
                # Сбрасываем таймер для остатка
                if call_data["buffer_timer"]:
                    call_data["buffer_timer"].cancel()
                
                # Страховочный таймер для "хвоста" без | (как в Voximplant)
                if call_data["response_buffer"].strip():
                    call_data["buffer_timer"] = asyncio.create_task(
                        self.flush_response_buffer(channel_id)
                    )
        
        total_stasis_time = time.time() - stasis_start
        logger.info(f"⏱️ ПРОФИЛИРОВАНИЕ STASIS: Обработка AI response заняла {total_stasis_time:.3f}с, чанков: {chunk_count}")
    
    async def flush_response_buffer(self, channel_id: str):
        """Страховочный таймер для остатка без | (из оригинальной версии)."""
        await asyncio.sleep(self.SPEECH_END_TIMEOUT)
        
        if channel_id not in self.active_calls:
            return
        
        call_data = self.active_calls[channel_id]
        
        if call_data["response_buffer"].strip():
            tail = self.clean_text(call_data["response_buffer"])
            call_data["response_buffer"] = ""
            call_data["buffer_timer"] = None
            
            if tail:
                await self.speak_optimized(channel_id, tail)
    
    def clean_text(self, text: str) -> str:
        """Очищает текст от лишних символов (из оригинальной версии)."""
        if not text:
            return ""
        
        # Убираем лишние пробелы и переносы
        text = text.strip()
        text = " ".join(text.split())
        
        return text

    async def speak_optimized(self, channel_id: str, text: str):
        """Оптимизированное воспроизведение через TTS Adapter"""
        try:
            if not self.tts_adapter:
                # Fallback на старый метод
                await self.speak_queued(channel_id, text)
                return

            # Синтезируем аудио через адаптер
            audio_data = await self.tts_adapter.synthesize(text)

            if not audio_data:
                logger.warning("⚠️ TTS Adapter вернул пустые данные")
                await self.speak_queued(channel_id, text)
                return

            # Воспроизводим аудио данные
            await self._play_audio_data(channel_id, audio_data)

        except Exception as e:
            logger.error(f"❌ Optimized speak error: {e}")
            # Fallback на старый метод
            await self.speak_queued(channel_id, text)

    async def _play_audio_data(self, channel_id: str, audio_data: bytes):
        """Воспроизводит аудио данные через ARI"""
        try:
            if not audio_data:
                logger.warning("⚠️ Пустые аудио данные")
                return
            
            # Сохраняем аудио данные во временный файл
            timestamp = datetime.now().strftime('%H%M%S%f')[:-3]  # миллисекунды
            temp_filename = f"stream_{channel_id}_{timestamp}.wav"
            temp_path = f"/var/lib/asterisk/sounds/{temp_filename}"
            
            # Создаем директорию если не существует
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            
            # Записываем аудио данные в файл
            with open(temp_path, 'wb') as f:
                f.write(audio_data)
            
            logger.info(f"💾 Сохранен аудио файл: {temp_path} ({len(audio_data)} bytes)")
            
            # Воспроизводим через ARI (как в оригинальном коде)
            async with AsteriskARIClient() as ari:
                playback_id = await ari.play_sound(channel_id, temp_filename[:-4], lang=None)  # убираем .wav
                
                if playback_id:
                    # Обновляем данные канала
                    if channel_id in self.active_calls:
                        call_data = self.active_calls[channel_id]
                        call_data["current_playback"] = playback_id
                        call_data["is_speaking"] = True
                        call_data["last_speak_started_at"] = int(time.time() * 1000)
                    
                    logger.info(f"✅ Аудио воспроизводится через ARI: {playback_id}")
                else:
                    logger.warning("⚠️ ARI playback не удался, пробуем fallback через dialplan")
                    # FALLBACK: Используем dialplan Playback (как в оригинале)
                    fallback_success = await self.playback_via_dialplan(channel_id, temp_filename[:-4])
                    if fallback_success:
                        logger.info("✅ Аудио воспроизводится через dialplan fallback")
                        if channel_id in self.active_calls:
                            call_data = self.active_calls[channel_id]
                            call_data["current_playback"] = f"dialplan_{temp_filename[:-4]}"
                            call_data["is_speaking"] = True
                            call_data["last_speak_started_at"] = int(time.time() * 1000)
                    else:
                        logger.error("❌ Не удалось воспроизвести аудио ни через ARI, ни через dialplan")
            
            # Очищаем временный файл после небольшой задержки
            # (даем время ARI прочитать файл)
            asyncio.create_task(self._cleanup_temp_file(temp_path, delay=5.0))
            
        except Exception as e:
            logger.error(f"❌ Audio playback error: {e}")
    
    async def _cleanup_temp_file(self, file_path: str, delay: float = 5.0):
        """Очищает временный файл после задержки"""
        try:
            await asyncio.sleep(delay)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"🗑️ Удален временный файл: {file_path}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось удалить временный файл {file_path}: {e}")
    
    async def playback_via_dialplan(self, channel_id: str, filename: str) -> bool:
        """FALLBACK: Проигрывание через dialplan если ARI не работает."""
        try:
            async with AsteriskARIClient() as ari:
                # Отправляем канал в dialplan для проигрывания
                url = f"{ari.base_url}/channels/{channel_id}/continue"
                data = {
                    "context": "playback-context",
                    "extension": "play",
                    "priority": 1,
                    "variables": {
                        "SOUND_FILE": filename
                    }
                }
                
                async with ari.session.post(url, json=data) as response:
                    if response.status in (200, 201, 202):
                        logger.info(f"✅ Dialplan playback запущен для {filename}")
                        return True
                    else:
                        logger.error(f"❌ Dialplan playback failed: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"❌ Dialplan playback error: {e}")
            return False

    async def stop_tts_on_barge_in_optimized(self, channel_id: str, event_name: str):
        """ОПТИМИЗИРОВАННЫЙ barge-in с очисткой всех очередей"""
        call_data = self.active_calls.get(channel_id)
        if not call_data:
            return
        
        # Защита от ложного barge-in
        BARGE_IN_GUARD_MS = 1500
        since_start = int(time.time() * 1000) - call_data.get("last_speak_started_at", 0)
        
        if since_start < BARGE_IN_GUARD_MS:
            logger.debug(f"🔇 Ignoring barge-in - too early ({since_start}ms)")
            return
        
        logger.info(f"🚫 [OPTIMIZED BARGE-IN] {event_name} → stopping all TTS processing")
        
        # Останавливаем текущее воспроизведение
        if call_data.get("current_playback"):
            try:
                async with AsteriskARIClient() as ari:
                    await ari.stop_playback(call_data["current_playback"])
            except:
                pass
        
        # КРИТИЧНО: Очищаем все очереди параллельного TTS
        if self.parallel_tts:
            await self.parallel_tts.clear_all_queues(channel_id)
        
        # Отмечаем прерывание
        call_data["user_interrupted"] = True
        call_data["barge_in_time"] = time.time()
        
        logger.info("✅ Optimized barge-in processed - ready for new input")

    async def _fallback_to_old_system(self, channel_id: str, user_text: str):
        """Fallback на старую систему при ошибках оптимизации"""
        try:
            logger.warning("🔄 Falling back to old system")
            
            # Используем старый метод обработки
            if self.agent:
                response_generator = self.agent.get_response_generator(user_text, self.active_calls[channel_id]["session_id"])
                await self.process_ai_response_streaming_old(channel_id, response_generator)
            else:
                await self.speak_queued(channel_id, "Извините, произошла ошибка в системе")
                
        except Exception as e:
            logger.error(f"❌ Fallback system error: {e}")

    async def process_ai_response_streaming_old(self, channel_id: str, response_generator):
        """Старый метод потоковой обработки (fallback)"""
        # Копируем логику из оригинального StasisHandler
        # ... (код из оригинального метода)
        pass

    async def speak_queued(self, channel_id: str, text: str):
        """Старый метод воспроизведения (fallback)"""
        # Копируем логику из оригинального StasisHandler
        # ... (код из оригинального метода)
        pass

    def _log_performance_metrics(self, channel_id: str, total_time: float):
        """Логирует метрики производительности"""
        call_data = self.active_calls.get(channel_id, {})
        
        metrics = {
            "total_time": total_time,
            "asr_complete_time": call_data.get("asr_complete_time"),
            "first_chunk_time": call_data.get("first_chunk_time"),
            "first_audio_time": call_data.get("first_audio_time"),
            "filler_time": call_data.get("filler_time")
        }
        
        self.performance_metrics[channel_id] = metrics
        
        logger.info(f"📊 Performance metrics for {channel_id}: {metrics}")

    # Остальные методы из оригинального StasisHandler...
    # (handle_channel_destroyed, clean_text, и т.д.)
    
    async def handle_channel_destroyed(self, event):
        """Обрабатывает завершение звонка"""
        channel_id = event.get('channel', {}).get('id')
        
        if channel_id in self.active_calls:
            call_data = self.active_calls[channel_id]
            call_data["status"] = "Completed"
            end_time = datetime.now(timezone.utc)
            
            logger.info(f"📞 Звонок завершен: {channel_id}")
            
            # Сохраняем лог звонка
            try:
                log_record = {
                    "id": call_data["session_id"],
                    "callerId": call_data["caller_id"],
                    "startTime": call_data["start_time"],
                    "endTime": end_time.isoformat(),
                    "status": call_data["status"],
                    "transcript": call_data["transcript"],
                    "performance_metrics": self.performance_metrics.get(channel_id, {})
                }
                await insert_log(log_record)
                logger.info(f"💾 Лог сохранен для звонка {call_data['session_id']}")
            except Exception as e:
                logger.error(f"❌ Ошибка сохранения лога: {e}")
            
            # Удаляем из активных звонков
            del self.active_calls[channel_id]
            if channel_id in self.performance_metrics:
                del self.performance_metrics[channel_id]

    def clean_text(self, text: str) -> str:
        """Очистка текста от служебных символов"""
        import re
        text = str(text).replace("|", " ").replace("*", " ")
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    async def run(self):
        """Основной цикл обработки WebSocket событий от Asterisk"""
        try:
            async with websockets.connect(self.ws_url) as websocket:
                logger.info("✅ Подключен к Asterisk ARI WebSocket")
                
                async for message in websocket:
                    try:
                        event = json.loads(message)
                        await self.handle_event(event)
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Ошибка парсинга JSON: {e}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка обработки события: {e}", exc_info=True)
                        
        except websockets.exceptions.ConnectionClosed:
            logger.warning("🔌 WebSocket соединение закрыто")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка WebSocket: {e}", exc_info=True)
    
    async def handle_event(self, event):
        """Обрабатывает события от Asterisk ARI"""
        event_type = event.get('type')
        
        if event_type == 'StasisStart':
            await self.handle_stasis_start(event)
        elif event_type == 'ChannelDestroyed':
            await self.handle_channel_destroyed(event)
        elif event_type == 'PlaybackStarted':
            await self.handle_playback_started(event)
        elif event_type == 'PlaybackFinished':
            await self.handle_playback_finished(event)
        elif event_type == 'RecordingFinished':
            await self.handle_recording_finished(event)
        elif event_type == 'UserEvent':
            await self.handle_user_event(event)
        # Добавляем обработку других событий по необходимости
    
    async def handle_playback_started(self, event):
        """Обрабатывает начало воспроизведения"""
        playback = event.get('playback', {})
        playback_id = playback.get('id')
        target_uri = playback.get('target_uri', '')
        
        if target_uri.startswith('channel:'):
            channel_id = target_uri.replace('channel:', '')
            if channel_id in self.active_calls:
                call_data = self.active_calls[channel_id]
                call_data["current_playback"] = playback_id
                call_data["is_speaking"] = True
                call_data["last_speak_started_at"] = int(time.time() * 1000)
                logger.info(f"🔊 Начало воспроизведения для {channel_id}: {playback_id}")
    
    async def handle_playback_finished(self, event):
        """Обрабатывает завершение воспроизведения - запускает запись пользователя"""
        playback = event.get('playback', {})
        playback_id = playback.get('id')
        target_uri = playback.get('target_uri', '')
        
        if target_uri.startswith('channel:'):
            channel_id = target_uri.replace('channel:', '')
            if channel_id in self.active_calls:
                call_data = self.active_calls[channel_id]
                call_data["is_speaking"] = False
                call_data["current_playback"] = None
                logger.info(f"🔇 Завершение воспроизведения для {channel_id}: {playback_id}")
                
                # После завершения приветствия запускаем запись пользователя
                await self.start_user_recording(channel_id)
    
    async def start_user_recording(self, channel_id: str):
        """Запускает запись речи пользователя."""
        try:
            # Проверяем, что запись не запущена уже
            if channel_id in self.active_calls and self.active_calls[channel_id].get("is_recording"):
                logger.warning(f"⚠️ Запись уже запущена для канала {channel_id}")
                return
            
            # Создаем уникальное имя файла с UUID
            import uuid
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            unique_id = str(uuid.uuid4())[:8]
            recording_filename = f"user_{channel_id}_{timestamp}_{unique_id}"
            
            logger.info(f"🎤 Запускаем запись речи пользователя: {recording_filename}")
            
            async with AsteriskARIClient() as ari:
                recording_id = await ari.start_recording(channel_id, recording_filename, max_duration=15)
                
                # Status 201 означает успешный запуск записи
                if recording_id and channel_id in self.active_calls:
                    self.active_calls[channel_id]["current_recording"] = recording_id
                    self.active_calls[channel_id]["recording_filename"] = recording_filename
                    self.active_calls[channel_id]["is_recording"] = True
                    logger.info(f"✅ Запись запущена: {recording_id}")
                else:
                    logger.warning(f"⚠️ Запись запущена, но не удалось сохранить данные в active_calls")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка запуска записи: {e}", exc_info=True)
    
    async def handle_recording_finished(self, event):
        """Обрабатывает завершение записи - запускает обработку речи пользователя."""
        recording = event.get('recording', {})
        recording_name = recording.get('name')
        
        logger.info(f"🎤 Запись завершена: {recording_name}")
        
        # ЭТАП 1.3: Улучшенный поиск канала по имени записи
        channel_id = None
        
        # Сначала ищем точное совпадение
        for cid, call_data in self.active_calls.items():
            if call_data.get("recording_filename") == recording_name:
                channel_id = cid
                logger.info(f"✅ Найден канал {channel_id} для записи {recording_name}")
                break
        
        # Если не найдено точное совпадение, ищем по частичному совпадению
        if not channel_id:
            for cid, call_data in self.active_calls.items():
                stored_filename = call_data.get("recording_filename", "")
                if recording_name in stored_filename or stored_filename in recording_name:
                    channel_id = cid
                    logger.info(f"✅ Найден канал {channel_id} по частичному совпадению: {recording_name} <-> {stored_filename}")
                    break
        
        # Если все еще не найдено, логируем все активные записи для отладки
        if not channel_id:
            logger.warning(f"❌ Не найден канал для записи: {recording_name}")
            logger.info("🔍 Активные записи:")
            for cid, call_data in self.active_calls.items():
                stored_filename = call_data.get("recording_filename", "НЕТ")
                is_recording = call_data.get("is_recording", False)
                logger.info(f"  Канал {cid}: {stored_filename} (запись: {is_recording})")
            return
                
        if channel_id:
            # Сбрасываем флаг записи
            if channel_id in self.active_calls:
                self.active_calls[channel_id]["is_recording"] = False
                self.active_calls[channel_id]["current_recording"] = None
                logger.info(f"✅ Сброшен флаг записи для канала {channel_id}")
            
            # Путь к записанному файлу (Asterisk сохраняет в /var/spool/asterisk/recording/)
            recording_path = f"/var/spool/asterisk/recording/{recording_name}.wav"
            
            # Проверяем существование файла перед обработкой
            if os.path.exists(recording_path):
                logger.info(f"✅ Файл записи найден: {recording_path}")
                # Обрабатываем речь пользователя
                await self.process_user_speech_optimized(channel_id, recording_path)
            else:
                logger.warning(f"⚠️ Файл записи не найден: {recording_path}")
        else:
            logger.warning(f"Не найден канал для записи: {recording_name}")
    
    async def handle_user_event(self, event):
        """Обрабатывает пользовательские события"""
        event_name = event.get('eventname')
        channel_id = event.get('channel', {}).get('id')
        
        if event_name == 'UserSpeech' and channel_id:
            # Обрабатываем речь пользователя
            audio_path = event.get('args', [{}])[0].get('audio_path')
            if audio_path:
                await self.process_user_speech_optimized(channel_id, audio_path)

async def main():
    """Основная функция запуска."""
    # Настраиваем логирование
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Загружаем переменные окружения
    from dotenv import load_dotenv
    load_dotenv()
    
    # Запускаем оптимизированный обработчик
    handler = OptimizedAsteriskAIHandler()
    
    # Инициализируем сервисы оптимизации
    await handler.initialize_optimization_services()
    
    # Запускаем основной цикл
    await handler.run()

if __name__ == "__main__":
    asyncio.run(main())
