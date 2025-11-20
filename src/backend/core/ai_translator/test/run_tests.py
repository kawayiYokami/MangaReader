# file: core/ai_translator/test/run_tests.py
"""
AI Translator 模块 - 核心流程冒烟测试
=======================================

本脚本旨在用最直接的方式，验证 Agent 驱动的新架构核心流程是否能跑通。

如何使用:
1.  **配置 Agents**:
    确保 `app/agents/manga_dialogue.json` 文件存在。
2.  **配置 API**:
    确保 `app/config/config.json` 文件中的 `my_openai_service` 配置正确。
3.  **运行脚本**:
    从项目根目录运行: `python -m core.ai_translator.test.run_tests`
"""
import asyncio
import logging
import sys
import os
import random

# --- 路径设置 ---
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

# --- 模块导入 ---
from src.backend.core.ai_translator.facade import AITranslatorFacade
from src.backend.utils.manga_logger import setup_logging, set_level

# --- 日志初始化 ---
setup_logging()
set_level("INFO")

# --- 测试配置 ---
TEST_CONFIG_NAME = "my_openai_service"
TARGET_LANG = "简体中文"

# --- 专业级漫画对话测试数据集 ---
page1_content = ["カイト、気をつけて！", "ドゴォォン！", "ソーグ！お前の悪事もここまでだ！", "彼の力は...本物よ。", "フソ、小僧が...。", "うわっ！", "この世界は使が作り変える！", "そんなこと、させるか！", "このクリスタルは渡さない！", "黙れ！お前たちに荷がわかる！", "3"]
random.shuffle(page1_content)
page2_content = ["...私が倒せると思ったか？", "だが、もう遅い！", "アニャ、何カ手は...？", "この程度の政撃で...", "...まだよ。", "小娘...そのカに気づいたか。", "まさか、共鳴しているの？", "くっ...！なんてカだ...", "無駄だと言っている。", "クリスタルが...先を...", "- 4 -"]
random.shuffle(page2_content)
all_manga_samples = page1_content + page2_content

# --- 结果打印辅助函数 ---
def print_text_results(results):
    print("\n--- 文本翻译结果 ---")
    if not results:
        print("未收到结果。")
        return
    for res in results:
        status_icon = "✅" if res.status.value == 'success' else "❌"
        nt_str = "(无需翻译)" if not res.needs_translation else ""
        print(f"{status_icon} 原文: {res.original_text}")
        print(f"    译文: {res.translated_text} {nt_str}")
        if res.error_message:
            print(f"    [错误]: {res.error_message}")
    print("-" * 20)

async def main():
    """运行核心流程测试"""
    facade = AITranslatorFacade()
    
    print("\n" + "="*50)
    print("=  AI Translator 核心流程冒烟测试  =")
    print("="*50 + "\n")
    
    logging.info("--- 开始测试：漫画对话翻译 (agent: manga_dialogue) ---")
    try:
        results = await facade.translate(
            texts=all_manga_samples,
            config_name=TEST_CONFIG_NAME,
            target_lang=TARGET_LANG,
            agent_name="manga_dialogue",
            manga_title="水晶の勇者",
            mode='multi'
        )
        print_text_results(results)
    except Exception as e:
        logging.error(f"核心流程测试失败: {e}", exc_info=True)
    
    await facade.close()
    logging.info("测试完成。")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())