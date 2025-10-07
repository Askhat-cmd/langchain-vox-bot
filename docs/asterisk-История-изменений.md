# 📜 ИСТОРИЯ ИЗМЕНЕНИЙ ASTERISK

---

## 🔥 Октябрь 2025 - Критическое исправление безопасности

### ⚠️ Проблема: Атака поддельных номеров

**Дата**: 26-30 сентября 2025  
**Обнаружено**: После оптимизации задержек дешевая AI-модель сломала конфигурацию

**Симптомы:**
- ❌ Звонки от поддельных номеров: 7005, 2600, 84957285000, default
- ❌ Мусорные звонки проходили в бота
- ❌ Невозможно было отличить реальные звонки от атак

**Причины:**
1. **Включен `anonymous` endpoint** в `/etc/asterisk/pjsip.conf`
   - Asterisk принимал звонки от ЛЮБОГО IP из интернета
   - Не было фильтрации по провайдеру

2. **Правило `_X.` с Answer()** в `/etc/asterisk/extensions.conf`
   - Любой набранный номер (даже мусорный) отвечался
   - Все звонки шли в бота без проверки

3. **ARI открыт на `0.0.0.0:8088`** в `/etc/asterisk/http.conf`
   - API был доступен из интернета
   - Увеличивало поверхность атаки

4. **Временный фильтр по CallerID**
   - Добавлен как временная мера
   - Пропускал только номер `79613566065`
   - **Убивал весь смысл системы** - клиенты не могли дозвониться

---

### ✅ Решение (01 октября 2025)

#### Шаг 1: Удален anonymous endpoint

**Файл**: `/etc/asterisk/pjsip.conf`

**Что было:**
```ini
[anonymous]
type=endpoint
transport=transport-udp
context=from-novofon
disallow=all
allow=alaw,ulaw,g722
dtmf_mode=rfc4733
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
direct_media=no
max_contacts=3
timers=yes
timers_sess_expires=120
```

**Что стало:**
```
# Полностью удалено - больше нет anonymous endpoint
```

**Команда применения:**
```bash
sudo asterisk -rx "pjsip reload"
```

---

#### Шаг 2: Настроена IP-фильтрация (PJSIP Identify)

**Файл**: `/etc/asterisk/pjsip.conf`

**Что добавлено:**
```ini
[novofon-incoming]
type=endpoint
transport=transport-udp
context=from-novofon
disallow=all
allow=alaw,ulaw,g722
dtmf_mode=rfc4733
rtp_symmetric=yes
force_rport=yes
rewrite_contact=yes
direct_media=no
timers=yes
timers_sess_expires=360

[novofon-identify]
type=identify
endpoint=novofon-incoming
match=37.139.38.224
match=37.139.38.56

[novofon-identify-2]
type=identify
endpoint=novofon-incoming
match=37.139.38.56/32
```

**Как получили IP-адреса:**
1. Поиск в документации Novofon
2. DNS lookup для:
   - `sip.novofon.ru` → `37.139.38.224`
   - `pbx.novofon.com` → `37.139.38.56`

**Команда применения:**
```bash
sudo asterisk -rx "pjsip reload"
```

**Проверка:**
```bash
sudo asterisk -rx "pjsip show identifies"
```

**Результат:**
```
Identify:  novofon-identify/novofon-incoming
     Match: 37.139.38.224/32
     Match: 37.139.38.56/32

Identify:  novofon-identify-2/novofon-incoming
     Match: 37.139.38.56/32
```

---

#### Шаг 3: Исправлен Dialplan

**Файл**: `/etc/asterisk/extensions.conf`

**Что было (НЕПРАВИЛЬНО):**
```ini
exten => _X.,1,NoOp(ВХОДЯЩИЙ ЗВОНОК: ${EXTEN} from ${CALLERID(num)})
exten => _X.,n,GotoIf($["${CALLERID(num)}" = "79613566065"]?allow:block)
exten => _X.,n(allow),NoOp(РАЗРЕШЕННЫЙ НОМЕР: ${CALLERID(num)})
exten => _X.,n,Answer()
exten => _X.,n,Set(CHANNEL(language)=ru)
exten => _X.,n,Stasis(asterisk-bot)
exten => _X.,n,Hangup()
exten => _X.,n(block),NoOp(ЗАБЛОКИРОВАННЫЙ НОМЕР: ${CALLERID(num)})
exten => _X.,n,Answer()  ← Проблема: отвечал даже на блокируемые
exten => _X.,n,Wait(1)
exten => _X.,n,Hangup()
```

**Что стало (ПРАВИЛЬНО):**
```ini
; Основной номер - главная точка входа
exten => 79581114700,1,NoOp(Main number to AI Handler)
exten => 79581114700,n,Answer()
exten => 79581114700,n,Set(CHANNEL(language)=ru)
exten => 79581114700,n,Stasis(asterisk-bot)
exten => 79581114700,n,Hangup()

; Алиас для основного номера
exten => 9581114700,1,Goto(79581114700,1)

; Внутренний номер
exten => 04912,1,NoOp(Internal number to AI Handler)
exten => 04912,n,Answer()
exten => 04912,n,Set(CHANNEL(language)=ru)
exten => 04912,n,Stasis(asterisk-bot)
exten => 04912,n,Hangup()

; Тестовый номер
exten => 0011,1,NoOp(Test number to AI Handler)
exten => 0011,n,Answer()
exten => 0011,n,Set(CHANNEL(language)=ru)
exten => 0011,n,Stasis(asterisk-bot)
exten => 0011,n,Hangup()

; Алиас для тестового номера
exten => 11,1,Goto(0011,1)

; ⭐ ЗАЩИТА: Все остальные номера блокируются БЕЗ Answer()
exten => _X.,1,NoOp(БЛОКИРОВКА неизвестного DID: ${EXTEN} от ${CALLERID(num)})
exten => _X.,n,Hangup()  ← Ключевое изменение: НЕТ Answer()!
```

