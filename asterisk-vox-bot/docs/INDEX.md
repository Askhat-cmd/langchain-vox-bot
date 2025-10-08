# 📚 ИНДЕКС ДОКУМЕНТАЦИИ - ASTERISK AI BOT

## 🎯 НАЗНАЧЕНИЕ

Этот файл служит **навигационным центром** для всей документации системы Asterisk AI Bot. Здесь собраны все ссылки, быстрые команды и экстренные процедуры для администраторов системы.

> 📖 **Для разработчиков**: Основное описание проекта находится в `../README.md` - там архитектура, API, конфигурация и примеры кода.

**Статус системы**: ✅ **Защищена и стабильна** (обновлено 01.10.2025)

---

## 📁 СТРУКТУРА ДОКУМЕНТАЦИИ

### **1. [Руководство по системе Asterisk](asterisk-system-guide.md)** ⭐ ГЛАВНЫЙ ДОКУМЕНТ
- 📜 Полная история проблем и исправлений
- 🔧 Детальная текущая конфигурация (PJSIP, Dialplan, ARI)
- 🛡️ Система безопасности (3 уровня защиты)
- 🔍 Команды диагностики и мониторинга
- 🚨 Типичные проблемы и решения
- 📊 Регулярное обслуживание
- ✅ Чеклист быстрой проверки

### **2. [Архитектура Python бота](python-bot-architecture.md)**
- 🤖 Структура проекта и компоненты
- ⚙️ Конфигурация (.env файл)
- 🔄 Поток обработки звонков
- 🚨 Проблемы Python бота и решения
- 📊 Мониторинг и логи

### **3. [Руководство по устранению неисправностей](troubleshooting-guide.md)**
- 🚨 Экстренное восстановление
- 📋 Диагностическая матрица
- 🔍 Подробная диагностика проблем
- 🔄 Процедуры восстановления
- 📊 Мониторинг и алерты

---

## 🚀 БЫСТРЫЙ СТАРТ

### **Если система не работает:**

#### **1. Экстренная диагностика (30 секунд):**
```bash
# Asterisk работает?
sudo systemctl status asterisk

# Python бот работает?
ps aux | grep stasis_handler

# Endpoints настроены?
sudo asterisk -rx "pjsip show endpoints" | grep novofon

# Identify правила есть?
sudo asterisk -rx "pjsip show identifies"
```

#### **2. Экстренное восстановление (2 минуты):**
```bash
# Перезапустить Asterisk
sudo systemctl restart asterisk
sleep 10

# Перезапустить Python бот
cd /root/Asterisk_bot/asterisk-vox-bot
source venv/bin/activate
pkill -f stasis_handler
nohup python app/backend/asterisk/stasis_handler_optimized.py > bot.log 2>&1 &
```

#### **3. Проверка результата:**
```bash
# Должно показать: novofon-incoming
sudo asterisk -rx "pjsip show endpoints" | grep novofon

# Должно показать: asterisk-bot
sudo asterisk -rx "stasis show apps"

# Должно показать identify правила
sudo asterisk -rx "pjsip show identifies"
```

---

## 🔍 ДИАГНОСТИЧЕСКИЕ КОМАНДЫ

### **Основные команды проверки:**
```bash
# Статус системы
sudo systemctl status asterisk
sudo asterisk -rx "pjsip show endpoints"
sudo asterisk -rx "core show channels"
sudo asterisk -rx "stasis show apps"

# ⭐ ВАЖНО: Проверить защиту
sudo asterisk -rx "pjsip show identifies"
# Должно показать IP: 37.139.38.224/32 и 37.139.38.56/32

sudo asterisk -rx "pjsip show endpoint anonymous"
# Должно: "Unable to find object anonymous" ✅

# Python бот
ps aux | grep stasis_handler

# Тестовый звонок
# Позвонить на 79581114700 с ЛЮБОГО номера
```

---

## 🛡️ СИСТЕМА БЕЗОПАСНОСТИ (ВАЖНО!)

### **✅ Что защищает систему:**

1. **PJSIP Identify** - фильтрация по IP провайдера
   - Только IP Novofon: `37.139.38.224`, `37.139.38.56`
   - Все остальные IP → блокируются

2. **Dialplan** - фильтрация по набранным номерам (DID)
   - Только реальные номера: `79581114700`, `04912`, `0011`
   - Мусорные номера → Hangup() БЕЗ Answer()

3. **ARI на localhost** - доступ только с сервера
   - `bindaddr = 127.0.0.1:8088`
   - Из интернета → недоступен

