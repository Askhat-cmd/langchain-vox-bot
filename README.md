# 📞 Голосовой AI-ассистент для компании "Метротэст"

> 📅 Актуально на 2025-09-05  
> 🚀 **МИГРАЦИЯ ЗАВЕРШЕНА**: Voximplant → Asterisk ARI

Проект реализует **автоматического голосового ассистента**, который:
- Принимает звонки через **Asterisk ARI** (мигрировано с Voximplant)
- Понимает голос клиента с помощью **OpenAI Whisper ASR**
- Находит ответ через **AI-агента с LangChain** (на Python)
- Отвечает вслух, используя **Yandex TTS** (gRPC + HTTP fallback)
- Поддерживает **интеллектуальный barge-in** — прерывание бота при речи клиента
- Предоставляет **продвинутый веб-интерфейс** для администрирования
- **Redis кеширование** для ускорения повторных запросов

---

## 🖥️ Админ-панель

Проект включает в себя многофункциональный веб-интерфейс для мониторинга и управления системой, доступный по адресу `/logs-ui/`.

**Возможности:**
- **Просмотр логов звонков:** Вся история общения с ботом доступна в виде таблицы с **сортировкой** по дате и статусу.
- **Детализация звонка:** Можно открыть любой звонок и посмотреть полный транскрипт диалога.
- **Продвинутая фильтрация:**
    - Полнотекстовый поиск по диалогам.
    - Фильтрация по статусу (`Completed`, `Failed` и т.д.) с помощью удобных чипов.
    - Гибкая фильтрация по датам с быстрыми пресетами ("Сегодня", "Вчера" и т.д.).
- **Уведомления:** Toast-уведомления информируют об успешном выполнении операций (например, "Промпты сохранены").
- **Экспорт в CSV:** Все логи можно выгрузить в `CSV` файл для дальнейшего анализа.
- **Две базы знаний и управление ими:**
  - Просмотр `.md` файлов: кнопки «База знаний (general)» и «База знаний (tech)».
  - Обновление: «Обновить БЗ (general)» и «Обновить БЗ (tech)». При загрузке **заголовки автоматически дублируются**, создаётся бэкап и фоном пересобираются эмбеддинги (агент перезагружается автоматически).
  - В таблице логов у завершённых звонков показывается метка источника ответа: `[general]` или `[tech]`. В модалке диалога метка отображается у каждой реплики бота.
- **Управление промптами:**
  - Редактирование всех ключевых промптов (приветствие, системный промпт, контекстуализатор) прямо из интерфейса.
  - Изменения применяются "на лету" без перезапуска сервера.
- **Настройки поиска:** Кнопка «Настройки поиска» позволяет менять `KB_TOP_K` (сколько документов извлекаем) и `KB_FALLBACK_THRESHOLD` (порог уверенности для fallback на вторую БЗ) без редактирования `.env`.
- **Инструкция:** Кнопка «Инструкция по настройке» открывает `logs-ui/instruction.md`.
- **Безопасность:** Доступ к операциям изменения данных (удаление логов, обновление промптов и БЗ) защищен **API-ключом**, который запрашивается в специальном модальном окне.

---

## 🧠 Архитектура проекта (после миграции)

| Компонент | Назначение |
|---|---|
| `app/backend/asterisk/stasis_handler.py` | **Основной обработчик** Asterisk ARI WebSocket |
| `app/backend/asterisk/ari_client.py` | Клиент для работы с Asterisk ARI API |
| `app/backend/rag/agent.py` | LangChain-агент: RAG, маршрутизация general/tech |
| `app/backend/services/yandex_tts_service.py` | Yandex TTS (gRPC + HTTP fallback) |
| `app/backend/services/asr_service.py` | OpenAI Whisper ASR |
| `scripts/create_embeddings.py` | Скрипт для создания/пересоздания базы векторов |
| `app/frontend/logs-ui/` | Веб-интерфейс для администрирования |
| `.env` | Файл конфигурации (API ключи, пути к файлам) |

### 🔄 **УСТАРЕВШИЕ КОМПОНЕНТЫ (после миграции):**
- ❌ `app/backend/main.py` - старый WebSocket сервер для Voximplant
- ❌ `app/voximplant/scenario_barge-in_2.js` - Voximplant сценарий


---

## 🔁 Сценарий звонка (Asterisk ARI)