**Ключевые изменения:**
1. ❌ **Убран фильтр по CallerID** - теперь ЛЮБОЙ может звонить
2. ✅ **Добавлены конкретные DID** (79581114700, 04912, 0011)
3. ✅ **`_X.` БЕЗ Answer()`** - мусор не считается "отвеченным"

**Команда применения:**
```bash
sudo asterisk -rx "dialplan reload"
```

**Проверка:**
```bash
sudo asterisk -rx "dialplan show from-novofon"
```

---

#### Шаг 4: Закрыт ARI на localhost

**Файл**: `/etc/asterisk/http.conf`

**Что было:**
```ini
[general]
enabled = yes
bindaddr = 0.0.0.0  ← Доступен из интернета!
bindport = 8088
```

**Что стало:**
```ini
[general]
enabled = yes
bindaddr = 127.0.0.1  ← Доступен только локально
bindport = 8088
```

**Команда применения:**
```bash
sudo asterisk -rx "module reload http.so"
```

**Проверка:**
```bash
sudo asterisk -rx "http show status"
# Должно: Server Enabled and Bound to 127.0.0.1:8088
```

---

#### Шаг 5: Исправлены синтаксические ошибки в pjsip.conf

**Проблема**: Настройки `timers` находились вне секций endpoint

**Что было (ОШИБКА):**
```ini
[novofon-incoming]
type=endpoint
...

; Настройки для стабильности каналов
timers = always  ← Вне секции!
timers_sess_expires = 360  ← Вне секции!
```

**Что стало:**
```ini
[novofon-incoming]
type=endpoint
transport=transport-udp
context=from-novofon
...
timers=yes  ← Внутри секции
timers_sess_expires=360  ← Внутри секции
```

**Проблема была в том, что:**
- PJSIP не загружал правила `identify` из-за ошибки парсинга
- В логах: `ERROR[856334] config_options.c: Could not find option suitable for category`

---

### 📊 Результаты исправлений

**До (26-30 сентября):**
- ❌ Атаки проходили (~50+ мусорных звонков в день)
- ❌ Невозможно отличить реальные звонки
- ❌ Временный фильтр блокировал реальных клиентов
- ❌ Система небезопасна

**После (01 октября):**
- ✅ Атаки блокируются на уровне PJSIP ("No matching endpoint found")
- ✅ Реальные звонки проходят без проблем
- ✅ Любой клиент может позвонить на 79581114700
- ✅ Мусорные DID не отвечаются (Hangup без Answer)
- ✅ Система защищена и стабильна

---

### 🔍 Проверка работы защиты

**Логи атак (блокируются):**
```
[Oct 1 07:05:59] NOTICE[879303] res_pjsip/pjsip_distributor.c: 
Request 'REGISTER' from '"9007" <sip:9007@31.207.75.71>' 
failed for '185.243.5.195:5350' (callid: 473982058) 
- No matching endpoint found
```

**Логи реальных звонков (проходят):**
```
2025-10-01 07:03:00,117 - __main__ - INFO - 🔔 Новый звонок: 
Channel=1759302179.412, Caller=79613566065
2025-10-01 07:03:00,118 - __main__ - INFO - ✅ Звонок уже принят в dialplan
```

---

### 📝 Что узнали из этого инцидента

1. **Никогда не использовать anonymous endpoint** в продакшене
   - Открывает сервер для всего интернета
   - Нет контроля кто звонит

2. **Всегда использовать PJSIP identify** для фильтрации по IP провайдера
   - Первая линия защиты
   - Блокирует на уровне SIP

3. **Dialplan должен быть строгим**
   - Конкретные DID → в приложение
   - Всё остальное → Hangup() БЕЗ Answer()
   - Не фильтровать по CallerID (убивает функциональность)

4. **ARI только на localhost**
   - Python бот на том же сервере
   - Нет доступа из интернета

5. **Проверять синтаксис конфигов**
   - Настройки должны быть внутри секций
   - Проверять что правила загружаются (`pjsip show identifies`)

6. **Не доверять дешевым AI-моделям** для критических изменений
   - Использовать только проверенные модели для продакшена
   - Делать бэкапы перед изменениями

---

## 📈 Будущие улучшения (TODO)

1. **Rate-limit на порту 5060** (опционально)
   - Уменьшит нагрузку от сканеров
   - iptables с hashlimit

2. **Мониторинг атак**
   - Dashboard с метриками
   - Алерты при подозрительной активности

3. **Автоматический бэкап конфигурации**
   - Ежедневный cron job
   - Хранение 30 дней

4. **Логирование в отдельный файл**
   - Только атаки в отдельный лог
   - Упростит анализ

5. **Fail2ban для SIP**
   - Автоматический бан IP сканеров
   - Уменьшит нагрузку на сервер

---

**Документ создан**: 01.10.2025  
**Последнее обновление**: 01.10.2025  
**Автор**: AI Cursor Assistant при участии пользователя

