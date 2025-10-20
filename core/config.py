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
from typing import Any, List, Union
from pathlib import Path


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


class BoolConfigItem(ConfigItem):
    """布尔配置项，继承自ConfigItem"""
    def __init__(self, group: str, key: str, default_value: bool):
        super().__init__(group, key, default_value, validator=None)
    
    @ConfigItem.value.setter
    def value(self, new_value):
        if isinstance(new_value, str):
            val = new_value.lower() in ('true', '1', 't', 'y', 'yes')
        else:
            val = bool(new_value)
        
        if self.validator and not self.validator.validate(val):
             raise ValueError(f"Invalid value for {self.group}.{self.key}: {val}")
        self._value = val


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

        # ==================== 缩略图缓存设置 ====================
        self.thumbnail_cache_dir = ConfigItem("ThumbnailCache", "CacheDirectory", "cache/thumbnails")
        self.thumbnail_output_width = RangeConfigItem("ThumbnailCache", "OutputWidth", 256, validator=RangeValidator(100, 1024))
        self.thumbnail_output_height = RangeConfigItem("ThumbnailCache", "OutputHeight", 342, validator=RangeValidator(100, 1024))
        self.thumbnail_quality = RangeConfigItem("ThumbnailCache", "Quality", 75, validator=RangeValidator(10, 100))
        self.thumbnail_max_size_mb = RangeConfigItem("ThumbnailCache", "MaxSizeMB", 500, validator=RangeValidator(50, 10240))

        # ==================== 页面缓存设置 ====================
        self.page_cache_enabled = BoolConfigItem("PageCache", "Enabled", False)
        self.page_cache_quality = RangeConfigItem("PageCache", "Quality", 85, validator=RangeValidator(10, 100))
        self.page_cache_max_size_mb = RangeConfigItem("PageCache", "MaxSizeMB", 2048, validator=RangeValidator(100, 20480))
        self.page_cache_standard_height = RangeConfigItem("PageCache", "StandardHeight", 1280, validator=RangeValidator(720, 4000))
        # --- 页面缓存决策阈值 ---
        self.page_cache_decision_ratio = RangeConfigItem("PageCacheDecision", "CompressionRatioThreshold", 0.25, validator=RangeValidator(0.05, 1.0))
        self.page_cache_decision_size_mb = RangeConfigItem("PageCacheDecision", "FileSizeThresholdMB", 2.0, validator=RangeValidator(0.5, 10.0))
        self.page_cache_decision_dimension = RangeConfigItem("PageCacheDecision", "DimensionThreshold", 4000, validator=RangeValidator(1000, 8000))

        # ==================== MangaManager 状态 ====================
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
            "OpenAI",
            validator=OptionsValidator(["智谱", "OpenAI", "Gemini"])
        )
        self.target_language = OptionsConfigItem(
            "Translation",
            "TargetLanguage",
            "zh",
            validator=OptionsValidator(["zh", "en", "ja", "ko"])
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
        

        # OpenAI翻译设置
        self.openai_api_key = ConfigItem("Translation", "OpenaiApiKey", "")
        self.openai_api_base_url = ConfigItem("Translation", "OpenaiApiBaseUrl", "https://api.openai.com/v1")
        self.openai_model = ConfigItem("Translation", "OpenaiModel", "gpt-4o")

        # Gemini翻译设置
        self.gemini_api_key = ConfigItem("Translation", "GeminiApiKey", "")
        self.gemini_model = ConfigItem("Translation", "GeminiModel", "gemini-1.5-flash")

        # 新增：用于选择当前激活的 AI 翻译器配置
        self.active_ai_translator_config = ConfigItem(
            "Translation",
            "ActiveAITranslatorConfig",
            "my_openai_service", # 默认使用第一个
        )

        # ==================== AI Translator 模块独立配置 ====================
        # Key 和 Group 相同，这样 value 就会是整个 "api_translator_configs" 对象
        self.api_translator_configs = ConfigItem("api_translator_configs", "api_translator_configs", [])
        
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
                    # 如果 group 和 key 相同, 则将其视为根级配置项
                    if item.group == item.key:
                        if item.key in data:
                            try:
                                item.value = data[item.key]
                            except ValueError as e:
                                print(f"配置项 {key} 值无效，使用默认值: {e}")
                    else:
                        # 标准的嵌套配置项
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
                value = item.value
                # 处理枚举类型
                if hasattr(value, 'value'):
                    value = value.value
                
                # 如果 group 和 key 相同, 则将其视为根级配置项
                if item.group == item.key:
                    data[item.key] = value
                else:
                    # 标准的嵌套配置项
                    if item.group not in data:
                        data[item.group] = {}
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
config.load()  # 加载用户已保存的配置
