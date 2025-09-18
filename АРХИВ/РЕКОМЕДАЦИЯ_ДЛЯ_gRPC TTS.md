# 🔍 ИССЛЕДОВАНИЕ ПРОБЛЕМЫ: Анализ документации и форумов

## 📊 КЛЮЧЕВЫЕ НАХОДКИ ИЗ ИССЛЕДОВАНИЯ

### **1. ФОРМАТ АУДИО YANDEX gRPC TTS**

**Из официальной документации Yandex Cloud :**[1]
```
SpeechKit поддерживает следующие аудио форматы:
- LPCM (Linear Pulse Code Modulation)
- OggOpus  
- MP3
```

**КРИТИЧЕСКОЕ ОТКРЫТИЕ:** Yandex gRPC TTS возвращает **LPCM** (raw PCM), а НЕ готовый WAV файл как я предполагал ранее!

### **2. ПРОБЛЕМА СОВМЕСТИМОСТИ С ASTERISK**

**Из Asterisk форумов :**[2][3]
- Asterisk ARI `play_sound` требует **файлы в директории `/var/lib/asterisk/sounds/`**  
- **Формат должен быть**: WAV, GSM, ALAW, ULAW для корректного воспроизведения
- **Raw LPCM данные не воспроизводятся** напрямую через ARI

**Пример успешной интеграции :**[3]
```bash
# Google TTS конвертирует в совместимый формат:
sox input.mp3 -r 8000 -c 1 -t wav output.wav
```

### **3. ЧАСТЫЕ ПРОБЛЕМЫ ARI ИНТЕГРАЦИИ**

**Channel not found 404 :**[4][5]
- **Проблема:** Каналы исчезают из ARI после высокой активности
- **Причина:** Race condition между событиями ARI и обращениями к API  
- **Решение:** Добавить проверки существования канала перед каждой операцией

**Пример защитного кода:**
```python
# Всегда проверять канал перед операциями
response = client.channels.get(channel_id)
if response.status_code == 404:
    logger.warning(f"Channel {channel_id} not found, skipping")
    return
```

***

## 🎯 ТЕХНИЧЕСКОЕ РЕШЕНИЕ ПРОБЛЕМЫ

### **КОРНЕВАЯ ПРИЧИНА:** 
**Yandex gRPC TTS возвращает raw LPCM данные, но Asterisk требует WAV файлы с правильными заголовками!**

### **ИСПРАВЛЕННЫЙ КОД `_play_audio_data`:**

```python
async def _play_audio_data(self, channel_id: str, audio_data: bytes):
    """Воспроизводит аудио данные через ARI с правильной конвертацией LPCM → WAV"""
    try:
        if not audio_data:
            return
            
        timestamp = datetime.now().strftime('%H%M%S%f')[:-3]
        temp_filename = f"stream_{channel_id}_{timestamp}.wav"
        temp_path = f"/var/lib/asterisk/sounds/{temp_filename}"
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Конвертация LPCM в WAV
        # Yandex gRPC возвращает raw LPCM 16kHz mono 16-bit
        await self._convert_lpcm_to_wav(audio_data, temp_path)
        
        # Проверяем существование канала перед воспроизведением
        async with AsteriskARIClient() as ari:
            if not await ari.channel_exists(channel_id):
                logger.warning(f"⚠️ Канал {channel_id} не существует")
                return
                
            playback_id = await ari.play_sound(channel_id, temp_filename[:-4])
            
            if playback_id:
                # Обновляем состояние канала
                if channel_id in self.active_calls:
                    call_data = self.active_calls[channel_id]
                    call_data["current_playback"] = playback_id
                    call_data["is_speaking"] = True
                    call_data["last_speak_started_at"] = int(time.time() * 1000)
                
                logger.info(f"✅ Аудио воспроизводится: {playback_id}")
            else:
                logger.error("❌ ARI playback failed")
                
    except Exception as e:
        logger.error(f"❌ Audio playback error: {e}")

async def _convert_lpcm_to_wav(self, lpcm_data: bytes, output_path: str):
    """Конвертирует raw LPCM в WAV файл"""
    import wave
    import struct
    
    # Параметры аудио от Yandex TTS
    sample_rate = 16000  # 16kHz
    channels = 1         # mono
    sample_width = 2     # 16-bit
    
    with wave.open(output_path, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width) 
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(lpcm_data)
        
    logger.info(f"✅ LPCM converted to WAV: {output_path}")
```

***

## 🚨 АЛЬТЕРНАТИВНОЕ РЕШЕНИЕ: SOX КОНВЕРТАЦИЯ

**Как делают успешные интеграции :**[3]

```python
async def _convert_lpcm_to_wav_sox(self, lpcm_data: bytes, output_path: str):
    """Конвертация через SOX (более надежный метод)"""
    import tempfile
    import subprocess
    
    # Сохраняем raw LPCM во временный файл
    with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as temp_raw:
        temp_raw.write(lpcm_data)
        raw_path = temp_raw.name
    
    # Конвертируем raw → wav через SOX
    sox_cmd = [
        "sox", "-t", "raw", "-r", "16000", "-e", "signed-integer", 
        "-b", "16", "-c", "1", raw_path, 
        "-r", "8000", "-c", "1", output_path  # Asterisk предпочитает 8kHz
    ]
    
    result = subprocess.run(sox_cmd, capture_output=True)
    
    # Удаляем временный файл
    os.unlink(raw_path)
    
    if result.returncode == 0:
        logger.info(f"✅ SOX conversion successful: {output_path}")
    else:
        logger.error(f"❌ SOX conversion failed: {result.stderr}")
        raise Exception(f"SOX conversion failed: {result.stderr}")
```

***

## 🎯 ПЛАН ИСПРАВЛЕНИЯ

### **ВАРИАНТ 1: БЫСТРОЕ ИСПРАВЛЕНИЕ (Python wave)**
1. Заменить метод `_convert_lpcm_to_wav` в коде
2. Перезапустить сервис  
3. Протестировать звук

### **ВАРИАНТ 2: НАДЕЖНОЕ ИСПРАВЛЕНИЕ (SOX)**
1. Установить SOX на сервере: `apt-get install sox`
2. Заменить на `_convert_lpcm_to_wav_sox`
3. Перезапустить и протестировать

### **ВАРИАНТ 3: ОТКАТ К HTTP TTS**
- При неудаче исправлений - вернуться к стабильной версии
- HTTP TTS уже создает правильные WAV файлы

***

## 📊 ЗАКЛЮЧЕНИЕ ИССЛЕДОВАНИЯ

**Проблема НЕ в gRPC TTS как таковом**, а в **неправильной обработке формата данных**:

1. ✅ **Yandex gRPC TTS работает** и возвращает качественный LPCM
2. ❌ **Система неправильно сохраняет** raw LPCM как WAV файл  
3. ❌ **Asterisk не может воспроизвести** некорректные аудио файлы
4. ✅ **Решение найдено**: Правильная конвертация LPCM → WAV

**Урок:** При интеграции TTS систем критически важно понимать **точный формат возвращаемых данных** и обеспечивать **правильную конвертацию** для целевой системы воспроизведения.

**Следующий шаг:** Выбрать метод исправления и применить одно из решений выше! 🎯

