# file: core/ai_translator/image_utils.py
"""
图片处理工具
============

提供图片预处理功能，例如调整尺寸、压缩和 Base64 编码，
以便为 AI 多模态模型的 API 调用做准备。
"""
import base64
import io
from PIL import Image
import logging

from typing import Tuple

def preprocess_and_encode_image(
    image_bytes: bytes,
    target_height: int = 1000,
    quality: int = 80
) -> Tuple[str, Tuple[int, int]]:
    """
    按比例将图片高度缩放到指定值、压缩并编码为 Base64 字符串。

    Args:
        image_bytes (bytes): 原始图片文件的字节数据。
        target_height (int): 目标高度。
        quality (int): JPEG 压缩质量 (0-100)。

    Returns:
        tuple: 包含 Base64 字符串和缩放后尺寸 (宽度, 高度) 元组的元组。
    """
    try:
        # 1. 从字节加载图片
        image = Image.open(io.BytesIO(image_bytes))

        # 2. 转换为 RGB (如果需要)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        original_width, original_height = image.size

        # 3. 按比例调整尺寸
        if original_height != target_height:
            aspect_ratio = original_width / original_height
            target_width = int(target_height * aspect_ratio)
            resized_image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        else:
            resized_image = image

        # 4. 压缩为 JPEG 并存入内存
        buffer = io.BytesIO()
        resized_image.save(buffer, format="JPEG", quality=quality)
        compressed_bytes = buffer.getvalue()

        # 5. Base64 编码
        base64_string = base64.b64encode(compressed_bytes).decode('utf-8')
        
        final_width, final_height = resized_image.size
        logging.info(f"图片预处理成功: {original_width}x{original_height} -> {final_width}x{final_height}, 大小: {len(compressed_bytes) / 1024:.2f} KB")

        return f"data:image/jpeg;base64,{base64_string}", (final_width, final_height)

    except Exception as e:
        logging.error(f"图片预处理失败: {e}", exc_info=True)
        raise