1. **Клиент звонит** → звонок принимается Asterisk и направляется в Stasis приложение `asterisk-bot`
2. **Asterisk ARI** запускает `stasis_handler.py` через WebSocket соединение
3. `stasis_handler.py` создает сессию звонка и инициализирует AI компоненты
4. **Приветствие**: TTS воспроизводит приветственное сообщение
5. **Запись речи**: Asterisk записывает речь пользователя
6. **ASR**: OpenAI Whisper распознает речь в текст
7. **AI обработка**: 
   - Агент использует **RAG** для поиска в базе знаний
   - **Redis кеширование** ускоряет повторные запросы
   - Ответ генерируется через `gpt-4o-mini` с streaming
8. **TTS**: Yandex TTS синтезирует речь (gRPC с HTTP fallback)
9. **Воспроизведение**: Asterisk воспроизводит аудио через ARI
10. **Логирование**: Полный диалог сохраняется в SQLite базу

---

## 🚀 Запуск проекта

### Предварительные требования:
- **Asterisk** с настроенным ARI
- **Redis** сервер
- **Python 3.12+** с виртуальным окружением
- **API ключи**: OpenAI, Yandex Cloud

### Команды запуска:
```bash
# 1. Активация виртуального окружения
cd /root/Asterisk_bot/asterisk-vox-bot
source venv/bin/activate

# 2. Запуск AI бота (systemd)
sudo systemctl start metrotech-bot

# 3. Запуск основного обработчика звонков
python app/backend/asterisk/stasis_handler.py

# 4. Проверка статуса
sudo systemctl status metrotech-bot
ps aux | grep stasis_handler
```

### Веб-интерфейс:
- **Админ-панель**: http://localhost:9000/logs-ui/
- **API**: http://localhost:9000/

### Технические требования для оптимизации:
```bash
# 1. Установить Redis для кеширования
sudo apt-get install redis-server

# 2. Обновить зависимости
pip install langchain-chroma  # вместо langchain-community

# 3. Перегенерировать proto файлы (если нужно)
python -m grpc_tools.protoc --python_out=. *.proto
```

---

## ⚠️ Текущие проблемы и оптимизации

### 🔥 **КРИТИЧЕСКИЕ ПРОБЛЕМЫ:**
1. **AI Streaming медленный**: 8.7с вместо целевых 2-3с
   - **Корневая причина**: Множественные embedding запросы (3-4 запроса к OpenAI API)
   - **Детали**: Каждый embedding запрос 0.5-1с, в сумме 2+ секунды
   - **Решение**: Redis кеширование embeddings уже добавлено

2. **gRPC TTS не работает**: 
   - **Ошибка**: `You have to specify folder ID for user account`
   - **Причина**: Проблемы с аутентификацией Yandex Cloud
   - **Fallback**: HTTP TTS (потеря 0.4с на запрос)
   - **Статус**: gRPC импорты исправлены, нужна настройка аутентификации

3. **Устаревшая ChromaDB**:
   - Используется deprecated `langchain-community.vectorstores.Chroma`
   - Нужно обновить до `langchain-chroma`
   - Предупреждения в логах о deprecation

### ✅ **ИСПРАВЛЕНО:**
- ✅ **Миграция Voximplant → Asterisk ARI** - полный переход на ARI WebSocket
- ✅ **Удалена медленная функция `_max_relevance()`** - экономия 6.4+ секунды
- ✅ **Redis кеширование включено** - предотвращение повторных embedding запросов
- ✅ **gRPC импорты исправлены** - `UtteranceSynthesisRequest` в `tts_pb2`
- ✅ **Система стабильно работает** - обработка звонков через Asterisk

### 📊 **ТЕКУЩАЯ ПРОИЗВОДИТЕЛЬНОСТЬ:**
- **ASR (Whisper)**: 2.5с ✅
- **AI Streaming**: 8.7с ❌ (цель: 2-3с)
- **TTS (HTTP)**: 0.7с ✅
- **TTS (gRPC)**: 0с ❌ (цель: 0.1с)

### 🎯 **ПЛАН ОПТИМИЗАЦИИ:**

#### **Критичные исправления (экономия 7 сек):**
- ✅ **Redis кеширование embeddings** - предотвратит повторные запросы к OpenAI API
- 🔄 **Оптимизация RAG pipeline** - устранение множественных LLM запросов

