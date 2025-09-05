# 🚨 ПРОБЛЕМЫ ПРОИЗВОДИТЕЛЬНОСТИ AI ГОЛОСОВОГО АССИСТЕНТА

## 📊 КРАТКОЕ РЕЗЮМЕ ПРОБЛЕМЫ

**БЫЛО (Voximplant)**: 2-3 секунды общее время ответа ✅  
**СТАЛО (Asterisk)**: 11+ секунд общее время ответа ❌

## 🔍 ДЕТАЛЬНЫЙ АНАЛИЗ ПРОИЗВОДИТЕЛЬНОСТИ

### ⏱️ Профилирование показало узкие места:

```
06:19:50,118 - ⏱️ ПРОФИЛИРОВАНИЕ: Маршрутизация заняла 0.000с ✅
06:19:56,503 - ⏱️ ПРОФИЛИРОВАНИЕ: Оценка релевантности заняла 6.385с ❌
06:19:56,516 - ⏱️ ПРОФИЛИРОВАНИЕ: Общая подготовка заняла 6.418с ❌
06:19:57,007 - ⏱️ ПРОФИЛИРОВАНИЕ: Первый чанк получен через 0.491с ✅
06:20:01,594 - ⏱️ ПРОФИЛИРОВАНИЕ: Весь streaming занял 5.064с ❌
06:20:01,595 - ⏱️ ПРОФИЛИРОВАНИЕ STASIS: Обработка AI response заняла 11.497с ❌
```

## 🎯 КОРНЕВАЯ ПРИЧИНА ПРОБЛЕМЫ

### **Функция `_max_relevance()` в agent.py**

**Что делает**: Выполняет `similarity_search_with_relevance_scores()` дважды для оценки релевантности
**Время выполнения**: 6.4+ секунды
**Проблема**: Эта функция ОТСУТСТВОВАЛА в быстрой Voximplant версии!

```python
def _max_relevance(self, question: str, kb: str, k: int) -> float:
    # ЭТА ФУНКЦИЯ ТРАТИТ 6.4 СЕКУНДЫ!
    res = self.db.similarity_search_with_relevance_scores(
        question, k=k, filter={"kb": kb}
    )
```

## 📋 АРХИТЕКТУРНЫЕ РАЗЛИЧИЯ

### **Voximplant (БЫСТРАЯ) архитектура:**
```
WebSocket → Agent.get_response_generator() → RAG chain → Ответ
```

### **Asterisk (МЕДЛЕННАЯ) архитектура:**
```
ARI WebSocket → stasis_handler → Agent.get_response_generator() → 
_max_relevance() (6.4 сек!) → RAG chain → Ответ
```

## 🔧 ВЫПОЛНЕННЫЕ ИСПРАВЛЕНИЯ

### ✅ **1. Удалена медленная функция `_max_relevance()`**
```python
# БЫЛО:
max_score = self._max_relevance(user_question, target, k)  # 6.4 сек!
alt_score = self._max_relevance(user_question, alt, k)    # +6.4 сек!

# СТАЛО:
target = self._route_kb(user_question)  # 0.001 сек
# Просто используем результат маршрутизации без дополнительных проверок
```

### ✅ **2. Упрощена маршрутизация**
```python
# Вернулись к простой логике как в Voximplant версии
def _route_kb(self, text: str) -> str:
    # Быстрая маршрутизация по ключевым словам
    if any(marker in text.lower() for marker in tech_markers):
        return "tech"
    return "general"
```

### ✅ **3. Добавлено детальное профилирование**
- В `agent.py`: время маршрутизации, streaming, чанков
- В `stasis_handler.py`: время обработки AI response

## 🚀 ДОПОЛНИТЕЛЬНЫЕ ПРОБЛЕМЫ И РЕШЕНИЯ

### **1. gRPC TTS не работает**
```
ERROR - ❌ Неожиданная ошибка gRPC TTS: module 'yandex.cloud.ai.tts.v3.tts_service_pb2' has no attribute 'UtteranceSynthesisRequest'
```

**Причина**: Неправильно сгенерированные proto файлы  
**Статус**: Fallback на HTTP API работает (0.3-0.5 сек)

### **2. Множественные embedding запросы**
```
05:30:12,740 - POST https://api.openai.com/v1/embeddings  
05:30:13,257 - POST https://api.openai.com/v1/embeddings
05:30:14,087 - POST https://api.openai.com/v1/embeddings
```

