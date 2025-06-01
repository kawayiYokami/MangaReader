import json
import os
import requests
import time
from abc import ABC, abstractmethod

# 导入deep_translator库
from deep_translator import GoogleTranslator

# 确保 app/config 目录存在
CACHE_DIR = "app/config"
CACHE_FILE = os.path.join(CACHE_DIR, "translation_cache.json")


class BaseTranslator(ABC):
    """
    翻译器基类，定义了所有翻译器共有的方法和属性
    """

    def __init__(self):
        """
        初始化基础翻译器
        """
        self.cache = {}
        self._load_cache()

        # 确保缓存目录存在
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
            print(f"Created cache directory: {CACHE_DIR}")

    def _load_cache(self):
        """
        从缓存文件加载翻译缓存。
        如果文件不存在或解析失败，则初始化一个空缓存。
        """
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                print(f"Loaded cache from {CACHE_FILE}")
            except (IOError, json.JSONDecodeError) as e:
                print(
                    f"Error loading cache file {CACHE_FILE}: {e}. Starting with empty cache."
                )
                self.cache = {}
        else:
            print(f"Cache file not found at {CACHE_FILE}. Starting with empty cache.")
            self.cache = {}

    def _save_cache(self):
        """
        将当前翻译缓存保存到文件（优化性能，避免频繁保存）
        """
        # 避免频繁保存，每10次翻译保存一次
        if not hasattr(self, '_save_counter'):
            self._save_counter = 0
            
        self._save_counter += 1
        
        if self._save_counter % 10 == 0:
            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.cache, f, ensure_ascii=False, indent=4)
                # print(f"Saved cache to {CACHE_FILE}") # 频繁打印可能干扰，按需开启
            except IOError as e:
                print(f"Error saving cache file {CACHE_FILE}: {e}")
        else:
            # 设置定时器在程序空闲时保存
            if not hasattr(self, '_save_timer'):
                from threading import Timer
                self._save_timer = Timer(5.0, self._force_save_cache)
                self._save_timer.daemon = True
                self._save_timer.start()
                
    def _force_save_cache(self):
        """强制保存缓存"""
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=4)
            # print(f"Saved cache to {CACHE_FILE}")
        except IOError as e:
            print(f"Error saving cache file {CACHE_FILE}: {e}")
        finally:
            if hasattr(self, '_save_timer'):
                del self._save_timer

    @abstractmethod
    def _translate_text(self, text, target_lang):
        """
        实际执行翻译的抽象方法，需要由子类实现

        Args:
            text (str): 需要翻译的文本
            target_lang (str): 目标语言代码

        Returns:
            str: 翻译结果，如果失败则返回 None
        """
        pass

    def translate(self, text, target_lang="en"):
        """
        翻译给定的文本。首先检查缓存，如果缓存中没有，则调用API进行翻译。

        Args:
            text (str): 需要翻译的文本。
            target_lang (str): 目标语言代码 (e.g., "en", "zh")。

        Returns:
            str: 翻译结果。如果翻译失败，返回原始文本或错误提示。
        """
        # 清理文本中的特殊字符
        clean_text = self._clean_text(text)
        
        # 使用更健壮的缓存键生成方式
        translator_type = type(self).__name__.replace("Translator", "").replace("Deep", "")
        cache_key = self._generate_cache_key(translator_type, clean_text, target_lang)

        if cache_key in self.cache:
            print(f"Cache hit for '{clean_text}' -> {target_lang}")
            return self.cache[cache_key]
        else:
            print(f"Cache miss for '{clean_text}' -> {target_lang}. Calling API...")
            translated_text = self._translate_text(clean_text, target_lang)

            if translated_text is not None:
                self.cache[cache_key] = translated_text
                self._save_cache()  # 每次新的翻译成功后保存缓存
                print(f"Translated and cached: '{clean_text}' -> '{translated_text}'")
                return translated_text
            else:
                print(f"Translation failed for '{clean_text}'")
                return f"[Translation Failed: {clean_text}]"  # 或者返回原始文本

    def _clean_text(self, text):
        """清理文本中的特殊字符和多余空格"""
        if not text:
            return ""
        # 移除多余空格和换行
        cleaned = ' '.join(text.strip().split())
        # 移除控制字符
        cleaned = ''.join(c for c in cleaned if c.isprintable())
        return cleaned

    def _generate_cache_key(self, translator_type, text, target_lang):
        """生成更健壮的缓存键"""
        import hashlib
        key_data = f"{translator_type}::{text}::{target_lang}".encode('utf-8')
        return hashlib.sha256(key_data).hexdigest()


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
        print(f"ZhipuTranslator initialized with batch_size: {self.batch_size}")

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
        uncached_texts_map = {} # 用于存储未缓存文本及其在原始clean_texts中的索引
        
        for i, text in enumerate(clean_texts):
            cache_key = self._generate_cache_key("Zhipu", text, target_lang)
            if cache_key in self.cache:
                print(f"Cache hit for '{text}' -> {target_lang}")
                results[i] = self.cache[cache_key]
            else:
                # 使用原始索引作为键，确保后续能正确更新results列表
                uncached_texts_map[i] = text 
                # results[i] 保持 None，稍后更新或由末尾逻辑处理

        # 如果有未缓存的文本，进行分批翻译
        if uncached_texts_map:
            # 将字典转换为列表进行分批处理，同时保留原始索引
            uncached_items = list(uncached_texts_map.items()) # [(original_index, text), ...]
            
            num_batches = (len(uncached_items) + self.batch_size - 1) // self.batch_size
            print(f"Found {len(uncached_items)} uncached texts. Processing in {num_batches} batches of up to {self.batch_size} texts each...")

            for i in range(0, len(uncached_items), self.batch_size):
                current_batch_items = uncached_items[i:i + self.batch_size]
                
                batch_texts_to_translate = [item[1] for item in current_batch_items] # 提取文本
                batch_original_indices = [item[0] for item in current_batch_items] # 提取原始索引
                
                current_batch_number = i // self.batch_size + 1
                print(f"Translating batch {current_batch_number}/{num_batches} with {len(batch_texts_to_translate)} texts...")
                translated_sub_batch = self._translate_batch(batch_texts_to_translate, target_lang)
                
                if translated_sub_batch and len(translated_sub_batch) == len(batch_texts_to_translate):
                    for j, translated_text in enumerate(translated_sub_batch):
                        original_list_index = batch_original_indices[j] # 获取在 'results' 列表中的正确索引
                        original_text_for_cache = batch_texts_to_translate[j]

                        results[original_list_index] = translated_text
                        cache_key = self._generate_cache_key("Zhipu", original_text_for_cache, target_lang)
                        self.cache[cache_key] = translated_text
                        print(f"Translated and cached: '{original_text_for_cache}' -> '{translated_text}'")
                else:
                    print(f"Warning: Batch {current_batch_number}/{num_batches} translation failed or returned an_unexpected number of results.")
                    # 对于失败的批次，results中对应的条目将保持None
                
                # 在每个批次处理后（无论成功与否）添加延时，以控制API请求频率
                # 如果不是最后一个批次，则添加延时
                if current_batch_number < num_batches:
                    print(f"Waiting for 2 seconds before next batch to respect API rate limit (30 RPM)...")
                    time.sleep(2)


            # 所有批次处理完成后保存缓存
            self._save_cache()

        # 处理任何未能成功翻译的文本（即results中仍为None的条目）
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
        if not texts: # 如果传入空列表，直接返回空列表
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
            print(f"\n=== API Request ===")
            print("Headers:", {k: v if k != 'Authorization' else '[REDACTED]' for k, v in headers.items()})
            print("Payload:", json.dumps(payload, ensure_ascii=False, indent=2))
            
            # 发送请求
            response = requests.post(self.api_base_url, headers=headers, json=payload)
            
            # 记录响应信息
            print(f"\n=== API Response ===")
            print(f"Status Code: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            print(f"Response Content: {response.text[:1000]}...")  # 只打印前1000个字符避免过长
            
            # 检查是否返回敏感内容错误
            if response.status_code == 400:
                try:
                    error_json = response.json()
                    if error_json.get("error", {}).get("code") == "1301":
                        print("检测到敏感内容错误，切换到Google翻译...")
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
                    print(f"Google translation fallback failed: {e}")
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
                            print(f"Warning: Could not parse translation line: {line}")
                
                if len(translations) == len(texts):
                    return translations
                else:
                    print(f"Translation count mismatch. Expected {len(texts)}, got {len(translations)}.")
                    print(f"Complete translated content: {translated_content}")
                    return None
            else:
                print(f"API response did not contain expected 'choices' field.")
                print(f"Complete response: {json.dumps(result, ensure_ascii=False, indent=2)}")
                return None

        except requests.RequestException as e:
            print(f"\n=== API Error ===")
            print(f"Request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Error response content: {e.response.text}")
            return None
        except json.JSONDecodeError as e:
            print(f"\n=== JSON Parse Error ===")
            print(f"Failed to parse API response: {str(e)}")
            print(f"Raw response content: {response.text}")
            return None
        except Exception as e:
            print(f"\n=== Unexpected Error ===")
            print(f"An unexpected error occurred: {str(e)}")
            import traceback
            print(traceback.format_exc())
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
            print(f"Google translation failed: {e}")
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
            print(f"未知的翻译器类型: {translator_type}，使用Google翻译作为默认选项")
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
