import json
import os
import requests
import time

# 确保 app/config 目录存在
CACHE_DIR = "app/config"
CACHE_FILE = os.path.join(CACHE_DIR, "translation_cache.json")

class Translator:
    """
    一个使用智谱AI API 进行翻译并带有缓存功能的类。
    """

    def __init__(self, api_key, model="glm-4-flash"):
        """
        初始化 Translator 类。

        Args:
            api_key (str): 智谱AI 的 API Key。
            model (str): 用于翻译的智谱AI 模型名称 (e.g., "glm-4-flash", "glm-4")。
        """
        self.api_key = api_key
        self.model = model
        self.cache = {}
        self._load_cache()
        self.api_base_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions" # 智谱AI 通用对话补全 API

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
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                print(f"Loaded cache from {CACHE_FILE}")
            except (IOError, json.JSONDecodeError) as e:
                print(f"Error loading cache file {CACHE_FILE}: {e}. Starting with empty cache.")
                self.cache = {}
        else:
            print(f"Cache file not found at {CACHE_FILE}. Starting with empty cache.")
            self.cache = {}

    def _save_cache(self):
        """
        将当前翻译缓存保存到文件。
        """
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=4)
            # print(f"Saved cache to {CACHE_FILE}") # 频繁打印可能干扰，按需开启
        except IOError as e:
            print(f"Error saving cache file {CACHE_FILE}: {e}")

    def _call_zhipu_api(self, text, target_lang):
        """
        调用智谱AI API 进行翻译。

        Args:
            text (str): 需要翻译的文本。
            target_lang (str): 目标语言代码 (e.g., "en" for English, "zh" for Chinese)。

        Returns:
            str: 翻译结果，如果失败则返回 None。
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 使用 chat completions API 通过 prompt 来实现翻译功能
        # 可以根据目标语言调整 prompt
        system_prompt = f"你是一个专业的翻译引擎，请将用户提供的内容翻译成{target_lang}。"
        # 为了鲁棒性，可以考虑更详细的prompt，比如指定输入语言，处理多段文本等

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            # 可以添加其他参数，如 temperature, top_p 等
        }

        try:
            response = requests.post(self.api_base_url, headers=headers, json=payload)
            response.raise_for_status() # 检查HTTP状态码，如果不是2xx则抛出异常

            result = response.json()

            # 解析API响应，提取翻译结果
            if result and result.get("choices"):
                translated_text = result["choices"][0]["message"]["content"].strip()
                return translated_text
            else:
                print(f"API response did not contain expected format: {result}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return None
        except KeyError as e:
             print(f"API response parsing error: Missing key {e}. Response: {result}")
             return None


    def translate(self, text, target_lang="en"):
        """
        翻译给定的文本。首先检查缓存，如果缓存中没有，则调用API进行翻译。

        Args:
            text (str): 需要翻译的文本。
            target_lang (str): 目标语言代码 (e.g., "en", "zh")。

        Returns:
            str: 翻译结果。如果翻译失败，返回原始文本或错误提示。
        """
        # 使用一个唯一的键来标识缓存条目，包含原文和目标语言
        cache_key = f"{text}::{target_lang}"

        if cache_key in self.cache:
            print(f"Cache hit for '{text}' -> {target_lang}")
            return self.cache[cache_key]
        else:
            print(f"Cache miss for '{text}' -> {target_lang}. Calling API...")
            translated_text = self._call_zhipu_api(text, target_lang)

            if translated_text is not None:
                self.cache[cache_key] = translated_text
                self._save_cache() # 每次新的翻译成功后保存缓存
                print(f"Translated and cached: '{text}' -> '{translated_text}'")
                return translated_text
            else:
                print(f"Translation failed for '{text}'")
                return f"[Translation Failed: {text}]" # 或者返回原始文本

# --- 如何使用 ---
if __name__ == "__main__":
    # 替换为你的智谱AI API Key
    # 建议从环境变量或配置文件读取，这里为了演示直接写死，实际应用中请避免
    YOUR_ZHIPU_API_KEY = "YOUR_API_KEY" # <-- 请替换为你的真实API Key

    if YOUR_ZHIPU_API_KEY == "YOUR_API_KEY":
        print("请将代码中的 'YOUR_API_KEY' 替换为你的智谱AI API Key。")
    else:
        # 示例用法
        translator = ZhipuTranslator(api_key=YOUR_ZHIPU_API_KEY)

        # 第一次翻译 (会调用API并缓存)
        text1 = "你好，世界！"
        translated1 = translator.translate(text1, target_lang="en")
        print(f"翻译 '{text1}' -> English: {translated1}")

        print("-" * 20)
        time.sleep(1) # 稍作等待，模拟不同时间调用

        # 第二次翻译相同的文本 (会从缓存读取)
        translated2 = translator.translate(text1, target_lang="en")
        print(f"再次翻译 '{text1}' -> English: {translated2}") # 应该会显示 Cache hit

        print("-" * 20)
        time.sleep(1)

        # 翻译新的文本 (会调用API并缓存)
        text2 = "人工智能很有趣。"
        translated3 = translator.translate(text2, target_lang="fr") # 翻译成法语
        print(f"翻译 '{text2}' -> French: {translated3}")

        print("-" * 20)
        time.sleep(1)

        # 再次翻译新的文本 (会从缓存读取)
        translated4 = translator.translate(text2, target_lang="fr")
        print(f"再次翻译 '{text2}' -> French: {translated4}") # 应该会显示 Cache hit

        print("-" * 20)
        time.sleep(1)

        # 翻译回中文 (会调用API并缓存，因为是新的目标语言)
        text3 = "Hello, how are you?"
        translated5 = translator.translate(text3, target_lang="zh")
        print(f"翻译 '{text3}' -> Chinese: {translated5}")

        # 退出程序时，最新的缓存已经保存到 app/config/translation_cache.json 文件中了