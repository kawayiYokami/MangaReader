#!/usr/bin/env python3
"""
图像压缩工具模块

提供图像压缩和格式转换功能，特别针对翻译后图像的优化
"""

import io
import base64
from typing import Optional, Tuple, Union
from PIL import Image
import numpy as np

from utils import manga_logger as log


class ImageCompressor:
    """图像压缩器"""
    
    def __init__(self):
        """初始化图像压缩器"""
        self.default_config = {
            'webp_quality': 80,
            'jpeg_quality': 85,
            'png_compress_level': 6,
            'max_dimension': 2048,  # 最大尺寸限制
            'enable_optimization': True
        }
    
    def compress_to_webp(self, image_array: np.ndarray, quality: int = 80, 
                        max_dimension: Optional[int] = None) -> bytes:
        """
        将图像数组压缩为WebP格式
        
        Args:
            image_array: 图像数组
            quality: 压缩质量 (1-100)
            max_dimension: 最大尺寸限制
            
        Returns:
            WebP格式的图像数据
        """
        try:
            # 转换为PIL图像
            image = self._array_to_pil_image(image_array)
            
            # 调整尺寸（如果需要）
            if max_dimension:
                image = self._resize_if_needed(image, max_dimension)
            
            # 转换为RGB（WebP不支持RGBA的某些特性）
            if image.mode in ('RGBA', 'LA'):
                # 创建白色背景
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'RGBA':
                    background.paste(image, mask=image.split()[-1])  # 使用alpha通道作为mask
                else:
                    background.paste(image)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 压缩为WebP
            output = io.BytesIO()
            image.save(output, format='WEBP', quality=quality, optimize=True)
            
            compressed_data = output.getvalue()
            
            log.debug(f"图像压缩完成: WebP质量{quality}, 大小{len(compressed_data)}字节")
            return compressed_data
            
        except Exception as e:
            log.error(f"WebP压缩失败: {e}")
            raise
    
    def compress_to_jpeg(self, image_array: np.ndarray, quality: int = 85,
                        max_dimension: Optional[int] = None) -> bytes:
        """
        将图像数组压缩为JPEG格式
        
        Args:
            image_array: 图像数组
            quality: 压缩质量 (1-100)
            max_dimension: 最大尺寸限制
            
        Returns:
            JPEG格式的图像数据
        """
        try:
            # 转换为PIL图像
            image = self._array_to_pil_image(image_array)
            
            # 调整尺寸（如果需要）
            if max_dimension:
                image = self._resize_if_needed(image, max_dimension)
            
            # 转换为RGB（JPEG不支持透明度）
            if image.mode in ('RGBA', 'LA', 'P'):
                # 创建白色背景
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'RGBA':
                    background.paste(image, mask=image.split()[-1])
                elif image.mode == 'P' and 'transparency' in image.info:
                    image = image.convert('RGBA')
                    background.paste(image, mask=image.split()[-1])
                else:
                    background.paste(image)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 压缩为JPEG
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=quality, optimize=True)
            
            compressed_data = output.getvalue()
            
            log.debug(f"图像压缩完成: JPEG质量{quality}, 大小{len(compressed_data)}字节")
            return compressed_data
            
        except Exception as e:
            log.error(f"JPEG压缩失败: {e}")
            raise
    
    def compress_to_base64_webp(self, image_array: np.ndarray, quality: int = 80,
                               max_dimension: Optional[int] = None) -> str:
        """
        将图像数组压缩为Base64编码的WebP格式
        
        Args:
            image_array: 图像数组
            quality: 压缩质量 (1-100)
            max_dimension: 最大尺寸限制
            
        Returns:
            Base64编码的WebP图像数据
        """
        webp_data = self.compress_to_webp(image_array, quality, max_dimension)
        base64_data = base64.b64encode(webp_data).decode('utf-8')
        
        log.debug(f"Base64 WebP编码完成: {len(base64_data)}字符")
        return base64_data
    
    def compress_to_base64_jpeg(self, image_array: np.ndarray, quality: int = 85,
                               max_dimension: Optional[int] = None) -> str:
        """
        将图像数组压缩为Base64编码的JPEG格式
        
        Args:
            image_array: 图像数组
            quality: 压缩质量 (1-100)
            max_dimension: 最大尺寸限制
            
        Returns:
            Base64编码的JPEG图像数据
        """
        jpeg_data = self.compress_to_jpeg(image_array, quality, max_dimension)
        base64_data = base64.b64encode(jpeg_data).decode('utf-8')
        
        log.debug(f"Base64 JPEG编码完成: {len(base64_data)}字符")
        return base64_data
    
    def _array_to_pil_image(self, image_array: np.ndarray) -> Image.Image:
        """将numpy数组转换为PIL图像"""
        try:
            # 确保数据类型正确
            if image_array.dtype != np.uint8:
                if image_array.max() <= 1.0:
                    # 假设是0-1范围的浮点数
                    image_array = (image_array * 255).astype(np.uint8)
                else:
                    # 假设是0-255范围的浮点数
                    image_array = image_array.astype(np.uint8)
            
            # 根据维度创建PIL图像
            if len(image_array.shape) == 2:
                # 灰度图像
                return Image.fromarray(image_array, mode='L')
            elif len(image_array.shape) == 3:
                if image_array.shape[2] == 1:
                    # 单通道图像
                    return Image.fromarray(image_array.squeeze(), mode='L')
                elif image_array.shape[2] == 3:
                    # RGB图像
                    return Image.fromarray(image_array, mode='RGB')
                elif image_array.shape[2] == 4:
                    # RGBA图像
                    return Image.fromarray(image_array, mode='RGBA')
                else:
                    raise ValueError(f"不支持的通道数: {image_array.shape[2]}")
            else:
                raise ValueError(f"不支持的图像维度: {image_array.shape}")
                
        except Exception as e:
            log.error(f"数组转PIL图像失败: {e}")
            raise
    
    def _resize_if_needed(self, image: Image.Image, max_dimension: int) -> Image.Image:
        """如果图像过大则调整尺寸"""
        width, height = image.size
        
        if width <= max_dimension and height <= max_dimension:
            return image
        
        # 计算缩放比例
        scale = min(max_dimension / width, max_dimension / height)
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        # 使用高质量重采样
        resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        log.debug(f"图像尺寸调整: {width}x{height} -> {new_width}x{new_height}")
        return resized_image
    
    def get_compression_info(self, original_size: int, compressed_size: int) -> dict:
        """获取压缩信息"""
        compression_ratio = compressed_size / original_size if original_size > 0 else 0
        space_saved = original_size - compressed_size
        space_saved_percent = (space_saved / original_size * 100) if original_size > 0 else 0
        
        return {
            'original_size': original_size,
            'compressed_size': compressed_size,
            'compression_ratio': compression_ratio,
            'space_saved': space_saved,
            'space_saved_percent': space_saved_percent
        }
    
    def estimate_webp_size(self, image_array: np.ndarray, quality: int = 80) -> int:
        """估算WebP压缩后的大小"""
        try:
            # 快速估算：基于图像尺寸和质量
            height, width = image_array.shape[:2]
            channels = image_array.shape[2] if len(image_array.shape) == 3 else 1
            
            # 基础估算公式（经验值）
            base_size = height * width * channels
            quality_factor = quality / 100.0
            
            # WebP通常能达到比JPEG更好的压缩率
            estimated_size = int(base_size * quality_factor * 0.1)
            
            return max(estimated_size, 1024)  # 最小1KB
            
        except Exception as e:
            log.warning(f"估算WebP大小失败: {e}")
            return 0


# 全局实例
_image_compressor = None

def get_image_compressor() -> ImageCompressor:
    """获取图像压缩器实例"""
    global _image_compressor
    if _image_compressor is None:
        _image_compressor = ImageCompressor()
    return _image_compressor
