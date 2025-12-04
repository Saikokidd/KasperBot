"""
Настройка логирования для бота
"""
import logging
import sys


def setup_logger(name: str = __name__, level: int = logging.INFO) -> logging.Logger:
    """
    Настраивает и возвращает logger с форматированием
    
    Args:
        name: Имя logger'а
        level: Уровень логирования
        
    Returns:
        Настроенный logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Если уже есть handlers, не добавляем новые
    if logger.handlers:
        return logger
    
    # Форматирование
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Handler для вывода в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    return logger


# Глобальный logger для использования в других модулях
logger = setup_logger("bot", logging.INFO)
