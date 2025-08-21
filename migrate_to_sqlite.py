import json
import os
import sqlite3
from datetime import datetime
from db_handler import init_database, add_message

def migrate_json_to_sqlite():
    """Переносит данные из JSON файлов в SQLite"""
    print("Начинаем миграцию данных из JSON в SQLite...")
    
    init_database()
    total_messages = 0
    
    learning_dir = "Learning"
    if not os.path.exists(learning_dir):
        print("Папка Learning не найдена")
        return
    
    for filename in os.listdir(learning_dir):
        if filename.endswith('.json'):
            print(f"Обрабатываем файл: {filename}")
            shift_name = filename[:-5]  # убираем .json
            
            filepath = os.path.join(learning_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Переносим входящие сообщения
                for msg in data.get('incoming', []):
                    add_message(
                        message=msg.get('message', ''),
                        shift=shift_name,
                        username=msg.get('username'),
                        message_type='incoming',
                        chat_id=msg.get('chat_id')
                    )
                    total_messages += 1
                
                # Переносим исходящие сообщения
                for msg in data.get('outgoing', []):
                    add_message(
                        message=msg.get('message', ''),
                        shift=shift_name,
                        username=msg.get('username'),
                        message_type='outgoing',
                        chat_id=msg.get('chat_id')
                    )
                    total_messages += 1
                    
            except Exception as e:
                print(f"Ошибка обработки файла {filename}: {e}")
    
    print(f"Миграция завершена. Перенесено сообщений: {total_messages}")
    
    # Создаем резервную копию JSON файлов
    backup_dir = "Learning_backup"
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        print(f"Создана резервная копия в {backup_dir}")

if __name__ == "__main__":
    migrate_json_to_sqlite()