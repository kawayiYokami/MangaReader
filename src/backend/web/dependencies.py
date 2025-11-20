"""
依赖注入模块

此模块的唯一职责是创建和提供应用程序范围内的单例实例，
以解决模块间的循环导入问题。
"""

from src.backend.web.core_interface import CoreInterface
import logging

# 在模块加载时创建全局单例实例
logging.info("正在创建 CoreInterface 全局单例...")
core_interface = CoreInterface()
logging.info(f"CoreInterface 全局单例已创建，实例 ID: {id(core_interface)}")

def get_interface() -> CoreInterface:
    """
    依赖注入函数，简单地返回已创建的全局单例。
    """
    return core_interface