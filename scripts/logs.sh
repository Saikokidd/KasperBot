
#!/bin/bash

YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}📋 Логи бота (Ctrl+C для выхода):${NC}\n"
tail -f output.log
