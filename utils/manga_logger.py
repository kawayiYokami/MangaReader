import logging
from logging.handlers import RotatingFileHandler
import sys
import os
from datetime import datetime

# ANSI 颜色代码
class Colors:
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BOLD = "\033[1m"


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""

    LOG_COLORS = {
        logging.DEBUG: Colors.CYAN,
        logging.INFO: Colors.WHITE,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.BOLD + Colors.RED,
    }

    def format(self, record):
        log_color = self.LOG_COLORS.get(record.levelno, Colors.WHITE)
        
        # 对整个消息应用颜色
        record.msg = f"{log_color}{record.msg}{Colors.RESET}"
        
        # 格式化级别名称
        record.levelname = f"{log_color}{record.levelname}{Colors.RESET}"

        return super().format(record)


class MangaLogger:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = MangaLogger()
        return cls._instance

    def __init__(self):
        from core.config import config
        self.logger = logging.getLogger("MangaViewer")

        if self.logger.handlers:
            return

        # 创建格式化器
        console_formatter = ColoredFormatter("%(asctime)s [%(levelname)-8s] %(message)s")
        file_formatter = logging.Formatter("%(asctime)s [%(levelname)-8s] %(message)s")
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # 创建文件处理器
        log_dir = ".log"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_file_path = os.path.join(log_dir, "manga_viewer.log")
        file_handler = RotatingFileHandler(log_file_path, maxBytes=1*1024*1024, backupCount=5, encoding='utf-8')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        self.logger.propagate = False
        self.set_level(config.log_level.value)
        
    def set_level(self, level_str):
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        level = level_map.get(level_str.upper(), logging.WARNING)
        self.logger.setLevel(level)
        for handler in self.logger.handlers:
            handler.setLevel(level)

    def _log(self, level, message, *args, **kwargs):
        self.logger.log(level, message, *args, **kwargs)

    # --- 兼容旧接口 ---
    def debug(self, message, *args, **kwargs):
        self._log(logging.DEBUG, message, *args, **kwargs)

    def info(self, message, *args, **kwargs):
        self._log(logging.INFO, message, *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        self._log(logging.WARNING, message, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        self._log(logging.ERROR, message, *args, **kwargs)

    def critical(self, message, *args, **kwargs):
        self._log(logging.CRITICAL, message, *args, **kwargs)
        
    # --- 新增辅助函数 ---
    def header(self, message):
        """打印一个格式化的标题"""
        separator = "=" * (len(message) + 4)
        self.info(f"\n{Colors.BOLD}{Colors.MAGENTA}{separator}{Colors.RESET}")
        self.info(f"{Colors.BOLD}{Colors.MAGENTA}  {message.upper()}  {Colors.RESET}")
        self.info(f"{Colors.BOLD}{Colors.MAGENTA}{separator}{Colors.RESET}\n")

    def separator(self, char='-', length=80):
        """打印一条分割线"""
        self.info(f"{Colors.BLUE}{char * length}{Colors.RESET}")
        
    def success(self, message):
        """打印成功信息"""
        self.info(f"{Colors.GREEN}{message}{Colors.RESET}")


# --- 便捷函数 ---
_logger = MangaLogger.get_instance()

def set_level(level_str):
    _logger.set_level(level_str)

def debug(message, *args, **kwargs):
    _logger.debug(message, *args, **kwargs)

def info(message, *args, **kwargs):
    _logger.info(message, *args, **kwargs)

def warning(message, *args, **kwargs):
    _logger.warning(message, *args, **kwargs)

def error(message, *args, **kwargs):
    _logger.error(message, *args, **kwargs)

def critical(message, *args, **kwargs):
    _logger.critical(message, *args, **kwargs)

def header(message):
    _logger.header(message)

def separator(char='-', length=80):
    _logger.separator(char, length)

def success(message):
    _logger.success(message)
