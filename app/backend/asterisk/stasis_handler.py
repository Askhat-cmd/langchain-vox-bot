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

logger = logging.getLogger(__name__)

class AsteriskAIHandler:
    def __init__(self):
        self.ws_url = "ws://localhost:8088/ari/events?app=asterisk-bot&api_key=asterisk:asterisk123"
        
        # Инициализируем AI Agent
        try:
            self.agent = Agent()
            logger.info("✅ AI Agent успешно инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации AI Agent: {e}")
            self.agent = None
        
        # Инициализируем Yandex TTS и ASR сервисы
        try:
            logger.info("🔊 Используем Yandex TTS (основной и единственный)")
            self.tts = get_yandex_tts_service()
            self.asr = get_asr_service()
            logger.info("✅ Yandex TTS и ASR сервисы инициализированы")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации TTS/ASR: {e}")
            self.tts = None
            self.asr = None
        
        # Активные звонки с потоковой обработкой (как в Voximplant)
        self.active_calls = {}
        
        # Константы из Voximplant для оптимизации
        self.SPEECH_END_TIMEOUT = 0.2    # страховка для остатка без | (секунды)
        self.BARGE_IN_GUARD_MS = 400     # защита от ложного barge-in (мс)
        self.INPUT_DEBOUNCE_MS = 1200    # тишина = конец реплики пользователя (мс)
        
    async def handle_stasis_start(self, event):
        """Обрабатывает начало звонка."""
        channel_id = event.get('channel', {}).get('id')
        caller_id = event.get('channel', {}).get('caller', {}).get('number', 'Unknown')
        
        logger.info(f"🔔 Новый звонок: Channel={channel_id}, Caller={caller_id}")
        
                # Создаем сессию звонка с потоковыми данными (как в Voximplant)
        session_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)

        self.active_calls[channel_id] = {
            "session_id": session_id,
            "caller_id": caller_id,
            "start_time": start_time.isoformat(),
            "transcript": [],
            "status": "Started",
            # Потоковые данные (как в Voximplant)
            "response_buffer": "",           # буфер от AI Agent
            "buffer_timer": None,           # таймер для остатка без |
            "tts_queue": [],                # очередь TTS фраз
            "tts_busy": False,              # флаг занятости TTS
            "current_playback": None,       # текущий playback_id
            "last_speak_started_at": 0,     # время начала последнего TTS
            "is_speaking": False,           # флаг проигрывания
            "preload_cache": {}             # кеш предзагруженных TTS фраз
        }
        
        # Канал уже принят в dialplan, сразу работаем с ним
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

            # Потоковое приветствие (разбиваем по | если есть)
            if "|" in greeting:
                # Обрабатываем как потоковый ответ
                greeting_parts = greeting.split("|")
                for part in greeting_parts:
                    if part.strip():
                        await self.speak_queued(channel_id, part.strip())
            else:
                # Обычное приветствие
                await self.speak_queued(channel_id, greeting)
            
            logger.info(f"🎤 Готов к приему речи от {caller_id}")

    

    async def handle_channel_destroyed(self, event):
        """Обрабатывает завершение звонка."""
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
                    "transcript": call_data["transcript"]
                }
                await insert_log(log_record)
                logger.info(f"💾 Лог сохранен для звонка {call_data['session_id']}")
            except Exception as e:
                logger.error(f"❌ Ошибка сохранения лога: {e}")
            
            # Удаляем из активных звонков
            del self.active_calls[channel_id]

    def clean_text(self, text: str) -> str:
        """Очистка текста от служебных символов (как в Voximplant)."""
        import re
        text = str(text).replace("|", " ").replace("*", " ")
        text = re.sub(r'\s+', ' ', text)  # Заменяем множественные пробелы на один
        return text.strip()
    
    async def speak_queued(self, channel_id: str, text: str):
        """Добавляет фразу в очередь TTS (аналог Voximplant speakQueued)."""
        if not text or channel_id not in self.active_calls:
            return
        
        call_data = self.active_calls[channel_id]
        call_data["tts_queue"].append(text)
        
        if not call_data["tts_busy"]:
            await self.process_tts_queue(channel_id)
    
    async def process_tts_queue(self, channel_id: str):
        """Обрабатывает очередь TTS с параллельной предзагрузкой (аналог Voximplant processTTSQueue)."""
        if channel_id not in self.active_calls:
            return
        
        call_data = self.active_calls[channel_id]
        
        if call_data["tts_busy"]:
            return
        
        if not call_data["tts_queue"]:
            return
        
        next_text = call_data["tts_queue"].pop(0)
        call_data["tts_busy"] = True
        
        # 🚀 ПАРАЛЛЕЛЬНАЯ ОПТИМИЗАЦИЯ: Пока говорим текущую фразу, генерируем следующую
        asyncio.create_task(self.preload_next_tts(channel_id))
        
        await self.speak_one(channel_id, next_text)
    
    async def preload_next_tts(self, channel_id: str):
        """Предзагружает следующую фразу TTS параллельно с текущим воспроизведением."""
        if channel_id not in self.active_calls:
            return
        
        call_data = self.active_calls[channel_id]
        
        # Если в очереди есть следующая фраза - генерируем её заранее
        if call_data["tts_queue"]:
            next_text = call_data["tts_queue"][0]  # Берем без удаления
            
            try:
                # Генерируем уникальное имя для предзагрузки
                timestamp = datetime.now().strftime('%H%M%S%f')[:-3]
                preload_filename = f"preload_{channel_id}_{timestamp}"
                
                # Генерируем TTS параллельно
                if self.tts:
                    preload_result = await self.tts.text_to_speech(next_text, preload_filename)
                    if preload_result:
                        # Сохраняем результат предзагрузки
                        if "preload_cache" not in call_data:
                            call_data["preload_cache"] = {}
                        call_data["preload_cache"][next_text] = preload_result
                        logger.info(f"🚀 Предзагружена следующая фраза: '{next_text[:30]}...'")
            except Exception as e:
                logger.debug(f"Предзагрузка не удалась (не критично): {e}")
    
    async def speak_one(self, channel_id: str, text: str):
        """Проигрывает одну фразу TTS (аналог Voximplant speakOne)."""
        if channel_id not in self.active_calls:
            return
        
        call_data = self.active_calls[channel_id]
        
        logger.info(f"▶️ TTS: \"{text}\" для канала {channel_id}")
        
        # Останавливаем предыдущий playback если есть
        if call_data["current_playback"]:
            async with AsteriskARIClient() as ari:
                # Пытаемся остановить (может уже завершиться)
                pass
        
        call_data["is_speaking"] = True
        call_data["last_speak_started_at"] = int(time.time() * 1000)  # миллисекунды
        
        try:
            if not self.tts:
                logger.warning("TTS сервис недоступен")
                await self.finish_speak_one(channel_id)
                return
            
            # 🚀 ПРОВЕРЯЕМ ПРЕДЗАГРУЖЕННЫЙ КЕШИРОВАНИЕ
            sound_filename = None
            if "preload_cache" in call_data and text in call_data["preload_cache"]:
                sound_filename = call_data["preload_cache"].pop(text)
                logger.info(f"⚡ Используем предзагруженную фразу: '{text[:30]}...'")
            
            # Если не предзагружено - генерируем сейчас
            if not sound_filename:
                timestamp = datetime.now().strftime('%H%M%S%f')[:-3]  # миллисекунды
                audio_filename = f"stream_{channel_id}_{timestamp}"
                sound_filename = await self.tts.text_to_speech(text, audio_filename)
            
            # Проигрывание через Asterisk
            async with AsteriskARIClient() as ari:
                playback_id = await ari.play_sound(channel_id, sound_filename, lang=None)
                
                if playback_id:
                    call_data["current_playback"] = playback_id
                    logger.info(f"✅ TTS запущен: {playback_id}")
                else:
                    logger.warning("Не удалось запустить TTS")
                    await self.finish_speak_one(channel_id)
        
        except Exception as e:
            logger.error(f"❌ Ошибка TTS: {e}")
            await self.finish_speak_one(channel_id)
    
    async def finish_speak_one(self, channel_id: str):
        """Завершает проигрывание одной фразы и запускает следующую."""
        if channel_id not in self.active_calls:
            return
        
        call_data = self.active_calls[channel_id]
        call_data["tts_busy"] = False
        call_data["current_playback"] = None
        call_data["is_speaking"] = False
        
        # Запускаем следующую фразу в очереди
        await self.process_tts_queue(channel_id)
    
    async def stop_tts_on_barge_in(self, channel_id: str, event_name: str):
        """Останавливает TTS при прерывании пользователем (аналог Voximplant stopPlayerOnBargeIn)."""
        if channel_id not in self.active_calls:
            return
        
        call_data = self.active_calls[channel_id]
        
        # Защита от ложного barge-in (как в Voximplant)
        since_start = int(time.time() * 1000) - call_data["last_speak_started_at"]
        if call_data["current_playback"] and since_start < self.BARGE_IN_GUARD_MS:
            logger.debug(f"Игнорируем barge-in - слишком рано ({since_start}ms)")
            return
        
        logger.info(f"[BARGE-IN] '{event_name}' → остановка TTS (sinceStart={since_start}ms)")
        
        # Останавливаем текущий playback
        if call_data["current_playback"]:
            # Asterisk автоматически остановит при новой записи
            call_data["current_playback"] = None
        
        call_data["is_speaking"] = False
        
        # ОЧИЩАЕМ ВСЮ ОЧЕРЕДЬ (ключевой момент из Voximplant!)
        if call_data["tts_queue"]:
            call_data["tts_queue"] = []
            call_data["tts_busy"] = False
            logger.info("🧹 Очередь TTS очищена при barge-in")
    
    async def process_ai_response_streaming(self, channel_id: str, response_generator):
        """Потоковая обработка ответа AI с разделителями | (аналог Voximplant MESSAGE handler)."""
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
                        await self.speak_queued(channel_id, sentence)
                
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
        """Страховочный таймер для остатка без | (аналог Voximplant SPEECH_END_TIMEOUT)."""
        await asyncio.sleep(self.SPEECH_END_TIMEOUT)
        
        if channel_id not in self.active_calls:
            return
        
        call_data = self.active_calls[channel_id]
        
        if call_data["response_buffer"].strip():
            tail = self.clean_text(call_data["response_buffer"])
            call_data["response_buffer"] = ""
            call_data["buffer_timer"] = None
            
            if tail:
                await self.speak_queued(channel_id, tail)

    async def process_user_speech(self, channel_id: str, audio_path: str):
        """Обрабатывает речь пользователя через ASR → AI → TTS."""
        if channel_id not in self.active_calls:
            logger.warning(f"Канал {channel_id} не найден в активных звонках")
            return

        call_data = self.active_calls[channel_id]
        session_id = call_data["session_id"]

        try:
            logger.info(f"🎯 Начинаем обработку речи пользователя для канала {channel_id}")
            
            # 1. ASR: Преобразуем речь в текст
            if self.asr:
                logger.info(f"🎤 Запускаем ASR для файла: {audio_path}")
                user_text = await self.asr.speech_to_text(audio_path)
                normalized_text = normalize_text(user_text)

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

            # 2. Останавливаем TTS при barge-in (пользователь заговорил)
            await self.stop_tts_on_barge_in(channel_id, "UserSpeech")

            # 3. AI: Получаем потоковый ответ от агента (как в Voximplant)
            if self.agent and normalized_text:
                logger.info(f"🤖 Запрашиваем потоковый ответ от AI агента для текста: '{normalized_text[:50]}...'")
                
                try:
                    response_generator = self.agent.get_response_generator(normalized_text, session_id=session_id)
                    
                    # ПОТОКОВАЯ ОБРАБОТКА (как в Voximplant MESSAGE handler)
                    await self.process_ai_response_streaming(channel_id, response_generator)
                    
                    # Собираем полный ответ для транскрипта
                    full_response = call_data.get("response_buffer", "") or "Ответ обработан потоково"
                    
                    logger.info(f"🤖 Потоковый ответ обработан для канала {channel_id}")

                    # Добавляем в транскрипт
                    call_data["transcript"].append({
                        "speaker": "bot", 
                        "text": full_response,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "kb": getattr(self.agent, 'last_kb', None)
                    })
                    
                except Exception as ai_error:
                    logger.error(f"❌ Ошибка AI агента: {ai_error}", exc_info=True)
                    # Fallback на обычный TTS
                    await self.speak_queued(channel_id, "Извините, произошла ошибка в системе ИИ")
            else:
                logger.warning("AI Agent недоступен или текст пустой")
                await self.speak_queued(channel_id, "Извините, система ИИ временно недоступна")

        except Exception as e:
            logger.error(f"❌ Ошибка обработки речи: {e}", exc_info=True)

    async def handle_playback_finished(self, event):
        """Обрабатывает завершение проигрывания - продолжает очередь TTS или запускает запись."""
        playback = event.get('playback', {})
        playback_id = playback.get('id')
        target_uri = playback.get('target_uri', '')

        # Извлекаем channel_id из target_uri (формат: channel:1234567890.123)
        if target_uri.startswith('channel:'):
            channel_id = target_uri.replace('channel:', '')

            logger.info(f"🔊 Проигрывание завершено: {playback_id} на канале {channel_id}")

            if channel_id in self.active_calls:
                call_data = self.active_calls[channel_id]

                # Проверяем, что это наше проигрывание
                if call_data.get("current_playback") == playback_id:
                    # Завершаем текущую фразу TTS и запускаем следующую
                    await self.finish_speak_one(channel_id)
                    
                    # Если очередь TTS пуста - запускаем запись пользователя
                    if not call_data.get("tts_queue") and not call_data.get("tts_busy"):
                        await self.start_user_recording(channel_id)
                    
    async def start_user_recording(self, channel_id: str):
        """Запускает запись речи пользователя."""
        try:
            # Генерируем имя файла для записи
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            recording_filename = f"user_{channel_id}_{timestamp}"
            
            logger.info(f"🎤 Запускаем запись речи пользователя: {recording_filename}")
            
            async with AsteriskARIClient() as ari:
                recording_id = await ari.start_recording(channel_id, recording_filename, max_duration=15)
                
                # Status 201 означает успешный запуск записи
                if recording_id and channel_id in self.active_calls:
                    self.active_calls[channel_id]["current_recording"] = recording_id
                    self.active_calls[channel_id]["recording_filename"] = recording_filename
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
        
        # Находим канал по имени записи
        channel_id = None
        for cid, call_data in self.active_calls.items():
            if call_data.get("recording_filename") == recording_name:
                channel_id = cid
                break
                
        if channel_id:
            # Путь к записанному файлу (Asterisk сохраняет в /var/spool/asterisk/recording/)
            recording_path = f"/var/spool/asterisk/recording/{recording_name}.wav"
            
            # Обрабатываем речь пользователя
            await self.process_user_speech(channel_id, recording_path)
        else:
            logger.warning(f"Не найден канал для записи: {recording_name}")
    
    async def handle_event(self, event):
        """Обрабатывает события от Asterisk ARI."""
        event_type = event.get('type')
        logger.info(f"📡 Event: {event_type}")
        
        if event_type == 'StasisStart':
            await self.handle_stasis_start(event)
        elif event_type == 'ChannelDestroyed':
            await self.handle_channel_destroyed(event)
        elif event_type == 'PlaybackFinished':
            # Событие завершения проигрывания - начинаем слушать пользователя
            await self.handle_playback_finished(event)
        elif event_type == 'RecordingFinished':
            # Событие завершения записи - обрабатываем речь пользователя
            await self.handle_recording_finished(event)
        else:
            # Логируем другие события для отладки
            logger.debug(f"Необработанное событие: {event_type}")
    
    async def run(self):
        """Запускает обработчик событий Asterisk ARI."""
        logger.info("🚀 Запуск AI Voice Assistant Handler...")
        
        if not self.agent:
            logger.warning("⚠️ AI Agent не инициализирован - работаем в режиме заглушки")
        
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
    
    # Запускаем обработчик
    handler = AsteriskAIHandler()
    await handler.run()

if __name__ == "__main__":
    asyncio.run(main())