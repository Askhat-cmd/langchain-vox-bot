"""
Основной файл приложения.
- WebSocket-сервер для общения с Voximplant
- API для просмотра логов
- Статика для UI логов
"""
import os, logging, uuid, json, asyncio, io, shutil, time
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, status, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from Agent import Agent
from log_storage import insert_log, query_logs, to_csv, delete_all_logs
from create_embeddings import recreate_embeddings

# --- Инициализация ---

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
app.mount("/logs-ui", StaticFiles(directory="logs-ui", html=True), name="logs-ui")

PROMPTS_FILE = "prompts.json"

try:
    agent = Agent()
    logger.info("Агент 'Метротест' успешно инициализирован.")
except Exception as e:
    logger.error(f"Ошибка при инициализации агента 'Метротест': {e}", exc_info=True)
    agent = None

# --- Глобальное состояние для управления звонками ---
active_calls: Dict[str, Dict[str, Any]] = {}

# --- Роуты ---

@app.get("/")
async def root():
    return HTMLResponse(
        "<h3>Бэкенд 'Метротэст' активен.<br>"
        "• WebSocket — <code>/ws</code><br>"
        "• UI логов — <code>/logs-ui/</code></h3>"
    )

# ... (остальные роуты для логов и CSV остаются без изменений) ...
@app.get("/logs")
async def get_logs(q: str | None = None,
                   date_from: str | None = None,
                   date_to: str | None = None,
                   status: str | None = None):
    rows = await query_logs({"from": date_from, "to": date_to, "status": status})
    if q:
        q_low = q.lower()
        filtered_rows = []
        for r in rows:
            if q_low in (r.get("callerId") or "").lower():
                filtered_rows.append(r)
                continue
            try:
                transcript = json.loads(r["transcript_json"])
                for turn in transcript:
                    if q_low in turn.get("text", "").lower():
                        filtered_rows.append(r)
                        break
            except (json.JSONDecodeError, AttributeError):
                continue
        rows = filtered_rows
    return JSONResponse(content=rows)

@app.delete("/logs")
async def clear_logs():
    try:
        await delete_all_logs()
        logger.info("🗑️ Все логи были удалены.")
        return JSONResponse(content={"message": "Все логи удалены"}, status_code=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении логов: {e}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@app.get("/logs/csv")
async def get_logs_csv():
    rows = await query_logs({})
    csv_data_str = await to_csv(rows)
    response_bytes = csv_data_str.encode('utf-8-sig')
    return StreamingResponse(
        io.BytesIO(response_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="call_logs.csv"'}
    )

# --- API для Базы Знаний и Промптов ---

@app.get("/api/prompts")
async def get_prompts():
    try:
        with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return JSONResponse(status_code=500, content={"error": f"Не удалось прочитать файл промптов: {e}"})

@app.post("/api/prompts")
async def update_prompts(new_prompts: Dict[str, Any]):
    try:
        with open(PROMPTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_prompts, f, ensure_ascii=False, indent=2)
        
        # Перезагружаем агента, чтобы он подхватил новые промпты
        if agent and hasattr(agent, 'reload'):
            agent.reload()
            
        return JSONResponse(content={"message": "Промпты успешно обновлены."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Не удалось сохранить промпты: {e}"})

@app.get("/kb")
async def get_knowledge_base():
    # ... (без изменений) ...
    kb_path = "Метротест_САЙТ.txt"
    try:
        with open(kb_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return JSONResponse(content={"text": content})
    except FileNotFoundError:
        return JSONResponse(content={"error": "Файл базы знаний не найден"}, status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@app.post("/kb/upload")
async def upload_kb(file: UploadFile = File(...)):
    # ... (без изменений) ...
    if not file.filename.endswith('.txt'):
        return JSONResponse(status_code=400, content={"message": "Ошибка: Пожалуйста, загрузите .txt файл."})

    try:
        kb_path = "Метротест_САЙТ.txt"
        
        backup_dir = "kb_backups"
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = os.path.join(backup_dir, f"Метротест_САЙТ_{timestamp}.txt.bak")
        shutil.copy(kb_path, backup_path)
        logger.info(f"💾 Создан бэкап базы знаний: {backup_path}")

        with open(kb_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"✅ Новый файл базы знаний '{file.filename}' сохранен.")

        asyncio.create_task(recreate_embeddings_and_reload_agent())
        
        return JSONResponse(status_code=202, content={"message": "Файл принят. Начался процесс обновления базы знаний. Это может занять несколько минут."})

    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке файла БЗ: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"message": f"Внутренняя ошибка сервера: {e}"})

async def recreate_embeddings_and_reload_agent():
    # ... (без изменений) ...
    logger.info("⏳ Начинаем пересоздание эмбеддингов в фоновом режиме...")
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, recreate_embeddings)
        logger.info("✅ Эмбеддинги успешно пересозданы.")
        
        if agent and hasattr(agent, 'reload'):
            agent.reload()
            
    except Exception as e:
        logger.error(f"❌ Исключение при пересоздании эмбеддингов: {e}", exc_info=True)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, callerId: str = Query(None)):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    start_time = datetime.now(timezone.utc)
    
    active_calls[session_id] = {
        "callerId": callerId,
        "startTime": start_time.isoformat(),
        "transcript": [],
        "status": "Initiated"
    }
    logger.info(f"Новый звонок: Session ID: {session_id}, Caller ID: {callerId}")

    if not agent:
        await websocket.send_text("Ошибка инициализации агента.")
        await websocket.close()
        del active_calls[session_id]
        return

    try:
        # Загружаем приветствие из файла
        greeting = agent.prompts.get("greeting", "Здравствуйте, чем могу помочь?")
        active_calls[session_id]["transcript"].append(
            {"speaker": "bot", "text": greeting, "timestamp": datetime.now(timezone.utc).isoformat()}
        )
        await websocket.send_text(greeting)

        while True:
            data = await websocket.receive_text()
            logger.info(f"Получен вопрос ({session_id}): {data}")
            active_calls[session_id]["transcript"].append(
                {"speaker": "user", "text": data, "timestamp": datetime.now(timezone.utc).isoformat()}
            )

            response_generator = agent.get_response_generator(data, session_id=session_id)
            
            full_response = ""
            for chunk in response_generator:
                if chunk:
                    await websocket.send_text(chunk)
                    full_response += chunk
            
            logger.info(f"Полный ответ ({session_id}) отправлен.")
            active_calls[session_id]["transcript"].append(
                {"speaker": "bot", "text": full_response, "timestamp": datetime.now(timezone.utc).isoformat()}
            )
            active_calls[session_id]["status"] = "InProgress"

    except WebSocketDisconnect:
        logger.info(f"Клиент ({session_id}) отключился.")
        active_calls[session_id]["status"] = "Completed"
    except Exception as e:
        logger.error(f"Ошибка WS ({session_id}): {e}", exc_info=True)
        active_calls[session_id]["status"] = "Failed"
    finally:
        # ... (логика сохранения лога без изменений) ...
        end_time = datetime.now(timezone.utc)
        call_log = active_calls.get(session_id)
        if call_log:
            log_record: Dict[str, Any] = {
                "id": session_id,
                "callerId": call_log["callerId"],
                "startTime": call_log["startTime"],
                "endTime": end_time.isoformat(),
                "status": call_log["status"],
                "transcript": call_log["transcript"],
            }
            try:
                await insert_log(log_record)
                logger.info(f"💾 Лог сохранён для Session {session_id}")
            except Exception as err:
                logger.error(f"❌ Ошибка insert_log: {err}", exc_info=True)
            
            del active_calls[session_id]
