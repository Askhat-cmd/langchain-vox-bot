# 📋 ЧЕКЛ-ЛИСТ АКТИВАЦИИ gRPC TTS

> **КРИТИЧЕСКИ ВАЖНО**: Каждый пункт должен быть выполнен ПО ПОРЯДКУ!  
> **При любой ошибке**: НЕМЕДЛЕННЫЙ ОТКАТ к бэкапу

---

## ⚠️ ПРЕДВАРИТЕЛЬНЫЕ ПРОВЕРКИ

### 🔍 **ПРОВЕРКА 1: Текущее состояние системы**
- [ ] Система работает стабильно
- [ ] HTTP TTS воспроизводит звук
- [ ] В логах нет критических ошибок
- [ ] Сервис metrotech-bot активен

**Команды проверки:**
```bash
sudo systemctl status metrotech-bot
sudo journalctl -u metrotech-bot -n 50 --no-pager | grep -E "(ERROR|CRITICAL)"
```

**Ожидаемый результат**: Сервис active (running), ошибок нет

---

### 🔍 **ПРОВЕРКА 2: TTS Adapter готов к активации**
- [ ] TTS Adapter инициализирован в логах
- [ ] gRPC TTS канал установлен
- [ ] Yandex API ключи настроены

**Поиск в логах:**
```bash
sudo journalctl -u metrotech-bot -n 100 --no-pager | grep -E "(TTSAdapter|gRPC TTS)"
```

**Ожидаемые логи:**
- ✅ TTSAdapter initialized with gRPC + HTTP fallback
- ✅ gRPC TTS channel initialized

---

## 💾 СОЗДАНИЕ БЭКАПА

### 🗂️ **БЭКАП ФАЙЛОВ**
- [ ] Остановить сервис: `sudo systemctl stop metrotech-bot`
- [ ] Создать бэкап основного файла
- [ ] Проверить бэкап создан

**Команды:**
```bash
cd /root/Asterisk_bot/asterisk-vox-bot
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
cp app/backend/asterisk/stasis_handler_optimized.py app/backend/asterisk/stasis_handler_optimized_BACKUP_BEFORE_GRPC_${TIMESTAMP}.py
ls -la app/backend/asterisk/stasis_handler_optimized_BACKUP_*
```

**Проверка**: Бэкап файл создан с правильным timestamp

---

## 🔧 ВНЕСЕНИЕ ИЗМЕНЕНИЙ

### ✏️ **МОДИФИКАЦИЯ КОДА**

**Файл:** `app/backend/asterisk/stasis_handler_optimized.py`  
**Метод:** `speak_optimized` (строки ~108-133)

#### **ЗАМЕНЯЕМЫЙ БЛОК:**
```python
# ВРЕМЕННО: Используем оригинальный TTS для тестирования
# TODO: Вернуться к TTS Adapter после исправления формата
logger.info("🔄 ВРЕМЕННО: Используем оригинальный TTS для тестирования")

# Используем оригинальный TTS сервис
from app.backend.services.yandex_tts_service import get_yandex_tts_service
original_tts = get_yandex_tts_service()

# Создаем файл через оригинальный TTS
timestamp = datetime.now().strftime('%H%M%S%f')[:-3]
audio_filename = f"stream_{channel_id}_{timestamp}"
sound_filename = await original_tts.text_to_speech(text, audio_filename)

if sound_filename:
    # Воспроизводим через ARI (как в оригинале)
    async with AsteriskARIClient() as ari:
        playback_id = await ari.play_sound(channel_id, sound_filename, lang=None)
        
        if playback_id:
            # Обновляем данные канала
            if channel_id in self.active_calls:
                call_data = self.active_calls[channel_id]
                call_data["current_playback"] = playback_id
                call_data["is_speaking"] = True
                call_data["last_speak_started_at"] = int(time.time() * 1000)
            
            logger.info(f"✅ Аудио воспроизводится через ARI: {playback_id}")
        else:
            logger.warning("⚠️ ARI playback не удался")
else:
    logger.warning("Оригинальный TTS не вернул имя файла")
```

