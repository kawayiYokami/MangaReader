import json
import os
import requests
import time
from abc import ABC, abstractmethod
from utils import manga_logger as log # 添加了日志记录器
from core.cache_factory import get_cache_factory_instance # 添加
from core.cache_interface import CacheInterface # 添加

# 导入deep_translator库
from deep_translator import GoogleTranslator

# 此处不再需要 CACHE_DIR 和 CACHE_FILE，因为 TranslationCacheManager 处理自己的路径。

class BaseTranslator(ABC):
    """
    翻译器基类，定义了所有翻译器共有的方法和属性
    """

    def __init__(self):
        """
        初始化基础翻译器
        """
        self.translation_cache_manager: CacheInterface = get_cache_factory_instance().get_manager("translation")
        # self.cache 和 _load_cache() 已移除，由 TranslationCacheManager 管理
        # 旧的 CACHE_DIR 逻辑也已移除。

    # _load_cache, _save_cache, _force_save_cache 已移除。
    # 缓存现在由 TranslationCacheManager 处理。

    @abstractmethod
    def _translate_text(self, text: str, target_lang: str) -> str | None: # 添加了类型提示
        """
        实际执行翻译的抽象方法，需要由子类实现

        Args:
            text (str): 需要翻译的文本
            target_lang (str): 目标语言代码

        Returns:
            str: 翻译结果，如果失败则返回 None
        """
        pass

    def translate(self, text: str, target_lang: str ="en") -> str: # 添加了类型提示
        """
        翻译给定的文本。首先检查缓存，如果缓存中没有，则调用API进行翻译。

        Args:
            text (str): 需要翻译的文本。
            target_lang (str): 目标语言代码 (e.g., "en", "zh")。

        Returns:
            str: 翻译结果。如果翻译失败，返回原始文本或错误提示。
        """
        if not text: # 提前处理空输入
            return ""

        clean_text = self._clean_text(text)
        if not clean_text: # 如果清理后得到空字符串
            return ""

        translator_name = self.__class__.__name__.replace("Translator", "").replace("Deep", "")

        # 使用缓存管理器的 generate_key 方法
        cache_key = self.translation_cache_manager.generate_key(
            original_text=clean_text,
            target_lang=target_lang,
            translator_type=translator_name
        )

        cached_translation = self.translation_cache_manager.get(cache_key)
        if cached_translation is not None:
            log.debug(f"缓存命中: '{clean_text[:30]}...' -> {target_lang} 使用 {translator_name}")
            return cached_translation
        else:
            log.debug(f"缓存未命中: '{clean_text[:30]}...' -> {target_lang} 使用 {translator_name}。调用API...")
            translated_text = self._translate_text(clean_text, target_lang)

            if translated_text is not None:
                self.translation_cache_manager.set(cache_key, translated_text)
                log.debug(f"已翻译并缓存: '{clean_text[:30]}...' -> '{translated_text[:30]}...'")
                return translated_text
            else:
                log.warning(f"翻译失败: '{clean_text[:30]}...' 使用 {translator_name}")
                return f"[Translation Failed: {clean_text}]"

    def _clean_text(self, text: str) -> str: # 添加了类型提示
        """清理文本中的特殊字符和多余空格"""
        if not text:
            return ""
        cleaned = ' '.join(text.strip().split())
        cleaned = ''.join(c for c in cleaned if c.isprintable())
        return cleaned

    # _generate_cache_key 已移除，因为它现在由 TranslationCacheManager 处理。

