import os
import sys

try:
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession
    print("Telethon импортирован успешно")
except ImportError as e:
    print("Ошибка импорта Telethon!")
    exit(1)

from db_handler import add_incoming, add_outgoing
from datetime import datetime
import asyncio

api_id = 20971051
api_hash = '24e5cd5f0fd8c083cdb49f2bc7f46992'
session_file = 'session_string.txt'

try:
    if os.path.exists(session_file):
        print("Загружаем сохраненную сессию...")
        with open(session_file, 'r') as f:
            session_string = f.read().strip()
        client = TelegramClient(StringSession(session_string), api_id, api_hash)
    else:
        print("Создаем новую сессию...")
        client = TelegramClient(StringSession(), api_id, api_hash)
    print("Telegram клиент создан")
except Exception as e:
    print(f"Ошибка создания клиента: {e}")
    exit(1)

def get_shift_name(timestamp):
    hour = timestamp.hour
    date_str = timestamp.strftime("%Y-%m-%d")
    if 9 <= hour < 21:
        return f"day_{date_str}"
    else:
        return f"night_{date_str}"

async def start_listener_async():
    print("Запуск Telegram слушателя...")

    @client.on(events.NewMessage(incoming=True))
    async def handle_incoming(event):
        try:
            sender = await event.get_sender()
            username = sender.username or sender.first_name or f"user_{sender.id}"
            message = event.message.message or ""
            
            print(f"[ВХОДЯЩЕЕ] {username}: {message[:50]}...")
            add_incoming(message, get_shift_name(datetime.now()), username)
            
        except Exception as e:
            print(f"Ошибка обработки входящего: {e}")

    @client.on(events.NewMessage(outgoing=True))
    async def handle_outgoing(event):
        try:
            chat = await event.get_chat()
            username = getattr(chat, 'username', None) or getattr(chat, 'first_name', None) or f"user_{chat.id}"
            message = event.message.message or ""
            
            print(f"[ИСХОДЯЩЕЕ] для {username}: {message[:50]}...")
            add_outgoing(message, get_shift_name(datetime.now()), username)
            
            # Проверяем, является ли сообщение прощальным
            from db_handler import is_greeting_message, force_close_chat
            if is_greeting_message(message):
                force_close_chat(username)
                print(f"Чат с {username} автоматически закрыт (прощальное сообщение)")
            
        except Exception as e:
            print(f"Ошибка обработки исходящего: {e}")

    try:
        print("Подключение к Telegram...")
        await client.start()
        print("Telegram слушатель успешно запущен!")
        await client.run_until_disconnected()
        
    except Exception as e:
        print(f"Ошибка запуска: {e}")
        raise

def start_listener():
    try:
        asyncio.run(start_listener_async())
    except KeyboardInterrupt:
        print("Telegram слушатель остановлен")
    except Exception as e:
        print(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    start_listener()