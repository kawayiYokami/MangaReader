import logging
from logging.handlers import RotatingFileHandler
import sys
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
        self.logger = logging.getLogger('MangaViewer')
        self.logger.setLevel(logging.CRITICAL)  # 只显示严重错误
        
        # 创建控制台处理器，显示所有日志
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        
        # 创建文件处理器，保存到文件
        file_handler = RotatingFileHandler(
            'manga_viewer.log',
            maxBytes=1024*1024,  # 1MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        # 创建格式化器
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        # 添加处理器到日志记录器
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
    
    def debug(self, message):
        self.logger.debug(message)
    
    def info(self, message):
        self.logger.info(message)
    
    def warning(self, message):
        self.logger.warning(message)
    
    def error(self, message):
        self.logger.error(message)
    
    def critical(self, message):
        self.logger.critical(message)

# 便捷函数，方便直接调用
def debug(message):
    MangaLogger.get_instance().debug(message)

def info(message):
    MangaLogger.get_instance().info(message)

def warning(message):
    MangaLogger.get_instance().warning(message)

def error(message):
    MangaLogger.get_instance().error(message)

def critical(message):
    MangaLogger.get_instance().critical(message)