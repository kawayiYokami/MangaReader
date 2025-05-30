# 核心业务逻辑模块
# 包含漫画管理器、数据模型、加载器和OCR管理器

from .manga_manager import MangaManager
from .manga_model import MangaInfo, MangaLoader
from .ocr_manager import OCRManager, OCRResult
from .translator import TranslatorFactory
from .config import config

__all__ = [
    'MangaManager',
    'MangaInfo',
    'MangaLoader',
    'OCRManager',
    'OCRResult',
    'TranslatorFactory',
    'config'
]