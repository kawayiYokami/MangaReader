# file: core/ai_translator/test/run_script_generation_test.py
"""
端到端测试：漫画剧本生成
==================================

该脚本用于测试从单张漫画图片生成结构化配音剧本的完整流程。

功能：
1. 从指定的漫画文件（如 .zip）中提取一页。
2. 调用 AI 翻译器外观（Facade），使用 `manga_script_generation` 智能体。
3. 执行翻译并获取结构化的 `TranslationScript` 对象。
4. 将结果打印到控制台并保存原始响应以供分析。

如何运行:
```bash
python -m core.ai_translator.test.run_script_generation_test "path/to/your/manga.zip" [page_number]
```
例如:
```bash
python -m core.ai_translator.test.run_script_generation_test "storage/manga/test.zip" 1
```
"""
import asyncio
import logging
import os
import sys
import zipfile
from pathlib import Path

# 确保能够导入核心模块
sys.path.append(str(Path(__file__).resolve().parents[3]))

from src.backend.core.ai_translator.facade import AITranslatorFacade
from src.backend.core.ai_translator.data_models import TranslationStatus

# --- 配置 ---
# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s",
    stream=sys.stdout,
)
# 降低 httpx 的日志级别，避免过多无关信息
logging.getLogger("httpx").setLevel(logging.WARNING)

# 定义输出目录
OUTPUT_DIR = "output_temp/script_generation_test"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_image_bytes_from_archive(archive_path: str, page_number: int) -> bytes | None:
    """从 ZIP 存档中按顺序读取指定页码的图片。"""
    try:
        with zipfile.ZipFile(archive_path, 'r') as z:
            # 获取所有文件并按名称排序
            files = sorted([f for f in z.namelist() if f.lower().endswith(('png', 'jpg', 'jpeg', 'webp')) and not f.startswith('__MACOSX')])
            if 0 <= page_number < len(files):
                with z.open(files[page_number]) as image_file:
                    return image_file.read()
            else:
                logging.error(f"页码 {page_number} 超出范围。存档中只有 {len(files)} 张图片。")
                return None
    except zipfile.BadZipFile:
        logging.error(f"文件不是一个有效的 ZIP 存档: {archive_path}")
        return None
    except Exception as e:
        logging.error(f"从存档 '{archive_path}' 读取图片时发生未知错误: {e}")
        return None

async def main(file_path: str, page_number: int):
    """主执行函数"""
    logging.info(f"开始处理文件: {file_path}, 页码: {page_number}")

    # --- 1. 提取图片数据 ---
    image_bytes = None
    try:
        if file_path.lower().endswith((".zip", ".cbz")):
            image_bytes = get_image_bytes_from_archive(file_path, page_number)
        elif os.path.exists(file_path):
             with open(file_path, 'rb') as f:
                image_bytes = f.read()
        
        if not image_bytes:
            logging.error(f"无法从 '{file_path}' 加载图片数据。")
            return
            
    except Exception as e:
        logging.error(f"提取图片时出错: {e}", exc_info=True)
        return

    # --- 2. 调用 AI 翻译器 ---
    translator = AITranslatorFacade()
    try:
        # 定义目标语言，以便传递
        target_language = "简体中文"
        results = await translator.translate_image(
            agent_name="manga_script_generation",
            config_name="哈基米", # 请确保你的 config.json 中有此配置
            images_data=[image_bytes],
            # --- 传递缓存所需参数 ---
            manga_path=file_path,
            page_index=page_number,
            target_lang=target_language,
        )
    finally:
        await translator.close()

    # --- 3. 处理并保存结果 ---
    if not results or results[0].status != TranslationStatus.SUCCESS:
        logging.error(f"翻译失败: {results[0].error_message if results else '未知错误'}")
        if results and results[0].raw_response:
             logging.error(f"原始失败响应: {results[0].raw_response}")
        return

    result = results[0]
    script = result.translation_script
    
    if not script:
        logging.error("成功响应，但未能生成剧本。")
        return

    logging.info("=" * 20 + " 翻译剧本生成成功 " + "=" * 20)
    print(f"处理文件: {os.path.basename(file_path)} - 第 {page_number} 页")
    
    for i, line in enumerate(script.script):
        print("-" * 50)
        print(f"  行号: {i + 1}")
        print(f"  发言人 ID: {line.speaker_id}")
        print(f"  原文: {line.original_text}")
        print(f"  译文: {line.translated_text}")
    
    print("=" * 62)

    # 保存原始的 AI 响应以供调试
    base_filename = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.join(OUTPUT_DIR, f"{base_filename}_p{page_number}_script.yaml")
    
    if result.raw_response:
        import yaml
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(result.raw_response, f, allow_unicode=True, sort_keys=False)
        logging.info(f"原始 AI 响应已保存到: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    file_path_arg = sys.argv[1]
    page_number_arg = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    asyncio.run(main(file_path_arg, page_number_arg))