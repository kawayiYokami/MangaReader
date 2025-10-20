# file: core/ai_translator/api_executor.py
"""
API 执行器 - OpenAI 库驱动版
==============================

本模块负责使用 openai 官方库与兼容 API 进行实际的异步交互。
"""
import asyncio
import copy
import json
from typing import Any, Dict, Optional, Tuple, Union, List

from openai import AsyncOpenAI, APIStatusError, APITimeoutError

from .data_models import APIConfig, TranslationResult, ImageTranslationResult
from .agents.base_agent import BaseAgent
from utils.manga_logger import logging

class APIExecutor:
    """
    一个通用的、由智能体驱动的 AI API 执行器。
    它使用 openai 库来处理底层的 API 调用。
    """
    def __init__(self):
        """
        初始化 API 执行器。
        注意：客户端实例将在每次调用时动态创建，以确保使用正确的 api_key 和 base_url。
        """
        pass

    async def execute(
        self,
        *,
        agent: BaseAgent,
        config: APIConfig,
        agent_name: str, # 新增
        **kwargs: Any
    ) -> Union[List[TranslationResult], List[ImageTranslationResult]]:
        """
        执行一次完整的、由智能体驱动的 AI 任务。
        """
        try:
            payload = agent.build_request_payload(config=config, **kwargs)
            response_data, error = await self._call_api_with_error_handling(payload, config)

            if error:
                return agent.parse_response({"error": {"message": error}}, **kwargs)

            response_dict = response_data.model_dump()
            try:
                # 尝试正常解析
                return agent.parse_response(response_dict, agent_name=agent_name, **kwargs)
            except Exception as parse_error:
                # 如果解析失败，记录错误，但将原始响应附加到错误结果中
                logging.error(f"解析 AI 响应时出错: {parse_error}", exc_info=False)
                error_payload = {
                    "error": {"message": f"Failed to parse AI response: {parse_error}"},
                    "raw_response": response_dict  # 附加原始响应
                }
                return agent.parse_response(error_payload, agent_name=agent_name, **kwargs)

        except Exception as e:
            logging.error(f"在 APIExecutor.execute 中发生意外错误: {e}", exc_info=True)
            return agent.parse_response({"error": {"message": str(e)}}, agent_name=agent_name, **kwargs)

    async def _call_api_with_error_handling(
        self, payload: Dict[str, Any], config: APIConfig
    ) -> Tuple[Optional[Any], Optional[str]]:
        """
        一个包装了重试和错误处理逻辑的 API 调用方法。
        """
        max_retries = 3
        retry_delay_seconds = 3
        last_error: Optional[str] = "Unknown error after all retries."

        # 为了日志记录，深度拷贝 payload 并移除图片数据
        log_payload = copy.deepcopy(payload)
        if 'messages' in log_payload:
            for message in log_payload.get('messages', []):
                if isinstance(message.get('content'), list):
                    # 创建一个新的 content 列表，只包含非图片部分
                    message['content'] = [part for part in message['content'] if part.get('type') != 'image_url']
        
        logging.debug(f"API Payload (excluding image data): {json.dumps(log_payload, ensure_ascii=False)}")

        # 动态创建客户端以使用正确的凭据
        base_url = config.api_base_url
        if base_url and not base_url.endswith(("/v1", "/v1/")):
            base_url = f"{base_url.rstrip('/')}/v1"

        client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=base_url
        )
        
        # 将 config 中的 max_tokens 添加到 payload
        if config.max_tokens:
            payload['max_tokens'] = config.max_tokens

        for attempt in range(max_retries):
            try:
                response = await client.chat.completions.create(**payload)
                logging.debug(f"API Response: {response.model_dump_json()}")
                return response, None # 成功

            except APIStatusError as e:
                last_error = f"API 响应错误 (状态码: {e.status_code}): {e.response.text}"
                logging.warning(f"API Status Error: {last_error}")
                retryable_status_codes = [502, 503, 504, 524]
                if e.status_code not in retryable_status_codes:
                    break
                
                logging.warning(f"API 调用失败 (尝试 {attempt + 1}/{max_retries})。将在 {retry_delay_seconds} 秒后重试...")
                if attempt + 1 < max_retries:
                    await asyncio.sleep(retry_delay_seconds)
            
            except APITimeoutError:
                last_error = "API 调用超时"
                logging.warning(f"{last_error} (尝试 {attempt + 1}/{max_retries})。将在 {retry_delay_seconds} 秒后重试...")
                if attempt + 1 < max_retries:
                    await asyncio.sleep(retry_delay_seconds)

            except Exception as e:
                last_error = f"未知网络或库错误: {e}"
                logging.error(f"{last_error} (尝试 {attempt + 1}/{max_retries})。将在 {retry_delay_seconds} 秒后重试...")
                if attempt + 1 < max_retries:
                    await asyncio.sleep(retry_delay_seconds)
        
        logging.error(f"API 调用在所有 {max_retries} 次重试后仍然失败。最终错误: {last_error}")
        return None, last_error