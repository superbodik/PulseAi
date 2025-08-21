import sqlite3
import os
from datetime import datetime, timedelta
from contextlib import contextmanager
import json


DB_PATH = "pulseai.db"
DB_FILE = "filetets.db"

CHAT_TIMEOUT_MINUTES = 5

# Фильтры
EXCLUDED_USERS = [
    'news_chrkssy',
    'GmailBot',
    'NewsChannel',
    'AutoBot',
    'news_updates'
    'kpszsu'

]

EXCLUDED_KEYWORDS = [
    '✉️ PULSE <admin@rideatom.com>',
    'Alert! Subaccount:',
    'Vehicle number',
    'moving!',
    'no-go zone',
    'Група ворожих БпЛА',
    'Ударні БпЛА',
    'шахедів',
    'курсом на'
    'Пуски '
    'ворожий розвідувальний  '
    'Загроза застосування  '
]

GREETINGS = [
    "Гарного дня😊", "Гарного дня!", "Гарного вечора!", "Гарного вечора😊",
    "Доброї ночі!", "Доброї ночі😊", "Будь ласка, Гарного дня😊", "Будь ласка, Гарного дня!",
    "Будь ласка, Гарного вечора!", "Будь ласка, Гарного вечора😊",
    "Будь ласка, Доброї ночі!", "Будь ласка, Доброї ночі😊"
]

