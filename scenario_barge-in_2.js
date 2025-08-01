/**
 * Voximplant‑сценарий для голосового ассистента «Метротэст»
 * Версия 8.2 (стабильная, ускоренный вариант, с barge‑in и progressive TTS)
 *
 * Изменения vs 8.1
 * • progressivePlayback:true — TTS начинает играть, пока ещё генерируется аудио (−300‑600 мс).
 * • SPEECH_END_TIMEOUT снижен до 200 мс (быстрее начинаем озвучивать ответ).
 * • ASR остается непрерывно включён; больше никаких stopMediaTo.
 * • Расширенный phraseHints сохранён.
 */

require(Modules.ASR);

// ─── конфигурация ────────────────────────────────────────
const WS_URL   = "ws://31.207.75.71:8000/ws";
const VOICE    = VoiceList.TBank.ru_RU_Alyona;
const SPEECH_END_TIMEOUT = 200;           // пауза перед TTS, мс
// ─────────────────────────────────────────────────────────

// ─── глобальное состояние ────────────────────────────────
let call, asr, wsReady = false;
let buf = "", bufTimer = null;
let currentPlayer = null;
// ─────────────────────────────────────────────────────────

function clean(txt){ return txt.replace(/[|*]/g," ").replace(/\s+/g," ").trim(); }

VoxEngine.addEventListener(AppEvents.CallAlerting, function(ev){
  call = ev.call;
  Logger.write("🚀 start, callId="+call.id);
  call.answer();

  /* 1. создаём ASR (не выключаем до конца звонка) */
  asr = VoxEngine.createASR({
    profile        : ASRProfileList.TBank.ru_RU,
    interimResults : true,
    phraseHints    : [
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

  asr.addEventListener(ASREvents.CaptureStarted, function(/*e*/){
    if (currentPlayer){ currentPlayer.stop(); currentPlayer=null; }
  });
  asr.addEventListener(ASREvents.InterimResult, function(/*e*/){
    if (currentPlayer){ currentPlayer.stop(); currentPlayer=null; }
  });
  asr.addEventListener(ASREvents.Result, function(e){
    if (!e.text) return;
    Logger.write("🗣️ "+e.text);
    if (bufTimer){ clearTimeout(bufTimer); bufTimer=null; buf=""; }
    if (wsReady) socket.send(e.text);
  });

  /* 2. подключаем входящий звук к ASR (один раз) */
  call.sendMediaTo(asr);

  /* 3. WebSocket к бэкенду */
  // Добавляем callerid в URL для бэкенда
  const callerId = call.callerid(); // Вызываем как функцию, чтобы получить значение
  const urlWithCallerId = `${WS_URL}?callerId=${encodeURIComponent(callerId)}`;
  const socket = VoxEngine.createWebSocket(urlWithCallerId);

  socket.addEventListener(WebSocketEvents.OPEN, function(/*e*/){
    wsReady = true;
    Logger.write(`✅ WS open for ${callerId}`);
    // Теперь бэкенд сам пришлёт приветствие
  });
  socket.addEventListener(WebSocketEvents.MESSAGE, function(m){
    if (!m.text) return;
    buf += m.text;
    if (bufTimer) clearTimeout(bufTimer);
    bufTimer = setTimeout(function(){
      const ready = clean(buf); buf=""; bufTimer=null;
      speak(ready);
    }, SPEECH_END_TIMEOUT);
  });
  socket.addEventListener(WebSocketEvents.ERROR,  function(e){ Logger.write("❌ WS error:"+JSON.stringify(e)); });
  socket.addEventListener(WebSocketEvents.CLOSE,  function(/*e*/){ wsReady=false; });

  /* 4. hang‑up handler */
  call.addEventListener(CallEvents.Disconnected, function(/*e*/){
    Logger.write("📴 hang‑up");
    VoxEngine.terminate();
  });
});

/* Проигрываем фразу с прогрессивной отдачей */
function speak(text){
  if (!text) return;
  if (currentPlayer){ currentPlayer.stop(); }
  currentPlayer = VoxEngine.createTTSPlayer(text,{
    language: VOICE,
    progressivePlayback: true
  });
  currentPlayer.sendMediaTo(call);
  currentPlayer.addEventListener(PlayerEvents.PlaybackFinished, function(/*e*/){
    currentPlayer = null;
  });
}
