"""
УЛУЧШЕНО: utils/logger.py
Добавлена ротация логов и разные уровни

ИЗМЕНЕНИЯ:
✅ Ротация файлов логов (10MB x 5 файлов)
✅ Разные уровни для console и file
✅ Цветной вывод в консоль (опционально)
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(
    name: str = __name__, 
    level: int = logging.INFO,
    log_file: str = "bot.log",
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG
) -> logging.Logger:
    """
    Настраивает и возвращает logger с форматированием и ротацией
    
    Args:
        name: Имя logger'а
        level: Общий уровень логирования
        log_file: Путь к файлу логов
        console_level: Уровень для консоли
        file_level: Уровень для файла
        
    Returns:
        Настроенный logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Если уже есть handlers, не добавляем новые
    if logger.handlers:
        return logger
    
    # ===== ФОРМАТИРОВАНИЕ =====
    
    # Формат для консоли (короткий)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S"
    )
    
    # Формат для файла (подробный)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # ===== CONSOLE HANDLER =====
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(console_formatter)
    
    # ✅ НОВОЕ: Цветной вывод (если поддерживается)
    try:
        import colorlog
        
        color_formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        console_handler.setFormatter(color_formatter)
    except ImportError:
        # Если colorlog не установлен - используем обычный формат
        pass
    
    logger.addHandler(console_handler)
    
    # ===== FILE HANDLER С РОТАЦИЕЙ =====
    
    try:
        # Создаём директорию logs если её нет
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # ✅ НОВОЕ: Ротация файлов
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,              # Хранить 5 старых файлов
            encoding='utf-8'
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(file_formatter)
        
        logger.addHandler(file_handler)
        
    except Exception as e:
        # Если не удалось создать файл - логируем в консоль
        logger.warning(f"⚠️ Не удалось создать file handler: {e}")
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    ✅ НОВОЕ: Получить существующий logger или создать новый
    
    Args:
        name: Имя logger'а (обычно __name__)
        
    Returns:
        Logger
    """
    logger = logging.getLogger(name)
    
    # Если logger ещё не настроен - настраиваем
    if not logger.handlers:
        return setup_logger(name)
    
    return logger


def set_log_level(level: int):
    """
    ✅ НОВОЕ: Изменить уровень логирования для всех handlers
    
    Args:
        level: Новый уровень (logging.DEBUG, logging.INFO, и т.д.)
    """
    logger = logging.getLogger("bot")
    logger.setLevel(level)
    
    for handler in logger.handlers:
        handler.setLevel(level)
    
    logger.info(f"🔧 Уровень логирования изменён на: {logging.getLevelName(level)}")


def get_log_stats(log_file: str = "bot.log") -> dict:
    """
    ✅ НОВОЕ: Получить статистику по логам
    
    Args:
        log_file: Путь к файлу логов
        
    Returns:
        Словарь со статистикой
    """
    try:
        log_path = Path(log_file)
        
        if not log_path.exists():
            return {
                "exists": False,
                "size_mb": 0,
                "lines": 0
            }
        
        # Размер файла
        size_bytes = log_path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        
        # Количество строк
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = sum(1 for _ in f)
        
        # Ротированные файлы
        rotated_files = list(log_path.parent.glob(f"{log_path.name}.*"))
        
        return {
            "exists": True,
            "size_mb": round(size_mb, 2),
            "lines": lines,
            "rotated_files": len(rotated_files)
        }
        
    except Exception as e:
        return {
            "error": str(e)
        }


# ===== ГЛОБАЛЬНЫЙ LOGGER =====

# Настраиваем главный logger для бота
logger = setup_logger(
    "bot", 
    level=logging.DEBUG,        # Общий уровень
    console_level=logging.INFO, # Консоль - только INFO и выше
    file_level=logging.DEBUG    # Файл - всё включая DEBUG
)

# Логируем успешную инициализацию
logger.info("✅ Logger инициализирован с ротацией файлов")

# ===== ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ =====

if __name__ == "__main__":
    # Тестирование
    logger.debug("🔍 Debug сообщение (видно только в файле)")
    logger.info("ℹ️ Info сообщение")
    logger.warning("⚠️ Warning сообщение")
    logger.error("❌ Error сообщение")
    
    # Статистика
    stats = get_log_stats()
    logger.info(f"📊 Статистика логов: {stats}")
    
    # Изменение уровня
    set_log_level(logging.DEBUG)
    logger.debug("🔍 Теперь debug видно и в консоли!")