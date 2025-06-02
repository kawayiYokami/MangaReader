# core/config.py
"""
漫画阅读器核心配置文件

定义应用程序的所有配置项，包括:
1. 漫画阅读相关设置（阅读方向、显示模式等）
2. 用户界面偏好（主题、颜色等）
3. 应用程序状态（当前阅读位置等）

配置使用 qfluentwidgets 的 QConfig 系统实现，支持:
- 类型安全的配置项定义
- 自动保存和加载
- 配置项验证
"""

from enum import Enum
from PySide6.QtCore import QLocale
from qfluentwidgets import (
    QConfig,
    ConfigItem,
    OptionsConfigItem,
    OptionsValidator,
    RangeValidator,
    RangeConfigItem,
    qconfig,
    Theme,
    FolderValidator,
    ConfigSerializer,
)
import os


class ReadingOrder(Enum):
    """
    漫画阅读方向枚举

    取值:
    - RIGHT_TOLEFT: 从右到左（日式漫画传统阅读方向）
    - LEFT_TO_RIGHT: 从左到右（西式漫画阅读方向）
    """

    RIGHT_TO_LEFT = "从右到左"
    LEFT_TO_RIGHT = "从左到右"


class DisplayMode(Enum):
    """
    漫画显示模式枚举

    取值:
    - SINGLE: 单页显示（每次只显示一页）
    - DOUBLE: 双页显示（同时显示两页，适合宽屏）
    - ADAPTIVE: 自适应（根据内容自动选择单页或双页）
    """

    SINGLE = "单页显示"
    DOUBLE = "双页显示"
    ADAPTIVE = "自适应"


class Config(QConfig):
    """
    用户自定义配置项类

    继承自 QConfig，提供以下功能:
    - 分组配置项管理
    - 自动保存/加载配置
    - 配置项值验证
    """

    # ==================== Manga 功能设置 ====================
    reading_order = OptionsConfigItem(
        "Manga",
        "ReadingOrder",
        ReadingOrder.LEFT_TO_RIGHT.value,
        validator=OptionsValidator([e.value for e in ReadingOrder]),
    )

    display_mode = OptionsConfigItem(
        "Manga",
        "DisplayMode",
        DisplayMode.DOUBLE.value,
        validator=OptionsValidator([e.value for e in DisplayMode]),
    )

    page_interval = ConfigItem(
        "Manga", "PageInterval", 3, validator=RangeValidator(1, 300)
    )

    translate_title = ConfigItem("Manga", "TranslateTitle", False)
    simplify_chinese = ConfigItem("Manga", "SimplifyChinese", False)
    merge_tags = ConfigItem("Manga", "MergeTags", True)
    webp_quality = RangeConfigItem(
        "Manga",
        "WebpQuality",
        80,  # 默认 WebP 质量为 80
        validator=RangeValidator(0, 100)  # WebP 质量范围 0-100
    )

    # ==================== MangaManager 状态 ====================
    manga_dir = ConfigItem("Manager", "MangaDirectory", "")
    current_page = ConfigItem("Manager", "CurrentPage", 0)
    current_manga_path = ConfigItem("Manager", "CurrentMangaPath", "")
    
    # ==================== 日志设置 ====================
    log_level = OptionsConfigItem(
        "System", 
        "LogLevel",
        "ERROR", 
        validator=OptionsValidator(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    )
    
    # ==================== OCR 设置 ====================
    ocr_confidence_threshold = RangeConfigItem(
        "OCR",
        "ConfidenceThreshold",
        0.60,
        validator=RangeValidator(0.0, 1.0)
    )

    # ==================== 翻译设置 ====================
    translator_type = OptionsConfigItem(
        "Translation", 
        "TranslatorType", 
        "Google", 
        validator=OptionsValidator(["Google", "智谱", "NLLB"])
    )

    # 文字替换设置
    font_name = ConfigItem("TextReplace", "FontName", "SourceHanSerifCN-Heavy.ttf")

    # 智谱AI翻译设置
    zhipu_api_key = ConfigItem("Translation", "ZhipuApiKey", "")
    zhipu_model = ConfigItem(
        "Translation",
        "ZhipuModel",
        "glm-4-flash",
        validator=OptionsValidator([
            "glm-4-flash",
            "glm-4",
            "glm-3-turbo",
            "glm-4-flash-250414"
        ])
    )
    
    # Google翻译设置
    google_api_key = ConfigItem("Translation", "GoogleApiKey", "")

    # NLLB翻译设置
    nllb_model_name = ConfigItem(
        "Translation", "NLLBModelName", 'facebook/nllb-200-distilled-600M'
    )
    # nllb_cache_dir 不再作为用户可配置项
    # _project_root_for_nllb_cache = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # _default_nllb_cache_dir = os.path.join(_project_root_for_nllb_cache, "models")
    # nllb_cache_dir = ConfigItem(
    #     "Translation", "NLLBCacheDir", _default_nllb_cache_dir
    # )
    nllb_source_lang = ConfigItem(
        "Translation", "NLLBSourceLang", "jpn_Jpan"
    )
    _default_nllb_target_lang = "zho_Hans"
    nllb_target_lang = ConfigItem(
        "Translation", "NLLBTargetLang", _default_nllb_target_lang
    )


# 创建全局 config 对象
config = Config()
# 确保在加载前设置默认主题模式，如果qconfig系统不处理这个
if config.themeMode.value not in [Theme.LIGHT, Theme.DARK, Theme.AUTO]:
    config.themeMode.value = Theme.AUTO
config.load(config=config) # 确保加载用户已保存的配置
