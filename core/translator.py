import json
import os
import requests
import time
from abc import ABC, abstractmethod

# 导入deep_translator库
from deep_translator import (
    GoogleTranslator,
    MicrosoftTranslator,
    DeeplTranslator,
    PonsTranslator,
    LingueeTranslator,
    MyMemoryTranslator,
    YandexTranslator,
    PapagoTranslator,
    BaiduTranslator,
    LibreTranslator,
    QcriTranslator
)

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
        将当前翻译缓存保存到文件。
        """
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=4)
            # print(f"Saved cache to {CACHE_FILE}") # 频繁打印可能干扰，按需开启
        except IOError as e:
            print(f"Error saving cache file {CACHE_FILE}: {e}")

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
        # 使用一个唯一的键来标识缓存条目，包含原文和目标语言
        cache_key = f"{text}::{target_lang}"

        if cache_key in self.cache:
            print(f"Cache hit for '{text}' -> {target_lang}")
            return self.cache[cache_key]
        else:
            print(f"Cache miss for '{text}' -> {target_lang}. Calling API...")
            translated_text = self._translate_text(text, target_lang)

            if translated_text is not None:
                self.cache[cache_key] = translated_text
                self._save_cache()  # 每次新的翻译成功后保存缓存
                print(f"Translated and cached: '{text}' -> '{translated_text}'")
                return translated_text
            else:
                print(f"Translation failed for '{text}'")
                return f"[Translation Failed: {text}]"  # 或者返回原始文本


class ZhipuTranslator(BaseTranslator):
    """
    使用智谱AI API进行翻译的翻译器
    """

    def __init__(self, api_key, model="glm-4-flash"):
        """
        初始化智谱翻译器

        Args:
            api_key (str): 智谱AI的API Key
            model (str): 使用的模型名称，默认为"glm-4-flash"
        """
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.api_base_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"  # 智谱AI通用对话补全API

    def _translate_text(self, text, target_lang):
        """
        调用智谱AI API进行翻译

        Args:
            text (str): 需要翻译的文本
            target_lang (str): 目标语言代码

        Returns:
            str: 翻译结果，如果失败则返回None
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 使用chat completions API通过prompt来实现翻译功能
        system_prompt = (
            f"你是一个专业的翻译引擎，请将用户提供的内容翻译成{target_lang}。"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
        }

        try:
            response = requests.post(self.api_base_url, headers=headers, json=payload)
            response.raise_for_status()  # 检查HTTP状态码

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


class DeeplTranslatorTranslator(BaseTranslator):
    """
    使用deep_translator库的DeeplTranslator API进行翻译
    """

    def __init__(self, api_key):
        """
        初始化DeeplTranslator翻译器

        Args:
            api_key (str): DeeplTranslator API密钥
        """
        super().__init__()
        self.api_key = api_key

    def _translate_text(self, text, target_lang):
        """
        使用DeeplTranslator API进行翻译

        Args:
            text (str): 需要翻译的文本
            target_lang (str): 目标语言代码

        Returns:
            str: 翻译结果，如果失败则返回None
        """
        try:
            # 标准化语言代码
            if target_lang.lower() == "zh":
                target_lang = "ZH"
            elif target_lang.lower() == "en":
                target_lang = "EN"

            # 使用DeeplTranslator进行翻译
            translator = DeeplTranslator(api_key=self.api_key, source="auto", target=target_lang)
            translated_text = translator.translate(text)
            return translated_text

        except Exception as e:
            print(f"DeeplTranslator translation failed: {e}")
            return None


class BaiduDeepTranslator(BaseTranslator):
    """
    使用deep_translator库的百度翻译API进行翻译
    """

    def __init__(self, app_id, app_key):
        """
        初始化百度翻译器

        Args:
            app_id (str): 百度翻译API的APP ID
            app_key (str): 百度翻译API的密钥
        """
        super().__init__()
        self.app_id = app_id
        self.app_key = app_key

    def _translate_text(self, text, target_lang):
        """
        使用百度翻译API进行翻译

        Args:
            text (str): 需要翻译的文本
            target_lang (str): 目标语言代码

        Returns:
            str: 翻译结果，如果失败则返回None
        """
        try:
            # 标准化语言代码
            if target_lang.lower() == "zh":
                target_lang = "zh"
            elif target_lang.lower() == "en":
                target_lang = "en"

            # 使用BaiduTranslator进行翻译
            translator = BaiduTranslator(
                app_id=self.app_id,
                app_key=self.app_key,
                source="auto",
                target=target_lang
            )
            translated_text = translator.translate(text)
            return translated_text

        except Exception as e:
            print(f"Baidu translation failed: {e}")
            return None


class MyMemoryDeepTranslator(BaseTranslator):
    """
    使用deep_translator库的MyMemory翻译API进行翻译
    """

    def __init__(self, email=None):
        """
        初始化MyMemory翻译器

        Args:
            email (str, optional): 用户邮箱，提供可增加免费额度
        """
        super().__init__()
        self.email = email

    def _translate_text(self, text, target_lang):
        """
        使用MyMemory翻译API进行翻译

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

            # 使用MyMemoryTranslator进行翻译
            translator_params = {
                "source": "auto",
                "target": target_lang
            }
            
            if self.email:
                translator_params["email"] = self.email
                
            translator = MyMemoryTranslator(**translator_params)
            translated_text = translator.translate(text)
            return translated_text

        except Exception as e:
            print(f"MyMemory translation failed: {e}")
            return None


# 创建翻译器工厂类
class TranslatorFactory:
    """
    翻译器工厂类，用于创建不同类型的翻译器实例
    """
    
    @staticmethod
    def create_translator(translator_type, api_key=None, model=None, app_id=None, app_key=None, email=None):
        """
        创建指定类型的翻译器实例
        
        Args:
            translator_type (str): 翻译器类型
            api_key (str, optional): API密钥
            model (str, optional): 模型名称
            app_id (str, optional): 应用ID
            app_key (str, optional): 应用密钥
            email (str, optional): 邮箱
            
        Returns:
            BaseTranslator: 翻译器实例
        """
        if translator_type == "智谱":
            return ZhipuTranslator(api_key=api_key, model=model or "glm-4-flash")
        elif translator_type == "Google":
            return GoogleDeepTranslator(api_key=api_key)
        elif translator_type == "DeeplTranslator":
            return DeeplTranslatorTranslator(api_key=api_key)
        elif translator_type == "百度":
            return BaiduDeepTranslator(app_id=app_id, app_key=app_key)
        elif translator_type == "MyMemory":
            return MyMemoryDeepTranslator(email=email)
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
        # 使用不需要API密钥的Google翻译作为演示
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
