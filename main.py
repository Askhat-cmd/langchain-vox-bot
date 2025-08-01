"""
Основной файл приложения.
- WebSocket-сервер для общения с Voximplant
- API для просмотра логов
- Статика для UI логов
"""
import os, logging, uuid, json, asyncio, io
from datetime import datetime, timezone
from typing import Dict, Any, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, status
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from Agent import Agent
from log_storage import insert_log, query_logs, to_csv, delete_all_logs

# --- Инициализация ---

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
app.mount("/logs-ui", StaticFiles(directory="logs-ui", html=True), name="logs-ui")

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
    """
    Удаляет все логи.
    """
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
    # Кодируем в utf-8-sig, чтобы Excel правильно распознавал кириллицу (добавляется BOM)
    response_bytes = csv_data_str.encode('utf-8-sig')
    return StreamingResponse(
        io.BytesIO(response_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="call_logs.csv"'}
    )

@app.get("/kb")
async def get_knowledge_base():
    """
    Отдает содержимое файла базы знаний.
    """
    kb_path = "Метротест_САЙТ.txt"
    try:
        with open(kb_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return JSONResponse(content={"text": content})
    except FileNotFoundError:
        return JSONResponse(content={"error": "Файл базы знаний не найден"}, status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, callerId: str = Query(None)):
    """
    Основной обработчик WebSocket-соединений от Voximplant.
    - Управляет жизненным циклом звонка.
    - Сохраняет лог после завершения звонка.
    """
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
        greeting = "Здравствуйте, Вы позвонили в компанию «Метротэст». Чем я могу помочь?"
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
