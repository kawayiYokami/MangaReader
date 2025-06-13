# core/config_new.py
"""
漫画阅读器核心配置文件 - 新版本

定义应用程序的所有配置项，包括:
1. 漫画阅读相关设置（阅读方向、显示模式等）
2. 用户界面偏好（主题、颜色等）
3. 应用程序状态（当前阅读位置等）

配置使用简洁的JSON配置系统实现，支持:
- 类型安全的配置项定义
- 自动保存和加载
- 配置项验证
- 分类存储
"""

import json
import os
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pathlib import Path


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


class Theme(Enum):
    """
    主题模式枚举
    
    取值:
    - LIGHT: 浅色主题
    - DARK: 深色主题  
    - AUTO: 自动主题（跟随系统）
    """
    
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


class ConfigItem:
    """
    简洁的配置项类
    
    支持类型验证、默认值和自动保存
    """
    
    def __init__(self, group: str, key: str, default_value: Any, validator=None):
        self.group = group
        self.key = key
        self.default_value = default_value
        self.validator = validator
        self._value = default_value
        
    @property
    def value(self):
        return self._value
        
    @value.setter
    def value(self, new_value):
        if self.validator and not self.validator.validate(new_value):
            raise ValueError(f"Invalid value for {self.group}.{self.key}: {new_value}")
        self._value = new_value


class OptionsConfigItem(ConfigItem):
    """选项配置项，继承自ConfigItem"""
    pass


class RangeConfigItem(ConfigItem):
    """范围配置项，继承自ConfigItem"""
    pass


# 验证器类
class OptionsValidator:
    """选项验证器"""
    
    def __init__(self, options: List[Any]):
        self.options = options
        
    def validate(self, value: Any) -> bool:
        return value in self.options


class RangeValidator:
    """范围验证器"""
    
    def __init__(self, min_value: Union[int, float], max_value: Union[int, float]):
        self.min_value = min_value
        self.max_value = max_value
        
    def validate(self, value: Union[int, float]) -> bool:
        return self.min_value <= value <= self.max_value