#### **Высокоприоритетные исправления (экономия 2.4 сек):**
- 🔄 **Исправление gRPC TTS** - восстановление быстрого синтеза речи
- 🔄 **Устранение fallback логики** - упрощение цепочки обработки

#### **Среднеприоритетные улучшения (экономия 0.7 сек):**
- 🔄 **Обновление ChromaDB** до актуальной версии
- ✅ **Детальное профилирование** для мониторинга производительности

### 🎯 **ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:**
- **Общее время ответа**: с 9.5 сек до 2-3 сек (3x ускорение)
- **AI Streaming**: с 9.5 сек до 2 сек
- **TTS**: восстановление gRPC (0.1 сек вместо 0.5 сек)
- **Кеш-попадания**: 80%+ для повторных запросов

---

## 🎙️ Asterisk: обработка звонков и barge-in

Система использует **Asterisk ARI** для обработки звонков с поддержкой интеллектуального barge-in:

- **Сегментация**: AI агент завершает предложения символом `|` для естественных пауз
- **Streaming TTS**: Yandex TTS синтезирует речь по частям для быстрого отклика
- **Barge-in**: Пользователь может прервать бота во время воспроизведения
- **Запись речи**: Asterisk записывает речь пользователя для ASR обработки
- **Профилирование**: Детальное логирование времени каждого этапа обработки

### Ключевые компоненты:
- **stasis_handler.py**: Основной обработчик ARI WebSocket событий
- **ari_client.py**: Клиент для управления каналами и воспроизведением
- **Профилирование**: Логи показывают время ASR, AI, TTS для оптимизации

---

## 🧭 Две базы знаний и маршрутизация (general/tech)

- Векторное хранилище общее (одна Chroma), документы помечены метаданными `kb=general` и `kb=tech`.
- Агент строит два ретривера с фильтрами по метаданным и выбирает первичный по ключевым словам (роутинг).
- Если максимальная релевантность ниже `KB_FALLBACK_THRESHOLD`, выполняется запрос ко второй БЗ; берётся лучший результат.
- Используемые параметры можно менять в админке: `KB_TOP_K`, `KB_FALLBACK_THRESHOLD`.
- В логах и в UI отображается источник ответа: `[general]` или `[tech]`.

---

## 📁 Структура проекта (упрощённая)

```bash
.
├── app/
│   ├── backend/
│   │   ├── main.py              # FastAPI‑сервер (HTTP/WS, статика)
│   │   ├── rag/agent.py         # Агент (LangChain + Chroma)
│   │   ├── services/log_storage.py
│   │   └── utils/text_normalizer.py
│   ├── frontend/logs-ui/        # Веб‑админка
│   └── voximplant/scenario_barge-in_2.js  # Сценарий Voximplant (локальная копия)
├── scripts/
│   ├── create_embeddings.py
│   └── test_agent.py
├── config/prompts.json
├── kb/
│   ├── general.md
│   └── tech.md
├── data/
│   ├── chroma/                  # Персистентное хранилище Chroma
│   ├── db/log_db.sqlite         # SQLite логи
│   └── logs/app.log             # Логи приложения
├── .env
├── requirements.txt
└── README.md
```

---

## 🚀 Запуск и настройка

### 1. Первоначальная настройка
1.  **Клонируйте репозиторий.**
2.  **Создайте и активируйте виртуальное окружение:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
3.  **Установите зависимости:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Создайте файл `.env`** и заполните его необходимыми переменными:
    ```env
    OPENAI_API_KEY="sk-..."
    API_SECRET_KEY="ваш_секретный_ключ_для_доступа_к_api"
    PROMPTS_FILE_PATH="config/prompts.json"
    KNOWLEDGE_BASE_PATH="kb/general.md"
    KNOWLEDGE_BASE2_PATH="kb/tech.md"
    PERSIST_DIRECTORY="data/chroma"
    DB_PATH="data/db/log_db.sqlite"
    KB_TOP_K="3"
    KB_FALLBACK_THRESHOLD="0.2"
    ```
5.  **Наполните `knowledge_base.md`** вашими данными.

### 2. Создание базы знаний
Теперь скрипт индексирует ОДНУ персистентную Chroma с двумя наборами документов и метаданными:
- `kb=general` из `knowledge_base.md`
- `kb=tech` из `knowledge_base_2.md`