### **⚠️ КРИТИЧНО: Anonymous endpoint УДАЛЕН!**
```bash
# Проверка что anonymous УДАЛЕН:
sudo asterisk -rx "pjsip show endpoint anonymous"
# Должно: "Unable to find object anonymous" ✅

# Если показывает anonymous endpoint - это ОПАСНО!
# См. раздел "Экстренные проблемы" ниже
```

---

## 🚨 КРИТИЧЕСКИЕ ПРОБЛЕМЫ И РЕШЕНИЯ

### **"Абонент занят" (busy signal)**
**Причина**: Endpoint недоступен или identify правила не работают  
**НЕ ДОБАВЛЯЙТЕ anonymous endpoint!**

**Правильное решение:**
```bash
# 1. Проверить identify правила
sudo asterisk -rx "pjsip show identifies"
# Должно показать: 37.139.38.224/32 и 37.139.38.56/32

# 2. Если identify правил нет - восстановить из бэкапа
sudo cp /root/backup-asterisk/*/asterisk/pjsip.conf /etc/asterisk/
sudo asterisk -rx "pjsip reload"

# 3. Проверить результат
sudo asterisk -rx "pjsip show endpoint novofon-incoming"
```

### **Бот не отвечает**
**Причина**: Python процесс упал  
**Решение**:
```bash
cd /root/Asterisk_bot/asterisk-vox-bot
source venv/bin/activate
pkill -f stasis_handler
python app/backend/asterisk/stasis_handler_optimized.py
```

### **Нет звука**
**Причина**: TTS проблема или права доступа  
**Решение**:
```bash
# Проверить права
sudo chown -R asterisk:asterisk /var/lib/asterisk/sounds/
sudo chmod -R 755 /var/lib/asterisk/sounds/

# Проверить TTS файлы
ls -la /var/lib/asterisk/sounds/ru/stream_*
```

### **⚠️ ЭКСТРЕННО: Anonymous endpoint обнаружен!**
**Это критическая уязвимость безопасности!**

```bash
# 1. НЕМЕДЛЕННО удалить anonymous
sudo nano /etc/asterisk/pjsip.conf
# Найти и УДАЛИТЬ все строки с [anonymous]

# 2. Перезагрузить PJSIP
sudo asterisk -rx "pjsip reload"

# 3. Проверить что удален
sudo asterisk -rx "pjsip show endpoint anonymous"
# Должно: "Unable to find object anonymous"
```

---

## 📊 ТЕКУЩИЙ СТАТУС СИСТЕМЫ

### **✅ Что работает:**
- ✅ **PJSIP Identify**: Фильтрация по IP провайдера Novofon
- ✅ **Dialplan**: Только реальные DID (79581114700, 04912, 0011)
- ✅ **Защита от атак**: SIP-сканеры блокируются автоматически
- ✅ **ARI**: Закрыт на localhost:8088
- ✅ **Python бот**: Обрабатывает звонки через ARI
- ✅ **TTS**: Yandex gRPC TTS быстрый синтез речи
- ✅ **ASR**: Распознавание русской речи Yandex
- ✅ **AI Agent**: Генерация ответов с RAG
- ✅ **Любой клиент может звонить** на ваш номер

### **🛡️ Уровни защиты (активны):**
1. **Уровень 1 - IP фильтрация** (PJSIP Identify)
   - Только провайдер Novofon
   - IP: 37.139.38.224, 37.139.38.56

2. **Уровень 2 - DID фильтрация** (Dialplan)
   - Только реальные номера идут в бота
   - Мусор блокируется без Answer()

3. **Уровень 3 - ARI на localhost**
   - API недоступен из интернета

### **📈 Метрики производительности:**
- **Время отклика**: 2-3 секунды
- **TTS скорость**: 0.14-0.33 секунды (gRPC)
- **Стабильность**: Система защищена и работает стабильно
- **Атаки**: Блокируются автоматически

---

## 🛠️ КОНФИГУРАЦИОННЫЕ ФАЙЛЫ

### **Asterisk конфигурация:**
- `/etc/asterisk/pjsip.conf` - ⭐ PJSIP endpoints, identify правила
- `/etc/asterisk/extensions.conf` - Dialplan маршрутизация
- `/etc/asterisk/ari.conf` - ARI пользователи
- `/etc/asterisk/http.conf` - HTTP/ARI сервер (localhost!)

### **Python бот конфигурация:**
- `/root/Asterisk_bot/asterisk-vox-bot/.env` - Основные настройки
- `/root/Asterisk_bot/asterisk-vox-bot/app/backend/` - Исходный код

### **Логи и мониторинг:**
- `/var/log/asterisk/messages.log` - ⭐ Логи Asterisk (атаки видны здесь)
- `/var/lib/asterisk/sounds/ru/` - Аудио файлы TTS
- `/var/spool/asterisk/recording/` - Записи звонков