#### **НОВЫЙ БЛОК:**
```python
# ЭТАП 2.2: Активация gRPC TTS через TTS Adapter
logger.info("🚀 ЭТАП 2.2: Активация gRPC TTS через TTS Adapter")

try:
    # Используем TTS Adapter (gRPC primary + HTTP fallback)
    start_time = time.time()
    audio_data = await self.tts_adapter.synthesize(text)
    tts_time = time.time() - start_time
    
    if audio_data:
        logger.info(f"✅ TTS Adapter success: {tts_time:.2f}s, {len(audio_data)} bytes")
        
        # Воспроизводим через _play_audio_data (ожидает bytes)
        await self._play_audio_data(channel_id, audio_data)
        
        # Обновляем данные канала
        if channel_id in self.active_calls:
            call_data = self.active_calls[channel_id]
            call_data["is_speaking"] = True
            call_data["last_speak_started_at"] = int(time.time() * 1000)
        
        logger.info("🎯 gRPC TTS через TTS Adapter - УСПЕХ!")
    else:
        logger.warning("⚠️ TTS Adapter не вернул аудио данные")
        
except Exception as e:
    logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА gRPC TTS: {e}")
    
    # КРИТИЧЕСКИЙ FALLBACK на HTTP TTS
    logger.warning("🔄 КРИТИЧЕСКИЙ FALLBACK на HTTP TTS")
    
    try:
        from app.backend.services.yandex_tts_service import get_yandex_tts_service
        original_tts = get_yandex_tts_service()
        
        timestamp = datetime.now().strftime('%H%M%S%f')[:-3]
        audio_filename = f"fallback_{channel_id}_{timestamp}"
        sound_filename = await original_tts.text_to_speech(text, audio_filename)
        
        if sound_filename:
            async with AsteriskARIClient() as ari:
                playback_id = await ari.play_sound(channel_id, sound_filename, lang=None)
                if playback_id:
                    if channel_id in self.active_calls:
                        call_data = self.active_calls[channel_id]
                        call_data["current_playback"] = playback_id
                        call_data["is_speaking"] = True
                        call_data["last_speak_started_at"] = int(time.time() * 1000)
                    logger.warning("🔄 HTTP TTS fallback - успешно")
                else:
                    logger.error("❌ HTTP TTS fallback - FAILED")
        else:
            logger.error("❌ HTTP TTS fallback - нет файла")
    except Exception as fallback_error:
        logger.critical(f"💀 КРИТИЧЕСКИЙ СБОЙ FALLBACK: {fallback_error}")
```

### ✅ **ЧЕКЛ-ЛИСТ ИЗМЕНЕНИЙ**
- [ ] Найден блок с "ВРЕМЕННО: Используем оригинальный TTS"
- [ ] Весь блок заменен на новую реализацию
- [ ] Добавлен критический fallback на HTTP TTS
- [ ] Логирование содержит "🚀 ЭТАП 2.2"
- [ ] Сохранен файл

---

## 🚀 ЗАПУСК И ТЕСТИРОВАНИЕ

### 1️⃣ **ЗАПУСК СЕРВИСА**
- [ ] Запустить сервис: `sudo systemctl start metrotech-bot`
- [ ] Проверить статус: `sudo systemctl status metrotech-bot`
- [ ] Мониторить логи: `sudo journalctl -u metrotech-bot -f`

**Ожидаемые логи при старте:**
- ✅ AI Agent успешно инициализирован
- ✅ TTSAdapter initialized with gRPC + HTTP fallback
- ✅ Все сервисы оптимизации инициализированы
- ✅ Подключен к Asterisk ARI WebSocket

### 2️⃣ **ТЕСТ ЗВУКА (КРИТИЧЕСКИ ВАЖНО!)**
- [ ] Позвонить на номер голосового ассистента
- [ ] **ПРИВЕТСТВИЕ СЛЫШНО?** ДА/НЕТ
- [ ] **AI ОТВЕТЫ СЛЫШНЫ?** ДА/НЕТ
- [ ] В логах: "🚀 ЭТАП 2.2: Активация gRPC TTS"
- [ ] В логах: "🎯 gRPC TTS через TTS Adapter - УСПЕХ!"

### 3️⃣ **АНАЛИЗ ЛОГОВ**
```bash
# Поиск успешных операций
sudo journalctl -u metrotech-bot -n 100 --no-pager | grep -E "(🎯|✅.*TTS)"

# Поиск ошибок
sudo journalctl -u metrotech-bot -n 100 --no-pager | grep -E "(❌|ERROR|CRITICAL)"

# Измерение производительности TTS
sudo journalctl -u metrotech-bot -n 50 --no-pager | grep -E "TTS.*success.*[0-9]\.[0-9]s"
```

