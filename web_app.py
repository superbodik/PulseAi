from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException, Form, Cookie
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from fastapi.templating import Jinja2Templates
from db_handler import get_shift_messages, get_chat_statistics, get_detailed_chat_statistics
from datetime import datetime
import json
import asyncio
from typing import List, Optional
import sqlite3
import csv
import io
import secrets
import base64
from io import BytesIO

app = FastAPI()
templates = Jinja2Templates(directory="templates")

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
    # Если уже на странице логина, не перенаправляем
    if str(request.url).endswith("/login"):
        return templates.TemplateResponse("login.html", {"request": request})
    return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Страница входа"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    """Обработка входа"""
    print(f"Попытка входа: {username}")  # Для отладки
    
    user = verify_user(username, password)
    if user:
        # Создаем сессию
        session_token = create_session_token()
        active_sessions[session_token] = user
        
        print(f"Вход успешен для {username}, токен: {session_token[:10]}...")  # Для отладки
        
        # Перенаправляем на главную с установкой cookie
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key="session_token", 
            value=session_token, 
            httponly=True,
            max_age=86400  # 24 часа
        )
        return response
    else:
        print(f"Неверные данные для {username}")  # Для отладки
        # Неверные данные - показываем ошибку
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
def dashboard(request: Request, user=Depends(require_auth)):
    """Главная страница дашборда"""
    try:
        now = datetime.now()
        shift_name = "day_" + now.strftime("%Y-%m-%d") if 9 <= now.hour < 21 else "night_" + now.strftime("%Y-%m-%d")
        incoming, outgoing = get_shift_messages(shift_name)
        chat_stats = get_detailed_chat_statistics()
        
        # Получаем последние 20 сообщений для быстрого просмотра
        recent_messages = []
        for msg in (incoming + outgoing)[-20:]:
            msg['type'] = 'incoming' if msg in incoming else 'outgoing'
            recent_messages.append(msg)
        recent_messages.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request, 
            "incoming": incoming[:10],  # Показываем только последние 10
            "outgoing": outgoing[:10],
            "recent_messages": recent_messages[:20],
            "shift": shift_name,
            "chat_stats": chat_stats,
            "user": user
        })
    except Exception as e:
        print(f"Ошибка загрузки дашборда: {e}")
        # В случае ошибки перенаправляем на страницу входа
        return RedirectResponse(url="/login")

@app.get("/shift/{shift_name}", response_class=HTMLResponse)
def view_shift(request: Request, shift_name: str, user=Depends(require_auth)):
    """Просмотр конкретной смены"""
    try:
        incoming, outgoing = get_shift_messages(shift_name)
        chat_stats = get_detailed_chat_statistics()
        
        return templates.TemplateResponse("shift.html", {
            "request": request, 
            "incoming": incoming, 
            "outgoing": outgoing, 
            "shift": shift_name,
            "chat_stats": chat_stats,
            "user": user
        })
    except Exception as e:
        print(f"Ошибка загрузки смены: {e}")
        return RedirectResponse(url="/login")

@app.get("/stats", response_class=HTMLResponse)
def chat_statistics(request: Request, user=Depends(require_auth)):
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

@app.get("/search")
def search_messages(q: str = Query(...), user=Depends(require_auth)):
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
def export_csv(shift_name: str = Query(None), user=Depends(require_auth)):
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

@app.get("/filters", response_class=HTMLResponse)
def filters_page(request: Request, user=Depends(require_admin)):
    """Страница настройки фильтров (только для админов)"""
    try:
        return templates.TemplateResponse("filters.html", {
            "request": request,
            "user": user
        })
    except Exception as e:
        # вместо print передаём в шаблон
        return templates.TemplateResponse("filters.html", {
            "request": request,
            "user": user,
            "error_message": f"Ошибка загрузки фильтров: {e}"
        })

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

# Добавляем новые маршруты после существующих

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request, user=Depends(require_auth)):
    """Страница аналитики"""
    try:
        return templates.TemplateResponse("analytics.html", {
            "request": request,
            "user": user
        })
    except HTTPException as e:
        if e.status_code == 401:  # Не авторизован
            return RedirectResponse(url="/login")
        raise
    except Exception as e:
        # Передаём ошибку прямо в шаблон
        return templates.TemplateResponse("analytics.html", {
            "request": request,
            "user": user,
            "error_message": f"Ошибка загрузки аналитики: {e}"
        })

@app.get("/api/analytics")
async def get_analytics_api(user=Depends(require_auth)):
    """API для получения данных аналитики"""
    try:
        # Здесь можно добавить реальные данные из БД
        return {
            "total_messages": 247,
            "avg_response_time": "2.3 хв", 
            "active_operators": 3,
            "satisfaction_rate": "94%"
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/chat/{username}", response_class=HTMLResponse)
async def chat_detail(request: Request, username: str, user=Depends(require_auth)):
    """Детальный просмотр чата пользователя"""
    try:
        with sqlite3.connect("pulseai.db") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Получаем все сообщения пользователя
            cursor.execute('''
                SELECT message, timestamp, message_type, chat_id
                FROM messages 
                WHERE username = ? 
                ORDER BY timestamp ASC
            ''', (username,))
            
            raw_messages = cursor.fetchall()
            messages = []
            
            for msg in raw_messages:
                messages.append({
                    'message': msg['message'],
                    'timestamp': msg['timestamp'],
                    'type': msg['message_type'],
                    'chat_id': msg['chat_id']
                })
            
            # Определяем статус чата
            if messages:
                last_message_time = datetime.fromisoformat(messages[-1]['timestamp']) if messages[-1]['timestamp'] else datetime.now()
                time_diff = datetime.now() - last_message_time
                chat_status = "Активний" if time_diff.total_seconds() < 300 else "Закритий"
            else:
                chat_status = "Порожній"
            
            incoming_count = sum(1 for msg in messages if msg['type'] == 'incoming')
            outgoing_count = sum(1 for msg in messages if msg['type'] == 'outgoing')
            
            return templates.TemplateResponse("chat_detail.html", {
                "request": request,
                "user": user,
                "username": username,
                "messages": messages,
                "chat_id": messages[-1]['chat_id'] if messages else 1,
                "chat_status": chat_status,
                "incoming_count": incoming_count,
                "outgoing_count": outgoing_count
            })
            
    except Exception as e:
        print(f"Ошибка загрузки чата: {e}")
        return RedirectResponse(url="/")

@app.websocket("/ws/chat/{username}")
async def chat_websocket(websocket: WebSocket, username: str):
    """WebSocket для обновлений конкретного чата"""
    await websocket.accept()
    try:
        while True:
            await asyncio.sleep(5)
            # Здесь можно отправлять обновления для конкретного чата
            await websocket.send_text(json.dumps({
                "type": "ping",
                "timestamp": datetime.now().isoformat()
            }))
    except WebSocketDisconnect:
        pass

@app.get("/api/recent-messages")
async def get_recent_messages_api(user=Depends(require_auth)):
    """API для получения последних сообщений"""
    try:
        from db_handler import get_recent_messages
        messages = get_recent_messages(20)
        
        # Добавляем тип сообщения
        for msg in messages:
            msg['type'] = msg['message_type']
            
        return {"messages": messages}
    except Exception as e:
        print(f"Ошибка получения сообщений: {e}")
        return {"messages": []}

@app.get("/favicon.ico")
async def favicon_advanced():
    """Продвинутый favicon с PNG в base64"""
    from datetime import datetime
    
    now = datetime.now()
    is_day_shift = 9 <= now.hour < 21
    
    if is_day_shift:
        # Дневной favicon (оранжевая молния) - PNG в base64
        favicon_data = """
        iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAABHNCSVQICAgIfAhkiAAAAAlwSFlz
        AAAOxAAADsQBlSsOGwAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAAO1SURB
        VFiFtZdLbBRVEIafru6Z7pm3w8wCGRYSHgGCBBJCQoQEYsKCGF0YNy5M3LnQhStXJu5cuHDhyo0L
        E1eu3Bg3JkaNiRETH1ETH4nGaIwxRqNRY4xGo9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPR
        aDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9Fo
        NBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0
        Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQa
        jUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqN
        RqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1G
        o9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj
        0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPR
        aDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0WiwEAAAAAAS
        UVORK5CYII=
        """
    else:
        # Ночной favicon (синяя молния) - PNG в base64
        favicon_data = """
        iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAABHNCSVQICAgIfAhkiAAAAAlwSFlz
        AAAOxAAADsQBlSsOGwAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAAO1SURF
        iFtZdLbBRVEIafru6Z7pm3w8wCGRYSHgGCBBJCQoQEYsKCGF0YNy5M3LnQhStXJu5cuHDhyo0L
        E1eu3Bg3JkaNiRETH1ETH4nGaIwxRqNRY4xGo9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPR
        aDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9Fo
        NBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0
        Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQa
        jUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqN
        RqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1G
        o9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj
        0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPR
        aDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0Wg0Go1Go9FoNBqNRqPRaDQajUaj0WiwEAAAAAAS
        UVORK5CYII=
        """
    
    # Декодируем base64 в байты
    try:
        favicon_bytes = base64.b64decode(favicon_data.strip())
        return Response(
            content=favicon_bytes,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=3600",  # Кэшируем на час
                "Content-Disposition": "inline; filename=favicon.ico"
            }
        )
    except Exception as e:
        print(f"Ошибка favicon: {e}")
        return Response(status_code=204)
    
@app.post("/add_user")
async def add_user(username: str = Form(...), email: str = Form(...)):
    """Добавить пользователя"""
    db_handler.add_user(username, email)
    return RedirectResponse(url="/", status_code=303)


@app.post("/add_message")
async def add_message(user_id: int = Form(...), content: str = Form(...)):
    """Добавить сообщение"""
    db_handler.add_message(user_id, content)
    return RedirectResponse(url="/", status_code=303)