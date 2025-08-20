import os
import glob
import time

def cleanup_telegram_sessions():
    """Очищает заблокированные файлы сессий Telegram"""
    
    print("🧹 Очистка файлов сессий Telegram...")
    
    # Список файлов сессий для удаления
    session_files = [
        'session_name.session',
        'session_name.session-journal',
        'session_name.session-wal',
        'session_name.session-shm'
    ]
    
    deleted_files = []
    
    for file_path in session_files:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                deleted_files.append(file_path)
                print(f"✅ Удален: {file_path}")
            except Exception as e:
                print(f"❌ Не удалось удалить {file_path}: {e}")
    
    # Также удаляем все .session файлы в текущей директории
    session_pattern = "*.session*"
    for file_path in glob.glob(session_pattern):
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                deleted_files.append(file_path)
                print(f"✅ Удален: {file_path}")
            except Exception as e:
                print(f"❌ Не удалось удалить {file_path}: {e}")
    
    if deleted_files:
        print(f"\n🎉 Очистка завершена! Удалено файлов: {len(deleted_files)}")
        print("📝 При следующем запуске потребуется повторная авторизация в Telegram")
    else:
        print("\n✨ Файлы сессий не найдены или уже очищены")
    
    return len(deleted_files)

def kill_python_processes():
    """Пытается завершить зависшие Python процессы (только для Windows)"""
    import platform
    
    if platform.system() == "Windows":
        print("\n🔄 Попытка завершения зависших Python процессов...")
        try:
            import subprocess
            # Завершаем процессы python.exe кроме текущего
            result = subprocess.run(['taskkill', '/f', '/im', 'python.exe'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Процессы завершены")
            else:
                print("ℹ️ Процессы не найдены или уже завершены")
        except Exception as e:
            print(f"❌ Ошибка завершения процессов: {e}")

if __name__ == "__main__":
    print("🚨 ВНИМАНИЕ: Этот скрипт удалит все файлы сессий Telegram!")
    print("После очистки потребуется повторная авторизация.")
    
    choice = input("\nПродолжить? (y/N): ").lower().strip()
    
    if choice in ['y', 'yes', 'да', 'д']:
        # Сначала пытаемся завершить процессы
        kill_python_processes()
        
        # Ждем немного
        time.sleep(2)
        
        # Очищаем сессии
        deleted_count = cleanup_telegram_sessions()
        
        if deleted_count > 0:
            print("\n🚀 Теперь можете запустить приложение заново:")
            print("python main.py")
        else:
            print("\n🤔 Возможно проблема в другом. Попробуйте перезагрузить компьютер.")
    else:
        print("❌ Очистка отменена")