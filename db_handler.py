import os
import json
from datetime import datetime, timedelta

LEARNING_DIR = "Learning"
CHATS_DIR = "Chats"
os.makedirs(LEARNING_DIR, exist_ok=True)
os.makedirs(CHATS_DIR, exist_ok=True)

CHAT_TIMEOUT_MINUTES = 5

def _get_file_path(shift_name):
    return os.path.join(LEARNING_DIR, f"{shift_name}.json")

def _get_chats_file():
    return os.path.join(CHATS_DIR, "active_chats.json")

def _load_active_chats():
    """Загружает активные чаты из файла"""
    chats_file = _get_chats_file()
    if os.path.exists(chats_file):
        try:
            with open(chats_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def _save_active_chats(chats_data):
    """Сохраняет активные чаты в файл"""
    chats_file = _get_chats_file()
    with open(chats_file, "w", encoding="utf-8") as f:
        json.dump(chats_data, f, ensure_ascii=False, indent=2)

def _is_chat_expired(last_activity_str):
    """Проверяет, истек ли чат (более 5 минут без активности)"""
    try:
        last_activity = datetime.fromisoformat(last_activity_str)
        return datetime.now() - last_activity > timedelta(minutes=CHAT_TIMEOUT_MINUTES)
    except:
        return True

def _get_or_create_chat_id(username):
    """Получает ID активного чата или создает новый"""
    chats_data = _load_active_chats()
    now = datetime.now().isoformat()
    
    if username in chats_data:
        chat_info = chats_data[username]
        # Проверяем, не истек ли чат
        if not _is_chat_expired(chat_info["last_activity"]):
            # Чат еще активен, обновляем время последней активности
            chat_info["last_activity"] = now
            _save_active_chats(chats_data)
            return chat_info["chat_id"]
        else:
            # Чат истек, создаем новый
            chat_info["chat_id"] += 1
    else:
        # Новый пользователь
        chats_data[username] = {"chat_id": 1}
    
    # Обновляем время активности и сохраняем
    chats_data[username]["last_activity"] = now
    _save_active_chats(chats_data)
    
    return chats_data[username]["chat_id"]

def get_chat_statistics():
    """Возвращает статистику по чатам"""
    chats_data = _load_active_chats()
    active_chats = 0
    closed_chats = 0
    
    for username, chat_info in chats_data.items():
        if _is_chat_expired(chat_info["last_activity"]):
            closed_chats += 1
        else:
            active_chats += 1
    
    return {
        "active_chats": active_chats,
        "closed_chats": closed_chats,
        "total_users": len(chats_data)
    }

def add_incoming(message, shift, username=None):
    path = _get_file_path(shift)
    chat_id = None
    if username:
        chat_id = _get_or_create_chat_id(username)
    _add_message(path, message, "incoming", username, chat_id)

def add_outgoing(message, shift, username=None):
    path = _get_file_path(shift)
    chat_id = None
    if username:
        # Для исходящих сообщений используем существующий chat_id
        chats_data = _load_active_chats()
        if username in chats_data and not _is_chat_expired(chats_data[username]["last_activity"]):
            chat_id = chats_data[username]["chat_id"]
            # Обновляем время активности
            chats_data[username]["last_activity"] = datetime.now().isoformat()
            _save_active_chats(chats_data)
    _add_message(path, message, "outgoing", username, chat_id)

def _add_message(path, message, key, username=None, chat_id=None):
    timestamp = datetime.now().isoformat()
    data = {"incoming": [], "outgoing": []}

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {"incoming": [], "outgoing": []}

    message_entry = {
        "message": message, 
        "timestamp": timestamp,
        "username": username,
        "chat_id": chat_id
    }
    
    data[key].append(message_entry)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_shift_messages(shift_name):
    """Возвращает сообщения смены в старом формате для совместимости"""
    path = _get_file_path(shift_name)
    if not os.path.exists(path):
        return [], []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("incoming", []), data.get("outgoing", [])

def get_detailed_chat_statistics():
    """Возвращает детальную статистику по чатам с именами пользователей"""
    chats_data = _load_active_chats()
    active_chats = []
    closed_chats = []
    
    print(f"DEBUG: Загружено чатов: {len(chats_data)}")
    
    for username, chat_info in chats_data.items():
        print(f"DEBUG: Пользователь {username}, последняя активность: {chat_info['last_activity']}")
        
        chat_entry = {
            "username": username,
            "chat_id": chat_info["chat_id"],
            "last_activity": chat_info["last_activity"]
        }
        
        if _is_chat_expired(chat_info["last_activity"]):
            closed_chats.append(chat_entry)
            print(f"DEBUG: {username} - закрытый чат")
        else:
            active_chats.append(chat_entry)
            print(f"DEBUG: {username} - активный чат")
    
    result = {
        "active_chats": len(active_chats),
        "closed_chats": len(closed_chats),
        "total_users": len(chats_data),
        "active_chat_list": active_chats,
        "closed_chat_list": closed_chats
    }
    
    print(f"DEBUG: Результат: {result}")
    return result
GREETINGS = [
    "Гарного дня😊", "Гарного дня!", "Гарного вечора!", "Гарного вечора😊",
    "Доброї ночі!", "Доброї ночі😊", "Будь ласка, Гарного дня😊", "Будь ласка, Гарного дня!",
    "Будь ласка, Гарного вечора!", "Будь ласка, Гарного вечора😊",
    "Будь ласка, Доброї ночі!", "Будь ласка, Доброї ночі😊"
]

def force_close_chat(username):
    """Принудительно закрывает чат пользователя"""
    chats_data = _load_active_chats()
    if username in chats_data:
        # Устанавливаем время активности на час назад, чтобы чат считался закрытым
        old_time = datetime.now() - timedelta(hours=1)
        chats_data[username]["last_activity"] = old_time.isoformat()
        _save_active_chats(chats_data)
        print(f"Чат с {username} принудительно закрыт")

def is_greeting_message(message):
    """Проверяет, является ли сообщение прощальным"""
    return message.strip() in GREETINGS