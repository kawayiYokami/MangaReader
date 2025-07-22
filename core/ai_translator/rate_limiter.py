# file: core/ai_translator/rate_limiter.py
"""
API 请求速率限制器
====================

本模块提供了一个速率限制器，用于控制对不同 API 配置的请求频率。
"""
import asyncio
import time
from typing import Dict
from collections import defaultdict
import logging
# from utils.manga_logger import logging # TODO: 切换为项目统一的 logger

class RateLimiter:
    """
    一个基于 API 配置名称的异步速率限制器。
    它能确保对同一个 API 端点的调用遵守其配置中定义的请求间隔。
    """
    def __init__(self):
        """
        初始化速率限制器。
        """
        # 存储每个 API 配置名称最后一次请求的时间戳
        self._last_request_times: Dict[str, float] = defaultdict(float)
        self._lock = asyncio.Lock()

    async def wait_for_token(self, config_name: str, interval_ms: int):
        """
        等待直到可以为指定的 API 配置执行下一次请求。

        Args:
            config_name (str): API 配置的唯一名称。
            interval_ms (int): 该配置要求的最小请求间隔（毫秒）。
        """
        async with self._lock:
            last_time = self._last_request_times[config_name]
            now = time.monotonic()
            elapsed = (now - last_time) * 1000  # 转换为毫秒

            if elapsed < interval_ms:
                wait_time_seconds = (interval_ms - elapsed) / 1000
                logging.debug(f"速率限制: 配置 '{config_name}' 需要等待 {wait_time_seconds:.2f} 秒。")
                await asyncio.sleep(wait_time_seconds)
            
            # 更新最后请求时间
            self._last_request_times[config_name] = time.monotonic()

# 创建一个单例供模块内部使用
rate_limiter = RateLimiter()