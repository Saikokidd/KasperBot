
#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ -f "bot.pid" ]; then
    PID=$(cat bot.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Бот работает${NC}"
        echo -e "📋 PID: $PID"
        echo -e "⏱️  Время работы: $(ps -p $PID -o etime= | tr -d ' ')"
        echo -e "💾 Память: $(ps -p $PID -o rss= | awk '{print $1/1024 " MB"}')"
    else
        echo -e "${RED}❌ Бот не работает (устаревший PID)${NC}"
        rm bot.pid
    fi
else
    echo -e "${RED}❌ Бот не запущен${NC}"
fi
