
#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ ! -f "bot.pid" ]; then
    echo -e "${RED}❌ PID файл не найден. Бот не запущен?${NC}"
    exit 1
fi

PID=$(cat bot.pid)

if ps -p $PID > /dev/null 2>&1; then
    echo -e "${YELLOW}⏹️  Остановка бота (PID: $PID)...${NC}"
    kill $PID
    rm bot.pid
    echo -e "${GREEN}✅ Бот остановлен${NC}"
else
    echo -e "${RED}❌ Процесс не найден (устаревший PID)${NC}"
    rm bot.pid
fi
