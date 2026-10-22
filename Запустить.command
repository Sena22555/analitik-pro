#!/bin/bash
# ============================================================
# Запуск Analitik Pro (macOS / Linux)
# ============================================================

set -e

# Переходим в директорию скрипта (поддерживает запуск из Finder)
cd "$(dirname "$0")"

echo "═══════════════════════════════════════════════"
echo "       🔬  Analitik Pro - Запуск"
echo "═══════════════════════════════════════════════"
echo ""

# --- Проверяем Python ---
if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    echo "❌ Python не найден. Установите Python 3.10+ с https://www.python.org/downloads/"
    read -p "Нажмите Enter для выхода..."
    exit 1
fi

echo "✅ Python: $($PYTHON --version)"

# --- Создаём venv при первом запуске ---
if [ ! -d ".venv" ]; then
    echo ""
    echo "📦 Первый запуск: создаю виртуальное окружение..."
    $PYTHON -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    echo "📥 Устанавливаю зависимости (это может занять пару минут)..."
    pip install --upgrade pip >/dev/null
    pip install -r requirements.txt
    echo "✅ Окружение готово."
else
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

echo ""
echo "🚀 Запускаю Analitik Pro..."
echo ""

# --- Запуск ---
$PYTHON app.py

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Приложение завершилось с ошибкой (код $EXIT_CODE)."
    read -p "Нажмите Enter для выхода..."
fi
