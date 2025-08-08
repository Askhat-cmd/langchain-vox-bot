/**
 * Voximplant-сценарий для голосового ассистента
 * Версия 8.4.1 (стабильная, с защитой от ложного barge-in)
 *
 * Изменения vs 8.4:
 * • DEBOUNCE_TIMEOUT увеличен с 300 до 700 мс для более надежной
 *   защиты от прерываний из-за эха на некоторых линиях.
 */

require(Modules.ASR);

// ─── конфигурация ────────────────────────────────────────
const WS_URL = "ws://31.207.75.71:8000/ws";
const VOICE = VoiceList.TBank.ru_RU_Alyona;
const SPEECH_END_TIMEOUT = 200; // пауза перед TTS, мс
const DEBOUNCE_TIMEOUT = 700;   // Задержка для защиты от barge-in, мс
// ─────────────────────────────────────────────────────────

// ─── глобальное состояние ────────────────────────────────
let call, asr, wsReady = false;
let buf = "", bufTimer = null;
let currentPlayer = null;
let isSpeaking = false; // Флаг, что бот сейчас говорит
// ─────────────────────────────────────────────────────────

function clean(txt) { return txt.replace(/[|*]/g, " ").replace(/\s+/g, " ").trim(); }

VoxEngine.addEventListener(AppEvents.CallAlerting, function(ev) {
    call = ev.call;
    Logger.write("🚀 start, callId=" + call.id);
    call.answer();

    /* 1. создаём ASR (не выключаем до конца звонка) */
    // Дополнительные подсказки ASR из доменного словаря (единицы, произношения, стандарты)
    const HINTS_EXTRA = [
        // единицы и произношения
        "кН", "кн", "килоньютон", "килоньютоны", "килоньютона",
        "ка-эн", "кэ-эн", "к эн", "к эН", "к эн", "кэн",
        "Н", "ньютон", "ньютонов", "ньютоне",
        "Н·м", "ньютон-метр", "ньютон метр", "н м",
        "Н·мм", "ньютон миллиметр", "н мм",
        "МПа", "мпа", "мэ-пэ-а", "эм-пэ-а", "мега паскаль", "мегапаскаль",
        "кПа", "кпа", "кэ-пэ-а", "кило паскаль", "килопаскаль", "паскаль", "Па",
        "Н/мм²", "ньютон на миллиметр квадратный", "н на мм2", "н/мм2",
        "Гц", "герц", "частота в герцах",
        "мм", "миллиметр", "миллиметры", "миллиметров", "mm",
        "см", "сантиметр", "сантиметры", "сантиметров", "cm",
        "м", "метр", "метры", "метров",
        "мм/мин", "миллиметров в минуту", "мм в минуту",
        "мм/с", "миллиметров в секунду", "мм в секунду",
        "м/с", "метров в секунду",
        "об/мин", "rpm", "об в минуту",
        "кг", "килограмм", "килограмма", "килограммы", "kg",
        "грамм", "грамма", "граммы",
        "т", "тонна", "тонны",
        "%", "проценты", "процент",
        "л/мин", "литр в минуту", "литров в минуту", "l/min",
        "бар", "bar", "кгс/см²", "килограмм силы на сантиметр квадратный",
        "Вт", "ватт", "w", "кВт", "квт", "киловатт", "kw", "кВт·ч", "квтч", "киловатт час",
        "В", "вольт", "v", "А", "ампер", "amp", "Ом", "омы", "ohm", "Ω",
        "дБ", "децибел", "db",
        "мин/ч", "минут в час", "мин на час",
        // некоторые стандарты
        "ISO 7500-1", "ASTM E4", "ISO 6892-1", "ASTM E8", "ASTM E9",
    ];

    asr = VoxEngine.createASR({
        profile: ASRProfileList.TBank.ru_RU,
        interimResults: true,
        phraseHints: [
            "твердомер", "твердомеры", "твердомер Роквелла", "твердомер Бринелля",
            "твердомер Виккерса", "микротвердомер",
            "разрывная машина", "разрывные машины", "испытательная машина",
            "испытательные машины", "универсальная разрывная машина",
            "испытательный пресс", "испытательные прессы", "пресс ПИ",
            "РГМ", "РГМ-1000", "РГМ-1000-А",
            "динамическая машина", "усталостная машина",
            "испытание на растяжение", "испытание на сжатие",
            "испытание на изгиб", "Метротэст",
            "РГМ-Г-А", "РЭМ", "РЭМ-I-0,1", "РЭМ-1", "РЭМ-50", "РЭМ-100",
            "РЭМ-200", "РЭМ-300", "РЭМ-500", "РЭМ-600",
            "РЭМ-I-2", "РЭМ-I-3", "РЭМ-I-5", "РЭМ-I-10",
            "УИМ-Д", "УИМ-Д-100", "УИМ-Д-250", "УИМ-Д-500",
            "УИМ-Д-750", "пневмодинамическая машина",
            "ПИМ-МР-100", "ПИМ-МР-200", "ПИМ-МР-300",
            "универсальные испытательные машины", "универсальная машина",
            "машина на усталость", "усталостные испытания",
            "машины на кручение", "машины на изгиб",
            "МК", "МКС", "МКС-1000", "МКС-2000", "МКС-3000", "МКС-500",
            "системы температурных испытаний", "СТИ",
            "экстензометр", "УИД-ПБ", "M-VIEW",
            "копра маятниковая", "копры", "КМ", "КВ", "КММ", "ИКМ-450-А",
            "стилоскоп", "СЛП", "СЛ-13У", "СЛ-15",
            "климатические камеры", "КТХ", "КИО", "КИУ", "КТВ", "КТЗ", "КТЧ",
            "ресурсное испытание", "испытание на износ",
            "машины шлифовально-полировальные", "МШП", "МП",
            "микроскоп металлографический", "ММИ", "ММР", "ММП",
            "лаборатория модульная", "ЛММ-25",
            "мебель лабораторная", "СКЗ-1", "СКЗ-2", "СКЗ-3-А", "СКЗ-4"
        ].concat(HINTS_EXTRA)
    });

    const stopPlayerOnBargeIn = (eventName) => {
        if (isSpeaking) {
            // Logger.write(`🎤 ASR event '${eventName}' received, but ignoring for ${DEBOUNCE_TIMEOUT}ms due to active playback.`);
            return;
        }
        if (currentPlayer) {
            Logger.write(`[BARGE-IN] ASR event '${eventName}' triggered. Stopping player.`);
            currentPlayer.stop();
            currentPlayer = null;
        }
    };
    
    asr.addEventListener(ASREvents.CaptureStarted, () => stopPlayerOnBargeIn('CaptureStarted'));
    asr.addEventListener(ASREvents.InterimResult, () => stopPlayerOnBargeIn('InterimResult'));

    // Нормализация распознанного текста (единицы измерения, произношения → канонический вид)
    function normalizeUtterance(input) {
        if (!input) return input;
        let t = input;
        // унификация дефисов и пробелов
        t = t.replace(/[–—−]/g, "-").replace(/\s+/g, " ");

        // кН: произносительные варианты → «кН»
        t = t.replace(/\b(к\s?эн|ка-эн|кэ-эн|к\s?ен|к\s?э\s?н|кэн)\b/gi, "кН");
        t = t.replace(/\bкило\s?ньютоны?\b/gi, "кН");
        t = t.replace(/\bкн\b/gi, "кН");

        // МПа
        t = t.replace(/\b(м\s?п\s?а|мэ-пэ-а|эм-пэ-а|мегапаскал[ьяеы]?|мега\s?паскал[ьяеы]?)\b/gi, "МПа");
        // кПа
        t = t.replace(/\b(к\s?п\s?а|кэ-пэ-а|килопаскал[ьяеы]?|кило\s?паскал[ьяеы]?)\b/gi, "кПа");
        // Гц
        t = t.replace(/\b(герц|герцы|гц)\b/gi, "Гц");

        // Ньютон, Ньютон-метр
        t = t.replace(/\bньютон[а-я]*\b/gi, "Н");
        t = t.replace(/\b(ньюто[нн][ -]?метр[а-я]*|н\s?м)\b/gi, "Н·м");
        // Ньютон-миллиметр
        t = t.replace(/\b(ньюто[нн][ -]?миллиметр[а-я]*|н\s?мм)\b/gi, "Н·мм");
        // Н/мм²
        t = t.replace(/\b(н(ь?ютон)?\s*(?:\/|на)\s*мм\s*(?:\^?2|²)|ньютон\s+на\s+миллиметр\s+квадратн[а-я]*)\b/gi, "Н/мм²");

        // Длины
        t = t.replace(/\bмиллиметр[а-я]*\b/gi, "мм");
        t = t.replace(/\bmm\b/gi, "мм");
        t = t.replace(/\bсантиметр[а-я]*\b/gi, "см");
        t = t.replace(/\bcm\b/gi, "см");
        t = t.replace(/\bметр[а-я]*\b/gi, "м");

        // Скорости
        t = t.replace(/\b(миллиметров\s+в\s+минуту|мм\s+в\s+минуту)\b/gi, "мм/мин");
        t = t.replace(/\b(миллиметров\s+в\s+секунду|мм\s+в\s+секунду|мм\/с)\b/gi, "мм/с");
        t = t.replace(/\b(метров\s+в\s+секунду)\b/gi, "м/с");
        // обороты в минуту
        t = t.replace(/\b(r\s?p\s?m|оборотов?\s+в\s+минуту|об\/?мин)\b/gi, "об/мин");

        // Масса
        t = t.replace(/\bкилограмм[а-я]*\b/gi, "кг");
        t = t.replace(/\bkg\b/gi, "кг");
        t = t.replace(/\bграмм[а-я]*\b/gi, "г");
        t = t.replace(/\bтонн[а-я]*\b/gi, "т");

        // Температура и проценты
        t = t.replace(/\bградус(ов)?\s+цельсия\b/gi, "°C");
        t = t.replace(/\bпо\s+цельсию\b/gi, "°C");
        t = t.replace(/\bпроцент(ов)?\b/gi, "%");

        // Электрика и мощность
        t = t.replace(/\b(ватт(а|ов)?|w)\b/gi, "Вт");
        t = t.replace(/\b(киловатт(а|ов)?|к\s?вт|kw)\b/gi, "кВт");
        t = t.replace(/\b(кВт\s*[·xx]\s*ч|киловатт\s*час[а-я]*|квтч)\b/gi, "кВт·ч");
        t = t.replace(/\b(вольт(а|ов)?|v)\b/gi, "В");
        t = t.replace(/\b(ампер(а|ов)?|amp(?:s)?)\b/gi, "А");
        t = t.replace(/\b(ом(а|ов)?|ohm|Ω)\b/gi, "Ом");

        // Давление/расход альтернативные единицы
        t = t.replace(/\b(литр(ов)?\s*в\s*минуту|л\/?мин|l\/?min)\b/gi, "л/мин");
        t = t.replace(/\b(бар|bar)\b/gi, "бар");
        t = t.replace(/\b(кгс\s*\/\s*см\s*(?:\^?2|²)|килограмм\s*силы\s*на\s*сантиметр\s*квадратн[а-я]*)\b/gi, "кгс/см²");

        // Звук
        t = t.replace(/\b(децибел(а|ов)?|дб|db)\b/gi, "дБ");

        // Приведение лишних пробелов
        t = t.replace(/\s+\/\s+/g, "/");

        return t.trim();
    }

    asr.addEventListener(ASREvents.Result, function(e) {
        if (!e.text) return;
        var normalized = normalizeUtterance(e.text);
        Logger.write("🗣️ RAW: " + e.text);
        if (normalized !== e.text) Logger.write("🧭 NORM: " + normalized);
        if (bufTimer) { clearTimeout(bufTimer); bufTimer = null; buf = ""; }
        if (wsReady) socket.send(normalized);
    });

    /* 2. подключаем входящий звук к ASR (один раз) */
    call.sendMediaTo(asr);

    /* 3. WebSocket к бэкенду */
    const callerId = call.callerid();
    const urlWithCallerId = `${WS_URL}?callerId=${encodeURIComponent(callerId)}`;
    const socket = VoxEngine.createWebSocket(urlWithCallerId);

    socket.addEventListener(WebSocketEvents.OPEN, function(e) {
        wsReady = true;
        Logger.write(`✅ WS open for ${callerId}.`);
    });
    socket.addEventListener(WebSocketEvents.MESSAGE, function(m) {
        if (!m.text) return;
        // Logger.write(`📄 WS chunk received: "${m.text}"`); // Можно раскомментировать для детальной отладки
        buf += m.text;
        if (bufTimer) clearTimeout(bufTimer);
        bufTimer = setTimeout(function() {
            const ready = clean(buf);
            buf = "";
            bufTimer = null;
            speak(ready);
        }, SPEECH_END_TIMEOUT);
    });
    socket.addEventListener(WebSocketEvents.ERROR, function(e) { Logger.write("❌ WS error:" + JSON.stringify(e)); });
    socket.addEventListener(WebSocketEvents.CLOSE, function(e) { 
        Logger.write(`🔌 WS close.`);
        wsReady = false; 
    });

    /* 4. hang‑up handler */
    call.addEventListener(CallEvents.Disconnected, function(e) {
        Logger.write(`📴 hang‑up.`);
        VoxEngine.terminate();
    });
});

