"""
日志工具模块
"""
import logging
import colorlog
from config import config


def setup_logger(name: str = "PolymarketAgent") -> logging.Logger:
    """设置彩色日志"""
    
    # 创建 logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.LOG_LEVEL))
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    # 控制台 handler（彩色）
    console_handler = colorlog.StreamHandler()
    console_handler.setLevel(getattr(logging, config.LOG_LEVEL))
    
    # 彩色格式
    console_format = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # 文件 handler
    file_handler = logging.FileHandler(config.LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    return logger


# 创建全局 logger
logger = setup_logger()
