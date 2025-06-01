# core/data_models.py
from typing import List, Dict, Any, Optional

class OCRResult:
    """OCR识别结果数据类"""
    def __init__(self, text: str, bbox: List[List[int]], confidence: float,
                 direction: Optional[str] = None, column: Optional[int] = None, row: Optional[int] = None,
                 merged_count: int = 1, ocr_results: Optional[List[Any]] = None, **kwargs):
        self.text = text  # 识别的文本
        self.translated_texts = []  # 翻译后的文本列表
        self.bbox = bbox  # 文本框坐标 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        self.confidence = confidence  # 置信度
        self.direction = direction  # 文本方向，例如 'horizontal' 或 'vertical'
        self.column = column  # 文本所属的列
        self.row = row  # 文本所属的行
        self.merged_count = merged_count  # 合并计数，表示由多少个文本框合并而来
        self.ocr_results = ocr_results if ocr_results is not None else []  # 原始OCR结果列表
        # Store any other attributes that might come from DB deserialization
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __str__(self):
        return f"OCRResult(text='{self.text}', confidence={self.confidence:.3f}, direction='{self.direction}', column={self.column}, row={self.row}, merged_count={self.merged_count})"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        # Only include attributes that are part of the core definition
        # or explicitly handled. Avoid serializing dynamic kwargs unless intended.
        data = {
            'text': self.text,
            'bbox': self.bbox,
            'confidence': self.confidence,
            'direction': self.direction,
            'column': self.column,
            'row': self.row,
            'merged_count': self.merged_count
            # 'ocr_results' could be included if it's serializable and needed in cache
        }
        return data