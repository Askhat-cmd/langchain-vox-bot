#!/usr/bin/env python3
"""
Улучшенный Barge-in Manager для chunked системы
Цель: корректная обработка прерываний в сложной параллельной архитектуре
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Set
from collections import defaultdict

logger = logging.getLogger(__name__)

class BargeInManager:
    """
    Менеджер barge-in для chunked системы
    
    Проблемы с chunked barge-in:
    - Старая система: Один TTS процесс → легко остановить
    - Новая система: Множество параллельных TTS + очередь воспроизведения → сложнее остановить
    
    Решение: каскадная остановка всех компонентов
    """
    
    def __init__(self):
        # Управление состоянием barge-in по каналам
        self.barge_in_states: Dict[str, Dict] = defaultdict(dict)
        
        # Константы для защиты от ложных срабатываний
        self.BARGE_IN_GUARD_MS = 1500  # Защита от ложного barge-in (мс)
        self.DEBOUNCE_MS = 200  # Дебаунс для множественных событий
        
        # Таймеры для дебаунса
        self.debounce_timers: Dict[str, asyncio.Task] = {}
        
        logger.info("🚫 BargeInManager инициализирован")
    
    async def handle_barge_in(self, channel_id: str, event_name: str, call_data: Dict) -> bool:
        """
        Обрабатывает barge-in событие с каскадной остановкой
        
        Args:
            channel_id: ID канала
            event_name: Название события (UserSpeech, ChannelHangup, etc.)
            call_data: Данные звонка
            
        Returns:
            bool: True если barge-in обработан, False если проигнорирован
        """
        try:
            # Проверяем защиту от ложного barge-in
            if not self._should_process_barge_in(channel_id, call_data):
                logger.debug(f"🔇 Ignoring barge-in - too early or debounced")
                return False
            
            logger.info(f"🚫 [BARGE-IN] {event_name} → stopping all TTS processing for {channel_id}")
            
            # Устанавливаем состояние barge-in
            self.barge_in_states[channel_id] = {
                "active": True,
                "event_name": event_name,
                "timestamp": time.time(),
                "processed": False
            }
            
            # Каскадная остановка всех компонентов
            await self._cascade_stop_all_components(channel_id, call_data)
            
            # Отмечаем как обработанный
            self.barge_in_states[channel_id]["processed"] = True
            
            logger.info(f"✅ Barge-in processed for {channel_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Barge-in processing error for {channel_id}: {e}")
            return False
    
    def _should_process_barge_in(self, channel_id: str, call_data: Dict) -> bool:
        """
        Проверяет, нужно ли обрабатывать barge-in
        
        Защита от ложных срабатываний:
        1. Проверка времени с последнего TTS
        2. Дебаунс множественных событий
        3. Проверка состояния канала
        """
        try:
            # 1. Проверка времени с последнего TTS
            last_speak_time = call_data.get("last_speak_started_at", 0)
            current_time = int(time.time() * 1000)
            time_since_speak = current_time - last_speak_time
            
            if time_since_speak < self.BARGE_IN_GUARD_MS:
                logger.debug(f"🔇 Barge-in too early: {time_since_speak}ms < {self.BARGE_IN_GUARD_MS}ms")
                return False
            
            # 2. Проверка дебаунса
            if channel_id in self.debounce_timers:
                if not self.debounce_timers[channel_id].done():
                    logger.debug(f"🔇 Barge-in debounced for {channel_id}")
                    return False
            
            # 3. Проверка состояния канала
            if call_data.get("status") == "Completed":
                logger.debug(f"🔇 Channel {channel_id} already completed")
                return False
            
            # 4. Проверка, что канал действительно говорит
            if not call_data.get("is_speaking", False):
                logger.debug(f"🔇 Channel {channel_id} not speaking")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Barge-in validation error: {e}")
            return False
    
    async def _cascade_stop_all_components(self, channel_id: str, call_data: Dict):
        """
        Каскадная остановка всех компонентов системы
        
        Порядок остановки:
        1. Остановка текущего воспроизведения
        2. Очистка очередей воспроизведения
        3. Отмена активных TTS задач
        4. Очистка буферов AI генерации
        5. Сброс состояния канала
        """
        try:
            # 1. Останавливаем текущее воспроизведение
            await self._stop_current_playback(channel_id, call_data)
            
            # 2. Очищаем очереди воспроизведения
            await self._clear_playback_queues(channel_id, call_data)
            
            # 3. Отменяем активные TTS задачи
            await self._cancel_pending_tts_tasks(channel_id, call_data)
            
            # 4. Очищаем буферы AI генерации
            await self._clear_ai_buffers(channel_id, call_data)
            
            # 5. Сбрасываем состояние канала
            await self._reset_channel_state(channel_id, call_data)
            
            # 6. Устанавливаем дебаунс таймер
            self._set_debounce_timer(channel_id)
            
        except Exception as e:
            logger.error(f"❌ Cascade stop error for {channel_id}: {e}")
    
    async def _stop_current_playback(self, channel_id: str, call_data: Dict):
        """Останавливает текущее воспроизведение"""
        try:
            current_playback = call_data.get("current_playback")
            if current_playback:
                # В реальной реализации здесь будет вызов ARI для остановки
                logger.info(f"🔇 Stopping current playback: {current_playback}")
                # await ari_client.stop_playback(current_playback)
                
                # Очищаем ссылку
                call_data["current_playback"] = None
                
        except Exception as e:
            logger.error(f"❌ Stop playback error: {e}")
    
    async def _clear_playback_queues(self, channel_id: str, call_data: Dict):
        """Очищает очереди воспроизведения"""
        try:
            # Очищаем TTS очередь
            if "tts_queue" in call_data:
                call_data["tts_queue"] = []
                logger.info(f"🧹 Cleared TTS queue for {channel_id}")
            
            # Очищаем буфер ответа
            if "response_buffer" in call_data:
                call_data["response_buffer"] = ""
                logger.info(f"🧹 Cleared response buffer for {channel_id}")
            
            # Отменяем таймер буфера
            if "buffer_timer" in call_data and call_data["buffer_timer"]:
                call_data["buffer_timer"].cancel()
                call_data["buffer_timer"] = None
                
        except Exception as e:
            logger.error(f"❌ Clear queues error: {e}")
    
    async def _cancel_pending_tts_tasks(self, channel_id: str, call_data: Dict):
        """Отменяет активные TTS задачи"""
        try:
            # В реальной реализации здесь будет отмена задач ParallelTTSProcessor
            # parallel_tts.clear_all_queues(channel_id)
            
            # Сбрасываем флаги занятости
            call_data["tts_busy"] = False
            call_data["is_speaking"] = False
            
            logger.info(f"🧹 Cancelled TTS tasks for {channel_id}")
            
        except Exception as e:
            logger.error(f"❌ Cancel TTS tasks error: {e}")
    
    async def _clear_ai_buffers(self, channel_id: str, call_data: Dict):
        """Очищает буферы AI генерации"""
        try:
            # Очищаем буфер ответа
            call_data["response_buffer"] = ""
            
            # Отменяем таймер буфера
            if call_data.get("buffer_timer"):
                call_data["buffer_timer"].cancel()
                call_data["buffer_timer"] = None
            
            logger.info(f"🧹 Cleared AI buffers for {channel_id}")
            
        except Exception as e:
            logger.error(f"❌ Clear AI buffers error: {e}")
    
    async def _reset_channel_state(self, channel_id: str, call_data: Dict):
        """Сбрасывает состояние канала"""
        try:
            # Сбрасываем флаги
            call_data["user_interrupted"] = True
            call_data["is_speaking"] = False
            call_data["tts_busy"] = False
            call_data["current_playback"] = None
            
            # Устанавливаем время barge-in
            call_data["barge_in_time"] = time.time()
            
            logger.info(f"🔄 Reset channel state for {channel_id}")
            
        except Exception as e:
            logger.error(f"❌ Reset channel state error: {e}")
    
    def _set_debounce_timer(self, channel_id: str):
        """Устанавливает таймер дебаунса"""
        try:
            # Отменяем предыдущий таймер если есть
            if channel_id in self.debounce_timers:
                self.debounce_timers[channel_id].cancel()
            
            # Создаем новый таймер
            self.debounce_timers[channel_id] = asyncio.create_task(
                self._debounce_timer_callback(channel_id)
            )
            
        except Exception as e:
            logger.error(f"❌ Set debounce timer error: {e}")
    
    async def _debounce_timer_callback(self, channel_id: str):
        """Колбэк для таймера дебаунса"""
        try:
            await asyncio.sleep(self.DEBOUNCE_MS / 1000.0)
            
            # Очищаем состояние barge-in
            if channel_id in self.barge_in_states:
                del self.barge_in_states[channel_id]
            
            # Удаляем таймер
            if channel_id in self.debounce_timers:
                del self.debounce_timers[channel_id]
            
            logger.debug(f"⏰ Debounce timer expired for {channel_id}")
            
        except Exception as e:
            logger.error(f"❌ Debounce timer callback error: {e}")
    
    def is_barge_in_active(self, channel_id: str) -> bool:
        """Проверяет, активен ли barge-in для канала"""
        return channel_id in self.barge_in_states and self.barge_in_states[channel_id].get("active", False)
    
    def get_barge_in_state(self, channel_id: str) -> Optional[Dict]:
        """Возвращает состояние barge-in для канала"""
        return self.barge_in_states.get(channel_id)
    
    def clear_channel_state(self, channel_id: str):
        """Очищает состояние канала при завершении звонка"""
        try:
            if channel_id in self.barge_in_states:
                del self.barge_in_states[channel_id]
            
            if channel_id in self.debounce_timers:
                self.debounce_timers[channel_id].cancel()
                del self.debounce_timers[channel_id]
            
            logger.info(f"🧹 Cleared barge-in state for {channel_id}")
            
        except Exception as e:
            logger.error(f"❌ Clear channel state error: {e}")
    
    def get_statistics(self) -> Dict:
        """Возвращает статистику barge-in"""
        return {
            "active_barge_ins": len(self.barge_in_states),
            "active_timers": len(self.debounce_timers),
            "channels": list(self.barge_in_states.keys())
        }

# Глобальный экземпляр для использования в других модулях
barge_in_manager = BargeInManager()

def get_barge_in_manager() -> BargeInManager:
    """Возвращает глобальный экземпляр BargeInManager"""
    return barge_in_manager