**Причина**: LangChain делает несколько embedding запросов для RAG  
**Решение**: Это нормальное поведение, но можно оптимизировать кешированием

### **3. Двойные LLM запросы**
```
05:30:15,298 - POST /chat/completions (первый)
05:30:52,919 - POST /chat/completions (второй!)
```

**Причина**: Возможно, retry логика или fallback механизм

## 📈 ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ ПОСЛЕ ИСПРАВЛЕНИЙ

| Компонент | ДО исправления | ПОСЛЕ исправления |
|-----------|----------------|-------------------|
| **Маршрутизация** | 0.001с ✅ | 0.001с ✅ |
| **Оценка релевантности** | 6.385с ❌ | УДАЛЕНА ✅ |
| **Общая подготовка** | 6.418с ❌ | ~0.001с ✅ |
| **AI streaming** | 5.064с | 2-3с (ожидается) |
| **ОБЩЕЕ ВРЕМЯ** | 11.5с ❌ | 2-3с ✅ |

## 🎯 ФАЙЛЫ УЧАСТВУЮЩИЕ В ЦЕПОЧКЕ

### **Основные файлы для анализа:**
1. `app/backend/asterisk/stasis_handler.py` - главный обработчик
2. `app/backend/rag/agent.py` - AI агент (исправлен)
3. `app/backend/asterisk/ari_client.py` - ARI клиент
4. `app/backend/services/yandex_tts_service.py` - TTS сервис
5. `app/backend/services/asr_service.py` - ASR сервис
6. `app/backend/utils/text_normalizer.py` - нормализация
7. `app/backend/services/log_storage.py` - логирование
8. `.env` - конфигурация

### **Конфигурация Asterisk:**
- `/etc/asterisk/extensions.conf` - диалплан
- `/etc/asterisk/pjsip.conf` - SIP
- `/etc/asterisk/ari.conf` - ARI настройки

## 🔄 ПОСЛЕДОВАТЕЛЬНОСТЬ ВЫПОЛНЕНИЯ

1. **Звонок** → Asterisk dialplan → `Stasis(asterisk-bot)`
2. **stasis_handler.py** получает ARI WebSocket событие
3. **ari_client.py**: Answer() → StartRecording()
4. **asr_service.py**: OpenAI Whisper распознавание (~2 сек)
5. **agent.py**: 
   - ~~_max_relevance() (УДАЛЕНО - было 6.4 сек)~~
   - _route_kb() (0.001 сек)
   - RAG chain с ChromaDB (2-3 сек)
6. **yandex_tts_service.py**: HTTP TTS (0.3-0.5 сек)
7. **ari_client.py**: Playback() → StartRecording()
8. **log_storage.py**: Сохранение в SQLite

## 🚨 КРИТИЧЕСКИЕ МОМЕНТЫ

### **1. ChromaDB производительность**
- Используется старая версия с предупреждением deprecation
- Возможны проблемы с индексацией при большой базе знаний
- Рекомендуется обновление до `langchain-chroma`

### **2. OpenAI API лимиты**
- Streaming может быть заблокирован для некоторых организаций
- Есть fallback на non-streaming режим

### **3. Память и ресурсы**
- ChromaDB загружается в память при старте (~9 секунд)
- Embeddings создаются для каждого запроса

## 💡 РЕКОМЕНДАЦИИ ДЛЯ ДАЛЬНЕЙШЕЙ ОПТИМИЗАЦИИ

### **Краткосрочные (1-2 дня):**
1. ✅ Удалить `_max_relevance()` (СДЕЛАНО)
2. 🔄 Исправить gRPC TTS для достижения 1-1.5 сек
3. 🔄 Добавить кеширование частых ответов

### **Среднесрочные (1 неделя):**
1. Обновить ChromaDB до новой версии
2. Оптимизировать размер embeddings
3. Добавить Redis для кеширования

### **Долгосрочные (1 месяц):**
1. Переписать на async/await полностью
2. Добавить load balancing
3. Оптимизировать промпты и RAG pipeline

## 🎯 ЗАКЛЮЧЕНИЕ

**Главная проблема найдена и исправлена**: функция `_max_relevance()` тратила 6.4+ секунды на ненужные similarity search запросы.

После удаления этой функции ожидается возврат к производительности уровня Voximplant версии: **2-3 секунды общего времени ответа**.

---

*Документ создан: 04.09.2025*  
*Статус: Критическая оптимизация выполнена*  
*Следующий шаг: Тестирование производительности*
