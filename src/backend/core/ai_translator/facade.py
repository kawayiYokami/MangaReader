# file: core/ai_translator/facade.py
"""
AI 翻译器统一门面
====================

本模块提供了 `ai_translator` 的唯一公共入口。
"""
import asyncio
from typing import List, Optional

from src.backend.utils.manga_logger import logging
from .data_models import TranslationResult, TranslationStatus, ImageTranslationResult, TaskType
from .request_dispatcher import RequestDispatcher

class AITranslatorFacade:
    """
    一个为外部调用者提供简洁、统一接口的门面类。
    它隐藏了内部的调度、执行、限流等复杂逻辑。
    """
    def __init__(self):
        """
        初始化翻译器门面。
        """
        self._dispatcher: Optional[RequestDispatcher] = None
        logging.info("AI 翻译器门面已初始化。")

    def _get_dispatcher(self) -> RequestDispatcher:
        """
        获取或创建调度器实例。
        """
        if self._dispatcher is None:
            self._dispatcher = RequestDispatcher()
            logging.info("Dispatcher 已创建。")
        return self._dispatcher

    async def close(self):
        """
        关闭翻译器资源。
        当前版本使用 openai 库，无需手动关闭。此方法保留以备将来扩展。
        """
        logging.info("AI 翻译器资源已释放。")
        await asyncio.sleep(0) # 保持 async 属性

    async def translate(
        self,
        texts: List[str],
        config_name: str,
        target_lang: str,
        agent_name: str = "manga_dialogue",
        manga_title: Optional[str] = None,
        mode: str = 'multi',
        special_prompt: Optional[str] = None
    ) -> List[TranslationResult]:
        """
        通用的文本翻译接口。
        """
        if not texts or not isinstance(texts, list):
            return []

        try:
            dispatcher = self._get_dispatcher()
            logging.info(f"收到文本翻译请求: Agent='{agent_name}', Config='{config_name}', Texts={len(texts)}")
            return await dispatcher.dispatch(
                agent_name=agent_name,
                config_name=config_name,
                task_type=TaskType.TEXT_TRANSLATION,
                # --- 传递给 Agent 的参数 ---
                texts=texts,
                mode=mode,
                target_lang=target_lang,
                manga_title=manga_title,
                special_prompt=special_prompt,
                original_texts=texts
            )
        except Exception as e:
            logging.error(f"文本翻译请求处理失败: {e}", exc_info=True)
            return [
                TranslationResult(
                    original_text=text,
                    translated_text="", # 修正：添加默认值
                    status=TranslationStatus.FAILURE,
                    error_message=str(e)
                ) for text in texts
            ]

    async def translate_image(
        self,
        *,
        images_data: List[bytes],
        config_name: str,
        agent_name: str,
        manga_path: str, # 新增，用于生成缓存键
        page_index: int, # 新增，用于生成缓存键
        target_lang: str, # 新增，用于生成缓存键
        **kwargs
    ) -> List[ImageTranslationResult]:
        """
        通用的图片翻译接口。
        它直接接收图片的字节数据，并通过 kwargs 传递所有其他动态参数。
        """
        if not images_data or not isinstance(images_data, list):
            return []

        # --- 缓存逻辑 (延迟导入) ---
        from src.backend.core.core_cache.cache_factory import get_cache_factory_instance
        from src.backend.core.core_cache.cache_key_generator import get_cache_key_generator
        
        cache_factory = get_cache_factory_instance()
        key_generator = get_cache_key_generator()
        cache_manager = cache_factory.get_manager("translation")

        master_key = key_generator.generate_master_key_for_path(manga_path)
        if not master_key:
            logging.warning(f"无法为 {manga_path} 生成 master_key，将跳过缓存。")
        else:
            cached_result = cache_manager.get(
                master_key,
                page_index=page_index
            )
            if cached_result and isinstance(cached_result, list):
                return cached_result

        # --- API 调用逻辑 ---
        try:
            dispatcher = self._get_dispatcher()
            logging.info(f"缓存未命中，发起图片翻译请求: Agent='{agent_name}', Config='{config_name}', Images={len(images_data)}")
            
            dispatch_params = {
                "agent_name": agent_name,
                "config_name": config_name,
                "task_type": TaskType.IMAGE_TRANSLATION,
                "images_data": images_data,
                "target_lang": target_lang,
            }
            dispatch_params.update(kwargs)

            results = await dispatcher.dispatch(**dispatch_params)

            # 如果成功，则写入缓存
            if master_key and results and results[0].status == TranslationStatus.SUCCESS:
                cache_manager.set(
                    master_key,
                    results,
                    page_index=page_index
                )

            return results
        except Exception as e:
            logging.error(f"图片翻译请求处理失败: {e}", exc_info=True)
            return [ImageTranslationResult(status=TranslationStatus.FAILURE, error_message=str(e)) for _ in range(len(images_data))]