class ZhipuTranslator(BaseTranslator):
    """
    使用智谱AI API进行翻译的翻译器
    """

    def __init__(self, api_key, model="glm-4-flash-250414"):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.api_base_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        self.batch_size = 20
        log.debug(f"智谱翻译器已初始化，批量大小: {self.batch_size}")

    def translate_batch(self, texts, target_lang="en"):
        """
        批量翻译文本列表。会先检查缓存，对未缓存的文本进行批量翻译。
        恢复分批逻辑，使用 self.batch_size，并加入频率控制。

        Args:
            texts (list[str]): 需要翻译的文本列表
            target_lang (str): 目标语言代码 (e.g., "en", "zh")

        Returns:
            list[str]: 翻译结果列表，与输入文本列表顺序对应
        """
        if not texts:
            return []

        # 清理文本
        clean_texts = [self._clean_text(text) for text in texts]

        # 检查缓存
        results = [None] * len(clean_texts) # 初始化结果列表
        uncached_texts_map = {}

        translator_name = self.__class__.__name__.replace("Translator", "").replace("Deep", "")

        for i, text in enumerate(clean_texts):
            if not text: # 清理后跳过空字符串
                results[i] = "" # 为原始为空/不可打印的文本设置空字符串
                continue

            cache_key = self.translation_cache_manager.generate_key(
                original_text=text,
                target_lang=target_lang,
                translator_type=translator_name
            )
            cached_translation = self.translation_cache_manager.get(cache_key)
            if cached_translation is not None:
                log.debug(f"批量缓存命中: '{text[:30]}...' -> {target_lang}")
                results[i] = cached_translation
            else:
                uncached_texts_map[i] = text

        if uncached_texts_map:
            uncached_items = list(uncached_texts_map.items())

            num_batches = (len(uncached_items) + self.batch_size - 1) // self.batch_size
            log.info(f"发现 {len(uncached_items)} 条未缓存文本进行批量翻译。将在 {num_batches} 批次中处理...")

            for i_batch_start in range(0, len(uncached_items), self.batch_size):
                current_batch_items = uncached_items[i_batch_start : i_batch_start + self.batch_size]
                batch_texts_to_translate = [item[1] for item in current_batch_items]
                batch_original_indices = [item[0] for item in current_batch_items]

                current_batch_number = i_batch_start // self.batch_size + 1
                log.info(f"正在翻译批次 {current_batch_number}/{num_batches}，共 {len(batch_texts_to_translate)} 条文本...")

                # 此调用应在内部处理 API 调用
                translated_sub_batch = self._translate_batch(batch_texts_to_translate, target_lang)

                if translated_sub_batch and len(translated_sub_batch) == len(batch_texts_to_translate):
                    for j, translated_text_item in enumerate(translated_sub_batch):
                        original_list_index = batch_original_indices[j]
                        original_text_for_cache = batch_texts_to_translate[j]

                        results[original_list_index] = translated_text_item
                        # 现在，缓存这个成功翻译的条目
                        current_cache_key = self.translation_cache_manager.generate_key(
                            original_text=original_text_for_cache,
                            target_lang=target_lang,
                            translator_type=translator_name
                        )
                        self.translation_cache_manager.set(current_cache_key, translated_text_item)
                        log.debug(f"批量翻译并缓存: '{original_text_for_cache[:30]}...' -> '{translated_text_item[:30]}...'")
                else:
                    log.warning(f"批次 {current_batch_number}/{num_batches} 翻译失败或返回结果数量异常。")

                if current_batch_number < num_batches:
                    log.info(f"等待 2 秒后进行下一批次...")
                    time.sleep(2)

            # 此处不再调用 _save_cache；TranslationCacheManager 会立即或按自己的计划保存。

        # 最终处理结果
        final_results = []
        for i, result_text in enumerate(results):
            if result_text is not None:
                final_results.append(result_text)
            else:
                # 对于翻译失败或缓存未命中的文本（且API调用也失败的）
                final_results.append(f"[Translation Failed: {clean_texts[i]}]")

        return final_results

    def _translate_batch(self, texts, target_lang):
        """
        调用智谱AI API进行批量翻译 (一次API调用处理传入的所有texts)

        Args:
            texts (list[str]): 需要翻译的文本列表
            target_lang (str): 目标语言代码

        Returns:
            list[str]: 翻译结果列表，如果API调用失败或解析错误则返回None
        """
        # 如果传入空列表，直接返回空列表
        if not texts:
            return []

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        lang_map = {
            "zh": "中文",
            "zh-cn": "中文",
            "en": "英文",
            "ja": "日文",
            "ko": "韩文",
            "fr": "法文",
            "de": "德文",
            "es": "西班牙文",
            "ru": "俄文"
        }

        target_lang_name = lang_map.get(target_lang.lower(), target_lang)

        # 构建带有序号的文本列表
        numbered_texts = [f"{i+1}. {text}" for i, text in enumerate(texts)]
        texts_content = "\n".join(numbered_texts)

        system_prompt = (
            f"你是一个专业的翻译专家。请将以下编号文本准确翻译成{target_lang_name}。\n"
            f"要求：\n"
            f"1. 保持原文的语气和风格，如果出现人名要注意统一人名，使用信达雅的人名翻译\n"
            f"2. 确保翻译准确自然，如果出现敏感词汇，不必紧张，使用隐晦的方式表达\n"
            f"3. 按原有编号顺序返回翻译结果\n"
            f"4. 只返回翻译结果，不要添加任何解释\n"
            f"5. 每行以编号开头，格式如：1. 译文"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": texts_content},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
        }

        try:
            # 记录请求信息
            log.debug(f"=== API 请求 ===")
            log.debug(f"Headers: {{k: v if k != 'Authorization' else '[REDACTED]' for k, v in headers.items()}}")
            log.debug(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")

            # 发送请求
            response = requests.post(self.api_base_url, headers=headers, json=payload)

            # 记录响应信息
            log.debug(f"=== API 响应 ===")
            log.debug(f"状态码: {response.status_code}")
            log.debug(f"响应头: {dict(response.headers)}")
            # 只打印前1000个字符避免过长
            log.debug(f"响应内容: {response.text[:1000]}...")

            # 检查是否返回敏感内容错误
            if response.status_code == 400:
                try:
                    error_json = response.json()
                    if error_json.get("error", {}).get("code") == "1301":
                        log.warning("检测到敏感内容错误，切换到Google翻译...")
                        # 使用Google翻译作为后备
                        google_translator = GoogleDeepTranslator()
                        translations = []
                        for text in texts:
                            translated = google_translator._translate_text(text, target_lang)
                            if translated:
                                translations.append(translated)
                            else:
                                raise Exception("Google translation failed")
                        return translations if len(translations) == len(texts) else None
                except Exception as e:
                    log.error(f"Google 翻译回退失败: {e}")
                    return None

            # 处理响应
            response.raise_for_status()
            result = response.json()

            if result and result.get("choices"):
                translated_content = result["choices"][0]["message"]["content"].strip()

                # 解析返回的编号文本
                translations = []
                for line in translated_content.split('\n'):
                    line = line.strip()
                    if line and line[0].isdigit():
                        parts = line.split('.', 1)
                        if len(parts) > 1:
                            translation = parts[1].strip()
                            translations.append(translation)
                        else:
                            log.warning(f"无法解析翻译行: {line}")

                if len(translations) == len(texts):
                    return translations
                else:
                    log.warning(f"翻译数量不匹配。预期 {len(texts)}，实际 {len(translations)}。")
                    log.warning(f"完整的翻译内容: {translated_content}")
                    return None
            else:
                log.warning(f"API 响应未包含预期的 'choices' 字段。")
                log.warning(f"完整的响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
                return None

        except requests.RequestException as e:
            # === API Error ===
            log.error(f"=== API 错误 ===")
            log.error(f"请求失败: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                log.error(f"错误响应内容: {e.response.text}")
            return None
        except json.JSONDecodeError as e:
            # === JSON Parse Error ===
            log.error(f"=== JSON 解析错误 ===")
            log.error(f"解析 API 响应失败: {str(e)}")
            log.error(f"原始响应内容: {response.text}")
            return None
        except Exception as e:
            # === Unexpected Error ===
            log.error(f"=== 未知错误 ===")
            log.error(f"发生未知错误: {str(e)}")
            import traceback
            log.error(traceback.format_exc())
            return None

    def _translate_text(self, text, target_lang):
        """单个文本翻译，通过调用批量翻译实现"""
        # 保持此方法，因为它被基类的 translate 方法调用
        results = self.translate_batch([text], target_lang)
        # translate_batch 返回列表，即使只有一个元素
        if results and results[0] and not results[0].startswith("[Translation Failed:"):
            return results[0]
        return None


class GoogleDeepTranslator(BaseTranslator):
    """
    使用deep_translator库的Google翻译API进行翻译
    """

    def __init__(self, api_key=None):
        """
        初始化Google翻译器

        Args:
            api_key (str, optional): Google API密钥，免费版可不提供
        """
        super().__init__()
        self.api_key = api_key

    def _translate_text(self, text, target_lang):
        """
        使用Google翻译API进行翻译

        Args:
            text (str): 需要翻译的文本
            target_lang (str): 目标语言代码

        Returns:
            str: 翻译结果，如果失败则返回None
        """
        try:
            # 标准化语言代码
            if target_lang.lower() == "zh":
                target_lang = "zh-CN"
            elif target_lang.lower() == "en":
                target_lang = "en"

            # 使用GoogleTranslator进行翻译
            translator = GoogleTranslator(source="auto", target=target_lang)
            translated_text = translator.translate(text)
            return translated_text

        except Exception as e:
            log.error(f"Google 翻译失败: {e}")
            return None


# 创建翻译器工厂类
class TranslatorFactory:
    """
    翻译器工厂类，用于创建不同类型的翻译器实例
    """

    @staticmethod
    def create_translator(translator_type, api_key=None, model=None, **kwargs):
        """
        创建指定类型的翻译器实例

        Args:
            translator_type (str): 翻译器类型
            api_key (str, optional): API密钥
            model (str, optional): 模型名称

        Returns:
            BaseTranslator: 翻译器实例
        """
        if translator_type == "智谱":
            return ZhipuTranslator(api_key=api_key, model=model or "glm-4-flash-250414")
        elif translator_type == "Google":
            return GoogleDeepTranslator(api_key=api_key)
        else:
            # 默认使用Google翻译
            log.warning(f"未知的翻译器类型: {translator_type}，使用Google翻译作为默认选项")
            return GoogleDeepTranslator()


# 为了向后兼容，保留原来的Translator类名，但实际上是ZhipuTranslator的别名
Translator = ZhipuTranslator


# --- 如何使用 ---
if __name__ == "__main__":
    # 示例：使用智谱AI翻译器
    YOUR_ZHIPU_API_KEY = "YOUR_API_KEY"  # 请替换为你的真实API Key

    if YOUR_ZHIPU_API_KEY == "YOUR_API_KEY":
        print("请将代码中的 'YOUR_API_KEY' 替换为你的智谱AI API Key。")
        # 使用不需要API 密钥的Google翻译作为演示
        translator = TranslatorFactory.create_translator("Google")
    else:
        # 使用智谱AI翻译器
        translator = TranslatorFactory.create_translator("智谱", api_key=YOUR_ZHIPU_API_KEY)

    # 第一次翻译 (会调用API并缓存)
    text1 = "你好，世界！"
    translated1 = translator.translate(text1, target_lang="en")
    print(f"翻译 '{text1}' -> English: {translated1}")

    print("-" * 20)
    time.sleep(1)  # 稍作等待，模拟不同时间调用

    # 第二次翻译相同的文本 (会从缓存读取)
    translated2 = translator.translate(text1, target_lang="en")
    print(f"再次翻译 '{text1}' -> English: {translated2}")  # 应该会显示 Cache hit

    print("-" * 20)
    time.sleep(1)

    # 翻译新的文本 (会调用API并缓存)
    text2 = "人工智能很有趣。"
    translated3 = translator.translate(text2, target_lang="fr")  # 翻译成法语
    print(f"翻译 '{text2}' -> French: {translated3}")

    print("-" * 20)
    time.sleep(1)

    # 再次翻译新的文本 (会从缓存读取)
    translated4 = translator.translate(text2, target_lang="fr")
    print(f"再次翻译 '{text2}' -> French: {translated4}")  # 应该会显示 Cache hit

    print("-" * 20)
    time.sleep(1)

    # 翻译回中文 (会调用API并缓存，因为是新的目标语言)
    text3 = "Hello, how are you?"
    translated5 = translator.translate(text3, target_lang="zh")
    print(f"翻译 '{text3}' -> Chinese: {translated5}")

    # 退出程序时，最新的缓存已经保存到 app/config/translation_cache.json 文件中了
