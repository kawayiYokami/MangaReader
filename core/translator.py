# core/translator.py
import json
import os
import requests
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional 
from utils import manga_logger as log 
from core.cache_factory import get_cache_factory_instance 
from core.cache_interface import CacheInterface 

# 导入deep_translator库
from deep_translator import GoogleTranslator

class BaseTranslator(ABC):
    def __init__(self):
        self.translation_cache_manager: CacheInterface = get_cache_factory_instance().get_manager("translation")

    @abstractmethod
    def _translate_text(self, text: str, target_lang: str) -> Optional[Dict[str, Any]]:
        """
        实际执行翻译的抽象方法。
        Returns: 一个包含 'text' 和 'is_sensitive' 的字典，或 None。
        """
        pass

    def translate(self, text: str, target_lang: str ="en") -> str:
        if not text: return ""
        clean_text = self._clean_text(text)
        if not clean_text: return ""

        translator_name = self.__class__.__name__.replace("Translator", "").replace("Deep", "")
        cache_key = self.translation_cache_manager.generate_key(
            original_text=clean_text, target_lang=target_lang, translator_type=translator_name
        )

        cached_result = self.translation_cache_manager.get(cache_key)

        if cached_result is not None and isinstance(cached_result, dict) and "text" in cached_result:
            if cached_result.get('is_sensitive', False):
                log.info(f"缓存命中但标记为敏感: '{clean_text[:30]}...' (键: {cache_key}). 将使用Google翻译尝试替换。")
                google_translator = GoogleDeepTranslator() 
                google_api_result = google_translator._translate_text(clean_text, target_lang) 

                if google_api_result and isinstance(google_api_result, dict) and "text" in google_api_result and google_api_result["text"]:
                    log.info(f"Google翻译成功替换敏感缓存: '{clean_text[:30]}...' -> '{google_api_result['text'][:30]}...'")
                    self.translation_cache_manager.set(
                        key=cache_key, 
                        data=google_api_result["text"], 
                        is_sensitive=False, 
                        original_text=clean_text
                    )
                    return google_api_result["text"]
                else:
                    log.warning(f"Google翻译替换敏感缓存失败 for '{clean_text[:30]}...'. 返回原始敏感缓存文本。")
                    return cached_result["text"] 
            else:
                log.debug(f"缓存命中 (不敏感): '{clean_text[:30]}...' -> {target_lang} 使用 {translator_name}")
                return cached_result["text"]
        else:
            log.debug(f"缓存未命中: '{clean_text[:30]}...' -> {target_lang} 使用 {translator_name}。调用API...")
            translation_api_result = self._translate_text(clean_text, target_lang) 

            if translation_api_result and isinstance(translation_api_result, dict) and "text" in translation_api_result:
                translated_text_api = translation_api_result["text"]
                is_sensitive = translation_api_result.get("is_sensitive", False)
                
                self.translation_cache_manager.set(
                    key=cache_key, 
                    data=translated_text_api, 
                    is_sensitive=is_sensitive,
                    original_text=clean_text
                )
                log.debug(f"已翻译并缓存: '{clean_text[:30]}...' -> '{translated_text_api[:30]}...'. 敏感: {is_sensitive}")
                return translated_text_api
            else:
                log.warning(f"翻译失败: '{clean_text[:30]}...' 使用 {translator_name}")
                return f"[Translation Failed: {clean_text}]"

    def _clean_text(self, text: str) -> str:
        if not text: return ""
        cleaned = ' '.join(text.strip().split())
        cleaned = ''.join(c for c in cleaned if c.isprintable())
        return cleaned