class Config:
    """
    用户自定义配置项类

    提供以下功能:
    - 分组配置项管理
    - 自动保存/加载配置
    - 配置项值验证
    - 分类存储到app/config目录
    """

    def __init__(self):
        # 配置文件目录
        self.config_dir = Path("app/config")
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        
        # 初始化所有配置项
        self._init_config_items()
        
        # 收集所有配置项
        self._collect_config_items()
        
    def _init_config_items(self):
        """初始化所有配置项"""
        # ==================== Manga 功能设置 ====================
        self.reading_order = OptionsConfigItem(
            "Manga",
            "ReadingOrder",
            ReadingOrder.LEFT_TO_RIGHT.value,
            validator=OptionsValidator([e.value for e in ReadingOrder]),
        )

        self.display_mode = OptionsConfigItem(
            "Manga",
            "DisplayMode",
            DisplayMode.DOUBLE.value,
            validator=OptionsValidator([e.value for e in DisplayMode]),
        )

        self.page_interval = ConfigItem(
            "Manga", "PageInterval", 3, validator=RangeValidator(1, 300)
        )

        self.translate_title = ConfigItem("Manga", "TranslateTitle", False)
        self.simplify_chinese = ConfigItem("Manga", "SimplifyChinese", False)
        self.merge_tags = ConfigItem("Manga", "MergeTags", True)
        self.webp_quality = RangeConfigItem(
            "Manga",
            "WebpQuality",
            80,  # 默认 WebP 质量为 80
            validator=RangeValidator(0, 100)  # WebP 质量范围 0-100
        )

        # ==================== 页面尺寸分析设置 ====================
        self.enable_dimension_analysis = ConfigItem("Manga", "EnableDimensionAnalysis", True)
        self.dimension_variance_threshold = RangeConfigItem(
            "Manga",
            "DimensionVarianceThreshold",
            0.15,  # 默认方差阈值 0.15
            validator=RangeValidator(0.0, 1.0)  # 方差阈值范围 0.0-1.0
        )
        self.filter_non_manga = ConfigItem("Manga", "FilterNonManga", False)  # 是否过滤非漫画文件

        # ==================== 缩略图缓存设置 ====================
        self.thumbnail_cache_dir = ConfigItem("ThumbnailCache", "CacheDirectory", "cache/thumbnails")
        self.thumbnail_output_width = RangeConfigItem("ThumbnailCache", "OutputWidth", 256, validator=RangeValidator(100, 1024))
        self.thumbnail_output_height = RangeConfigItem("ThumbnailCache", "OutputHeight", 342, validator=RangeValidator(100, 1024))
        self.thumbnail_quality = RangeConfigItem("ThumbnailCache", "Quality", 75, validator=RangeValidator(10, 100))
        self.thumbnail_max_size_mb = RangeConfigItem("ThumbnailCache", "MaxSizeMB", 500, validator=RangeValidator(50, 10240))

        # ==================== MangaManager 状态 ====================
        self.manga_dir = ConfigItem("Manager", "MangaDirectory", "")
        self.current_page = ConfigItem("Manager", "CurrentPage", 0)
        self.current_manga_path = ConfigItem("Manager", "CurrentMangaPath", "")
        
        # ==================== 日志设置 ====================
        self.log_level = OptionsConfigItem(
            "System", 
            "LogLevel",
            "ERROR", 
            validator=OptionsValidator(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        )
        
        # ==================== OCR 设置 ====================
        self.ocr_confidence_threshold = RangeConfigItem(
            "OCR",
            "ConfidenceThreshold",
            0.60,
            validator=RangeValidator(0.0, 1.0)
        )

        # ==================== 翻译设置 ====================
        self.translator_type = OptionsConfigItem(
            "Translation", 
            "TranslatorType", 
            "Google", 
            validator=OptionsValidator(["Google", "智谱"])
        )

        # 文字替换设置
        self.font_name = ConfigItem("TextReplace", "FontName", "SourceHanSerifCN-Heavy.ttf")

        # 智谱AI翻译设置
        self.zhipu_api_key = ConfigItem("Translation", "ZhipuApiKey", "")
        self.zhipu_model = ConfigItem(
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
        self.google_api_key = ConfigItem("Translation", "GoogleApiKey", "")
        
        # 主题设置
        self.themeMode = ConfigItem("UI", "ThemeMode", Theme.AUTO)
        
    def _collect_config_items(self):
        """收集所有配置项"""
        self._config_items = {}
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if isinstance(attr, ConfigItem):
                self._config_items[f"{attr.group}.{attr.key}"] = attr

    def load(self, config=None):
        """从文件加载配置"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 按分类加载配置
                for key, item in self._config_items.items():
                    group_data = data.get(item.group, {})
                    if item.key in group_data:
                        try:
                            item.value = group_data[item.key]
                        except ValueError as e:
                            print(f"配置项 {key} 值无效，使用默认值: {e}")

        except Exception as e:
            print(f"加载配置文件失败: {e}")

    def save(self):
        """保存配置到文件，按分类组织"""
        try:
            # 按分类组织数据
            data = {}
            for key, item in self._config_items.items():
                if item.group not in data:
                    data[item.group] = {}

                value = item.value
                # 处理枚举类型
                if hasattr(value, 'value'):
                    value = value.value
                data[item.group][item.key] = value

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"保存配置文件失败: {e}")

    def get(self, group: str, key: str, default=None):
        """获取配置项值"""
        config_key = f"{group}.{key}"
        if config_key in self._config_items:
            return self._config_items[config_key].value
        return default

    def set(self, group: str, key: str, value):
        """设置配置项值"""
        config_key = f"{group}.{key}"
        if config_key in self._config_items:
            self._config_items[config_key].value = value
            self.save()  # 自动保存


# 创建全局 config 对象
config = Config()
# 确保在加载前设置默认主题模式
if config.themeMode.value not in [Theme.LIGHT, Theme.DARK, Theme.AUTO]:
    config.themeMode.value = Theme.AUTO
config.load()  # 加载用户已保存的配置
