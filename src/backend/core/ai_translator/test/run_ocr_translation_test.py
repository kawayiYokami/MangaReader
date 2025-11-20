# file: core/ai_translator/test/run_ocr_translation_test.py
"""
端到端测试：漫画 OCR、翻译及边界框提取
==========================================

该脚本用于测试从单张漫画图片中提取所有文本（对话和拟声词）、
进行翻译，并获取每个文本块精确归一化边界框的完整流程。

功能：
1. 从指定的漫画文件（图片或 .zip 压缩包）中加载一页。
2. 调用 AI 翻译器外观（Facade），使用 `manga_ocr_and_translation` 智能体。
3. 获取 AI 返回的原始 YAML 响应。
4. 解析 YAML，提取对话和拟声词的文本及边界框。
5. 在控制台打印归一化坐标和根据图片尺寸计算出的实际像素坐标。
6. 在图片副本上绘制所有边界框，并将结果保存到输出目录以供验证。

如何运行:
```bash
# 处理单个图片文件
python -m core.ai_translator.test.run_ocr_translation_test "path/to/your/image.jpg"

# 处理 ZIP 压缩包中的特定页
python -m core.ai_translator.test.run_ocr_translation_test "path/to/your/manga.zip" [page_number]
```
例如:
```bash
python -m core.ai_translator.test.run_ocr_translation_test "storage/manga/005.jpg"
python -m core.ai_translator.test.run_ocr_translation_test "storage/manga/test.zip" 1
```
"""
import asyncio
import logging
import os
import sys
import zipfile
import yaml
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# 确保能够导入核心模块
sys.path.append(str(Path(__file__).resolve().parents))

from src.backend.core.ai_translator.facade import AITranslatorFacade
from src.backend.core.ai_translator.data_models import TranslationStatus

# --- 配置 ---
# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s",
    stream=sys.stdout,
)
# 降低 httpx 的日志级别
logging.getLogger("httpx").setLevel(logging.WARNING)

# 定义输出目录
OUTPUT_DIR = "output_temp/ocr_translation_test"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 尝试加载字体用于绘制标签
try:
    # 优先使用Windows系统字体，为其他系统提供备用
    FONT = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 15)
except IOError:
    try:
        FONT = ImageFont.truetype("font/arial.ttf", 15)
    except IOError:
        FONT = ImageFont.load_default()

def get_image_from_path(file_path: str, page_number: int = 0) -> tuple[bytes | None, str]:
    """从路径（单个文件或 ZIP）加载图片字节数据和基础文件名。"""
    base_filename = os.path.splitext(os.path.basename(file_path))[0]
    
    if file_path.lower().endswith((".zip", ".cbz")):
        try:
            with zipfile.ZipFile(file_path, 'r') as z:
                files = sorted([f for f in z.namelist() if f.lower().endswith(('png', 'jpg', 'jpeg', 'webp')) and not f.startswith('__MACOSX')])
                if 0 <= page_number < len(files):
                    image_filename = files[page_number]
                    final_base_filename = f"{base_filename}_p{page_number}"
                    with z.open(image_filename) as image_file:
                        return image_file.read(), final_base_filename
                else:
                    logging.error(f"页码 {page_number} 超出范围。存档中只有 {len(files)} 张图片。")
                    return None, base_filename
        except zipfile.BadZipFile:
            logging.error(f"文件不是一个有效的 ZIP 存档: {file_path}")
            return None, base_filename
        except Exception as e:
            logging.error(f"从存档 '{file_path}' 读取图片时发生未知错误: {e}")
            return None, base_filename
            
    elif os.path.exists(file_path):
        with open(file_path, 'rb') as f:
            return f.read(), base_filename
    
    logging.error(f"文件路径不存在: {file_path}")
    return None, base_filename

def draw_boxes_on_image(image_bytes: bytes, data: dict, output_path: str):
    """在图片上绘制边界框，使用 AI 分析时所用的缩放后尺寸。"""
    try:
        # 1. 加载原始图片并转换为 RGBA
        original_image = Image.open(BytesIO(image_bytes)).convert("RGBA")

        # 2. 复制核心代码中的缩放逻辑，得到 AI 实际看到的图片
        target_height = 1000
        original_width, original_height = original_image.size
        aspect_ratio = original_width / original_height
        target_width = int(target_height * aspect_ratio)
        
        # 这张 resized_image 就是 AI 分析的那张图
        resized_image = original_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        # 3. 在这张缩放后的图片上进行绘制
        draw = ImageDraw.Draw(resized_image)
        width, height = resized_image.size # 使用缩放后的尺寸

        print(f"\n--- 在 {width}x{height} 的缩放图上绘制边界框 ---")
        
        all_boxes = data.get('dialogues', []) + data.get('sfx', [])
        
        for i, item in enumerate(all_boxes):
            box = item.get('bounding_box')
            if not box or len(box) != 4:
                logging.warning(f"项目 {i} 缺少有效的边界框: {item}")
                continue

            # AI返回的是 [y,x,y,x]，我们将其解析并转换为标准的 [x,y,x,y]
            norm_y_min, norm_x_min, norm_y_max, norm_x_max = box
            
            # 将 0-1000 的归一化坐标转换为最终图片的像素坐标
            px_x_min = int(norm_x_min / 1000 * width)
            px_y_min = int(norm_y_min / 1000 * height)
            px_x_max = int(norm_x_max / 1000 * width)
            px_y_max = int(norm_y_max / 1000 * height)
            
            item_type = 'D' if 'speaker_id' in item else 'S'
            label = f"{item_type}{i}"
            color = (255, 0, 0, 255) if item_type == 'D' else (0, 0, 255, 255)

            draw.rectangle([px_x_min, px_y_min, px_x_max, px_y_max], outline=color, width=2)
            draw.text((px_x_min, px_y_min - 15), label, fill=color, font=FONT)

        # 4. 保存这张带有边界框的缩放后图片
        resized_image.save(output_path)
        logging.info(f"已绘制边界框的缩放图片已保存到: {output_path}")

    except Exception as e:
        logging.error(f"绘制边界框时出错: {e}", exc_info=True)

