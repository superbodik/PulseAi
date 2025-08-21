from functools import wraps
from fastapi import HTTPException, Depends, Request, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import RedirectResponse
import secrets
from typing import Optional

# Простая система аутентификации
security = HTTPBasic(auto_error=False)

# Пользователи системы (в реальном проекте лучше использовать базу данных)
USERS = {
    "admin": {
        "password": "pulse2024",
        "role": "admin",
        "username": "Administrator"
    },
    "operator": {
        "password": "support123",
        "role": "operator", 
        "username": "Support Operator"
    },
    "viewer": {
        "password": "view123",
        "role": "viewer",
        "username": "Viewer"
    }
}

def get_current_user(credentials: Optional[HTTPBasicCredentials] = Depends(security)):
    """Получает текущего пользователя без принудительной аутентификации"""
    if not credentials:
        return None
    
    username = credentials.username
    password = credentials.password
    
    if username not in USERS:
        return None
    
    user_data = USERS[username]
    is_correct_password = secrets.compare_digest(password, user_data["password"])
    
    if not is_correct_password:
        return None
    
    return {
        "username": username,
        "display_name": user_data["username"],
        "role": user_data["role"]
    }

def authenticate_user(credentials: Optional[HTTPBasicCredentials] = Depends(security)):
    """Базовая аутентификация пользователя с принудительным входом"""
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Требуется аутентификация",
            headers={"WWW-Authenticate": "Basic realm='PulseAi Support'"},
        )
    
    user = get_current_user(credentials)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Basic realm='PulseAi Support'"},
        )
    
    return user

def check_admin_role(user=Depends(authenticate_user)):
    """Проверяет права администратора"""
    if user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Недостаточно прав доступа"
        )
    return user

def check_operator_role(user=Depends(authenticate_user)):
    """Проверяет права оператора или выше"""
    if user["role"] not in ["admin", "operator"]:
        raise HTTPException(
            status_code=403,
            detail="Недостаточно прав доступа"
        )
    return user