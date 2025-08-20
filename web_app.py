from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from db_handler import get_shift_messages, get_chat_statistics
from datetime import datetime
import json
import asyncio
from typing import List

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Список активных WebSocket соединений
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"WebSocket подключен. Всего соединений: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"WebSocket отключен. Осталось соединений: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
            
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                disconnected.append(connection)
        
        # Удаляем неактивные соединения
        for connection in disconnected:
            self.disconnect(connection)

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    now = datetime.now()
    shift_name = "day_" + now.strftime("%Y-%m-%d") if 9 <= now.hour < 21 else "night_" + now.strftime("%Y-%m-%d")
    incoming, outgoing = get_shift_messages(shift_name)
    
    # Получаем статистику чатов
    chat_stats = get_chat_statistics()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "incoming": incoming, 
        "outgoing": outgoing, 
        "shift": shift_name,
        "chat_stats": chat_stats
    })

@app.get("/shift/{shift_name}", response_class=HTMLResponse)
def view_shift(request: Request, shift_name: str):
    incoming, outgoing = get_shift_messages(shift_name)
    chat_stats = get_chat_statistics()
    
    return templates.TemplateResponse("shift.html", {
        "request": request, 
        "incoming": incoming, 
        "outgoing": outgoing, 
        "shift": shift_name,
        "chat_stats": chat_stats
    })

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Отправляем обновления каждые 10 секунд
            await asyncio.sleep(10)
            
            # Проверяем состояние соединения
            if websocket.client_state.name != "CONNECTED":
                break
            
            try:
                # Получаем актуальные данные
                now = datetime.now()
                shift_name = "day_" + now.strftime("%Y-%m-%d") if 9 <= now.hour < 21 else "night_" + now.strftime("%Y-%m-%d")
                incoming, outgoing = get_shift_messages(shift_name)
                chat_stats = get_chat_statistics()
                
                # Создаем данные для отправки
                update_data = {
                    "type": "update",
                    "data": {
                        "chat_stats": chat_stats,
                        "incoming_count": len(incoming),
                        "outgoing_count": len(outgoing),
                        "total_messages": len(incoming) + len(outgoing),
                        "shift": shift_name,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    }
                }
                
                # Отправляем данные
                await websocket.send_text(json.dumps(update_data))
                
            except Exception as e:
                print(f"Ошибка отправки WebSocket данных: {e}")
                break
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket ошибка: {e}")
    finally:
        manager.disconnect(websocket)

@app.get("/stats", response_class=HTMLResponse)
def chat_statistics(request: Request):
    """Отдельная страница со статистикой чатов"""
    from db_handler import get_detailed_chat_statistics
    chat_stats = get_detailed_chat_statistics()
    return templates.TemplateResponse("stats.html", {
        "request": request,
        "chat_stats": chat_stats
    })

@app.get("/api/stats")
async def get_stats_api():
    """API для получения статистики (для AJAX запросов)"""
    try:
        now = datetime.now()
        shift_name = "day_" + now.strftime("%Y-%m-%d") if 9 <= now.hour < 21 else "night_" + now.strftime("%Y-%m-%d")
        incoming, outgoing = get_shift_messages(shift_name)
        
        # Импортируем новую функцию
        from db_handler import get_detailed_chat_statistics
        detailed_stats = get_detailed_chat_statistics()
        
        return {
            "chat_stats": detailed_stats,
            "incoming_count": len(incoming),
            "outgoing_count": len(outgoing),
            "total_messages": len(incoming) + len(outgoing),
            "shift": shift_name,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
    except Exception as e:
        print(f"Ошибка API stats: {e}")
        return {
            "chat_stats": {"active_chats": 0, "closed_chats": 0, "total_users": 0, "active_chat_list": [], "closed_chat_list": []},
            "incoming_count": 0,
            "outgoing_count": 0,
            "total_messages": 0,
            "shift": "error",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        

@app.post("/api/notify")
async def notify_new_message_endpoint(data: dict):
    """Эндпоинт для получения уведомлений о новых сообщениях"""
    try:
        await manager.broadcast({
            "type": "new_message",
            "message_type": data["type"],
            "data": data
        })
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}