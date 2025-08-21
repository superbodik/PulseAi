from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException, Form, Cookie
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from db_handler import get_shift_messages, get_chat_statistics, get_detailed_chat_statistics
from datetime import datetime
import json
import asyncio
from typing import List, Optional
import sqlite3
import csv
import io
import secrets
from urllib.parse import unquote

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Подключение статических файлов
app.mount("/static", StaticFiles(directory="templates"), name="static")

# Простая система пользователей
USERS = {
    "admin": {
        "password": "pulse2024",
        "role": "admin",
        "display_name": "Administrator"
    },
    "operator": {
        "password": "support123",
        "role": "operator", 
        "display_name": "Support Operator"
    },
    "viewer": {
        "password": "view123",
        "role": "viewer",
        "display_name": "Viewer"
    }
}

# Активные сессии
active_sessions = {}

def create_session_token():
    """Создает токен сессии"""
    return secrets.token_urlsafe(32)

def verify_user(username: str, password: str):
    """Проверяет данные пользователя"""
    if username in USERS:
        user_data = USERS[username]
        if password == user_data["password"]:
            return {
                "username": username,
                "role": user_data["role"],
                "display_name": user_data["display_name"]
            }
    return None

def get_current_user(session_token: Optional[str] = Cookie(None)):
    """Получает текущего пользователя из сессии"""
    if not session_token or session_token not in active_sessions:
        return None
    return active_sessions[session_token]

def require_auth(session_token: Optional[str] = Cookie(None)):
    """Требует аутентификации"""
    user = get_current_user(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Требуется вход в систему")
    return user

def require_admin(user=Depends(require_auth)):
    """Требует права администратора"""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    return user

# Список активных WebSocket соединений
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
            
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                disconnected.append(connection)
        
        for connection in disconnected:
            self.disconnect(connection)

manager = ConnectionManager()

@app.exception_handler(401)
async def auth_exception_handler(request: Request, exc):
    """Обработчик ошибок аутентификации"""
    if str(request.url).endswith("/login"):
        return templates.TemplateResponse("login.html", {"request": request})
    return RedirectResponse(url="/login")

@app.get("/favicon.ico")
async def favicon():
    """Заглушка для favicon"""
    return Response(status_code=204)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Страница входа"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    """Обработка входа"""
    user = verify_user(username, password)
    if user:
        session_token = create_session_token()
        active_sessions[session_token] = user
        
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key="session_token", 
            value=session_token, 
            httponly=True,
            max_age=86400
        )
        return response
    else:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Неверное имя пользователя или пароль"
        })

@app.get("/logout")
async def logout(session_token: Optional[str] = Cookie(None)):
    """Выход из системы"""
    if session_token and session_token in active_sessions:
        del active_sessions[session_token]
    
    response = RedirectResponse(url="/login")
    response.delete_cookie("session_token")
    return response

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user=Depends(require_auth)):
    """Главная страница дашборда"""
    try:
        now = datetime.now()
        shift_name = "day_" + now.strftime("%Y-%m-%d") if 9 <= now.hour < 21 else "night_" + now.strftime("%Y-%m-%d")
        incoming, outgoing = get_shift_messages(shift_name)
        chat_stats = get_detailed_chat_statistics()
        
        recent_messages = []
        for msg in (incoming + outgoing)[-20:]:
            msg['type'] = 'incoming' if msg in incoming else 'outgoing'
            recent_messages.append(msg)
        recent_messages.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request, 
            "incoming": incoming[:10],
            "outgoing": outgoing[:10],
            "recent_messages": recent_messages[:20],
            "shift": shift_name,
            "chat_stats": chat_stats,
            "user": user
        })
    except Exception as e:
        print(f"Ошибка загрузки дашборда: {e}")
        return RedirectResponse(url="/login")

@app.get("/stats", response_class=HTMLResponse)
async def chat_statistics(request: Request, user=Depends(require_auth)):
    """Отдельная страница со статистикой чатов"""
    try:
        chat_stats = get_detailed_chat_statistics()
        return templates.TemplateResponse("stats.html", {
            "request": request,
            "chat_stats": chat_stats,
            "user": user
        })
    except Exception as e:
        print(f"Ошибка загрузки статистики: {e}")
        return RedirectResponse(url="/login")

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request, user=Depends(require_auth)):
    """Страница аналитики"""
    try:
        return templates.TemplateResponse("analytics.html", {
            "request": request,
            "user": user
        })
    except Exception as e:
        print(f"Ошибка загрузки аналитики: {e}")
        return RedirectResponse(url="/login")

@app.get("/filters", response_class=HTMLResponse)
async def filters_page(request: Request, user=Depends(require_admin)):
    """Страница настройки фильтров (только для админов)"""
    try:
        return templates.TemplateResponse("filters.html", {
            "request": request,
            "user": user
        })
    except Exception as e:
        print(f"Ошибка загрузки фильтров: {e}")
        return RedirectResponse(url="/login")

@app.get("/chat/{username}", response_class=HTMLResponse)
async def chat_detail(request: Request, username: str, user=Depends(require_auth)):
    """Детальный просмотр чата пользователя"""
    try:
        decoded_username = unquote(username)
        
        with sqlite3.connect("pulseai.db") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT message, timestamp, message_type, chat_id
                FROM messages 
                WHERE username = ? 
                ORDER BY timestamp ASC
            ''', (decoded_username,))
            
            raw_messages = cursor.fetchall()
            messages = []
            
            for msg in raw_messages:
                messages.append({
                    'message': msg['message'] or '',
                    'timestamp': msg['timestamp'] or '',
                    'type': msg['message_type'] or 'unknown',
                    'chat_id': msg['chat_id'] or 0
                })
            
            if messages:
                try:
                    last_message_time = datetime.fromisoformat(messages[-1]['timestamp']) if messages[-1]['timestamp'] else datetime.now()
                    time_diff = datetime.now() - last_message_time
                    chat_status = "Активний" if time_diff.total_seconds() < 300 else "Закритий"
                except (ValueError, TypeError):
                    chat_status = "Невідомий"
            else:
                chat_status = "Порожній"
            
            incoming_count = sum(1 for msg in messages if msg['type'] == 'incoming')
            outgoing_count = sum(1 for msg in messages if msg['type'] == 'outgoing')
            
            return templates.TemplateResponse("chat_detail.html", {
                "request": request,
                "user": user,
                "username": decoded_username,
                "messages": messages,
                "chat_id": messages[-1]['chat_id'] if messages else 1,
                "chat_status": chat_status,
                "incoming_count": incoming_count,
                "outgoing_count": outgoing_count
            })
            
    except Exception as e:
        print(f"Ошибка загрузки чата для '{username}': {e}")
        return RedirectResponse(url="/")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket соединение для обновлений в реальном времени"""
    await manager.connect(websocket)
    try:
        while True:
            await asyncio.sleep(10)
            
            if websocket.client_state.name != "CONNECTED":
                break
            
            try:
                now = datetime.now()
                shift_name = "day_" + now.strftime("%Y-%m-%d") if 9 <= now.hour < 21 else "night_" + now.strftime("%Y-%m-%d")
                incoming, outgoing = get_shift_messages(shift_name)
                detailed_stats = get_detailed_chat_statistics()
                
                update_data = {
                    "type": "update",
                    "data": {
                        "chat_stats": detailed_stats,
                        "incoming_count": len(incoming),
                        "outgoing_count": len(outgoing),
                        "total_messages": len(incoming) + len(outgoing),
                        "shift": shift_name,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    }
                }
                
                await websocket.send_text(json.dumps(update_data))
                
            except Exception as e:
                print(f"Ошибка WebSocket: {e}")
                break
            
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)

