@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

echo ═══════════════════════════════════════════════
echo        🔬  Analitik Pro - Запуск
echo ═══════════════════════════════════════════════
echo.

REM --- Проверка Python ---
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Python не найден. Установите Python 3.10+ с https://www.python.org/downloads/
    pause
    exit /b 1
)

REM --- Создаём venv при первом запуске ---
if not exist ".venv" (
    echo 📦 Первый запуск: создаю виртуальное окружение...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo 📥 Устанавливаю зависимости...
    python -m pip install --upgrade pip >nul
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

echo.
echo 🚀 Запускаю Analitik Pro...
echo.

python app.py

if %errorlevel% neq 0 (
    echo.
    echo ❌ Приложение завершилось с ошибкой.
    pause
)