При первом запуске или после обновления любой из БЗ создайте векторы:
```bash
python3 scripts/create_embeddings.py
```

### Как устроена подготовка БЗ (RAG)

1) Обогащение заголовков

- Перед разбиением текста скрипт дублирует каждый Markdown‑заголовок (h1–h6): сразу после строки вида `# Раздел` добавляется строка без `#` — `Раздел`. Это повышает информативность каждого чанка и улучшает поиск.

2) Разбиение на чанки

- Текст делится по кастомному разделителю «<<->>».
- Параметры: `chunk_size=4000`, `chunk_overlap=200`, `add_start_index=True`.
- Если в файле мало «<<->>», чанков будет мало и они будут крупные. Рекомендуется ставить «<<->>» между логическими блоками.

3) Эмбеддинги и хранилище

- Используется `OpenAIEmbeddings` (ключ берётся из `OPENAI_API_KEY`).
- Векторное хранилище — `Chroma` с персистентностью в `PERSIST_DIRECTORY` (по умолчанию `chroma_db_metrotech/`).
- Скрипт пересоздаёт базу при каждом запуске.
- Пересборка выполняется атомарно: новая БД строится во временной директории `chroma_db_metrotech_tmp` и затем заменяет основную; старый каталог удаляется. Это исключает ошибки чтения во время обновления.

> Примечание: файлы БЗ можно просматривать и обновлять из админки; сервер сам продублирует заголовки, сделает бэкап и пересоберёт эмбеддинги в фоне.

### 3. Тестирование агента (Опционально, но рекомендуется)
После любых изменений в `knowledge_base.md` или `prompts.json` запустите тесты, чтобы убедиться в качестве ответов:
```bash
python3 test_agent.py
```

### 4. Запуск сервера
Для разработки (с автоматической перезагрузкой при изменении кода):
```bash
uvicorn app.backend.main:app --host 0.0.0.0 --port 9000 --reload
```

Для продакшн-режима:
```bash
nohup venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:9000 app.backend.main:app &
```

---

## ℹ️ Полезные детали

- Переменные `.env`:
  - `OPENAI_API_KEY` — ключ OpenAI.
  - `API_SECRET_KEY` — секрет для защищённых операций в админке (передаётся в заголовке `X-API-Key`).
  - `PROMPTS_FILE_PATH` — путь к `prompts.json`.
  - `KNOWLEDGE_BASE_PATH` — путь к файлу БЗ (`knowledge_base.md` или др.).
  - `PERSIST_DIRECTORY` — директория Chroma (например, `chroma_db_metrotech`).

- Эндпойнты:
  - `GET /` — здоровье сервиса.
  - `GET /logs` — логи (параметры: `q`, `date_from`, `date_to`, `status`).
  - `GET /logs/csv` — экспорт CSV.
  - `DELETE /logs` — очистка логов (нужен `X-API-Key`).
  - `GET /kb` — получить текущую БЗ.
  - `POST /kb/upload` — загрузка новой БЗ; сервер сам дублирует заголовки, делает бэкап и в фоне пересоздаёт эмбеддинги (нужен `X-API-Key`).
  - `GET /kb2` — получить техническую БЗ.
  - `POST /kb2/upload` — загрузка технической БЗ (нужен `X-API-Key`).
  - `GET /api/prompts` — получить промпты.
  - `POST /api/prompts` — сохранить промпты и «горячо» перезагрузить агента (нужен `X-API-Key`).
  - `GET /api/settings` — текущие значения `KB_TOP_K`, `KB_FALLBACK_THRESHOLD`, а также `llm_model_primary`, `llm_model_fallback`, `llm_temperature`.
  - `POST /api/settings` — обновить параметры поиска (нужен `X-API-Key`).
  - `POST /api/model-settings` — обновить модельные настройки LLM (нужен `X-API-Key`).
  - `POST /api/normalize` — тест нормализации текста (см. раздел ниже).
  - `WS /ws?callerId=...` — стриминг ответов агента (наружу всегда идёт поток по WebSocket).

### Настройки модели (LLM)

- Переменные окружения:
  - `LLM_MODEL_PRIMARY` — основная модель (например, `gpt-4o-mini`).
  - `LLM_MODEL_FALLBACK` — запасная модель (опционально).
  - `LLM_TEMPERATURE` — температура (0..1, по умолчанию 0.2).
