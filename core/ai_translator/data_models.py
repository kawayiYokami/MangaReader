# file: core/ai_translator/data_models.py
"""
AI 翻译器数据模型
==================

本文件定义了 `ai_translator` 模块在各层之间传递数据所使用的核心数据结构。
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

class TranslationMode(Enum):
    """
    翻译模式枚举
    - SINGLE: 单文本模式，逐条翻译。
    - MULTI: 多文本模式，打包后翻译。
    """
    SINGLE = "single"
    MULTI = "multi"

class TaskType(Enum):
    """
    AI 任务类型枚举
    """
    TEXT_TRANSLATION = "text_translation"
    IMAGE_TRANSLATION = "image_translation"

@dataclass
class APIConfig:
    """
    API 配置数据模型
    存储一个特定 API Key 的所有相关配置。
    """
    name: str  # 配置名称，例如 "my_openai_1"
    api_type: str  # API 类型, 例如 "openai" 或 "gemini"
    api_key: str  # API 密钥
    model: str  # 模型名称
    temperature: float = 0.2  # 温度参数
    max_tokens: int = 4096 # AI 返回的最大 token 数量
    api_base_url: Optional[str] = None  # OpenAI 兼容 API 的基础 URL
    request_interval_ms: int = 1000  # 请求间隔（毫秒）

@dataclass
class TranslationRequest:
    """
    翻译请求数据模型
    代表一个完整的翻译任务。
    """
    texts: List[str]
    config: APIConfig
    mode: TranslationMode
    system_prompt: str
    special_prompt: Optional[str] = None

class TranslationStatus(Enum):
    """
    翻译结果状态枚举
    """
    SUCCESS = "success"
    FAILURE = "failure"
    NOT_TRANSLATED = "not_translated"

@dataclass
class TranslationResult:
    """
    翻译结果数据模型
    """
    original_text: str
    translated_text: str
    status: TranslationStatus = TranslationStatus.SUCCESS
    needs_translation: bool = True # 新增字段，标记是否需要翻译
    error_message: Optional[str] = None

# ==================== 图片翻译数据模型 (剧本生成模式) ====================

@dataclass
class DialogueLine:
    """
    单行对话的数据模型，代表剧本中的一行。
    """
    speaker_id: int
    original_text: str
    translated_text: str

    def to_dict(self) -> Dict[str, Any]:
        return {"speaker_id": self.speaker_id, "original_text": self.original_text, "translated_text": self.translated_text}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DialogueLine":
        return cls(speaker_id=data["speaker_id"], original_text=data["original_text"], translated_text=data["translated_text"])

@dataclass
class TranslationScript:
    """
    完整的翻译剧本数据模型
    """
    script: List[DialogueLine] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"script": [line.to_dict() for line in self.script]}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranslationScript":
        return cls(script=[DialogueLine.from_dict(line_data) for line_data in data.get("script", [])])

@dataclass
class ImageTranslationResult:
    """
    单张图片翻译的完整结果
    """
    status: TranslationStatus
    translation_script: Optional[TranslationScript] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        # 序列化时有意排除了 raw_response，因为它包含易变元数据，会污染缓存。
        return {
            "status": self.status.value,
            "translation_script": self.translation_script.to_dict() if self.translation_script else None,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImageTranslationResult":
        script_data = data.get("translation_script")
        return cls(
            status=TranslationStatus(data["status"]),
            translation_script=TranslationScript.from_dict(script_data) if script_data else None,
            error_message=data.get("error_message"),
            # raw_response 在反序列化时不存在，这是预期的
            raw_response=None,
        )