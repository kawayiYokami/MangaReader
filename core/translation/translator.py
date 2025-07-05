# core/translation/translator.py
import json
import asyncio
import requests
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging

from core.core_cache.cache_factory import get_cache_factory_instance
from core.core_cache.cache_interface import CacheInterface
from .llm_prompt_handler import LLMPromptHandler
from ..data_models import TranslationResult


class BaseTranslator(ABC):
    """所有翻译器的抽象基类。"""

    def __init__(self):
        self.cache: CacheInterface = get_cache_factory_instance().get_manager("translation")

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        cleaned = ' '.join(text.strip().split())
        return ''.join(c for c in cleaned if c.isprintable())

    @abstractmethod
    async def _translate_batch_api(
        self, texts: List[str], target_lang: str, cancel_flag: Optional[asyncio.Event], system_prompt: Optional[str] = None
    ) -> Dict[str, TranslationResult]:
        """
        批量文本的实际API调用实现。
        每个具体的翻译器类都必须实现此方法。
        它应该返回一个将原始文本映射到其 TranslationResult 对象的字典。
        在API失败时，它必须引发异常。
        """
        pass

    async def translate_batch(
        self, texts: List[str], target_lang: str, cancel_flag: Optional[asyncio.Event] = None, system_prompt: Optional[str] = None
    ) -> Dict[str, TranslationResult]:
        """
        带缓存的通用批量翻译逻辑。
        此方法由所有翻译器共享，返回从原始文本到TranslationResult的映射。
        """
        if not texts:
            return {}

        original_texts_map = {self._clean_text(text): text for text in texts}
        clean_texts = list(original_texts_map.keys())

        final_results: Dict[str, TranslationResult] = {}
        uncached_texts = []
        translator_name = self.__class__.__name__

        for text in clean_texts:
            cache_key = self.cache.generate_key(text=text, target_lang=target_lang, translator_type=translator_name)
            cached_data = self.cache.get(cache_key)
            if cached_data and isinstance(cached_data, dict):
                try:
                    # 从缓存的字典重建TranslationResult对象
                    final_results[text] = TranslationResult(**cached_data)
                except TypeError:
                    logging.warning(f"缓存中 '{text}' 的数据格式不正确，将重新翻译。数据: {cached_data}")
                    uncached_texts.append(text)
            else:
                uncached_texts.append(text)

        cached_count = len(final_results)
        if uncached_texts:
            logging.info(f"{translator_name}: 在缓存中找到 {cached_count} 条。正在翻译 {len(uncached_texts)} 条新文本。")

        if not uncached_texts:
            return {original_texts_map[clean]: result for clean, result in final_results.items()}

        try:
            if cancel_flag and cancel_flag.is_set():
                raise asyncio.CancelledError("翻译任务在API调用前被取消。")

            api_results = await self._translate_batch_api(uncached_texts, target_lang, cancel_flag, system_prompt)

            for text, result in api_results.items():
                if not isinstance(result, TranslationResult):
                    logging.error(f"API为文本 '{text}' 返回了无效的类型: {type(result)}。已跳过。")
                    final_results[text] = TranslationResult(text=text, translated=False)
                    continue

                final_results[text] = result
                # 将新的、包含更丰富信息的结果对象转换为字典后再存入缓存
                cache_key = self.cache.generate_key(text=text, target_lang=target_lang, translator_type=translator_name)
                self.cache.set(key=cache_key, data=result.to_dict(), is_sensitive=False)

        except Exception as e:
            logging.error(f"{translator_name} API调用失败: {e}", exc_info=True)
            # 对于失败的API调用，将未缓存的文本视为未翻译
            for text in uncached_texts:
                if text not in final_results:
                     final_results[text] = TranslationResult(text=text, translated=False)

        # 构建最终的映射，确保所有原始文本都有一个结果
        # 注意：这里的 't' 是原始文本，'self._clean_text(t)' 是清理后的文本
        return {t: final_results.get(self._clean_text(t), TranslationResult(text=t, translated=False)) for t in texts}