- Управление из UI: в «Настройки поиска» доступны поля основной/запасной модели и температура. Сохранение меняет `.env` и перезагружает агента «на лету».

### Стрим модели и фолбэк

- Сервер всегда отдаёт ответы наружу потоком по WebSocket.
- На стороне провайдера LLM иногда может быть запрещён режим stream. В этом случае агент автоматически переключается на нестриминговый запрос (получает ответ целиком) и всё равно отдаёт его наружу потоком (по предложениям благодаря символам `|`, которые генерирует модель по промпту).
- Когда stream у модели доступен — используется стрим.

- Данные:
  - SQLite логи: `data/db/log_db.sqlite`.
  - Векторная база: `data/chroma/`.

- Обновление БЗ:
  - Через UI: кнопка «Обновить БЗ» в `/logs-ui/` → выбрать `.md` → заголовки будут продублированы → эмбеддинги пересоздадутся → агент перезагрузится.
  - Через консоль: отредактировать файл → `python3 create_embeddings.py`.

- Рекомендации по качеству RAG:
  - Ставьте «<<->>» между логическими разделами.
  - Используйте информативные Markdown‑заголовки — они будут продублированы и попадут в чанк.

## 🔤 Нормализация речи и единиц (ASR + бэкенд)

- Чтобы бот одинаково понимал произнесённые варианты («ка-эн», «кн», «килоньютон», «мэ‑пэ‑а», «герц/гц», «миллиметров в секунду» и т.д.), добавлены два слоя нормализации:
  - На стороне Voximplant (`scenario_barge-in_2.js`): подсказки `phraseHints` и функция `normalizeUtterance(...)` приводят речь к канону ещё до отправки на сервер.
  - На бэкенде (`text_normalizer.py`): функция `normalize(text)` выполняет те же замены перед вызовом агента. Используется для всех каналов, а также доступна через `POST /api/normalize`.

Пример запроса:

```bash
curl -sS -X POST http://<HOST>:9000/api/normalize \
  -H 'Content-Type: application/json' \
  -d '{"text":"Есть РЭМ на тысячу килоньютон, скорость 5 миллиметров в секунду при 220 вольт"}'
```

Пример ответа:

```json
{ "raw": "Есть РЭМ на тысячу килоньютон, скорость 5 миллиметров в секунду при 220 вольт",
  "normalized": "Есть РЭМ на тысячу кН, скорость 5 мм/с при 220 В" }
```

---

## 💡 План доработок

- **Аналитика:** Добавить больше метрик и визуализаций в админ-панель (например, самые частые вопросы, средняя длительность звонка).
- **Поддержка других форматов БЗ:** Научить систему работать с `.pdf` и `.docx` файлами.
- **Подключение к CRM:** Интеграция с CRM для получения информации о клиенте по номеру телефона и сохранения истории общения.
- **Расширение тестового покрытия:** Добавлять новые тестовые случаи для более глубокой проверки логики и знаний агента.

---

## 📡 Примеры запросов к API

Получить логи с фильтрами:

```bash
curl -sS "http://<HOST>:9000/logs?q=7961&date_from=2025-08-01T00:00:00Z&date_to=2025-08-31T23:59:59Z"
```

Экспорт CSV:

```bash
curl -L "http://<HOST>:9000/logs/csv" -o call_logs.csv
```

Удалить все логи (защищено API‑ключом):

```bash
curl -X DELETE "http://<HOST>:9000/logs" -H "X-API-Key: $API_SECRET_KEY"
```

Получить текущие промпты:

```bash
curl -sS "http://<HOST>:9000/api/prompts"
```

Сохранить промпты и перезагрузить агента:

```bash
curl -X POST "http://<HOST>:9000/api/prompts" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_SECRET_KEY" \
  -d @prompts.json
```

Получить БЗ / Загрузить новую БЗ:

```bash
curl -sS "http://<HOST>:9000/kb"

curl -X POST "http://<HOST>:9000/kb/upload" \
  -H "X-API-Key: $API_SECRET_KEY" \
  -F file=@knowledge_base.md
```

## 🗄️ Схема БД логов

SQLite файл: `data/log_db.sqlite`.

```sql
CREATE TABLE IF NOT EXISTS logs (
  id TEXT PRIMARY KEY,
  callerId TEXT,
  startTime TEXT,
  endTime   TEXT,
  status    TEXT,
  transcript_json TEXT
);
```

