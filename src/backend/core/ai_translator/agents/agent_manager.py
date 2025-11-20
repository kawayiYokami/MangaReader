# file: core/ai_translator/agents/agent_manager.py
"""
智能体定义管理器
=====================

负责从 app/agents 目录加载所有智能体的 JSON 定义文件，
并提供一个按名称检索这些定义的接口。
"""
import json
import os
from typing import Dict, Optional, List

from src.backend.utils.manga_logger import logging

class AgentDefinition:
    """一个封装了智能体 JSON 定义的数据类。"""
    def __init__(self, data: Dict):
        self.name: str = data.get("name", "")
        self.description: str = data.get("description", "")
        self.agent_type: str = data.get("agent_type", "") # 可选的元数据字段

        prompt_template = data.get("system_prompt_template", "")
        # 如果模板是列表，则合并为单个字符串
        if isinstance(prompt_template, list):
            self.system_prompt_template: str = "\n".join(prompt_template)
        else:
            self.system_prompt_template: str = prompt_template

        if not all([self.name, self.system_prompt_template]):
            raise ValueError(f"Agent 定义文件缺少必要字段 (name, system_prompt_template): {data}")

class AgentDefinitionManager:
    """
    一个加载和管理智能体定义的单例类。
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentDefinitionManager, cls).__new__(cls)
            cls._instance._definitions: Dict[str, AgentDefinition] = {}
            cls._instance._load_definitions()
        return cls._instance

    def _load_definitions(self):
        """从 app/agents 目录加载所有 .json 文件。"""
        agents_dir = "app/agents"
        if not os.path.isdir(agents_dir):
            logging.warning(f"智能体定义目录未找到: {agents_dir}")
            return

        for filename in os.listdir(agents_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(agents_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        definition = AgentDefinition(data)
                        if definition.name in self._definitions:
                            logging.warning(f"重复的智能体名称: '{definition.name}' 在 {filename} 中。将被忽略。")
                            continue
                        self._definitions[definition.name] = definition
                        logging.info(f"成功加载智能体定义: {definition.name}")
                except (json.JSONDecodeError, ValueError, IOError) as e:
                    logging.error(f"加载智能体定义文件失败: {filepath} - {e}")

    def get_definition(self, name: str) -> Optional[AgentDefinition]:
        """根据名称获取一个智能体定义。"""
        return self._definitions.get(name)

    def list_definitions(self) -> List[AgentDefinition]:
        """列出所有已加载的智能体定义。"""
        return list(self._definitions.values())

# 创建一个单例供全局使用
agent_definition_manager = AgentDefinitionManager()