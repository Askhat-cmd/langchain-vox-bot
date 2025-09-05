# 🚀 ПЛАН КОМПЛЕКСНОЙ ОПТИМИЗАЦИИ AI ГОЛОСОВОГО БОТА

## 📊 ТЕКУЩЕЕ СОСТОЯНИЕ
- **Общее время ответа**: 9.5+ секунд ❌
- **Целевое время**: 2-3 секунды ✅
- **Основная проблема решена**: _max_relevance() удалена (-6.4 сек) ✅

## 🎯 КРИТИЧЕСКИЕ УЗКИЕ МЕСТА

### 1. AI STREAMING (9.5 сек → 2-3 сек) - КРИТИЧНО ⚡
**Проблема**: Множественные LLM запросы и неоптимальная потоковая обработка
**Файл**: `agent.py`

#### Конкретные исправления:
```python
# ТЕКУЩАЯ ПРОБЛЕМА в agent.py:
- Множественные embedding запросы (3-4 запроса по 0.5-1 сек каждый)
- Двойные LLM запросы (primary + fallback)
- Медленная история контекста
- Неоптимальные промпты

# РЕШЕНИЕ:
1. Кеширование embeddings
2. Оптимизация RAG pipeline
3. Уменьшение контекста
4. Batch processing
```

### 2. gRPC TTS НЕ РАБОТАЕТ (HTTP fallback: 0.5 сек) - ВЫСОКИЙ ⚡
**Проблема**: `UtteranceSynthesisRequest` не найден в proto файлах
**Файл**: `yandex_tts_service.py`

#### Решение:
```bash
# Перегенерировать proto файлы:
pip install grpcio-tools
python -m grpc_tools.protoc --python_out=. --grpc_python_out=. *.proto

# ИЛИ: Исправить импорт в коде
from yandex.cloud.ai.tts.v3 import tts_service_pb2_grpc
from yandex.cloud.ai.tts.v3.tts_service_pb2 import UtteranceSynthesisRequest
```

### 3. CHROMADB УСТАРЕВШАЯ ВЕРСИЯ - СРЕДНИЙ ⚠️
**Проблема**: Deprecation warnings и медленные запросы
**Файл**: `agent.py`

#### Решение:
```bash
pip uninstall langchain-community
pip install langchain-chroma
```

## 🔧 ПОШАГОВЫЙ ПЛАН ИСПРАВЛЕНИЙ

### ЭТАП 1: Критические исправления (1-2 часа)
1. **Исправить gRPC TTS** - экономия 0.3-0.5 сек
2. **Добавить кеширование embeddings** - экономия 1-2 сек
3. **Оптимизировать промпты** - экономия 1-2 сек

### ЭТАП 2: Архитектурные улучшения (2-4 часа)  
1. **Обновить ChromaDB** - экономия 0.5-1 сек
2. **Оптимизировать RAG pipeline** - экономия 2-3 сек  
3. **Добавить профилирование** - мониторинг производительности

### ЭТАП 3: Продвинутая оптимизация (4-8 часов)
1. **Redis кеширование**
2. **Batch processing** 
3. **Connection pooling**
4. **Load balancing**

## 📝 КОНКРЕТНЫЕ ФАЙЛЫ ДЛЯ ИЗМЕНЕНИЯ

### 1. `agent.py` - ОСНОВНЫЕ ИЗМЕНЕНИЯ
```python
# ДОБАВИТЬ кеширование embeddings:
import redis
self.redis_client = redis.Redis()

def _get_cached_embeddings(self, text):
    cache_key = f"emb:{hashlib.md5(text.encode()).hexdigest()}"
    cached = self.redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    return None

# ОПТИМИЗИРОВАТЬ RAG запросы:
def _optimized_retrieval(self, question, kb, k=3):
    # Сначала проверяем кеш
    cached_docs = self._get_cached_documents(question, kb)
    if cached_docs:
        return cached_docs
    
    # Один запрос вместо множественных
    docs = self.db.similarity_search(
        question, k=k, filter={"kb": kb}
    )
    self._cache_documents(question, kb, docs)
    return docs
```

### 2. `yandex_tts_service.py` - ИСПРАВЛЕНИЕ gRPC
```python
# ИСПРАВИТЬ импорты:
try:
    from yandex.cloud.ai.tts.v3.tts_service_pb2 import UtteranceSynthesisRequest
    from yandex.cloud.ai.tts.v3.tts_pb2 import AudioFormatOptions, ContainerAudio
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False

# ДОБАВИТЬ fallback логику:
async def text_to_speech(self, text, filename):
    if GRPC_AVAILABLE:
        try:
            return await self.text_to_speech_grpc(text, filename)
        except Exception as e:
            logger.warning(f"gRPC failed: {e}, using HTTP")
    
    return await self.text_to_speech_http(text, filename)
```

### 3. `stasis_handler.py` - ПРОФИЛИРОВАНИЕ
```python
# ДОБАВИТЬ детальное профилирование:
import time

async def process_user_speech(self, channel_id, audio_path):
    total_start = time.time()
    
    # ASR профилирование
    asr_start = time.time()
    user_text = await self.asr.speech_to_text(audio_path)
    asr_time = time.time() - asr_start
    logger.info(f"⏱️ ASR время: {asr_time:.3f}с")
    
    # AI профилирование  
    ai_start = time.time()
    response_generator = self.agent.get_response_generator(user_text, session_id)
    ai_time = time.time() - ai_start  
    logger.info(f"⏱️ AI время: {ai_time:.3f}с")
    
    total_time = time.time() - total_start
    logger.info(f"⏱️ Общее время обработки: {total_time:.3f}с")
```

## 📈 ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ

| Компонент | Сейчас | После оптимизации | Экономия |
|-----------|---------|-------------------|----------|
| gRPC TTS | 0.5с (HTTP) | 0.1с (gRPC) | 0.4с |
| AI Streaming | 9.5с | 2.5с | 7.0с |
| Embeddings | 2.0с | 0.2с (кеш) | 1.8с |
| ChromaDB | 1.0с | 0.3с | 0.7с |
| **ИТОГО** | **13.0с** | **3.1с** | **9.9с** |

## ✅ КРИТЕРИИ УСПЕХА
- [ ] Общее время ответа ≤ 3 секунды
- [ ] gRPC TTS работает без ошибок  
- [ ] Отсутствие множественных embedding запросов
- [ ] Профилирование показывает узкие места
- [ ] Стабильная работа при нагрузке

## 🚨 ПРИОРИТЕТНОСТЬ ИСПРАВЛЕНИЙ
1. **🔥 КРИТИЧНО**: Исправить AI streaming (экономия 7 сек)
2. **⚡ ВЫСОКО**: gRPC TTS (экономия 0.4 сек)  
3. **⚠️ СРЕДНЕ**: ChromaDB обновление (экономия 0.7 сек)
4. **💡 НИЗКО**: Дополнительные оптимизации

---

*Документ создан: 04.09.2025*  
*Статус: План готов к реализации*  
*Ожидаемый результат: 3x ускорение работы бота*