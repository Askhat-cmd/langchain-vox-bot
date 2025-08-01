# 📞 Голосовой ассистент для компании "Метротэст"

> 📅 Актуально на 2025-07-30

Проект реализует **автоматического голосового ассистента**, который:
- Принимает звонки через платформу **Voximplant**
- Понимает голос клиента с помощью ASR
- Находит ответ через **AI-агента с LangChain** (на Python)
- Отвечает вслух, используя TTS
- Поддерживает barge-in — прерывание бота при речи клиента

---

## 🧠 Архитектура проекта

Состоит из двух компонентов:

| Компонент      | Назначение                                      |
|----------------|--------------------------------------------------|
| `scenario_barge-in_2.js` | Voximplant-сценарий обработки звонка и речи |
| `main.py`      | FastAPI WebSocket-сервер                         |
| `Agent.py`     | LangChain-агент: извлечение знаний и ответы      |
| `create_embeddings.py` | Предварительная индексация базы знаний      |

---

## 🔁 Сценарий звонка

1. **Клиент звонит** → звонок принимается `scenario_barge-in_2.js`
2. Сценарий открывает WebSocket-соединение с `main.py`
3. `main.py` передаёт запрос в `Agent.py`
4. Агент:
   - Ищет ответ в базе знаний (`Метротест_САЙТ.txt`)
   - Строит промпт и делает запрос к `ChatOpenAI`
5. Ответ приходит по частям (stream) и отправляется обратно в WebSocket
6. `scenario.js` воспроизводит текст сразу (TTS)
7. Клиент может перебить — срабатывает barge-in (`ASREvents.CaptureStarted`)

---

## 🗂️ Поддержка Barge-in

Сценарий использует:

- `createTTSPlayer(..., { language: ..., progressivePlayback: true })` — ответ звучит ещё до полной генерации
- `ASR` с `interimResults: true`
- Прерывание речи при:
  - `ASREvents.CaptureStarted`
  - `ASREvents.InterimResult`

---

## 🧾 Формат общения с WebSocket

| Исходящий (Voximplant → Backend) | Текст из ASR |
|----------------------------------|--------------|
| Входящий (Backend → Voximplant)  | Поток текста от модели (стриминг) |

Маркер `|` в ответе от модели никак не обрабатывается — он просто очищается функцией `cleanText(text)`:
```js
return text.replace(/\|/g, ' ').replace(/\*/g, '').trim().replace(/\s+/g, ' ');
```

---

## 📁 Структура проекта

```bash
.
├── scenario_barge-in_2.js       # Скрипт сценария на Voximplant
├── main.py                      # FastAPI WebSocket-сервер
├── Agent.py                     # LangChain агент (поиск и генерация ответов)
├── create_embeddings.py         # Подготовка базы знаний и эмбеддингов
├── Метротест_САЙТ.txt                      # Текстовая база знаний
├── requirements.txt             # Зависимости
└── .env                         # Секреты (ключ OpenAI, и т.п.)
```

---

## 🚀 Запуск сервера

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Создание эмбеддингов
python create_embeddings.py

# Запуск WebSocket-сервера
uvicorn main:app --host 0.0.0.0 --port 8000
```

Для продакшн:
```bash
nohup venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 main:app &
```

---

## 🔐 .env файл

```env
OPENAI_API_KEY=...
```

---

## 📞 Voximplant: как подключить

1. Создать приложение в [Voximplant](https://manage.voximplant.com/)
2. Загрузить `scenario_barge-in_2.js`
3. Привязать к номеру
4. Убедиться, что IP-адрес сервера с `main.py` доступен снаружи

---

## 💡 Возможные улучшения

- История звонков (логгирование)
- Подключение к CRM
- Введение ID клиента
- Мультиязычность (добавить переключение языков)
- Расширенные phraseHints

---
