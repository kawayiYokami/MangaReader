from core.translators.nllb_translator import NLLBTranslator

# 使用一个合适的缓存目录，这里我们假设项目根目录下有一个 'models_nllb_cache' 文件夹
# 或者使用 README 中提到的 'models_nllb_translator_test'
# 为确保路径正确，我们相对于此脚本文件定位缓存目录
# 假设脚本在 core/translators/ 目录下，模型缓存可以放在项目根目录下的 models_nllb_translator_test
import os
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir)) # 退两级到项目根目录
cache_directory = os.path.join(project_root, "models")

# 确保缓存目录存在，如果不存在则创建
if not os.path.exists(cache_directory):
    os.makedirs(cache_directory)
    print(f"Created cache directory: {cache_directory}")

try:
    translator = NLLBTranslator(cache_dir=cache_directory)

    individual_japanese_sentences = [
        "こんにちは、世界。",
        "これはテストです。",
        "ありがとうございます。"
    ]
    translated_chinese_sentences = translator.translate(individual_japanese_sentences)

    print("翻译结果:")
    for i, original_text in enumerate(individual_japanese_sentences):
        print(f"原文: {original_text} -> 译文: {translated_chinese_sentences[i]}")

except Exception as e:
    print(f"在测试过程中发生错误: {e}")
    print("请确保：")
    print(f"1. 模型缓存目录 '{cache_directory}' 是可写并且有效的。")
    print("2. 相关的依赖 (transformers, sentencepiece, torch) 已经安装。")
    print("3. 如果是第一次运行，模型文件会被下载，请确保网络连接正常。")