class ZhipuTranslator(BaseTranslator):
    """使用智谱（GLM）API的翻译器。"""

    def __init__(self, api_key: str, model: str = "glm-4-flash"):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.api_base_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        logging.debug(f"ZhipuTranslator已使用模型 {self.model} 初始化")

    @staticmethod
    def list_models(api_key: str, **kwargs) -> List[str]:
        # 智谱的API不提供模型列表接口，因此返回一个硬编码的列表
        logging.warning("Zhipu `list_models` is a placeholder and returns a fixed list.")
        return ["glm-4-flash", "glm-4", "glm-3-turbo"]

    async def _translate_batch_api(
        self, texts: List[str], target_lang: str, cancel_flag: Optional[asyncio.Event], system_prompt: Optional[str] = None
    ) -> Dict[str, TranslationResult]:
        if not system_prompt:
            raise ValueError("LLM翻译器需要一个系统提示词。")
        
        results: Dict[str, TranslationResult] = {}
        for packed_prompt in texts:
            if cancel_flag and cancel_flag.is_set():
                raise asyncio.CancelledError("翻译任务被取消。")

            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            
            # 方案验证成功：将用户提示词封装在Markdown代码块中
            content_with_markdown = f"```json\n{packed_prompt}\n```"
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content_with_markdown}
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            }

            loop = asyncio.get_running_loop()
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.post(
                        self.api_base_url,
                        headers=headers,
                        json=payload, # 使用 `json` 参数自动处理序列化
                        timeout=45
                    )
                )
                response.raise_for_status()
                response_json = response.json()
                # 返回的文本是LLM生成的JSON字符串，由上层业务逻辑解包
                translated_content_str = response_json["choices"][0]["message"]["content"]
                results[packed_prompt] = TranslationResult(text=translated_content_str, translated=True)
            except Exception as e:
                logging.error(f"调用智谱API时出错: {e}", exc_info=True)
                results[packed_prompt] = TranslationResult(text=packed_prompt, translated=False)
        
        return results


class OpenAITranslator(BaseTranslator):
    """使用OpenAI（GPT）API的翻译器。"""
    def __init__(self, api_key: str, model: str = "gpt-4o", api_base_url: Optional[str] = None):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.api_base_url = api_base_url or "https://api.openai.com/v1"
        logging.debug(f"OpenAITranslator已使用模型 {self.model} 和基础URL {self.api_base_url} 初始化")

    @staticmethod
    def list_models(api_key: str, api_base_url: Optional[str] = None) -> List[str]:
        if not api_key: raise ValueError("列出OpenAI模型需要API密钥。")
        url = f"{(api_base_url or 'https://api.openai.com/v1').rstrip('/')}/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            return sorted([m['id'] for m in data.get('data', []) if 'gpt' in m['id'] and 'instruct' not in m['id']], reverse=True)
        except Exception as e:
            logging.error(f"获取OpenAI模型失败：{e}", exc_info=True)
            raise ValueError(f"连接到OpenAI API失败：{e}")

    async def _translate_batch_api(
        self, texts: List[str], target_lang: str, cancel_flag: Optional[asyncio.Event], system_prompt: Optional[str] = None
    ) -> Dict[str, TranslationResult]:
        if not system_prompt:
            raise ValueError("LLM翻译器需要一个系统提示词。")

        api_url = f"{self.api_base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        results: Dict[str, TranslationResult] = {}

        for packed_prompt in texts:
            if cancel_flag and cancel_flag.is_set():
                raise asyncio.CancelledError("翻译任务被取消。")

            # 方案验证成功：将用户提示词封装在Markdown代码块中
            content_with_markdown = f"```json\n{packed_prompt}\n```"
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content_with_markdown}
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            }

            # --- 增加详细日志 ---
            logging.debug(f"即将发送到 OpenAI API 的 Payload (请求体):\n{json.dumps(payload, indent=2, ensure_ascii=False)}")
            
            loop = asyncio.get_running_loop()
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.post(
                        api_url,
                        headers=headers,
                        json=payload, # 使用 `json` 参数自动处理序列化
                        timeout=45
                    )
                )
                response.raise_for_status()
                response_json = response.json()

                # --- 增加详细日志 ---
                logging.debug(f"从 OpenAI API 收到的原始响应:\n{json.dumps(response_json, indent=2, ensure_ascii=False)}")
                
                translated_content_str = response_json["choices"][0]["message"]["content"]
                results[packed_prompt] = TranslationResult(text=translated_content_str, translated=True)
            except Exception as e:
                logging.error(f"调用OpenAI API时出错: {e}", exc_info=True)
                results[packed_prompt] = TranslationResult(text=packed_prompt, translated=False)
        
        return results


