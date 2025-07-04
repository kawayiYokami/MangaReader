# file: core/manga_translation/processor.py
import asyncio
import os
import numpy as np
from typing import List, Optional, Dict

from core.ocr.ocr_manager import OCRManager, OCRResult
from core.translation.translator import BaseTranslator
from core.manga.manga_text_replacer import MangaTextReplacer
from core.config import config
from core.harmonization_map_manager import HarmonizationMapManager
from utils import manga_logger as log

# 提示词现在由负责漫画翻译的业务层来定义，而不是通用的翻译器层。
MANGA_LLM_PROMPT = """
你是一位顶级的漫画翻译专家，精通日语和中文，尤其擅长处理口语化、生活化的对话。你的核心任务是产出**自然、流畅、符合人物性格和当前场景**的中文译文。你的目标语言是：**{target_lang_name}**。
{manga_title_context}
**任务要求:**
1.  **优先意译**: 忘掉生硬的直译。请深度理解原文的语境和情感，用地道的中文口语进行意译。
2.  **上下文关联**: 将所有文本块视为一个完整的对话场景，确保前后文逻辑通顺，风格一致。
3.  **修正OCR小错误**: 如果遇到少量明显不通顺的OCR识别错误，请根据上下文进行合理推断和修正。
4.  **保持简洁**: 漫画对话追求简洁有力，请避免啰嗦的翻译。
5.  **处理非翻译内容**: 只有当文本是**纯粹的、无任何翻译价值的乱码**（如'icationepost,aning'）、**单个重复的标点符号**（如'!!!!'）、或者**明确标示为特效词**（如'SFX_ドガァァ'）时，才可将其视为非翻译内容，并将 `translated` 设为 `false`。
6.  **必须翻译的内容**: **任何包含实际词义的短语、对话、感叹、甚至单个的词语（例如'まさか…', 'ん?', 'お茶ありとる'）**，都必须被视为需要翻译的内容，并将 `translated` 设为 `true`。即使译文和原文碰巧很像或完全一样（例如人名），只要它不是上述定义的“非翻译内容”，就**必须**将 `translated` 设为 `true`。

**输出格式要求 (非常重要):**
你必须返回一个单一的JSON对象。
- 这个JSON对象的**键 (key)** 必须是用户提供给你的**原始数字索引** (字符串格式)。
- 这个JSON对象的**值 (value)** 必须是一个包含两个字段的 **JSON 对象**:
    - `"translated"`: 一个布尔值。如果文本被翻译了，则为 `true`；如果文本未被翻译 (因为它是无意义的)，则为 `false`。
    - `"text"`: 字符串。如果 `translated` 为 `true`，则为译文；如果为 `false`，则为原始输入文本。

**示例:**
如果用户输入:
```json
{{
  "0": "お前はもう死んでいる。",
  "1": "一体どういうことだ？",
  "2": "SFX_ドガァァ",
  "3": "まさか…"
}}
```

你的输出必须是:
```json
{{
  "0": {{ "translated": true, "text": "你已经死了。" }},
  "1": {{ "translated": true, "text": "这到底是怎么回事？" }},
  "2": {{ "translated": false, "text": "SFX_ドガァァ" }},
  "3": {{ "translated": true, "text": "难道说…" }}
}}
```

**重要约束:**
- **不要改变键**: 绝对不要修改或遗漏任何用户提供的数字索引。
- **严格遵守格式**: 每个值都必须是包含 `translated` 和 `text` 字段的JSON对象。
- **纯JSON**: 你的回答**只能包含一个完整的JSON对象**，不要在JSON代码块前后添加任何额外的解释、介绍或总结。
"""


