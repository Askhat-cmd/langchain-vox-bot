# 🚀 ПРОФЕССИОНАЛЬНЫЙ ПЛАН ОПТИМИЗАЦИИ AI ГОЛОСОВОГО БОТА

## 📊 ТЕКУЩИЙ СТАТУС ПРОЕКТА

### ✅ ВЫПОЛНЕННЫЕ ИСПРАВЛЕНИЯ:
- Удалена функция `_max_relevance()` (экономия 6.4+ сек)
- Добавлено детальное профилирование в `agent.py` и `stasis_handler.py`
- Упрощена логика маршрутизации RAG

### ❌ КРИТИЧЕСКИЕ ПРОБЛЕМЫ:
- **AI Streaming**: 9.5 секунд (целевое: 2-3 сек)
- **gRPC TTS**: не работает, fallback на HTTP (0.5 сек вместо 0.1 сек)
- **Множественные embedding запросы**: 3-4 запроса по 0.5-1 сек каждый
- **Устаревшая ChromaDB**: deprecation warnings

## 🎯 СТРУКТУРА ПРОЕКТА И ФАЙЛЫ

### Основная цепочка обработки:
```
/etc/asterisk/extensions.conf → Stasis(asterisk-bot)
    ↓
app/backend/asterisk/stasis_handler.py (ARI WebSocket)
    ↓
app/backend/asterisk/ari_client.py (Answer, Record, Play)
    ↓
app/backend/services/asr_service.py (OpenAI Whisper)
    ↓
app/backend/utils/text_normalizer.py (нормализация)
    ↓
app/backend/rag/agent.py (RAG + ChromaDB + OpenAI GPT)
    ↓
app/backend/services/yandex_tts_service.py (Yandex TTS)
    ↓
app/backend/asterisk/ari_client.py (Playback)
    ↓
app/backend/services/log_storage.py (SQLite лог)
```

### Конфигурационные файлы:
- `config/prompts.json` - промпты для AI
- `kb/general.md`, `kb/tech.md` - база знаний
- `scripts/create_embeddings.py` - создание векторной базы
- `data/chroma/` - ChromaDB векторная база
- `data/db/log_db.sqlite` - логи звонков

## 🔧 ПЛАН ОПТИМИЗАЦИИ ПО ЭТАПАМ

### ЭТАП 1: КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ (2-4 часа)

#### 1.1 Исправить gRPC TTS (экономия 0.4 сек)
**Файл**: `app/backend/services/yandex_tts_service.py`

**Проблема**: 
```python
# ОШИБКА:
module 'yandex.cloud.ai.tts.v3.tts_service_pb2' has no attribute 'UtteranceSynthesisRequest'
```

**Решение**:
```bash
# 1. Перегенерировать proto файлы
cd /root/Asterisk_bot/asterisk-vox-bot/app/backend/services/
python -m grpc_tools.protoc \
    --python_out=. \
    --grpc_python_out=. \
    yandex/cloud/ai/tts/v3/*.proto

# 2. Исправить импорты в yandex_tts_service.py
```

**Ожидаемый результат**: gRPC TTS работает, латентность 0.1 сек вместо 0.5 сек

#### 1.2 Добавить Redis кеширование embeddings (экономия 1-2 сек)
**Файл**: `app/backend/rag/agent.py`

**Установка зависимостей**:
```bash
sudo apt-get install redis-server
sudo systemctl start redis-server
pip install redis
```

**Изменения в коде**:
- Добавить Redis клиент в `__init__`
- Кешировать результаты `similarity_search`
- TTL кеша: 1 час для embeddings

**Ожидаемый результат**: 80%+ кеш-попаданий для повторных запросов

#### 1.3 Оптимизировать RAG pipeline (экономия 2-3 сек)
**Файл**: `app/backend/rag/agent.py`

**Проблемы**:
- Множественные embedding запросы
- Двойные LLM запросы (primary + fallback)
- Избыточный контекст

**Решения**:
- Один embedding запрос вместо 3-4
- Убрать fallback логику для streaming
- Сократить размер контекста с 10 до 5 документов

### ЭТАП 2: АРХИТЕКТУРНЫЕ УЛУЧШЕНИЯ (4-6 часов)

#### 2.1 Обновить ChromaDB (экономия 0.5-1 сек)
**Файл**: `app/backend/rag/agent.py`

```bash
pip uninstall langchain-community
pip install langchain-chroma
```

**Изменения**:
```python
# БЫЛО:
from langchain_community.vectorstores import Chroma

# СТАЛО:
from langchain_chroma import Chroma
```

#### 2.2 Оптимизировать промпты (экономия 1-2 сек)
**Файл**: `config/prompts.json`