Замечания:
- `transcript_json` — JSON‑массив реплик; в UI парсится и показывает диалог.
- Сортировка по `startTime` по убыванию делается на стороне запроса в коде.

## 🧪 Пример подключения к WebSocket

Простой пример в браузерной консоли:

```javascript
const ws = new WebSocket("ws://<HOST>:9000/ws?callerId=TEST");
ws.onmessage = (e) => console.log("BOT:", e.data);
ws.onopen = () => ws.send("Здравствуйте!");
```

## 🚢 Чек‑лист деплоя

- [ ] Python 3.12+, `python3 -m venv venv && source venv/bin/activate`.
- [ ] `pip install -r requirements.txt`.
- [ ] Заполнить `.env` (см. список переменных выше).
- [ ] Подготовить БЗ: отредактировать `knowledge_base.md`, расставить «<<->>» между блоками.
- [ ] `python3 create_embeddings.py` (пересоздаст `chroma_db_metrotech/`).
- [ ] Запустить сервер (dev) `uvicorn main:app --host 0.0.0.0 --port 9000 --reload` или (prod) gunicorn.
- [ ] Проверить `GET /`, `GET /logs-ui/`.

## 🧩 Автозапуск через systemd (понятно для новичка)

Ниже — что такое systemd, где лежит конфигурация и как всем управлять.

### Что такое systemd

- Это «менеджер сервисов» в Linux. Он:
  - автоматически запускает ваш бот при старте сервера;
  - следит, чтобы процесс работал (перезапускает при падении);
  - даёт единые команды `start/stop/restart/status`;
  - собирает логи в системный журнал.

### Где хранится конфигурация сервиса

- Конфигурация — это unit‑файл: `/etc/systemd/system/metrotech-bot.service`.
- Внутри него указаны:
  - `WorkingDirectory` — папка проекта: `/root/Asterisk_bot/asterisk-vox-bot`;
  - `Environment` — какой `PATH` (наш `venv`): `/root/Asterisk_bot/asterisk-vox-bot/venv/bin`;
  - `ExecStart` — команда старта (gunicorn на порту 9000):
    - `/root/Asterisk_bot/asterisk-vox-bot/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:9000 app.backend.main:app`
  - `Restart=always` — перезапускать при сбоях.

Важно: unit‑файл лежит вне репозитория (в `/etc/systemd/system/`). Сам код и все настройки (.env, БЗ, статика) — внутри проекта в `/root/Asterisk_bot/asterisk-vox-bot`.

### Как создать сервис (один раз)

```bash
sudo tee /etc/systemd/system/metrotech-bot.service >/dev/null << 'EOF'
[Unit]
Description=Metrotech Voice Bot (FastAPI on 9000)
After=network-online.target

[Service]
User=root
WorkingDirectory=/root/Asterisk_bot/asterisk-vox-bot
Environment="PATH=/root/Asterisk_bot/asterisk-vox-bot/venv/bin"
ExecStart=/root/Asterisk_bot/asterisk-vox-bot/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:9000 main:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now metrotech-bot
sudo systemctl status metrotech-bot --no-pager
```

### Ежедневные команды управления

```bash
sudo systemctl status metrotech-bot     # посмотреть состояние
sudo systemctl restart metrotech-bot    # перезапуск (после правок .env/кода)
sudo systemctl stop metrotech-bot       # остановить
sudo systemctl start metrotech-bot      # запустить
sudo systemctl disable metrotech-bot    # убрать автозапуск при перезагрузке
sudo systemctl enable metrotech-bot     # включить автозапуск
```

### Где смотреть логи сервиса

```bash
journalctl -u metrotech-bot -n 100 --no-pager   # последние 100 строк
journalctl -u metrotech-bot -f                  # «хвост» в реальном времени
```

Внутренние логи приложения также пишутся в `data/logs/app.log` внутри проекта.

---

## 📋 История изменений и миграция

### 🚀 **МИГРАЦИЯ VOXIMPLANT → ASTERISK (2025-09-05)**

**Причины миграции:**
- Необходимость полного контроля над обработкой звонков
- Интеграция с существующей Asterisk инфраструктурой
- Улучшение производительности и надежности

