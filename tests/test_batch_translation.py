import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

import numpy as np

# 确保所有相关模块都被导入
from core.translation.image_translator import ImageTranslator
from core.data_models import OCRResult
from core.core_cache.translation_cache_manager import TranslationCacheManager
from core.core_cache.ocr_cache_manager import OcrCacheManager

# 使用真实实例，只模拟最底层的 I/O
class TestBatchTranslationIntegration(unittest.TestCase):

    @patch('core.translation.image_translator.OCRManager')
    @patch('core.translation.translator.GoogleDeepTranslator')
    def setUp(self, mock_google_translator, mock_ocr_manager):
        """
        测试环境设置：
        - 将 ImageTranslator 配置为使用 Google 翻译。
        - 模拟 OCRManager 的构造函数，以完全控制其行为。
        - 模拟 Google 翻译器。
        """
        
        # 1. 模拟 OCR 管理器
        # mock_ocr_manager 现在代表 OCRManager 类
        # .return_value 是当 OCRManager() 被调用时返回的实例
        self.mock_ocr_manager_instance = mock_ocr_manager.return_value
        # 现在我们在这个模拟实例上配置 recognize_image_data 和 get_structured_text 方法
        mock_ocr_results = [
            OCRResult(bbox=[[0, 0], [10, 0], [10, 10], [0, 10]], text='你好', confidence=0.95),
            OCRResult(bbox=[[20, 20], [30, 20], [30, 30], [20, 30]], text='世界', confidence=0.95)
        ]
        self.mock_ocr_manager_instance.recognize_image_data = AsyncMock(return_value=mock_ocr_results)
        # 确保 get_structured_text 也被模拟，直接返回结果，绕过内部逻辑
        self.mock_ocr_manager_instance.get_structured_text.return_value = mock_ocr_results
    
    
        # 2. 模拟 Google 翻译器
        self.mock_google_translator_instance = mock_google_translator.return_value
        self.mock_google_translator_instance.translate.return_value = "Translated Text"
    
        # --- 创建真实的实例 ---
        # 使用 :memory: 数据库进行缓存
        with patch('core.core_cache.translation_cache_manager.DB_PATH', ":memory:"), \
             patch('core.core_cache.ocr_cache_manager.DB_PATH', ":memory:"):
            
            # 当 ImageTranslator 内部调用 OCRManager() 时，它将获得我们的模拟实例
            self.image_translator = ImageTranslator(translator_type="Google")

    def test_batch_translation_flow_with_empty_cache(self):
        """
        测试使用 Google 翻译的端到端批量翻译流程（空缓存场景）。
        """
        # --- 测试数据 ---
        images = [np.zeros((100, 100, 3), dtype=np.uint8)]

        # --- 执行 ---
        results = asyncio.run(self.image_translator.batch_translate_images_optimized(images))

        # --- 断言 ---
        # 1. 验证 OCR 相关方法在我们的模拟实例上被调用
        self.mock_ocr_manager_instance.recognize_image_data.assert_called_once()
        self.mock_ocr_manager_instance.get_structured_text.assert_called()
        
        # 2. 验证 Google 翻译器被调用
        # 因为缓存为空，并且模拟的 OCR 结果非空
        self.mock_google_translator_instance.translate.assert_called()

        # 3. 验证最终的图像结果
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], np.ndarray)

        print("\n✅ Test 'test_batch_translation_flow_with_empty_cache' passed.")
        print("   - Verified real ImageTranslator instance works correctly.")
        print("   - Verified OCR and Translation APIs are called on empty cache.")
        print("   - Verified final result is a valid image array.")

    def tearDown(self):
        """
        移除 tearDown 逻辑以避免 SQLite 线程错误。
        由于测试使用 :memory: 数据库，连接和数据会在测试进程结束时自动清理，
        无需手动关闭连接，从而规避了在不同线程中创建和关闭连接的问题。
        """
        pass


if __name__ == '__main__':
    unittest.main()