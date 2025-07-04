"""
统一图像处理核心模块
- 引擎: OpenCV
- 标准内部表示: NumPy ndarray (BGR色彩空间)
"""
import cv2
import numpy as np
from typing import Union, Tuple, Optional, List
from PIL import Image, ImageDraw, ImageFont

# --- 类型别名 ---
ImageType = np.ndarray  # 标准内部图像表示

# --- 统一输入输出 ---

def read_image(source: Union[str, bytes]) -> Optional[ImageType]:
    """
    从文件路径或字节流中读取图像，并解码为标准的内部图像表示。

    :param source: 文件路径 (str) 或图像字节流 (bytes)。
    :return: BGR格式的NumPy ndarray，如果失败则返回None。
    """
    try:
        if isinstance(source, str):
            # 健壮的文件读取：先用Python的open读取，再用imdecode解码，以正确处理特殊路径字符
            with open(source, 'rb') as f:
                source_bytes = f.read()
            np_arr = np.frombuffer(source_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        elif isinstance(source, bytes):
            # 从字节流读取
            np_arr = np.frombuffer(source, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        else:
            return None
        
        # Pillow作为备用解码器
        if img is None:
            from io import BytesIO
            from PIL import Image
            log.warning(f"OpenCV could not decode image, trying with Pillow...")
            try:
                if isinstance(source, str):
                     # 如果是从路径来的，我们已经读取了字节
                    image_io = BytesIO(source_bytes)
                else: # source is bytes
                    image_io = BytesIO(source)

                pil_image = Image.open(image_io).convert('RGB')
                # 将Pillow图像 (RGB) 转换为OpenCV图像 (BGR)
                img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            except Exception as e:
                log.error(f"Pillow也无法解码图像: {e}")
                return None

        return img
    except Exception as e:
        log.error(f"读取图像时发生未知错误: {e}")
        return None

from utils import manga_logger as log

def write_image(image: ImageType, ext: str = '.jpg', quality: int = 85) -> Optional[bytes]:
    """
    将标准内部图像编码为指定格式的字节流。

    :param image: BGR格式的NumPy ndarray。
    :param ext: 目标文件扩展名，如 '.jpg', '.webp'。
    :param quality: 图像质量 (0-100 for jpg, 1-100 for webp)。
    :return: 编码后的字节流，如果失败则返回None。
    """
    if image is None or image.size == 0:
        log.error(f"严重错误: processor.write_image 接收到无效图像。Image is None: {image is None}, Size: {getattr(image, 'size', 'N/A')}")
        return None
        
    try:
        # 确保扩展名以点开头，并转为小写，以进行可靠的判断
        clean_ext = (ext if ext.startswith('.') else f".{ext}").lower()

        params = []
        if clean_ext == '.webp':
            params = [cv2.IMWRITE_WEBP_QUALITY, quality]
        elif clean_ext in ['.jpg', '.jpeg']:
            params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        
        # 如果 params 为空，说明是不支持的格式
        if not params:
            log.error(f"不支持的编码格式: {ext} (cleaned: {clean_ext})")
            return None

        success, buffer = cv2.imencode(clean_ext, image, params)
        if not success:
            log.warning(f"cv2.imencode failed to encode to {clean_ext}.")
            return None
        return buffer.tobytes()
    except Exception as e:
        log.error(f"processor.write_image 编码时发生异常: {e}", exc_info=True)
        return None

# --- 核心算法 ---

def resize(image: ImageType, size: Tuple[int, int]) -> ImageType:
    """
    将图像缩放到指定尺寸。

    :param image: 输入图像。
    :param size: 目标尺寸 (width, height)。
    :return: 缩放后的图像。
    """
    return cv2.resize(image, size, interpolation=cv2.INTER_AREA if size[0] < image.shape[1] else cv2.INTER_LANCZOS4)

def thumbnail(image: ImageType, max_size: Tuple[int, int]) -> ImageType:
    """
    创建等比缩放的缩略图，使其尺寸不超过max_size。
    行为类似于Pillow的 `thumbnail`。

    :param image: 输入图像。
    :param max_size: 最大尺寸 (max_width, max_height)。
    :return: 缩放后的图像。
    """
    h, w = image.shape[:2]
    max_w, max_h = max_size

    if w <= max_w and h <= max_h:
        return image.copy()

    scale = min(max_w / w, max_h / h)
    new_w = int(w * scale)
    new_h = int(h * scale)

    return resize(image, (new_w, new_h))

def fit(image: ImageType, size: Tuple[int, int]) -> ImageType:
    """
    缩放并居中裁剪图像以完全适应指定尺寸。
    行为类似于Pillow的 `ImageOps.fit`。

    :param image: 输入图像。
    :param size: 目标尺寸 (width, height)。
    :return: 处理后的图像。
    """
    target_w, target_h = size
    h, w = image.shape[:2]

    # 1. 计算缩放比例，使其能覆盖目标尺寸
    scale = max(target_w / w, target_h / h)
    inter_w, inter_h = int(w * scale), int(h * scale)
    
    # 2. 缩放到中间尺寸
    intermediate_img = resize(image, (inter_w, inter_h))
    
    # 3. 计算居中裁剪的起始点
    y = (inter_h - target_h) // 2
    x = (inter_w - target_w) // 2
    
    # 4. 裁剪并返回
    return intermediate_img[y:y+target_h, x:x+target_w]

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
    在图像上绘制文本（使用Pillow作为字体引擎）。

    :param image: OpenCV图像 (BGR ndarray)。
    :param text: 要绘制的文本。
    :param box: 文本框 [x1, y1, x2, y2]。文本将在此框内绘制。
    :param font_path: 字体文件路径 (.ttf, .otf)。
    :param font_size: 字体大小。
    :param fill: 文本颜色 (R, G, B)。
    :return: 绘制了文本的OpenCV图像 (BGR ndarray)。
    """
    # 1. 将OpenCV图像 (BGR) 转换为Pillow图像 (RGB)
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb_image)
    
    # 2. 使用Pillow绘制文本
    draw = ImageDraw.Draw(pil_img)
    font = ImageFont.truetype(font_path, font_size)
    
    # 用白色矩形覆盖原区域
    draw.rectangle(box, fill=(255, 255, 255))
    
    # 绘制文本
    # 注意: Pillow的draw.text位置是左上角，这里我们简化为使用box的左上角
    draw.text((box[0], box[1]), text, font=font, fill=fill)
    
    # 3. 将Pillow图像 (RGB) 转换回OpenCV图像 (BGR)
    bgr_result = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    
    return bgr_result