**Что изменилось:**
- ✅ **Новый обработчик**: `stasis_handler.py` вместо `main.py`
- ✅ **ARI WebSocket**: Прямое подключение к Asterisk ARI
- ✅ **Улучшенное профилирование**: Детальные метрики времени
- ✅ **Redis кеширование**: Ускорение повторных запросов
- ✅ **gRPC TTS**: Подготовка к быстрому синтезу речи

**Устаревшие компоненты:**
- ❌ `app/backend/main.py` - старый WebSocket сервер
- ❌ `app/voximplant/scenario_barge-in_2.js` - Voximplant сценарий

**Текущий статус:**
- ✅ Система работает стабильно
- ⚠️ Требуется оптимизация AI streaming (8.7с → 2-3с)
- ⚠️ Требуется исправление gRPC TTS аутентификации

### Как вносить изменения и применять их

1) Меняете `.env` или файлы проекта.
2) Перезапускаете сервис:

```bash
sudo systemctl restart metrotech-bot
```

Если вы редактировали сам unit‑файл (`/etc/systemd/system/metrotech-bot.service`), то после сохранения сделайте:

```bash
sudo systemctl daemon-reload
sudo systemctl restart metrotech-bot
```

### (Опционально) Инициализация БД перед стартом сервиса

Чтобы при первом запуске автоматически собрать эмбеддинги и подчистить временные каталоги, можно добавить `ExecStartPre` в unit‑файл:

```ini
[Service]
WorkingDirectory=/root/Asterisk_bot/asterisk-vox-bot
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/root/Asterisk_bot/asterisk-vox-bot/venv/bin"
ExecStartPre=/bin/bash -lc 'cd /root/Asterisk_bot/asterisk-vox-bot && /bin/rm -rf data/chroma_tmp data/chroma_old && [ -d data/chroma ] || /root/Asterisk_bot/asterisk-vox-bot/venv/bin/python3 scripts/create_embeddings.py'
```

### Частые проблемы

- «Address already in use»: порт 9000 занят другим процессом (например, dev‑uvicorn). Найти и остановить:
```bash
pgrep -af uvicorn
kill <PID_dev_uvicorn>
sudo systemctl restart metrotech-bot
```

- Сервис не стартует: проверьте правильность путей в `WorkingDirectory`, `ExecStart`, наличие `venv` и зависимостей; смотрите ошибки через `journalctl -u metrotech-bot -n 200`.

## 🛠️ Troubleshooting

- Пустая админка / ошибки загрузки React:
  - В `logs-ui/index.html` используется importmap с CDN `jsdelivr` для ESM. Если сеть ограничена, соберите мини‑бандл локально или используйте другой доступный CDN.
- `Address already in use` при старте:
  - Освободите порт: `lsof -ti :9000 | xargs -r kill -9` и запустите снова.
- `OPENAI_API_KEY` не задан:
  - Убедитесь, что ключ в `.env`, и перезапустите процесс.
- После загрузки новой БЗ ответы не меняются:
  - Дождитесь завершения фонового пересоздания эмбеддингов; в логах будет «Эмбеддинги успешно пересозданы» и «Агент успешно перезагружен».
- Ошибка при `DELETE /logs` или `POST /api/prompts`:
  - Проверьте заголовок `X-API-Key` и значение `API_SECRET_KEY`.

### О служебных файлах `__init__.py` и кэше `__pycache__`

- `__init__.py` помечает папку как Python‑пакет, чтобы работали импорты вида `app.backend.*`. Файл может быть пустым — это норма.
- `__pycache__/*.pyc` — кэш‑байткод, Python создаёт его автоматически для ускорения. В репозиторий их не коммитим; чистить можно без вреда: `find . -name __pycache__ -type d -exec rm -rf {} +`.

### Где хранится сценарий Voximplant

- Локальная копия сценария находится в `app/voximplant/scenario_barge-in_2.js` — для контроля версий и удобного просмотра. В реальности он редактируется и исполняется в консоли Voximplant, а подключается к номеру через правила роутинга. Актуальный адрес сервера в сценарии: `WS_URL = "ws://31.207.75.71:9000/ws"`.

## 🔒 Безопасность

- Не храните реальные ключи в репозитории; используйте `.env`/секреты среды.
- Операции изменения данных защищены заголовком `X-API-Key` — держите ключ в секрете.
- Логи могут содержать пользовательские данные — регулируйте доступ к `logs-ui/` и БД.
