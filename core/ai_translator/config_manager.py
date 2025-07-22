# file: core/ai_translator/config_manager.py
"""
API 配置管理器
===============

负责从项目的主配置文件中加载和管理所有的 API 配置。
采用直接读取 app/config/config.json 的方式，与 core.config 解耦。
"""
from typing import Dict, List, Optional
from .data_models import APIConfig
import logging
from core.config import config # 导入全局配置对象

# from utils.manga_logger import logging # TODO: 切换为项目统一的 logger

class APIConfigManager:
    """
    一个用于加载、解析和提供 API 配置的管理器。
    """
    def __init__(self):
        """
        初始化配置管理器。
        在初始化时，它会尝试从主配置文件加载所有可用的 API 配置。
        """
        self._configs: Dict[str, APIConfig] = {}
        self._load_configs_from_source()

    def get_config(self, name: str) -> Optional[APIConfig]:
        """
        根据名称获取一个已加载的 API 配置。

        Args:
            name (str): 要获取的配置的唯一名称。

        Returns:
            Optional[APIConfig]: 如果找到，则返回 APIConfig 对象；否则返回 None。
        """
        return self._configs.get(name)

    def list_configs(self) -> List[APIConfig]:
        """
        列出所有已加载的 API 配置。

        Returns:
            List[APIConfig]: 所有 APIConfig 对象的列表。
        """
        return list(self._configs.values())

    def reload(self):
        """
        清空并重新加载所有配置。
        """
        logging.info("正在重新加载 AI 翻译器 API 配置...")
        self._configs.clear()
        self._load_configs_from_source()
        logging.info("AI 翻译器 API 配置已重新加载。")

    def _load_configs_from_source(self):
        """
        从 core.config 框架加载并解析所有 API 配置。
        这是一个私有方法，应在初始化时调用。
        """
        logging.info("正在通过 core.config 加载 AI 翻译器 API 配置...")
        
        try:
            raw_configs: List[Dict] = config.api_translator_configs.value

            # 只要值是一个列表（即使是空列表），就认为是有效的。
            if not isinstance(raw_configs, list):
                logging.warning(f"在 core.config 中 'api_translator_configs' 的格式不是列表，而是 {type(raw_configs)}。")
                return

            for settings in raw_configs:
                if not isinstance(settings, dict):
                    logging.error(f"API 配置项格式无效，应为一个字典。已跳过: {settings}")
                    continue
                
                config_name = settings.get("name")
                if not config_name:
                    logging.error(f"API 配置项缺少 'name' 字段。已跳过: {settings}")
                    continue

                try:
                    # 为了灵活性，我们手动映射字段
                    config_obj = APIConfig(
                        name=settings.get("name"),
                        api_type=settings.get("api_type"),
                        api_key=settings.get("api_key"),
                        model=settings.get("model"),
                        temperature=settings.get("temperature", 0.2),
                        max_tokens=settings.get("max_tokens", 4096),
                        api_base_url=settings.get("api_base_url"),
                        request_interval_ms=settings.get("request_interval_ms", 1000)
                    )
                    self._configs[config_name] = config_obj
                    logging.info(f"成功加载 AI 翻译器配置: {config_name}")
                except TypeError as e:
                    logging.error(f"加载 AI 翻译器配置 '{config_name}' 失败: 缺少或无效的参数 - {e}")
        
        except Exception as e:
            logging.error(f"从 core.config 加载 AI 翻译器配置时发生未知错误: {e}", exc_info=True)

# 创建一个单例供模块内部使用
api_config_manager = APIConfigManager()