def init_database():
    """Создает таблицы базы данных"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Таблица сообщений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                message TEXT,
                timestamp TEXT,
                message_type TEXT,
                shift_name TEXT,
                chat_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица активных чатов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_chats (
                username TEXT PRIMARY KEY,
                chat_id INTEGER,
                last_activity TEXT
            )
        ''')
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
        conn.commit()
        
        # Создаем индексы для быстрого поиска
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_username ON messages(username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_shift ON messages(shift_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_type ON messages(message_type)')
        
        conn.commit()

@contextmanager
def get_db_connection():
    """Контекстный менеджер для работы с БД"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def load_filters_config():
    """Загружает конфигурацию фильтров из файла"""
    try:
        with open("filters_config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
            global EXCLUDED_USERS, EXCLUDED_KEYWORDS
            EXCLUDED_USERS = config.get("excluded_users", EXCLUDED_USERS)
            EXCLUDED_KEYWORDS = config.get("excluded_keywords", EXCLUDED_KEYWORDS)
    except FileNotFoundError:
        pass

def save_filters_config():
    """Сохраняет конфигурацию фильтров в файл"""
    config = {
        "excluded_users": EXCLUDED_USERS,
        "excluded_keywords": EXCLUDED_KEYWORDS
    }
    with open("filters_config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def should_exclude_message(username, message):
    """Проверяет фильтры"""
    if username in EXCLUDED_USERS:
        return True
    
    for keyword in EXCLUDED_KEYWORDS:
        if keyword in message:
            return True
    
    if message.startswith(('✉️', '🛵', '❗️')):
        return True
    
    if len(message) > 1500:
        return True
    
    return False

def is_greeting_message(message):
    """Проверяет, является ли сообщение прощальным"""
    return message.strip() in GREETINGS

def force_close_chat(username):
    """Принудительно закрывает чат пользователя"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        old_time = (datetime.now() - timedelta(hours=1)).isoformat()
        cursor.execute('UPDATE active_chats SET last_activity = ? WHERE username = ?',
                     (old_time, username))
        conn.commit()
        print(f"Чат с {username} принудительно закрыт")

def add_incoming(message, shift, username=None):
    if should_exclude_message(username or 'unknown', message):
        print(f"Сообщение от {username} отфильтровано")
        return
    
    chat_id = get_or_create_chat_id(username) if username else None
    add_message(message, shift, username, 'incoming', chat_id)

def add_outgoing(message, shift, username=None):
    if should_exclude_message(username or 'unknown', message):
        print(f"Исходящее для {username} отфильтровано")
        return
    
    chat_id = get_or_create_chat_id(username) if username else None
    add_message(message, shift, username, 'outgoing', chat_id)

def add_message(message, shift, username, message_type, chat_id):
    """Добавляет сообщение в БД"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (username, message, timestamp, message_type, shift_name, chat_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, message, datetime.now().isoformat(), message_type, shift, chat_id))
        conn.commit()

def get_or_create_chat_id(username):
    """Получает или создает ID чата"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('SELECT chat_id, last_activity FROM active_chats WHERE username = ?', (username,))
        row = cursor.fetchone()
        
        if row:
            last_activity = datetime.fromisoformat(row['last_activity'])
            if datetime.now() - last_activity < timedelta(minutes=CHAT_TIMEOUT_MINUTES):
                cursor.execute('UPDATE active_chats SET last_activity = ? WHERE username = ?',
                             (datetime.now().isoformat(), username))
                conn.commit()
                return row['chat_id']
            else:
                new_chat_id = row['chat_id'] + 1
                cursor.execute('UPDATE active_chats SET chat_id = ?, last_activity = ? WHERE username = ?',
                             (new_chat_id, datetime.now().isoformat(), username))
                conn.commit()
                return new_chat_id
        else:
            cursor.execute('INSERT INTO active_chats (username, chat_id, last_activity) VALUES (?, 1, ?)',
                         (username, datetime.now().isoformat()))
            conn.commit()
            return 1

def get_chat_statistics():
    """Возвращает статистику чатов"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) as total FROM active_chats')
        total = cursor.fetchone()['total']
        
        cutoff = (datetime.now() - timedelta(minutes=CHAT_TIMEOUT_MINUTES)).isoformat()
        cursor.execute('SELECT COUNT(*) as active FROM active_chats WHERE last_activity > ?', (cutoff,))
        active = cursor.fetchone()['active']
        
        return {
            "active_chats": active,
            "closed_chats": total - active,
            "total_users": total
        }

def get_detailed_chat_statistics():
    """Возвращает детальную статистику чатов"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(minutes=CHAT_TIMEOUT_MINUTES)).isoformat()
        
        cursor.execute('SELECT username, chat_id, last_activity FROM active_chats WHERE last_activity > ? ORDER BY last_activity DESC', (cutoff,))
        active_chats = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute('SELECT username, chat_id, last_activity FROM active_chats WHERE last_activity <= ? ORDER BY last_activity DESC', (cutoff,))
        closed_chats = [dict(row) for row in cursor.fetchall()]
        
        return {
            "active_chats": len(active_chats),
            "closed_chats": len(closed_chats),
            "total_users": len(active_chats) + len(closed_chats),
            "active_chat_list": active_chats,
            "closed_chat_list": closed_chats
        }

def get_shift_messages(shift_name):
    """Получает сообщения смены"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT username, message, timestamp, chat_id 
            FROM messages 
            WHERE shift_name = ? AND message_type = 'incoming'
            ORDER BY timestamp DESC
        ''', (shift_name,))
        incoming = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute('''
            SELECT username, message, timestamp, chat_id 
            FROM messages 
            WHERE shift_name = ? AND message_type = 'outgoing'
            ORDER BY timestamp DESC
        ''', (shift_name,))
        outgoing = [dict(row) for row in cursor.fetchall()]
        
        return incoming, outgoing

def get_recent_messages(limit=50):
    """Получает последние сообщения для главной страницы"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT username, message, timestamp, message_type, chat_id
            FROM messages 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]

def cleanup_old_messages(days=30):
    """Удаляет старые сообщения (старше N дней)"""
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM messages WHERE timestamp < ?', (cutoff_date,))
        deleted = cursor.rowcount
        conn.commit()
        print(f"Удалено {deleted} старых сообщений")

def add_user(username: str, email: str):
    """Добавить пользователя"""
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO users (username, email) VALUES (?, ?)", (username, email))
        conn.commit()


def get_users():
    """Получить всех пользователей"""
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, username, email FROM users")
        return cur.fetchall()


def add_message(user, message, chat_id=None, timestamp=None, extra=None):
    """Добавить сообщение"""
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO messages (user_id, content) VALUES (?, ?)", (user, message))
        conn.commit()


def get_messages(limit: int = 50):
    """Получить последние сообщения"""
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT m.id, u.username, m.content, m.created_at
            FROM messages m
            JOIN users u ON m.user_id = u.id
            ORDER BY m.created_at DESC
            LIMIT ?
        """, (limit,))
        return cur.fetchall()

# Инициализируем БД при импорте
init_database()

load_filters_config()
