#!/bin/bash
echo "🔄 Перезапуск бота..."
sudo systemctl restart error_bot
sleep 2
sudo systemctl status error_bot --no-pager
