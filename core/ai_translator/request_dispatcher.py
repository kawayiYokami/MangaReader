# file: core/ai_translator/request_dispatcher.py
"""
请求调度器 - 数据驱动版
===========================

本模块负责接收 AI 任务请求，并将其智能地分发给底层的 API 执行器。
它通过 AgentDefinitionManager 加载和实例化由 JSON 定义的智能体。
"""
from typing import List, Union

from .data_models import (
    TranslationResult, ImageTranslationResult, TaskType
)
from .config_manager import api_config_manager
from .api_executor import APIExecutor
from .rate_limiter import rate_limiter
from .agents.agent_manager import agent_definition_manager
from .agents.text_translation_agent import TextTranslationAgent
from .agents.image_translation_agent import ImageTranslationAgent
from utils.manga_logger import logging

class RequestDispatcher:
    """
    负责分发和并发执行 AI 任务的调度器。
    """
    def __init__(self):
        self._executor = APIExecutor()

    async def dispatch(
        self,
        *,
        agent_name: str,
        config_name: str,
        task_type: TaskType,
        **kwargs
    ) -> Union[List[TranslationResult], List[ImageTranslationResult]]:
        """
        通用的、数据驱动的任务分发逻辑。

        Args:
            agent_name (str): 要使用的智能体的名称 (对应于 app/agents/下的json文件名)。
            config_name (str): API 配置的名称。
            task_type (TaskType): 明确的任务类型，用于决定使用哪个Agent类。
            **kwargs: 传递给 Agent 的具体任务参数。

        Returns:
            翻译或处理结果。
        """
        # 1. 获取 API 配置
        config = api_config_manager.get_config(config_name)
        if not config:
            error_msg = f"API 配置 '{config_name}' 未找到。"
            logging.error(error_msg)
            # 在实际应用中，这里应该返回一个带错误信息的标准结果对象
            return []

        # 2. 获取智能体定义
        definition = agent_definition_manager.get_definition(agent_name)
        if not definition:
            error_msg = f"智能体定义 '{agent_name}' 未找到。"
            logging.error(error_msg)
            return []

        # 3. 根据 task_type 决定 Agent 类
        if task_type == TaskType.IMAGE_TRANSLATION:
            agent_class = ImageTranslationAgent
        elif task_type == TaskType.TEXT_TRANSLATION:
            agent_class = TextTranslationAgent
        else:
            logging.error(f"不支持的任务类型: {task_type}")
            return []

        try:
            agent_instance = agent_class(definition.system_prompt_template)
        except Exception as e:
            logging.error(f"实例化智能体 '{agent_name}' 失败: {e}")
            return []

        # 4. 使用速率限制器执行 API 调用
        logging.info(f"正在使用智能体 '{agent_name}' (类型: {task_type.value}) 和配置 '{config_name}' 分发任务...")
        await rate_limiter.wait_for_token(config.name, config.request_interval_ms)

        return await self._executor.execute(
            agent=agent_instance,
            config=config,
            agent_name=agent_name, # 传递 agent_name
            **kwargs
        )