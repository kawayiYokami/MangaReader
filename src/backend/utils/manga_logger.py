# utils/manga_logger.py
"""
全局日志配置模块

提供一个函数来设置和配置Python的root logger。
"""
import logging
from logging.handlers import RotatingFileHandler
import sys
import os
import coloredlogs
from src.backend.core.config import config

def set_level(level_str: str):
    """动态设置 Root Logger 和所有处理器的日志级别"""
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    level = level_map.get(level_str.upper(), logging.INFO)
    
    # 获取根日志记录器
    logger = logging.getLogger()
    
    # 1. 首先设置根日志记录器的级别
    # 这决定了哪些级别的消息可以被传递给处理器
    logger.setLevel(level)

    # 2. 遍历并更新所有处理器的级别
    # 这是确保日志级别实时生效的关键步骤
    for handler in logger.handlers:
        handler.setLevel(level)
            
    logging.info(f"全局日志级别已设置为: {level_str}")

    # 在调试模式下，打印出每个处理器的级别以供验证
    if level == logging.DEBUG:
        for i, handler in enumerate(logger.handlers):
            logging.debug(f"  > 处理器 {i} ({type(handler).__name__}) 的级别已更新为: {logging.getLevelName(handler.level)}")

def setup_logging():
    """
    配置全局 Root Logger。
    此函数应在应用程序启动时调用一次。
    使用 coloredlogs 库来美化控制台输出，并保留文件日志。
    这个版本会强制重置任何预先存在的日志处理器。
    """
    root_logger = logging.getLogger()
    
    # 强制重置：移除所有可能由第三方库添加的处理器
    if root_logger.hasHandlers():
        logging.debug(f"检测到预先存在的日志处理器: {root_logger.handlers}。正在移除以强制重新配置...")
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

    # 使用 coloredlogs 配置控制台日志
    coloredlogs.install(
        level=config.log_level.value.upper(),
        logger=root_logger,
        fmt="%(asctime)s [%(name)s:%(lineno)d] [%(levelname)s] - %(message)s",
        stream=sys.stdout
    )

    # 单独配置和添加文件处理器（不带颜色）
    log_dir = ".log"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file_path = os.path.join(log_dir, "manga_viewer.log")
    
    file_formatter = logging.Formatter("%(asctime)s - [%(name)s:%(lineno)d] [%(levelname)-8s] - %(message)s")
    
    file_handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    
    # 文件处理器将遵循根记录器的级别
    root_logger.addHandler(file_handler)
    
    # 抑制第三方库的日志噪音
    logging.getLogger("fontTools").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    root_logger.propagate = False
    
    # 根据配置设置最终的正确级别
    set_level(config.log_level.value)
    
    logging.info("全局日志系统初始化完成。")