@app.get("/api/stats")
async def get_stats_api(user=Depends(require_auth)):
    """API для получения статистики"""
    try:
        now = datetime.now()
        shift_name = "day_" + now.strftime("%Y-%m-%d") if 9 <= now.hour < 21 else "night_" + now.strftime("%Y-%m-%d")
        incoming, outgoing = get_shift_messages(shift_name)
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
            "chat_stats": {"active_chats": 0, "closed_chats": 0, "total_users": 0},
            "incoming_count": 0,
            "outgoing_count": 0,
            "total_messages": 0,
            "shift": "error",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

@app.get("/api/recent-messages")
async def get_recent_messages_api(user=Depends(require_auth)):
    """API для получения последних сообщений"""
    try:
        from db_handler import get_recent_messages
        messages = get_recent_messages(20)
        
        for msg in messages:
            msg['type'] = msg['message_type']
            
        return {"messages": messages}
    except Exception as e:
        print(f"Ошибка получения сообщений: {e}")
        return {"messages": []}

@app.get("/search")
async def search_messages(q: str = Query(...), user=Depends(require_auth)):
    """Поиск по сообщениям"""
    try:
        with sqlite3.connect("pulseai.db") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT username, message, timestamp, message_type, shift_name, chat_id
                FROM messages 
                WHERE message LIKE ? 
                ORDER BY timestamp DESC 
                LIMIT 100
            ''', (f"%{q}%",))
            
            results = [dict(row) for row in cursor.fetchall()]
        
        return {"results": results, "total": len(results)}
    except Exception as e:
        print(f"Ошибка поиска: {e}")
        return {"results": [], "total": 0}

@app.get("/export/csv")
async def export_csv(shift_name: str = Query(None), user=Depends(require_auth)):
    """Экспорт данных в CSV"""
    try:
        if not shift_name:
            shift_name = f"day_{datetime.now().strftime('%Y-%m-%d')}"
        
        incoming, outgoing = get_shift_messages(shift_name)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['Тип', 'Пользователь', 'Сообщение', 'Время', 'ID чата'])
        
        for msg in incoming:
            writer.writerow([
                'Входящее',
                msg.get('username', ''),
                msg.get('message', ''),
                msg.get('timestamp', ''),
                msg.get('chat_id', '')
            ])
        
        for msg in outgoing:
            writer.writerow([
                'Исходящее',
                msg.get('username', ''),
                msg.get('message', ''),
                msg.get('timestamp', ''),
                msg.get('chat_id', '')
            ])
        
        output.seek(0)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={shift_name}.csv"}
        )
    except Exception as e:
        print(f"Ошибка экспорта: {e}")
        return {"error": "Ошибка экспорта данных"}

@app.get("/health")
async def health_check():
    """Проверка работоспособности сервиса"""
    return {
        "status": "ok", 
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "websocket_connections": len(manager.active_connections)
    }