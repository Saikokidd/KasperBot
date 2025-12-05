#!/bin/bash

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Переходим в директорию бота
cd "$(dirname "$0")"

echo -e "${GREEN}🚀 Запуск Error Bot в фоновом режиме...${NC}\n"

# Проверка venv
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}📦 Создаём venv...${NC}"
    python3 -m venv venv
fi

# Активация venv (ВАЖНО: локальный путь!)
source venv/bin/activate

# Проверка зависимостей
if ! python -c "import telegram" 2>/dev/null; then
    echo -e "${YELLOW}📦 Установка зависимостей...${NC}"
    pip install -r requirements.txt
fi

# Проверка .env
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Файл .env не найден!${NC}"
    exit 1
fi

# Проверка, не запущен ли уже бот
if [ -f "bot.pid" ]; then
    OLD_PID=$(cat bot.pid)
    if ps -p $OLD_PID > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Бот уже запущен (PID: $OLD_PID)${NC}"
        echo "Используйте ./stop.sh для остановки"
        exit 1
    else
        rm bot.pid
    fi
fi

# Запуск в фоне (используем python из ЛОКАЛЬНОГО venv!)
nohup ./venv/bin/python main.py > output.log 2>&1 &
echo $! > bot.pid

echo -e "${GREEN}✅ Бот запущен в фоне!${NC}"
echo -e "📋 PID: $(cat bot.pid)"
echo -e "📄 Логи: tail -f output.log"
echo -e "⏹️  Остановить: ./stop.sh"