async def main(file_path: str, page_number: int):
    """主执行函数"""
    logging.info(f"开始处理文件: {file_path}, 页码: {page_number}")

    # --- 1. 提取图片数据 ---
    image_bytes, base_filename = get_image_from_path(file_path, page_number)
    if not image_bytes:
        logging.error(f"无法从 '{file_path}' 加载图片数据。")
        return

    # --- 2. 调用 AI 翻译器 ---
    translator = AITranslatorFacade()
    results = None
    try:
        results = await translator.translate_image(
            agent_name="manga_ocr_and_translation",
            config_name="哈基米",
            images_data=[image_bytes],
            manga_path=file_path,
            page_index=page_number,
            source_lang="Japanese", # 添加源语言
            target_lang="简体中文",
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
    raw_yaml_str = result.raw_response
    
    if not raw_yaml_str or not isinstance(raw_yaml_str, str):
        logging.error(f"成功响应，但未能获取有效的 YAML 字符串。收到类型: {type(raw_yaml_str)}")
        return

    # 清理并解析 YAML
    try:
        # 移除 Markdown 代码块标记
        if raw_yaml_str.strip().startswith("```yaml"):
            raw_yaml_str = raw_yaml_str.strip()[7:].strip()
        if raw_yaml_str.strip().endswith("```"):
            raw_yaml_str = raw_yaml_str.strip()[:-3].strip()
            
        data = yaml.safe_load(raw_yaml_str)
    except yaml.YAMLError as e:
        logging.error(f"解析剧本 YAML 失败: {e}")
        logging.error(f"原始响应内容:\n---\n{raw_yaml_str}\n---")
        return

    logging.info("=" * 20 + " OCR & 翻译结果 " + "=" * 20)
    
    # 计算缩放后的尺寸用于打印正确的像素坐标
    original_image = Image.open(BytesIO(image_bytes))
    original_width, original_height = original_image.size
    target_height = 1000
    aspect_ratio = original_width / original_height
    resized_width = int(target_height * aspect_ratio)
    
    print(f"原始图片尺寸: {original_width}x{original_height}")
    print(f"用于AI分析的缩放尺寸: {resized_width}x{target_height}")

    # 打印对话
    if data.get('dialogues'):
        print("\n--- 对话 (Dialogues) ---")
        for i, line in enumerate(data['dialogues']):
            print(f"  - 项目 D{i}:")
            print(f"    原文: {line.get('original_text')}")
            print(f"    译文: {line.get('translated_text')}")
            box = line.get('bounding_box', [])
            print(f"    归一化坐标: {box}")
            if box and len(box) == 4:
                # AI返回 [y,x,y,x]，解析为标准 [x,y,x,y]
                y1, x1, y2, x2 = box
                px_box = [int(x1/1000*resized_width), int(y1/1000*target_height), int(x2/1000*resized_width), int(y2/1000*target_height)]
                print(f"    缩放图像素坐标: {px_box}")

    # 打印拟声词
    if data.get('sfx'):
        print("\n--- 拟声词 (SFX) ---")
        for i, line in enumerate(data['sfx']):
            print(f"  - 项目 S{i}:")
            print(f"    原文: {line.get('original_text')}")
            print(f"    译文: {line.get('translated_text')}")
            box = line.get('bounding_box', [])
            print(f"    归一化坐标: {box}")
            if box and len(box) == 4:
                # AI返回 [y,x,y,x]，解析为标准 [x,y,x,y]
                y1, x1, y2, x2 = box
                px_box = [int(x1/1000*resized_width), int(y1/1000*target_height), int(x2/1000*resized_width), int(y2/1000*target_height)]
                print(f"    缩放图像素坐标: {px_box}")

    print("=" * 56)

    # --- 4. 绘制边界框并保存 ---
    output_image_path = os.path.join(OUTPUT_DIR, f"{base_filename}_boxed.png")
    draw_boxes_on_image(image_bytes, data, output_image_path)
    
    # 保存原始的 AI 响应
    output_yaml_path = os.path.join(OUTPUT_DIR, f"{base_filename}_response.yaml")
    with open(output_yaml_path, "w", encoding="utf-8") as f:
        f.write(raw_yaml_str)
    logging.info(f"原始 AI 响应已保存到: {output_yaml_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    file_path_arg = sys.argv[1]
    page_number_arg = 0
    if len(sys.argv) > 2:
        try:
            page_number_arg = int(sys.argv[2])
        except ValueError:
            logging.error("第二个参数必须是有效的页码数字。")
            sys.exit(1)

    asyncio.run(main(file_path_arg, page_number_arg))