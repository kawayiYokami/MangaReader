"""
统一图像处理核心模块
- 引擎: Pillow (PIL)
- 标准内部表示: PIL.Image.Image (RGB色彩空间)
"""
import logging
from typing import Union, Tuple, Optional, List
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# --- 类型别名 ---
ImageType = Image.Image  # 标准内部图像表示

# --- 统一输入输出 ---

def read_image(source: Union[str, bytes]) -> Optional[ImageType]:
    """
    从文件路径或字节流中读取图像，并解码为标准的内部图像表示。

    :param source: 文件路径 (str) 或图像字节流 (bytes)。
    :return: RGB格式的PIL.Image.Image，如果失败则返回None。
    """
    try:
        if isinstance(source, str):
            # 从文件路径读取
            img = Image.open(source)
        elif isinstance(source, bytes):
            # 从字节流读取
            img = Image.open(BytesIO(source))
        else:
            return None

        # 统一转换为RGB模式
        if img.mode != 'RGB':
            img = img.convert('RGB')

        return img
    except Exception as e:
        logging.error(f"读取图像时发生错误: {e}")
        return None


def write_image(image: ImageType, ext: str = '.jpg', quality: int = 85) -> Optional[bytes]:
    """
    将标准内部图像编码为指定格式的字节流。

    :param image: RGB格式的PIL.Image.Image。
    :param ext: 目标文件扩展名，如 '.jpg', '.webp'。
    :param quality: 图像质量 (1-100)。
    :return: 编码后的字节流，如果失败则返回None。
    """
    if image is None:
        logging.error("严重错误: processor.write_image 接收到 None 图像")
        return None

    try:
        # 确保扩展名以点开头，并转为小写
        clean_ext = (ext if ext.startswith('.') else f".{ext}").lower()

        # 映射扩展名到Pillow格式名
        format_map = {
            '.jpg': 'JPEG',
            '.jpeg': 'JPEG',
            '.webp': 'WEBP',
            '.png': 'PNG',
            '.bmp': 'BMP',
            '.gif': 'GIF'
        }

        format_name = format_map.get(clean_ext)
        if not format_name:
            logging.error(f"不支持的编码格式: {ext}")
            return None

        # 编码图像到字节流
        buffer = BytesIO()

        # WebP 和 JPEG 支持质量参数
        if format_name in ('WEBP', 'JPEG'):
            image.save(buffer, format=format_name, quality=quality)
        else:
            image.save(buffer, format=format_name)

        return buffer.getvalue()
    except Exception as e:
        logging.error(f"processor.write_image 编码时发生异常: {e}", exc_info=True)
        return None

# --- 核心算法 ---

def resize(image: ImageType, size: Tuple[int, int]) -> ImageType:
    """
    将图像缩放到指定尺寸。

    :param image: 输入图像。
    :param size: 目标尺寸 (width, height)。
    :return: 缩放后的图像。
    """
    # Pillow的resize第一个参数是(width, height)，与OpenCV一致
    # 根据缩放方向选择合适的重采样方法
    current_width, current_height = image.size
    if size[0] < current_width or size[1] < current_height:
        # 缩小使用LANCZOS（高质量）
        resample = Image.Resampling.LANCZOS
    else:
        # 放大使用BICUBIC
        resample = Image.Resampling.BICUBIC

    return image.resize(size, resample=resample)

def thumbnail(image: ImageType, max_size: Tuple[int, int]) -> ImageType:
    """
    创建等比缩放的缩略图，使其尺寸不超过max_size。

    :param image: 输入图像。
    :param max_size: 最大尺寸 (max_width, max_height)。
    :return: 缩放后的图像。
    """
    # Pillow的thumbnail方法会原地修改，所以先复制
    img_copy = image.copy()
    img_copy.thumbnail(max_size, Image.Resampling.LANCZOS)
    return img_copy

def fit(image: ImageType, size: Tuple[int, int]) -> ImageType:
    """
    缩放并居中裁剪图像以完全适应指定尺寸。

    :param image: 输入图像。
    :param size: 目标尺寸 (width, height)。
    :return: 处理后的图像。
    """
    from PIL import ImageOps
    return ImageOps.fit(image, size, Image.Resampling.LANCZOS)

# --- 文本处理 (混合模式) ---

def draw_text(
    image: ImageType,
    text: str,
    box: List[int],
    font_path: str,
    font_size: int,
    fill: Tuple[int, int, int] = (0, 0, 0)
) -> ImageType:
    """
    在图像上绘制文本。

    :param image: PIL图像 (RGB)。
    :param text: 要绘制的文本。
    :param box: 文本框 [x1, y1, x2, y2]。文本将在此框内绘制。
    :param font_path: 字体文件路径 (.ttf, .otf)。
    :param font_size: 字体大小。
    :param fill: 文本颜色 (R, G, B)。
    :return: 绘制了文本的PIL图像 (RGB)。
    """
    # 创建副本避免修改原图
    img_copy = image.copy()
    draw = ImageDraw.Draw(img_copy)
    font = ImageFont.truetype(font_path, font_size)

    # 用白色矩形覆盖原区域
    draw.rectangle(box, fill=(255, 255, 255))

    # 绘制文本
    draw.text((box[0], box[1]), text, font=font, fill=fill)

    return img_copy