**Ожидаемые результаты:**
- TTS время: 0.16-0.25 секунды (улучшение с 0.5-0.7с)
- Отсутствие критических ошибок
- Успешные playback через ARI

---

## ✅ КРИТЕРИИ УСПЕХА

### 🎯 **ОБЯЗАТЕЛЬНЫЕ КРИТЕРИИ**
- [ ] **ЗВУК РАБОТАЕТ**: Приветствие и AI ответы слышны
- [ ] **ПРОИЗВОДИТЕЛЬНОСТЬ**: TTS < 0.3 секунды  
- [ ] **СТАБИЛЬНОСТЬ**: Нет критических ошибок
- [ ] **ЛОГИ**: Присутствует "🎯 gRPC TTS через TTS Adapter - УСПЕХ!"

### 📊 **ЖЕЛАТЕЛЬНЫЕ КРИТЕРИИ**
- [ ] **МЕТРИКИ**: TTS время 0.16-0.25 секунды
- [ ] **FALLBACK**: HTTP fallback работает при проблемах gRPC
- [ ] **НАДЕЖНОСТЬ**: Система стабильна при длительной работе

---

## 🚨 АВАРИЙНЫЙ ОТКАТ

### ⚠️ **КОГДА ОТКАТЫВАТЬСЯ:**
- ❌ Приветствие не слышно
- ❌ AI ответы не слышны  
- ❌ Критические ошибки в логах
- ❌ Сервис не запускается
- ❌ TTS время > 1 секунды

### 🔄 **ПРОЦЕДУРА ОТКАТА:**
```bash
# 1. Остановить сервис
sudo systemctl stop metrotech-bot

# 2. Восстановить бэкап
cd /root/Asterisk_bot/asterisk-vox-bot
cp app/backend/asterisk/stasis_handler_optimized_BACKUP_BEFORE_GRPC_[TIMESTAMP].py app/backend/asterisk/stasis_handler_optimized.py

# 3. Запустить сервис
sudo systemctl start metrotech-bot

# 4. Проверить восстановление
sudo journalctl -u metrotech-bot -f
```

### ✅ **ПРОВЕРКА ПОСЛЕ ОТКАТА:**
- [ ] Сервис запущен успешно
- [ ] HTTP TTS работает
- [ ] Приветствие слышно
- [ ] AI ответы слышны
- [ ] В логах "🔄 ВРЕМЕННО: Используем оригинальный TTS"

---

## 📝 ОТЧЕТ О РЕЗУЛЬТАТАХ

### 📊 **ЗАПОЛНИТЬ ПОСЛЕ ТЕСТИРОВАНИЯ:**

**Дата тестирования:** ________________  
**Время тестирования:** ________________  

**РЕЗУЛЬТАТ АКТИВАЦИИ:**
- [ ] ✅ УСПЕХ - gRPC TTS работает
- [ ] ⚠️ ЧАСТИЧНЫЙ УСПЕХ - работает с проблемами  
- [ ] ❌ НЕУДАЧА - выполнен откат

**ПРОИЗВОДИТЕЛЬНОСТЬ:**
- Время TTS до оптимизации: _______ сек
- Время TTS после оптимизации: _______ сек
- Улучшение: _______ раз

**СТАБИЛЬНОСТЬ:**
- Приветствие слышно: ДА / НЕТ
- AI ответы слышны: ДА / НЕТ
- Критические ошибки: ДА / НЕТ

**СЛЕДУЮЩИЕ ШАГИ:**
- [ ] Переход к Этапу 2.3 (Parallel TTS Processor)
- [ ] Дополнительная отладка gRPC TTS
- [ ] Откат и анализ проблем

---

## 🎯 ЗАКЛЮЧЕНИЕ

**ПОМНИТЕ**: Этап 2.2 - критический шаг к целевой производительности 1.1 секунды. 

**Главные принципы:**
1. **ОДНО ИЗМЕНЕНИЕ ЗА РАЗ** 
2. **ОБЯЗАТЕЛЬНАЯ ПРОВЕРКА ЗВУКА**
3. **НЕМЕДЛЕННЫЙ ОТКАТ ПРИ ПРОБЛЕМАХ**

Успех этого этапа открывает дорогу к полной оптимизации системы!