---

## 📞 ТЕСТИРОВАНИЕ

### **Базовый тест работоспособности:**
1. Позвонить на `79581114700` **с любого номера** ✅
2. Дождаться ответа бота (должен ответить в течение 3 секунд)
3. Сказать что-то на русском языке
4. Проверить, что бот отвечает голосом

### **Тест безопасности:**
```bash
# 1. Проверить что anonymous УДАЛЕН
sudo asterisk -rx "pjsip show endpoint anonymous"
# ✅ Должно: "Unable to find object anonymous"

# 2. Проверить identify правила
sudo asterisk -rx "pjsip show identifies"
# ✅ Должно показать: 37.139.38.224/32 и 37.139.38.56/32

# 3. Проверить что атаки блокируются
sudo tail -20 /var/log/asterisk/messages.log | grep "No matching endpoint"
# ✅ Должно показать блокировки от сканеров
```

### **Расширенный тест:**
```bash
# 1. Проверить endpoints
sudo asterisk -rx "pjsip show endpoints"
# novofon-incoming должен быть Unavailable (это нормально)

# 2. Сделать звонок и проверить каналы
sudo asterisk -rx "core show channels"
# Должны появиться PJSIP каналы

# 3. Проверить Stasis приложение
sudo asterisk -rx "stasis show apps"
# Должно показать: asterisk-bot

# 4. Проверить создание аудио файлов
ls -la /var/lib/asterisk/sounds/ru/stream_*
# Должны создаваться новые WAV файлы
```

---

## 🆘 ЭКСТРЕННЫЕ КОНТАКТЫ

### **При критических проблемах:**
1. **Сначала**: Читать [asterisk-system-guide.md](asterisk-system-guide.md) - там все подробно
2. **Экстренное восстановление**: См. раздел выше "Быстрый старт"
3. **Логи для анализа**: `/var/log/asterisk/messages.log`

### **Бэкап конфигурации:**
```bash
# Создать бэкап перед изменениями
sudo tar -czf /root/asterisk_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
    /etc/asterisk/pjsip.conf \
    /etc/asterisk/extensions.conf \
    /etc/asterisk/ari.conf \
    /etc/asterisk/http.conf \
    /root/Asterisk_bot/asterisk-vox-bot/.env
```

---

## 📝 ИСТОРИЯ ИЗМЕНЕНИЙ

### **2025-10-01 - v2.0 (Критическое обновление безопасности)**
- ✅ **УДАЛЕН anonymous endpoint** - критическая уязвимость
- ✅ **Настроен PJSIP Identify** - фильтрация по IP провайдера
- ✅ **Исправлен Dialplan** - убран фильтр по CallerID, защита по DID
- ✅ **ARI закрыт на localhost** - недоступен из интернета
- ✅ **Атаки блокируются** - "No matching endpoint found"
- ✅ **Любой клиент может звонить** - на реальный номер
- ✅ **Документация обновлена** - актуальная информация

### **2025-09-26 - v1.0**
- ⚠️ **УСТАРЕЛО**: Anonymous endpoint (создавал уязвимость)
- ✅ Исправлена проблема "абонент занят"
- ✅ Система работала стабильно (но была уязвима)

### **Критические проблемы (решены 01.10.2025):**
- ❌ Anonymous endpoint → ✅ УДАЛЕН, настроен identify
- ❌ Атаки от поддельных номеров → ✅ Блокируются автоматически
- ❌ Фильтр по CallerID → ✅ Убран, любой может звонить
- ❌ ARI открыт в интернет → ✅ Закрыт на localhost

---

## 🎓 ДЛЯ НОВИЧКОВ

### **Что такое PJSIP Identify?**
Это правило которое говорит Asterisk: "Принимай звонки ТОЛЬКО от этих IP-адресов". Все остальные - отклоняй.

### **Почему anonymous endpoint опасен?**
Потому что он принимает звонки от **ЛЮБОГО IP** из интернета. Это как дверь без замка - кто угодно может войти.

### **Как работает защита?**
1. Звонок приходит → Asterisk проверяет IP
2. IP совпадает с провайдером? → Принимает
3. IP не совпадает? → Блокирует ("No matching endpoint")

### **Что если я хочу добавить еще один IP?**
Добавьте в `/etc/asterisk/pjsip.conf` в секцию `[novofon-identify]`:
```ini
match=НОВЫЙ_IP_АДРЕС
```
Затем: `sudo asterisk -rx "pjsip reload"`

---

**Дата создания**: 2025-09-26  
**Версия документации**: 2.0  
**Статус системы**: ✅ **Защищена и работает стабильно**  
**Последнее обновление**: 2025-10-01 (Критическое обновление безопасности)
