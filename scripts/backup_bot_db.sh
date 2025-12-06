#!/bin/bash
#
# Скрипт автоматического бэкапа базы данных бота
# Использование: ./backup_bot_db.sh
#

# ===== НАСТРОЙКИ =====
BOT_DIR="/root/projects/error_bot"
BACKUP_DIR="/root/backups/error_bot"
DB_FILE="$BOT_DIR/bot_data.db"
LOG_FILE="/var/log/bot_backup.log"
DAYS_TO_KEEP=30  # Сколько дней хранить старые бэкапы

# ===== ФУНКЦИИ =====
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# ===== ПРОВЕРКИ =====
if [ ! -f "$DB_FILE" ]; then
    log "❌ ОШИБКА: Файл БД не найден: $DB_FILE"
    exit 1
fi

if [ ! -d "$BACKUP_DIR" ]; then
    log "📁 Создаю директорию для бэкапов: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
fi

# ===== СОЗДАНИЕ БЭКАПА =====
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/bot_data_$DATE.db"

log "🔄 Начало бэкапа..."

# Копируем БД
cp "$DB_FILE" "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    # Получаем размер файла
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "✅ Бэкап создан успешно: bot_data_$DATE.db ($SIZE)"
    
    # Сжимаем для экономии места
    gzip "$BACKUP_FILE"
    if [ $? -eq 0 ]; then
        COMPRESSED_SIZE=$(du -h "$BACKUP_FILE.gz" | cut -f1)
        log "📦 Файл сжат: bot_data_$DATE.db.gz ($COMPRESSED_SIZE)"
    fi
else
    log "❌ ОШИБКА: Не удалось создать бэкап!"
    exit 1
fi

# ===== ОЧИСТКА СТАРЫХ БЭКАПОВ =====
log "🗑️  Удаление бэкапов старше $DAYS_TO_KEEP дней..."

DELETED_COUNT=$(find "$BACKUP_DIR" -name "bot_data_*.db.gz" -mtime +$DAYS_TO_KEEP -delete -print | wc -l)

if [ $DELETED_COUNT -gt 0 ]; then
    log "🗑️  Удалено старых бэкапов: $DELETED_COUNT"
else
    log "ℹ️  Нет старых бэкапов для удаления"
fi

# ===== СТАТИСТИКА =====
TOTAL_BACKUPS=$(ls -1 "$BACKUP_DIR"/bot_data_*.db.gz 2>/dev/null | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)

log "📊 Всего бэкапов: $TOTAL_BACKUPS | Занято места: $TOTAL_SIZE"
log "✅ Бэкап завершён успешно!"

exit 0