class MangaPageProcessor:
    """
    The core processing pipeline for translating a single or multiple manga pages.
    This class contains the logic migrated from the old ImageTranslator.
    It orchestrates OCR, text translation, and text replacement.
    """
    def __init__(
        self,
        ocr_manager: OCRManager,
        translator: BaseTranslator,
        text_replacer: MangaTextReplacer,
        harmonization_manager: HarmonizationMapManager
    ):
        """
        Initializes the processor with all necessary dependencies.
        
        Args:
            ocr_manager: An instance of OCRManager.
            translator: An instance of a class that inherits from BaseTranslator.
            text_replacer: An instance of MangaTextReplacer.
            harmonization_manager: An instance of HarmonizationMapManager.
        """
        self.ocr_manager = ocr_manager
        self.translator = translator
        self.text_replacer = text_replacer
        self.harmonization_manager = harmonization_manager
        self.cancel_event = asyncio.Event()

    def set_cancel_event(self, event: asyncio.Event):
        """Sets the cancellation event from an external source (like the service)."""
        self.cancel_event = event

    def reset(self):
        """Resets the cancellation flag for a new task."""
        self.cancel_event.clear()

    def _build_system_prompt(self, target_lang: str, manga_title: Optional[str] = None) -> str:
        """构建用于LLM翻译的系统提示词。"""
        lang_map = {"zh": "中文", "zh-cn": "中文", "en": "英文", "ja": "日文", "ko": "韩文"}
        target_lang_name = lang_map.get(target_lang.lower(), target_lang)

        manga_title_context = ""
        if manga_title:
            manga_title_context = f"**漫画标题上下文**: `{manga_title}`。请在翻译时参考这个标题，以确保术语和风格的一致性。\n"

        return MANGA_LLM_PROMPT.format(
            target_lang_name=target_lang_name,
            manga_title_context=manga_title_context
        )

    async def process_pages(self,
                              image_inputs: List[np.ndarray],
                              target_language: str = "zh",
                              manga_title: Optional[str] = None,
                              file_paths_for_cache: Optional[List[str]] = None,
                              page_nums_for_cache: Optional[List[int]] = None,
                              original_archive_paths_for_cache: Optional[List[Optional[str]]] = None
                             ) -> List[np.ndarray]:
        """
        Takes a list of raw image ndarray and returns a list of translated image ndarray.
        This is the main workflow method, adapted from batch_translate_images_optimized.
        """
        images_data = image_inputs

        try:
            log.debug("开始批量OCR识别...")
            all_structured_texts_per_page: List[List[OCRResult]] = []

            for i, img_data_item in enumerate(images_data):
                if self.cancel_event.is_set():
                    log.warning(f"🛑 在OCR阶段（页面 {i+1}）处理被取消。")
                    raise asyncio.CancelledError("Page processing was cancelled.")

                # 假设在需要时正确提供了缓存键
                ocr_results_page = await self.ocr_manager.recognize_image_data(
                    img_data_item,
                    file_path_for_cache=file_paths_for_cache[i] if file_paths_for_cache else None,
                    page_num_for_cache=page_nums_for_cache[i] if page_nums_for_cache else None,
                    original_archive_path=original_archive_paths_for_cache[i] if original_archive_paths_for_cache else None
                )
                
                filtered_results_page = self.ocr_manager.filter_numeric_and_symbols(ocr_results_page)
                filtered_results_page = [r for r in filtered_results_page if r.confidence >= config.ocr_confidence_threshold.value]
                structured_texts_page: List[OCRResult] = self.ocr_manager.get_structured_text(filtered_results_page)
                all_structured_texts_per_page.append(structured_texts_page)
                log.debug(f"页面 {i+1} OCR完成，找到 {len(structured_texts_page)} 个文本块。")

            unique_original_texts = set()
            for structured_texts_page_item in all_structured_texts_per_page:
                for item_ocr_result in structured_texts_page_item:
                    text = item_ocr_result.text.strip()
                    if text:
                        unique_original_texts.add(text)

            texts_to_translate_mapping = {}
            actual_texts_for_api = []
            
            log.debug("应用和谐化规则...")
            for original_text in unique_original_texts:
                harmonized_text = self.harmonization_manager.apply_mapping_to_text(original_text)
                texts_to_translate_mapping[original_text] = harmonized_text
                actual_texts_for_api.append(harmonized_text)
            
            log.debug(f"开始为 {len(actual_texts_for_api)} 个独立文本进行批量翻译...")
            
            system_prompt = self._build_system_prompt(target_language, manga_title)
            
            # 领域层（这里）负责打包和解包，这是正确的架构
            from core.translation.llm_prompt_handler import LLMPromptHandler
            prompt_handler = LLMPromptHandler(max_chars=80000)
            
            # 1. 打包文本为用户提示词块
            packed_user_prompts = prompt_handler.pack_texts(actual_texts_for_api)
            
            log.debug(f"已将 {len(actual_texts_for_api)} 个文本块打包成 {len(packed_user_prompts)} 个API请求。")

            # 2. 调用通用翻译器，传入打包好的用户提示词
            # translator现在返回一个从“打包的提示”到“包含LLM响应的TranslationResult”的映射
            packed_results_map = await self.translator.translate_batch(
                texts=packed_user_prompts,
                target_lang=target_language,
                cancel_flag=self.cancel_event,
                system_prompt=system_prompt
            )

            # 3. 解包从API收到的所有JSON响应
            llm_responses = [res.text for res in packed_results_map.values() if res.translated and res.text]
            translation_results_map = prompt_handler.unpack_results(llm_responses, actual_texts_for_api)

            # 将和谐化前的原始文本映射到最终的翻译结果
            final_translations_map = {}
            for original_text, harmonized_text in texts_to_translate_mapping.items():
                if harmonized_text in translation_results_map:
                    final_translations_map[original_text] = translation_results_map[harmonized_text]
                else:
                    # 确保即使在解包失败或部分失败时，也有一个回退
                    final_translations_map[original_text] = translation_results_map.get(
                        harmonized_text,
                        final_translations_map.get(original_text) # 检查是否已经有回退
                    )

            log.debug("批量翻译完成。开始页面内文本替换...")
            final_result_images: List[np.ndarray] = []
            
            for page_idx, (img_data_item, structured_texts_page_item) in enumerate(zip(images_data, all_structured_texts_per_page)):
                if self.cancel_event.is_set():
                    log.warning(f"🛑 在文本替换阶段（页面 {page_idx+1}）处理被取消。")
                    raise asyncio.CancelledError("Page processing was cancelled.")

                if not structured_texts_page_item:
                    final_result_images.append(img_data_item)
                    continue

                # MangaTextReplacer 现在需要接收新的 map 类型
                result_image_page = self.text_replacer.process_manga_image(
                    img_data_item,
                    structured_texts_page_item,
                    translation_map=final_translations_map, # 传递整个映射
                    target_language=target_language,
                    inpaint_background=True
                )
                final_result_images.append(result_image_page)
                
                page_identifier = f"页面 {page_idx+1}"
                if file_paths_for_cache and file_paths_for_cache[page_idx]:
                    page_identifier = f"文件 '{os.path.basename(file_paths_for_cache[page_idx])}' (页码 {page_idx+1})"
                log.debug(f"{page_identifier} 文本替换完成。")
            
            return final_result_images
        
        except asyncio.CancelledError:
            log.warning("捕获到取消请求。正在返回部分或空结果。")
            # 根据需求，可以返回目前已处理的内容，或者直接返回空。
            # 目前，重新引发异常，让服务层来处理它。
            raise
        except Exception as e:
            log.error(f"处理页面时发生意外错误: {e}", exc_info=True)
            raise RuntimeError(f"处理页面失败: {e}")

    async def process_page_for_diagnostics(self,
                                           image_input: np.ndarray,
                                           target_language: str = "zh",
                                           manga_title: Optional[str] = None,
                                           ) -> Dict:
        """
        为诊断目的处理单个页面，返回所有中间结果。
        此方法将大部分业务逻辑集中于此，供诊断服务器等工具调用。
        """
        # 1. OCR
        log.debug("诊断模式：开始OCR...")
        ocr_results: List[OCRResult] = await self.ocr_manager.recognize_image_data(image_input)
        filtered_results = self.ocr_manager.filter_numeric_and_symbols(ocr_results)
        # 在诊断模式下，我们可能希望看到所有结果，所以暂时不过滤置信度
        # filtered_results = [r for r in filtered_results if r.confidence >= config.ocr_confidence_threshold.value]
        structured_ocr_results = self.ocr_manager.get_structured_text(filtered_results)
        log.debug(f"诊断模式：OCR完成，找到 {len(structured_ocr_results)} 个文本块。")

        # 2. 翻译
        translation_map = {}
        if not structured_ocr_results:
            log.debug("诊断模式：未找到文本，跳过翻译。")
        else:
            # 和谐化处理
            log.debug("诊断模式：开始和谐化处理...")
            unique_texts = {res.text.strip() for res in structured_ocr_results if res.text.strip()}
            texts_to_translate_mapping = {text: self.harmonization_manager.apply_mapping_to_text(text) for text in unique_texts}
            actual_texts_for_api = sorted(list(set(texts_to_translate_mapping.values())))

            if not actual_texts_for_api:
                log.debug("诊断模式：和谐化后无实际需要翻译的文本。")
            else:
                # 打包
                log.debug(f"诊断模式：打包 {len(actual_texts_for_api)} 条文本...")
                from core.translation.llm_prompt_handler import LLMPromptHandler
                prompt_handler = LLMPromptHandler(max_chars=80000)
                packed_user_prompts = prompt_handler.pack_texts(actual_texts_for_api)
                log.debug(f"诊断模式：打包完成，生成 {len(packed_user_prompts)} 个API请求。")

                # 翻译
                system_prompt = self._build_system_prompt(target_language, manga_title)
                packed_results_map = await self.translator.translate_batch(
                    texts=packed_user_prompts,
                    target_lang=target_language,
                    cancel_flag=self.cancel_event,
                    system_prompt=system_prompt
                )

                # 解包
                log.debug("诊断模式：解包API响应...")
                llm_responses = [res.text for res in packed_results_map.values() if res.translated and res.text]
                unpacked_results_map = prompt_handler.unpack_results(llm_responses, actual_texts_for_api)

                # 构建最终的原文到译文映射
                for original_text, harmonized_text in texts_to_translate_mapping.items():
                    if harmonized_text in unpacked_results_map:
                        translation_map[original_text] = unpacked_results_map[harmonized_text]
                    else:
                        from core.data_models import TranslationResult
                        translation_map[original_text] = TranslationResult(text=original_text, translated=False)
        
        log.debug("诊断模式：翻译流程完成。")

        # 3. 文本替换
        log.debug("诊断模式：开始文本替换...")
        replaced_image = self.text_replacer.process_manga_image(
            image_input.copy(),
            structured_ocr_results,
            translation_map,
            target_language,
            inpaint_background=True
        )
        log.debug("诊断模式：文本替换完成。")

        return {
            "structured_ocr_results": structured_ocr_results,
            "translation_map": translation_map,
            "replaced_image": replaced_image
        }
