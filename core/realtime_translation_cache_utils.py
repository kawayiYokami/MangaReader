# core/realtime_translation_cache_utils.py
"""
实时翻译缓存工具类

提供图像哈希计算、数据提取、缓存数据构建等辅助功能。
"""

import hashlib
import base64
import numpy as np
import cv2
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from dataclasses import asdict

from core.realtime_translation_cache_manager import RealtimeTranslationCacheData
from core.data_models import OCRResult
from utils import manga_logger as log


class RealtimeTranslationCacheUtils:
    """实时翻译缓存工具类"""
    
    @staticmethod
    def calculate_image_hash(image: np.ndarray) -> str:
        """计算图像的MD5哈希值"""
        try:
            # 将图像转换为字节数据
            if len(image.shape) == 3:
                # 彩色图像，转换为BGR格式
                image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            else:
                image_bgr = image
            
            # 编码为PNG格式（无损）
            _, buffer = cv2.imencode('.png', image_bgr)
            image_bytes = buffer.tobytes()
            
            # 计算MD5哈希
            hash_md5 = hashlib.md5(image_bytes)
            return hash_md5.hexdigest()
            
        except Exception as e:
            log.error(f"计算图像哈希失败: {e}")
            # 返回一个基于图像形状和数据类型的简单哈希
            shape_str = f"{image.shape}_{image.dtype}"
            return hashlib.md5(shape_str.encode()).hexdigest()
    
    @staticmethod
    def encode_image_to_base64(image: np.ndarray) -> str:
        """将图像编码为base64字符串"""
        try:
            # 确保图像是RGB格式
            if len(image.shape) == 3 and image.shape[2] == 3:
                # 转换为BGR格式（OpenCV默认）
                image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            else:
                image_bgr = image
            
            # 编码为JPEG格式
            _, buffer = cv2.imencode('.jpg', image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            # 转换为base64
            image_base64 = base64.b64encode(buffer).decode('utf-8')
            return image_base64
            
        except Exception as e:
            log.error(f"图像base64编码失败: {e}")
            return ""
    
    @staticmethod
    def extract_ocr_data(ocr_results: List[OCRResult]) -> List[Dict[str, Any]]:
        """提取OCR结果数据"""
        try:
            return [result.to_dict() for result in ocr_results]
        except Exception as e:
            log.error(f"提取OCR数据失败: {e}")
            return []
    
    @staticmethod
    def extract_structured_text_data(structured_texts: List[Any]) -> List[Dict[str, Any]]:
        """提取结构化文本数据"""
        try:
            result = []
            for text_item in structured_texts:
                if hasattr(text_item, 'to_dict'):
                    result.append(text_item.to_dict())
                elif hasattr(text_item, '__dict__'):
                    result.append(text_item.__dict__)
                elif isinstance(text_item, dict):
                    result.append(text_item)
                else:
                    # 尝试转换为字典
                    try:
                        result.append(asdict(text_item))
                    except:
                        result.append({"data": str(text_item)})
            return result
        except Exception as e:
            log.error(f"提取结构化文本数据失败: {e}")
            return []
    
    @staticmethod
    def extract_translation_mappings(original_texts: List[str], 
                                   translated_texts: List[str]) -> Dict[str, str]:
        """提取翻译映射关系"""
        try:
            mappings = {}
            for i, (original, translated) in enumerate(zip(original_texts, translated_texts)):
                if original and translated:
                    mappings[original] = translated
            return mappings
        except Exception as e:
            log.error(f"提取翻译映射失败: {e}")
            return {}
    
    @staticmethod
    def extract_text_regions(structured_texts: List[Any]) -> List[Dict[str, Any]]:
        """提取文本区域信息"""
        try:
            regions = []
            for text_item in structured_texts:
                region_info = {}
                
                # 尝试提取坐标信息
                if hasattr(text_item, 'bbox'):
                    region_info['bbox'] = text_item.bbox
                elif hasattr(text_item, 'coordinates'):
                    region_info['bbox'] = text_item.coordinates
                elif isinstance(text_item, dict) and 'bbox' in text_item:
                    region_info['bbox'] = text_item['bbox']
                
                # 尝试提取文本内容
                if hasattr(text_item, 'text'):
                    region_info['text'] = text_item.text
                elif hasattr(text_item, 'content'):
                    region_info['text'] = text_item.content
                elif isinstance(text_item, dict) and 'text' in text_item:
                    region_info['text'] = text_item['text']
                
                # 尝试提取置信度
                if hasattr(text_item, 'confidence'):
                    region_info['confidence'] = text_item.confidence
                elif isinstance(text_item, dict) and 'confidence' in text_item:
                    region_info['confidence'] = text_item['confidence']
                
                if region_info:
                    regions.append(region_info)
            
            return regions
        except Exception as e:
            log.error(f"提取文本区域信息失败: {e}")
            return []
    
    @staticmethod
    def build_cache_data(manga_path: str, page_index: int, target_language: str,
                        image: np.ndarray, ocr_results: List[OCRResult],
                        structured_texts: List[Any], original_texts: List[str],
                        translated_texts: List[str], harmonized_texts: List[str] = None,
                        result_image: np.ndarray = None,
                        **kwargs) -> RealtimeTranslationCacheData:
        """构建完整的缓存数据"""
        try:
            # 计算图像哈希
            image_hash = RealtimeTranslationCacheUtils.calculate_image_hash(image)
            
            # 提取各种数据
            ocr_data = RealtimeTranslationCacheUtils.extract_ocr_data(ocr_results)
            structured_data = RealtimeTranslationCacheUtils.extract_structured_text_data(structured_texts)
            translation_mappings = RealtimeTranslationCacheUtils.extract_translation_mappings(
                original_texts, translated_texts
            )
            text_regions = RealtimeTranslationCacheUtils.extract_text_regions(structured_texts)
            
            # 编码结果图像
            result_image_data = None
            if result_image is not None:
                result_image_data = RealtimeTranslationCacheUtils.encode_image_to_base64(result_image)
            
            # 构建缓存数据
            cache_data = RealtimeTranslationCacheData(
                manga_path=manga_path,
                page_index=page_index,
                target_language=target_language,
                image_hash=image_hash,
                image_width=image.shape[1],
                image_height=image.shape[0],
                ocr_results=ocr_data,
                structured_texts=structured_data,
                original_texts=original_texts,
                translated_texts=translated_texts,
                translation_mappings=translation_mappings,
                harmonized_texts=harmonized_texts or [],
                harmonization_applied=bool(harmonized_texts),
                text_regions=text_regions,
                inpaint_regions=kwargs.get('inpaint_regions', []),
                font_settings=kwargs.get('font_settings', {}),
                result_image_data=result_image_data
            )
            
            return cache_data
            
        except Exception as e:
            log.error(f"构建缓存数据失败: {e}")
            raise
    
    @staticmethod
    def validate_cache_data(cache_data: RealtimeTranslationCacheData, 
                           current_image: np.ndarray) -> bool:
        """验证缓存数据是否与当前图像匹配"""
        try:
            # 计算当前图像的哈希
            current_hash = RealtimeTranslationCacheUtils.calculate_image_hash(current_image)
            
            # 比较哈希值
            if cache_data.image_hash != current_hash:
                log.debug(f"图像哈希不匹配: 缓存={cache_data.image_hash}, 当前={current_hash}")
                return False
            
            # 比较图像尺寸
            if (cache_data.image_width != current_image.shape[1] or 
                cache_data.image_height != current_image.shape[0]):
                log.debug(f"图像尺寸不匹配: 缓存=({cache_data.image_width}, {cache_data.image_height}), "
                         f"当前=({current_image.shape[1]}, {current_image.shape[0]})")
                return False
            
            return True
            
        except Exception as e:
            log.error(f"验证缓存数据失败: {e}")
            return False

    @staticmethod
    def _get_current_time() -> str:
        """获取当前时间的ISO格式字符串"""
        return datetime.now().isoformat()
    
    @staticmethod
    def decode_result_image(base64_data: str) -> Optional[np.ndarray]:
        """解码base64图像数据"""
        try:
            if not base64_data:
                return None
            
            # 解码base64数据
            image_bytes = base64.b64decode(base64_data)
            
            # 转换为numpy数组
            nparr = np.frombuffer(image_bytes, np.uint8)
            
            # 解码为图像
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is not None:
                # 转换为RGB格式
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                return image_rgb
            
            return None
            
        except Exception as e:
            log.error(f"解码结果图像失败: {e}")
            return None
