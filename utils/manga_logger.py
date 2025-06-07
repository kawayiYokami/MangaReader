import logging
from logging.handlers import RotatingFileHandler
import sys
import os # 新增导入 os 模块
from datetime import datetime


class MangaLogger:
    # 日志级别
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = MangaLogger()
        return cls._instance

    # 在 __init__ 方法中修改
    def __init__(self):
        from core.config import config
        self.logger = logging.getLogger("MangaViewer")

        # 防止重复添加handler
        if self.logger.handlers:
            return

        # 创建格式化器
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

        # 创建控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # 创建文件处理器
        log_dir = ".log"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_file_path = os.path.join(log_dir, "manga_viewer.log")
        # 设置日志文件大小为 1MB，保留5个备份文件
        file_handler = RotatingFileHandler(log_file_path, maxBytes=1*1024*1024, backupCount=5, encoding='utf-8')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # 防止日志传播到根logger
        self.logger.propagate = False

        # 从配置中设置日志等级
        self.set_level(config.log_level.value)
        
    def set_level(self, level_str):
        """设置日志等级
        
        Args:
            level_str (str): 日志等级字符串，可选值：DEBUG, INFO, WARNING, ERROR, CRITICAL
        """
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        level = level_map.get(level_str, logging.WARNING)
        self.logger.setLevel(level)
        for handler in self.logger.handlers:
            handler.setLevel(level)

    def debug(self, message, *args, **kwargs):
        self.logger.debug(message, *args, **kwargs)

    def info(self, message, *args, **kwargs):
        self.logger.info(message, *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        self.logger.warning(message, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        self.logger.error(message, *args, **kwargs)

    def critical(self, message, *args, **kwargs):
        self.logger.critical(message, *args, **kwargs)


# 便捷函数，方便直接调用
def debug(message, *args, **kwargs):
    MangaLogger.get_instance().debug(message, *args, **kwargs)


def info(message, *args, **kwargs):
    MangaLogger.get_instance().info(message, *args, **kwargs)


def warning(message, *args, **kwargs):
    MangaLogger.get_instance().warning(message, *args, **kwargs)


def error(message, *args, **kwargs):
    MangaLogger.get_instance().error(message, *args, **kwargs)


def critical(message, *args, **kwargs):
    MangaLogger.get_instance().critical(message, *args, **kwargs)