/* Проигрываем фразу с прогрессивной отдачей */
function speak(text) {
    if (!text) {
        Logger.write("🔇 speak() called with empty text, skipping.");
        return;
    }
    Logger.write(`▶️ Playing TTS for: "${text}"`);
    if (currentPlayer) {
        Logger.write("⚠️ speak() called while another player is active. Stopping old one.");
        currentPlayer.stop();
    }
    
    isSpeaking = true;
    setTimeout(() => {
        isSpeaking = false;
        // Logger.write(`🎤 Barge-in debounce period ended. ASR can now interrupt.`); // Можно раскомментировать для детальной отладки
    }, DEBOUNCE_TIMEOUT);
    
    currentPlayer = VoxEngine.createTTSPlayer(text, {
        language: VOICE,
        progressivePlayback: true
    });
    currentPlayer.sendMediaTo(call);
    
    currentPlayer.addEventListener(PlayerEvents.Started, function(e){
        // Logger.write(`🔊 Player started.`);
    });
    currentPlayer.addEventListener(PlayerEvents.Stopped, function(e){
        Logger.write(`⏹️ Player stopped.`);
        currentPlayer = null;
    });
    currentPlayer.addEventListener(PlayerEvents.PlaybackFinished, function(e) {
        // Logger.write(`✅ Player finished playback.`);
        currentPlayer = null;
    });
}