class ZhipuTranslator(BaseTranslator):
    def __init__(self, api_key, model="glm-4-flash-250414"):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.api_base_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        self.batch_size = 20
        log.debug(f"智谱翻译器已初始化，批量大小: {self.batch_size}")

    def translate_batch(self, texts: List[str], target_lang: str ="en") -> List[str]:
        if not texts: return []
        clean_texts = [self._clean_text(text) for text in texts]
        results = [None] * len(clean_texts)
        uncached_texts_map = {} 
        retry_with_zhipu_single_map = {} 
        google_translate_texts_map = {} 
        translator_name = "Zhipu"

        for i, text in enumerate(clean_texts):
            if not text:
                results[i] = ""
                continue

            cache_key = self.translation_cache_manager.generate_key(
                original_text=text, target_lang=target_lang, translator_type=translator_name
            )
            cached_result = self.translation_cache_manager.get(cache_key)

            if cached_result is not None and isinstance(cached_result, dict) and "text" in cached_result:
                if cached_result.get('is_sensitive', False):
                    log.info(f"批量缓存命中 (智谱键) 但标记为敏感: '{text[:30]}...'. 将尝试智谱单条翻译。")
                    retry_with_zhipu_single_map[i] = text 
                else:
                    log.debug(f"批量缓存命中 (智谱键, 不敏感): '{text[:30]}...'")
                    results[i] = cached_result["text"]
            else:
                log.debug(f"批量缓存未命中 (智谱): '{text[:30]}...'. 准备调用智谱API...")
                uncached_texts_map[i] = text
        
        if uncached_texts_map:
            uncached_items = list(uncached_texts_map.items())
            for i_batch_start in range(0, len(uncached_items), self.batch_size):
                current_batch_items = uncached_items[i_batch_start : i_batch_start + self.batch_size]
                batch_texts_to_translate = [item[1] for item in current_batch_items]
                batch_original_indices = [item[0] for item in current_batch_items]
                
                translated_sub_batch_results = self._translate_batch_api(batch_texts_to_translate, target_lang)
                
                if translated_sub_batch_results and len(translated_sub_batch_results) == len(batch_texts_to_translate):
                    for j, translated_item_or_signal in enumerate(translated_sub_batch_results):
                        original_list_index = batch_original_indices[j]
                        original_text_for_item = batch_texts_to_translate[j]
                        if isinstance(translated_item_or_signal, str) and translated_item_or_signal == "__USE_GOOGLE_TRANSLATOR__":
                            log.info(f"批量API指示 '{original_text_for_item[:30]}...' 敏感，将尝试智谱单条翻译。")
                            retry_with_zhipu_single_map[original_list_index] = original_text_for_item
                        elif isinstance(translated_item_or_signal, str):
                            results[original_list_index] = translated_item_or_signal
                            current_cache_key = self.translation_cache_manager.generate_key(
                                original_text=original_text_for_item, target_lang=target_lang, translator_type=translator_name
                            )
                            self.translation_cache_manager.set(
                                current_cache_key, translated_item_or_signal, is_sensitive=False, original_text=original_text_for_item
                            )
                        else: 
                            log.warning(f"批量API翻译失败 for '{original_text_for_item[:30]}...'. 将尝试智谱单条翻译。")
                            retry_with_zhipu_single_map[original_list_index] = original_text_for_item
                else: 
                    log.warning(f"智谱批量API调用失败 for sub-batch starting with '{batch_texts_to_translate[0][:30]}...'. 将对该批次所有文本尝试智谱单条翻译。")
                    for idx, text_to_retry_single in zip(batch_original_indices, batch_texts_to_translate):
                        retry_with_zhipu_single_map[idx] = text_to_retry_single
                
                if (i_batch_start // self.batch_size + 1) < ((len(uncached_items) + self.batch_size - 1) // self.batch_size): time.sleep(1)

        if retry_with_zhipu_single_map:
            log.info(f"开始对 {len(retry_with_zhipu_single_map)} 条文本进行智谱单条重试...")
            for original_list_idx, text_to_retry in retry_with_zhipu_single_map.items():
                if results[original_list_idx] is not None: continue 

                log.debug(f"智谱单条重试 for '{text_to_retry[:30]}...' (原索引: {original_list_idx})")
                single_translation_text = self.translate(text_to_retry, target_lang) # BaseTranslator.translate handles API and caching
                
                if not single_translation_text.startswith("[Translation Failed:"):
                    results[original_list_idx] = single_translation_text
                else: 
                    log.warning(f"智谱单条重试（通过 self.translate）最终失败 for '{text_to_retry[:30]}...'.")
                    results[original_list_idx] = single_translation_text 


        if google_translate_texts_map: 
            log.info(f"开始对 {len(google_translate_texts_map)} 条文本进行Google翻译 (translate_batch)...")
            google_items_to_translate = list(google_translate_texts_map.items())
            google_translator_instance = GoogleDeepTranslator()
            for original_list_idx, (text_to_google_translate, is_sensitive_reason) in google_items_to_translate:
                if results[original_list_idx] is not None: continue 

                google_translated_text = google_translator_instance.translate(text_to_google_translate, target_lang)
                
                if not google_translated_text.startswith("[Translation Failed:"):
                    results[original_list_idx] = google_translated_text
                    if is_sensitive_reason:
                        original_translator_cache_key = self.translation_cache_manager.generate_key(
                            original_text=text_to_google_translate, target_lang=target_lang, translator_type="Zhipu"
                        )
                        log.info(f"批量: 使用Google结果更新原Zhipu缓存键 '{original_translator_cache_key}' for '{text_to_google_translate[:30]}...', 标记为敏感: True")
                        self.translation_cache_manager.set(
                            original_translator_cache_key, google_translated_text, is_sensitive=True, original_text=text_to_google_translate
                        )
                else:
                    log.warning(f"批量: Google翻译最终失败 for '{text_to_google_translate[:30]}...'")
                    results[original_list_idx] = google_translated_text 

        final_results = [res if res is not None else f"[Translation Failed: {clean_texts[i]}]" for i, res in enumerate(results)]
        return final_results

    def _translate_batch_api(self, texts: List[str], target_lang: str) -> List[Optional[str]]:
        if not texts: return []
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        lang_map = {"zh": "中文", "zh-cn": "中文", "en": "英文", "ja": "日文", "ko": "韩文"} 
        target_lang_name = lang_map.get(target_lang.lower(), target_lang)
        
        system_prompt_content = (
            f"你是一个专业的翻译引擎。请将用户提供的每一行文本独立翻译成{target_lang_name}。"
            "严格按照原始文本的顺序逐行翻译，每行翻译结果占一行。"
            "不要添加任何额外的解释、编号、或者与翻译无关的内容。"
            "如果某行文本由于内容限制无法翻译，请针对该行明确输出特殊标记：[UNTRANSLATABLE_CONTENT]"
        )
        
        user_prompt_content = "\n".join(texts)

        messages = [
            {"role": "system", "content": system_prompt_content},
            {"role": "user", "content": user_prompt_content}
        ]
        payload = {"model": self.model, "messages": messages, "temperature": 0.1} 
        
        log.debug(f"智谱批量API请求 ({len(texts)}条): 模型={self.model}, 目标语言={target_lang_name}")

        try:
            response = requests.post(self.api_base_url, headers=headers, json=payload, timeout=45) 
            
            if response.status_code == 400:
                try:
                    error_json = response.json()
                    error_info = error_json.get("error", {})
                    log.warning(f"智谱API返回400错误: Code={error_info.get('code')}, Message={error_info.get('message')}")
                    if error_info.get("code") == "1301": 
                        log.warning("智谱API指示批量内容敏感 (1301)。")
                        return ["__USE_GOOGLE_TRANSLATOR__"] * len(texts)
                except json.JSONDecodeError:
                    log.error(f"智谱API返回400，但响应不是有效JSON: {response.text}")
                return [None] * len(texts) 

            response.raise_for_status() 
            
            result = response.json()
            if result and result.get("choices") and result["choices"][0].get("message"):
                translated_content = result["choices"][0]["message"]["content"].strip()
                translated_lines = translated_content.split('\n')
                
                if len(translated_lines) == len(texts):
                    processed_translations = []
                    for i, line in enumerate(translated_lines):
                        clean_line = line.strip()
                        if clean_line == "[UNTRANSLATABLE_CONTENT]":
                            log.warning(f"智谱API标记第 {i+1} 条文本 '{texts[i][:30]}...' 为不可翻译。")
                            processed_translations.append("__USE_GOOGLE_TRANSLATOR__") 
                        elif not clean_line: 
                            log.warning(f"智谱API返回第 {i+1} 条文本 '{texts[i][:30]}...' 的翻译为空。")
                            processed_translations.append(None)
                        else:
                            processed_translations.append(clean_line)
                    return processed_translations
                else:
                    log.warning(f"智谱批量翻译返回的行数 ({len(translated_lines)}) 与请求的文本数量 ({len(texts)}) 不匹配。")
                    log.debug(f"智谱原始输出:\n{translated_content}")
                    if len(texts) == 1 and len(translated_lines) >= 1:
                        log.info("单条文本批量请求，但返回多行，取第一行。")
                        first_line_clean = translated_lines[0].strip()
                        if first_line_clean == "[UNTRANSLATABLE_CONTENT]": return ["__USE_GOOGLE_TRANSLATOR__"]
                        return [first_line_clean if first_line_clean else None]
                    return [None] * len(texts) 
            else:
                log.warning(f"智谱API响应格式不符合预期: {result}")
                return [None] * len(texts)
        except requests.exceptions.Timeout:
            log.error(f"智谱批量API请求超时 ({len(texts)}条)。")
            return [None] * len(texts)
        except requests.exceptions.RequestException as e:
            log.error(f"智谱批量API请求失败 ({len(texts)}条): {e}")
            return [None] * len(texts)
        except json.JSONDecodeError as e:
            log.error(f"解析智谱API响应JSON失败: {e}. Response text: {response.text if 'response' in locals() else 'N/A'}")
            return [None] * len(texts)
        except Exception as e:
            log.error(f"智谱 _translate_batch_api 未知错误: {e}")
            return [None] * len(texts)

    def _translate_text(self, text: str, target_lang: str) -> Optional[Dict[str, Any]]:
        if not text: return None
        
        log.debug(f"单文本 (_translate_text): 调用智谱批量API翻译 '{text[:30]}...'")
        api_results = self._translate_batch_api([text], target_lang) 

        if not api_results or api_results[0] is None:
            log.warning(f"单文本: 智谱API翻译失败 for '{text[:30]}...'. 将使用Google翻译。")
            google_translator = GoogleDeepTranslator()
            google_result_dict = google_translator._translate_text(text, target_lang) 
            if google_result_dict and google_result_dict["text"]:
                return {"text": google_result_dict["text"], "is_sensitive": False} 
            return None 

        first_result = api_results[0]

        if first_result == "__USE_GOOGLE_TRANSLATOR__":
            log.warning(f"单文本: 智谱API指示 '{text[:30]}...' 敏感. 将使用Google翻译 (标记敏感).")
            google_translator = GoogleDeepTranslator()
            google_result_dict = google_translator._translate_text(text, target_lang) 
            if google_result_dict and google_result_dict["text"]:
                return {"text": google_result_dict["text"], "is_sensitive": True}
            return None 
        
        if isinstance(first_result, str):
            log.info(f"单文本: 智谱API翻译成功 '{text[:30]}...' -> '{first_result[:30]}...'")
            return {"text": first_result, "is_sensitive": False}
        
        log.error(f"单文本: 未知智谱API结果类型 for '{text[:30]}...': {first_result}")
        return None

class GoogleDeepTranslator(BaseTranslator):
    def __init__(self, api_key=None):
        super().__init__()
        self.api_key = api_key 

    def _translate_text(self, text: str, target_lang: str) -> Optional[Dict[str, Any]]:
        if not text: return None
        try:
            dt_target_lang = target_lang
            if target_lang.lower() in ["zh", "zh-cn", "zh-hans"]: dt_target_lang = "zh-CN"
            elif target_lang.lower() in ["zh-tw", "zh-hant"]: dt_target_lang = "zh-TW"
            
            log.debug(f"GoogleDeepTranslator: Translating '{text[:30]}...' to {dt_target_lang}")
            translator = GoogleTranslator(source="auto", target=dt_target_lang)
            translated_text = translator.translate(text)
            
            if translated_text:
                log.debug(f"GoogleDeepTranslator: Success '{text[:30]}...' -> '{translated_text[:30]}...'")
                return {"text": translated_text, "is_sensitive": False} 
            else:
                log.warning(f"GoogleDeepTranslator: Translation returned empty for '{text[:30]}...'")
                return None
        except Exception as e:
            log.error(f"GoogleDeepTranslator: Error translating '{text[:30]}...': {e}")
            return None

class TranslatorFactory:
    @staticmethod
    def create_translator(translator_type, api_key=None, model=None, **kwargs):
        if translator_type == "智谱":
            if not api_key: raise ValueError("ZhipuTranslator requires an API key.")
            return ZhipuTranslator(api_key=api_key, model=model or "glm-4-flash-250414")
        elif translator_type == "Google":
            return GoogleDeepTranslator(api_key=api_key) 
        else:
            raise ValueError(f"Unknown translator type: {translator_type}")
