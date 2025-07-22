# file: core/ai_translator/test/run_batch_translation.py
"""
批量翻译整本漫画
==================================

该脚本用于顺序翻译一本漫画的所有页面，并利用现有缓存。

功能：
1. 确定漫画文件的总页数。
2. 逐页调用 AI 翻译器，请求生成剧本。
3. 自动利用缓存，跳过已翻译的页面。
4. 严格遵守 API 请求间隔。
5. 打印每一页的处理状态。

如何运行:
```bash
python -m core.ai_translator.test.run_batch_translation "path/to/your/manga.zip"
```
例如:
```bash
python -m core.ai_translator.test.run_batch_translation "storage/manga/test.zip"
```
"""
import asyncio
import logging
import os
import sys
import zipfile
from pathlib import Path
from typing import List

# 确保能够导入核心模块
sys.path.append(str(Path(__file__).resolve().parents[3]))

from core.ai_translator.facade import AITranslatorFacade
from core.ai_translator.data_models import TranslationStatus

# --- 配置 ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s",
    stream=sys.stdout,
)
logging.getLogger("httpx").setLevel(logging.WARNING)


def get_image_files_from_archive(archive_path: str) -> List[str]:
    """从 ZIP 存档中获取所有图片文件的有序列表。"""
    try:
        with zipfile.ZipFile(archive_path, 'r') as z:
            return sorted([f for f in z.namelist() if f.lower().endswith(('png', 'jpg', 'jpeg', 'webp')) and not f.startswith('__MACOSX')])
    except (zipfile.BadZipFile, FileNotFoundError):
        logging.error(f"无法打开或找到文件: {archive_path}")
        return []

async def main(manga_path: str):
    """主执行函数"""
    logging.info(f"开始批量翻译任务: {manga_path}")

    image_files = get_image_files_from_archive(manga_path)
    total_pages = len(image_files)
    if total_pages == 0:
        logging.error("在指定的路径中没有找到任何图片文件。")
        return

    logging.info(f"漫画总页数: {total_pages}")

    translator = AITranslatorFacade()
    try:
        for i, image_file_path in enumerate(image_files):
            page_number = i
            logging.info(f"--- 开始处理第 {page_number + 1}/{total_pages} 页 ---")

            # 从存档中读取单页图片数据
            with zipfile.ZipFile(manga_path, 'r') as z:
                with z.open(image_file_path) as image_file:
                    image_bytes = image_file.read()

            if not image_bytes:
                logging.warning(f"无法读取第 {page_number} 页的图片数据，跳过。")
                continue

            # 调用翻译器
            results = await translator.translate_image(
                agent_name="manga_script_generation",
                config_name="my_gemini_service",
                images_data=[image_bytes],
                manga_path=manga_path,
                page_index=page_number,
                target_lang="简体中文",
            )

            # 报告结果
            if results and results[0].status == TranslationStatus.SUCCESS:
                logging.info(f"第 {page_number + 1}/{total_pages} 页处理成功。")
            else:
                error_msg = results[0].error_message if results else "未知错误"
                logging.error(f"第 {page_number + 1}/{total_pages} 页处理失败: {error_msg}")

    finally:
        await translator.close()

    logging.info(f"批量翻译任务完成: {manga_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    
    manga_path_arg = sys.argv[1]
    asyncio.run(main(manga_path_arg))