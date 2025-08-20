import os
import sys
import asyncio

try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
except ImportError:
    print("Ошибка импорта Telethon!")
    print("Установите Telethon: pip install telethon")
    sys.exit(1)

api_id = 20971051
api_hash = '24e5cd5f0fd8c083cdb49f2bc7f46992'
session_file = 'session_string.txt'

async def authorize_telegram():
    print("АВТОРИЗАЦИЯ В TELEGRAM API")
    print("="*50)
    
    # Проверяем существующую сессию
    if os.path.exists(session_file):
        print("Найдена существующая сессия...")
        with open(session_file, 'r') as f:
            session_string = f.read().strip()
        
        client = TelegramClient(StringSession(session_string), api_id, api_hash)
        try:
            await client.start()
            me = await client.get_me()
            print(f"Авторизация уже выполнена!")
            print(f"Пользователь: {me.first_name} {me.last_name or ''}")
            print(f"Телефон: {me.phone}")
            await client.disconnect()
            return True
        except:
            print("Существующая сессия недействительна, создаем новую...")
            os.remove(session_file)
    
    # Создаем новую сессию
    print("Создание новой сессии...")
    client = TelegramClient(StringSession(), api_id, api_hash)
    
    try:
        await client.start()
        me = await client.get_me()
        
        print("\\nАВТОРИЗАЦИЯ УСПЕШНА!")
        print("="*30)
        print(f"Имя: {me.first_name} {me.last_name or ''}")
        print(f"Телефон: {me.phone}")
        print(f"ID: {me.id}")
        
        # Сохраняем сессию
        session_string = client.session.save()
        with open(session_file, 'w') as f:
            f.write(session_string)
        
        print(f"\\nСессия сохранена в {session_file}")
        print("Теперь можете запускать: python main.py")
        
        await client.disconnect()
        return True
        
    except Exception as e:
        print(f"Ошибка авторизации: {e}")
        await client.disconnect()
        return False

def main():
    print("Настройка подключения к Telegram API")
    print("Вам нужно будет ввести номер телефона и код подтверждения")
    
    choice = input("\\nНачать авторизацию? (y/N): ").lower().strip()
    if choice not in ['y', 'yes', 'да', 'д']:
        print("Авторизация отменена")
        return
    
    try:
        success = asyncio.run(authorize_telegram())
        if success:
            print("\\nНастройка завершена!")
            print("Запустите основное приложение: python main.py")
        else:
            print("\\nАвторизация не удалась")
            
    except Exception as e:
        print(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    main()
    input("\\nНажмите Enter для выхода...")