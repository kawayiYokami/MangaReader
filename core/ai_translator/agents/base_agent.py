# file: core/ai_translator/agents/base_agent.py
"""
智能体模块 - 抽象基类
=======================

定义了所有 AI 智能体必须遵循的通用接口。
每个智能体都封装了针对特定任务的 Prompt 构建和响应解析逻辑。
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Union

from ..data_models import APIConfig, TranslationResult, ImageTranslationResult

class BaseAgent(ABC):
    """
    AI 智能体抽象基类。
    """

    def __init__(self, system_prompt_template: str):
        """
        初始化智能体。

        Args:
            system_prompt_template (str): 从 JSON 定义中加载的系统提示模板。
        """
        self.system_prompt_template = system_prompt_template

    def build_system_prompt(self, **kwargs: Any) -> str:
        """
        使用模板和参数构建最终的系统提示。
        这是一个通用方法，可以被子类覆盖以实现更复杂的逻辑。
        """
        return self.system_prompt_template.format(**kwargs)

    @abstractmethod
    def build_request_payload(
        self,
        *,
        config: APIConfig,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        构建发送给 AI API 的请求体 (payload)。

        Args:
            config (APIConfig): 当前任务使用的 API 配置。
            system_prompt (str): 指导 AI 行为的系统级提示。
            **kwargs: 特定于智能体的额外参数 (例如文本列表或图片数据)。

        Returns:
            Dict[str, Any]: 构造好的、可直接序列化为 JSON 的请求体。
        """
        pass

    @abstractmethod
    def parse_response(
        self, 
        response_data: Dict[str, Any],
        **kwargs: Any
    ) -> Union[List[TranslationResult], List[ImageTranslationResult]]:
        """
        解析来自 AI API 的响应。

        Args:
            response_data (Dict[str, Any]): 从 AI API 返回的已解析的 JSON 数据。
            **kwargs: 特定于智能体的额外参数，可能在解析时需要 (例如原始文本数量)。

        Returns:
            Union[List[TranslationResult], List[ImageTranslationResult]]: 
            一个包含结构化结果对象的列表。
        """
        pass