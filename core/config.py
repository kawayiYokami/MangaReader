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

    # ==================== MangaManager 状态 ====================
    manga_dir = ConfigItem("Manager", "MangaDirectory", "")
    current_page = ConfigItem("Manager", "CurrentPage", 0)
    current_manga_path = ConfigItem("Manager", "CurrentMangaPath", "")
    
    # ==================== 日志设置 ====================
    log_level = OptionsConfigItem(
        "System", 
        "LogLevel", 
        "WARNING",
        validator=OptionsValidator(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    )
    
    # ==================== 翻译设置 ====================
    translator_type = OptionsConfigItem(
        "Translation", 
        "TranslatorType", 
        "Google",
        validator=OptionsValidator(["Google", "智谱", "DeepL", "百度", "MyMemory"])
    )
    # 智谱AI翻译设置
    zhipu_api_key = ConfigItem("Translation", "ZhipuApiKey", "")
    zhipu_model = OptionsConfigItem(
        "Translation",
        "ZhipuModel",
        "glm-4-flash-250414",
        validator=OptionsValidator([
            "glm-4-flash-250414",
            "glm-4-flash",
            "glm-4",
            "glm-3-turbo"
        ])
    )
    
    # Google翻译设置
    google_api_key = ConfigItem("Translation", "GoogleApiKey", "")
    
    # DeepL翻译设置
    deepl_api_key = ConfigItem("Translation", "DeepLApiKey", "")
    
    # 百度翻译设置
    baidu_app_id = ConfigItem("Translation", "BaiduAppId", "")
    baidu_app_key = ConfigItem("Translation", "BaiduAppKey", "")
    
    # MyMemory翻译设置
    mymemory_email = ConfigItem("Translation", "MyMemoryEmail", "")


# 创建全局 config 对象
config = Config()
config.themeMode.value = Theme.AUTO
config.load(config=config)