class GeminiTranslator(BaseTranslator):
    """使用谷歌Gemini API的翻译器。"""
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.api_base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        logging.debug(f"GeminiTranslator已使用模型 {self.model} 初始化")

    @staticmethod
    def list_models(api_key: str, **kwargs) -> List[str]:
        if not api_key: raise ValueError("列出Gemini模型需要API密钥。")
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return sorted([m['name'].replace('models/', '') for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])])
        except Exception as e:
            logging.error(f"获取Gemini模型失败：{e}", exc_info=True)
            raise ValueError(f"连接到Gemini API失败：{e}")

    async def _translate_batch_api(
        self, texts: List[str], target_lang: str, cancel_flag: Optional[asyncio.Event], system_prompt: Optional[str] = None
    ) -> Dict[str, TranslationResult]:
        if not system_prompt:
            raise ValueError("LLM翻译器需要一个系统提示词。")

        api_url = f"{self.api_base_url}/{self.model}:generateContent?key={self.api_key}"
        headers = {'Content-Type': 'application/json'}
        results: Dict[str, TranslationResult] = {}
        
        # Gemini API的特定JSON结构
        generation_config = {"temperature": 0.2, "response_mime_type": "application/json"}
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        for packed_prompt in texts:
            if cancel_flag and cancel_flag.is_set():
                raise asyncio.CancelledError("翻译任务被取消。")

            # 方案验证成功：将用户提示词封装在Markdown代码块中
            content_with_markdown = f"```json\n{packed_prompt}\n```"

            payload = {
                "contents": [
                    # Gemini API的系统提示词是作为独立部分发送的
                    {"parts": [{"text": system_prompt}]},
                    {"parts": [{"text": content_with_markdown}]}
                ],
                "generationConfig": generation_config,
                "safetySettings": safety_settings
            }

            loop = asyncio.get_running_loop()
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.post(
                        api_url,
                        headers=headers,
                        json=payload, # 使用 `json` 参数自动处理序列化
                        timeout=60
                    )
                )
                response.raise_for_status()
                response_json = response.json()
                translated_content_str = response_json["candidates"][0]["content"]["parts"][0]["text"]
                results[packed_prompt] = TranslationResult(text=translated_content_str, translated=True)
            except Exception as e:
                logging.error(f"调用Gemini API时出错: {e}", exc_info=True)
                results[packed_prompt] = TranslationResult(text=packed_prompt, translated=False)
        
        return results


class TranslatorFactory:
    """
    一个支持延迟加载和实例缓存的翻译器工厂。
    在初始化时接收所有配置，但只在首次请求时创建翻译器实例。
    """
    def __init__(self, **kwargs):
        self.configs = kwargs
        self._instances: Dict[str, BaseTranslator] = {}

    def get_translator(self, translator_type: str) -> BaseTranslator:
        """根据类型获取翻译器实例，如果不存在则创建并缓存。"""
        if translator_type not in self._instances:
            logging.info(f"翻译器 '{translator_type}' 不在缓存中。正在创建新实例...")
            translator = self._create_translator(translator_type)
            self._instances[translator_type] = translator
        
        return self._instances[translator_type]

    def _create_translator(self, translator_type: str) -> BaseTranslator:
        """根据类型创建新的翻译器实例。"""
        if translator_type == "智谱":
            api_key = self.configs.get("zhipu_api_key")
            model = self.configs.get("zhipu_model")
            if not api_key: raise ValueError("智谱翻译器需要API密钥。")
            return ZhipuTranslator(api_key=api_key, model=model or "glm-4-flash")

        elif translator_type == "OpenAI":
            api_key = self.configs.get("openai_api_key")
            model = self.configs.get("openai_model")
            api_base_url = self.configs.get("openai_api_base_url")
            if not api_key: raise ValueError("OpenAI翻译器需要API密钥。")
            return OpenAITranslator(api_key=api_key, model=model or "gpt-4o", api_base_url=api_base_url)

        elif translator_type == "Gemini":
            api_key = self.configs.get("gemini_api_key")
            model = self.configs.get("gemini_model")
            if not api_key: raise ValueError("Gemini翻译器需要API密钥。")
            return GeminiTranslator(api_key=api_key, model=model or "gemini-1.5-flash")

        else:
            raise ValueError(f"未知的翻译器类型: {translator_type}")
