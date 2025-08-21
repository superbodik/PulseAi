import multiprocessing
import os
import time
import signal
import sys
from telegram_listener import start_listener
import uvicorn

def run_listener():
    """Запускает Telegram слушатель"""
    try:
        print("Запуск Telegram слушателя...")
        start_listener()
    except KeyboardInterrupt:
        print("Telegram слушатель остановлен пользователем")
    except Exception as e:
        print(f"Ошибка Telegram слушателя: {e}")

def run_web():
    """Запускает веб-сервер"""
    try:
        print("Запуск веб-сервера...")
        uvicorn.run("web_app:app", host="127.0.0.1", port=8000, reload=False, log_level="info")
    except KeyboardInterrupt:
        print("Веб-сервер остановлен пользователем")
    except Exception as e:
        print(f"Ошибка веб-сервера: {e}")

def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    print("\\nПолучен сигнал завершения. Останавливаем процессы...")
    sys.exit(0)

def check_dependencies():
    """Проверяет наличие необходимых зависимостей"""
    required_modules = ['telethon', 'fastapi', 'uvicorn', 'jinja2']
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print("Отсутствуют необходимые модули:")
        for module in missing_modules:
            print(f"   - {module}")
        print("\\nУстановите их командой:")
        print("pip install telethon fastapi uvicorn jinja2")
        return False
    
    return True

def main():
    """Главная функция запуска приложения"""
    print("="*50)
    print("Запуск PulseAi Support System")
    print("="*50)
    
    # Проверяем зависимости
    if not check_dependencies():
        input("\\nНажмите Enter для выхода...")
        return
    
    # Устанавливаем обработчик сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Создаем необходимые директории
    os.makedirs("Learning", exist_ok=True)
    os.makedirs("Chats", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    
    print("Директории созданы")
    print("Запуск компонентов...")
    
    # Запускаем процессы
    processes = []
    
    try:
        # Процесс для Telegram слушателя
        p1 = multiprocessing.Process(target=run_listener, name="TelegramListener")
        p1.start()
        processes.append(p1)
        print(f"Telegram слушатель запущен (PID: {p1.pid})")
        
        # Небольшая задержка между запусками
        time.sleep(2)
        
        # Процесс для веб-сервера
        p2 = multiprocessing.Process(target=run_web, name="WebServer")
        p2.start()
        processes.append(p2)
        print(f"Веб-сервер запущен (PID: {p2.pid})")
        
        print("\\n" + "="*50)
        print("PulseAi Support System запущен!")
        print("Веб-интерфейс: http://127.0.0.1:8000")
        print("Статистика: http://127.0.0.1:8000/stats")
        print("Нажмите Ctrl+C для остановки")
        print("="*50)
        
        # Ожидаем завершения процессов
        for process in processes:
            process.join()
            
    except KeyboardInterrupt:
        print("\\nПолучен сигнал остановки...")
        
    except Exception as e:
        print(f"\\nКритическая ошибка: {e}")
        
    finally:
        # Завершаем все процессы
        print("Завершение процессов...")
        for process in processes:
            if process.is_alive():
                print(f"   Останавливаем {process.name}...")
                process.terminate()
                process.join(timeout=5)
                
                if process.is_alive():
                    print(f"   Принудительно завершаем {process.name}...")
                    process.kill()
                    process.join()
        
        print("Все процессы завершены")
        print("PulseAi Support System остановлен")

if __name__ == "__main__":
    # Поддержка для Windows multiprocessing
    multiprocessing.freeze_support()
    
    try:
        main()
    except Exception as e:
        print(f"\\nНеожиданная ошибка: {e}")
        print("Попробуйте:")
        print("   1. Перезагрузить компьютер")
        print("   2. Переустановить зависимости: pip install telethon fastapi uvicorn jinja2")
        
    input("\\nНажмите Enter для выхода...")