- Сократить системные промпты на 30-50%
- Убрать избыточные инструкции
- Оптимизировать для streaming

#### 2.3 Добавить connection pooling
**Файлы**: `app/backend/services/asr_service.py`, `yandex_tts_service.py`

- Переиспользование HTTP соединений
- Async session pooling
- Timeout оптимизация

### ЭТАП 3: МОНИТОРИНГ И СТАБИЛЬНОСТЬ (2-4 часа)

#### 3.1 Улучшить профилирование
**Файл**: `app/backend/asterisk/stasis_handler.py`

- Детальные метрики по каждому компоненту
- Сохранение метрик в SQLite
- Dashboard для мониторинга

#### 3.2 Error handling и fallback
- Graceful degradation при ошибках
- Circuit breaker pattern
- Health checks

## 📈 ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ

### До оптимизации:
| Компонент | Время | Проблемы |
|-----------|-------|----------|
| ASR | 2.0с | ✅ Работает |
| AI Streaming | 9.5с | ❌ Критично |
| TTS | 0.5с | ❌ HTTP fallback |
| **ИТОГО** | **12.0с** | ❌ Неприемлемо |

### После оптимизации:
| Компонент | Время | Улучшения |
|-----------|-------|-----------|
| ASR | 2.0с | ✅ Без изменений |
| AI Streaming | 2.5с | ✅ Кеш + оптимизация |
| TTS | 0.1с | ✅ gRPC работает |
| **ИТОГО** | **4.6с** | ✅ Приемлемо |

### Целевые метрики:
- **Общее время ответа**: ≤ 3 секунды
- **Cache hit rate**: ≥ 80% для embeddings
- **gRPC TTS success rate**: ≥ 95%
- **Error rate**: ≤ 1%

## 🚨 ПЛАН РЕАЛИЗАЦИИ

### Неделя 1: Критические исправления
- **День 1-2**: Исправить gRPC TTS
- **День 3-4**: Добавить Redis кеширование
- **День 5**: Оптимизировать RAG pipeline

### Неделя 2: Архитектурные улучшения
- **День 1-2**: Обновить ChromaDB
- **День 3-4**: Оптимизировать промпты и connection pooling
- **День 5**: Тестирование и отладка

### Неделя 3: Мониторинг и стабильность
- **День 1-2**: Улучшить профилирование
- **День 3-4**: Error handling и fallback
- **День 5**: Финальное тестирование

## ✅ КРИТЕРИИ ПРИЕМКИ

### Обязательные требования:
- [ ] Общее время ответа ≤ 3 секунды
- [ ] gRPC TTS работает стабильно
- [ ] Отсутствуют множественные embedding запросы
- [ ] Нет deprecation warnings
- [ ] Детальные метрики производительности

### Желательные улучшения:
- [ ] Cache hit rate ≥ 80%
- [ ] Error rate ≤ 1%
- [ ] Graceful degradation при ошибках
- [ ] Dashboard для мониторинга

## 🔧 ГОТОВЫЕ КОМАНДЫ ДЛЯ ВЫПОЛНЕНИЯ

### Подготовка среды:
```bash
cd /root/Asterisk_bot/asterisk-vox-bot
source venv/bin/activate

# Установка зависимостей
sudo apt-get install redis-server
sudo systemctl start redis-server
pip install redis grpcio-tools langchain-chroma psutil

# Обновление ChromaDB
pip uninstall langchain-community
pip install langchain-chroma
```

### Перегенерация proto файлов:
```bash
cd app/backend/services/
python -m grpc_tools.protoc \
    --python_out=. \
    --grpc_python_out=. \
    yandex/cloud/ai/tts/v3/*.proto
```

### Проверка статуса:
```bash
# Проверить Redis
redis-cli ping

# Проверить Asterisk
sudo systemctl status asterisk

# Проверить сервис
sudo systemctl status metrotech-bot
```

## 📋 РИСКИ И МИТИГАЦИЯ

### Высокие риски:
1. **gRPC proto файлы**: Может потребоваться ручная правка импортов
2. **Redis производительность**: Мониторинг памяти и CPU
3. **ChromaDB миграция**: Возможны проблемы совместимости

### Митигация:
- Поэтапное внедрение с rollback планом
- Тестирование на копии продакшена
- Мониторинг метрик после каждого изменения

---

**Документ создан**: 04.09.2025  
**Статус**: Готов к реализации  
**Ожидаемый результат**: 4x ускорение работы бота (12с → 3с)  
**Команда**: AI Assistant + User  
**Приоритет**: КРИТИЧЕСКИЙ
