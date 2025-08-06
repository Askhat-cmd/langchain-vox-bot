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
        ]
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

    asr.addEventListener(ASREvents.Result, function(e) {
        if (!e.text) return;
        Logger.write("🗣️ " + e.text);
        if (bufTimer) { clearTimeout(bufTimer); bufTimer = null; buf = ""; }
        if (wsReady) socket.send(e.text);
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
