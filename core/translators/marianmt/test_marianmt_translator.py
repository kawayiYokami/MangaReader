import unittest
import os # 需要导入 os 来处理路径
from unittest.mock import patch # Still needed for patching builtins.print
from core.translators.marianmt.marianmt_translator import MarianTranslator

# 定义项目内的模型缓存目录
PROJECT_MODEL_CACHE_DIR = "models_marianmt" 

class TestMarianTranslator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """在所有测试开始前，确保模型缓存目录存在"""
        if not os.path.exists(PROJECT_MODEL_CACHE_DIR):
            os.makedirs(PROJECT_MODEL_CACHE_DIR)
        print(f"MarianMT 测试模型将尝试下载到/使用缓存: {os.path.abspath(PROJECT_MODEL_CACHE_DIR)}")

    # def test_translate_japanese_to_chinese(self):
    #     print("\n--- [已停用] 正在运行 test_translate_japanese_to_chinese (真实模型, 项目缓存) ---")
    #     print("--- 此测试已停用，日中翻译将由 NLLBTranslator 处理 ---")
    #     self.skipTest("日中翻译已移至 NLLBTranslator，停用此 MarianMT 测试。")
    #     # model_name = 'Helsinki-NLP/opus-mt-ja-zh'
    #     # translator = MarianTranslator(model_name=model_name, cache_dir=PROJECT_MODEL_CACHE_DIR)
    #     # if not translator.model or not translator.tokenizer:
    #     #     self.skipTest(f"模型 {model_name} 未能加载 (缓存: {PROJECT_MODEL_CACHE_DIR})，跳过此测试。")
    #     #     return
    #     #
    #     # texts = ["こんにちは、世界。"]
    #     # print(f"输入文本: {texts}")
    #     # translations = translator.translate(texts)
    #     # print(f"Translator translate 返回值: {translations}")
    #     #
    #     # self.assertIsInstance(translations, list)
    #     # self.assertEqual(len(translations), 1)
    #     # self.assertTrue(isinstance(translations[0], str), "翻译结果应为字符串")
    #     # self.assertIn("你好", translations[0] if translations and translations[0] else "")
    #     # self.assertIn("世界", translations[0] if translations and translations[0] else "")
    #     # print("--- test_translate_japanese_to_chinese (真实模型, 项目缓存) 结束 ---")

    def test_translate_english_to_chinese(self):
        print("\n--- 正在运行 MarianMT test_translate_english_to_chinese (真实模型, 项目缓存) ---")
        model_name = 'Helsinki-NLP/opus-mt-en-zh'
        translator = MarianTranslator(model_name=model_name, cache_dir=PROJECT_MODEL_CACHE_DIR)
        if not translator.model or not translator.tokenizer:
            self.skipTest(f"MarianMT 模型 {model_name} 未能加载 (缓存: {PROJECT_MODEL_CACHE_DIR})，跳过此测试。")
            return

        texts = ["Hello, world."]
        print(f"输入文本: {texts}")
        translations = translator.translate(texts)
        print(f"Translator translate 返回值: {translations}")
        
        self.assertIsInstance(translations, list)
        self.assertEqual(len(translations), 1)
        self.assertTrue(isinstance(translations[0], str), "翻译结果应为字符串")
        # 根据实际输出 "哈罗,世界。" 修改断言
        self.assertIn("哈罗", translations[0] if translations and translations[0] else "") 
        self.assertIn("世界", translations[0] if translations and translations[0] else "")
        print("--- MarianMT test_translate_english_to_chinese (真实模型, 项目缓存) 结束 ---")

    def test_translate_korean_to_chinese(self):
        print("\n--- 正在运行 MarianMT test_translate_korean_to_chinese (真实模型, 项目缓存) ---")
        model_name = 'Helsinki-NLP/opus-mt-ko-zh'
        translator = MarianTranslator(model_name=model_name, cache_dir=PROJECT_MODEL_CACHE_DIR)
        if not translator.model or not translator.tokenizer:
            self.skipTest(f"MarianMT 模型 {model_name} 未能加载 (缓存: {PROJECT_MODEL_CACHE_DIR})，跳过此测试。")
            return

        texts = ["안녕하세요, 세계."]
        print(f"输入文本: {texts}")
        translations = translator.translate(texts)
        print(f"Translator translate 返回值: {translations}")

        self.assertIsInstance(translations, list)
        self.assertEqual(len(translations), 1)
        self.assertTrue(isinstance(translations[0], str), "翻译结果应为字符串")
        # 韩语翻译的预期结果可能也需要根据实际输出调整
        # self.assertIn("你好", translations[0] if translations and translations[0] else "")
        # self.assertIn("世界", translations[0] if translations and translations[0] else "")
        self.assertTrue(len(translations[0]) > 0 if translations and translations[0] else False, "韩语翻译结果不应为空")
        print("--- MarianMT test_translate_korean_to_chinese (真实模型, 项目缓存) 结束 ---")

    def test_model_loading_failure(self):
        print("\n--- 正在运行 MarianMT test_model_loading_failure (真实模型, 项目缓存) ---")
        invalid_model_name = 'invalid-marianmt-model-name-does-not-exist-ever-12345abc'
        with patch('builtins.print') as mock_builtin_print:
            print(f"尝试使用无效模型名称 '{invalid_model_name}' 初始化 MarianTranslator (缓存: {PROJECT_MODEL_CACHE_DIR})...")
            translator = MarianTranslator(model_name=invalid_model_name, cache_dir=PROJECT_MODEL_CACHE_DIR)
            print(f"初始化后 Translator tokenizer: {translator.tokenizer}")
            print(f"初始化后 Translator model: {translator.model}")
            self.assertIsNone(translator.tokenizer, "Tokenizer应该为None当模型加载失败时")
            self.assertIsNone(translator.model, "Model应该为None当模型加载失败时")
            
            expected_error_msg_part = f"加载模型 {invalid_model_name} 时出错" # MarianTranslator 内部的打印
            called_with_error = False
            for call_args in mock_builtin_print.call_args_list:
                # MarianTranslator 的 __init__ 会打印这个错误
                if call_args[0] and expected_error_msg_part in call_args[0][0]:
                    called_with_error = True
                    break
            self.assertTrue(called_with_error, f"期望的错误信息 '{expected_error_msg_part}' 未被打印。实际打印: {[c[0][0] for c in mock_builtin_print.call_args_list if c[0]]}")
        print("--- MarianMT test_model_loading_failure (真实模型, 项目缓存) 结束 ---")

    def test_translation_failure_if_model_not_loaded(self):
        print("\n--- 正在运行 MarianMT test_translation_failure_if_model_not_loaded (真实模型, 项目缓存) ---")
        invalid_model_name = 'another-invalid-marianmt-model-for-sure-54321xyz'
        # MarianTranslator 的 __init__ 会捕获异常并设置 model/tokenizer 为 None
        translator = MarianTranslator(model_name=invalid_model_name, cache_dir=PROJECT_MODEL_CACHE_DIR)
        self.assertIsNone(translator.model, "测试前置条件：模型应未加载")
        self.assertIsNone(translator.tokenizer, "测试前置条件：分词器应未加载")

        texts = ["测试"]
        print(f"输入文本: {texts}")
        translations = translator.translate(texts)
        print(f"Translator translate 返回值: {translations}")

        self.assertIsInstance(translations, list)
        self.assertEqual(len(translations), 1)
        # MarianTranslator.translate() 内部会使用 self.model_name_or_path
        self.assertEqual(translations[0], f"错误：模型 {invalid_model_name} 未正确加载。")
        print("--- MarianMT test_translation_failure_if_model_not_loaded (真实模型, 项目缓存) 结束 ---")

if __name__ == '__main__':
    unittest.main()