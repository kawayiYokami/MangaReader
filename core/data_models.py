# core/data_models.py
from typing import List, Dict, Any, Optional

class OCRResult:
    """OCR识别结果数据类"""
    def __init__(self, text: str, bbox: List[List[int]], confidence: float,
                 direction: Optional[str] = None, column: Optional[int] = None, row: Optional[int] = None,
                 merged_count: int = 1,
                 image_width: Optional[int] = None, # 新增
                 image_height: Optional[int] = None, # 新增
                 ocr_results: Optional[List[Any]] = None, **kwargs):
        self.text = text  # 识别的文本 (通常是合并后的)
        self.translated_texts: List[str] = []  # 翻译后的文本列表 (运行时数据)
        self.bbox = bbox  # 文本框坐标 (通常是合并后的)
        self.confidence = confidence  # 置信度 (通常是合并后的)
        self.direction = direction  # 文本方向
        self.column = column  # 文本所属的列
        self.row = row  # 文本所属的行
        self.merged_count = merged_count  # 合并计数
        self.image_width = image_width # 新增
        self.image_height = image_height # 新增

        # 初始化和反序列化 ocr_results (原始/子结果)
        self.ocr_results: List[OCRResult] = [] # Ensure type hint matches content
        if ocr_results:
            for res_data in ocr_results:
                if isinstance(res_data, dict):
                    self.ocr_results.append(OCRResult(**res_data))
                elif isinstance(res_data, OCRResult):
                    self.ocr_results.append(res_data)
                # else: # Optionally handle or log other types in the list

        # 处理 kwargs 中可能存在的、尚未被显式参数处理的属性
        remaining_kwargs = kwargs.copy()
        if 'ocr_results' in remaining_kwargs and ocr_results is not None: # Already handled as explicit arg
            del remaining_kwargs['ocr_results']
        if 'image_width' in remaining_kwargs and image_width is not None: # Already handled
            del remaining_kwargs['image_width']
        if 'image_height' in remaining_kwargs and image_height is not None: # Already handled
            del remaining_kwargs['image_height']
        
        for key, value in remaining_kwargs.items():
            if key == 'ocr_results' and ocr_results is None: 
                temp_list = []
                if isinstance(value, list):
                    for item_data in value:
                        if isinstance(item_data, dict):
                            temp_list.append(OCRResult(**item_data))
                        elif isinstance(item_data, OCRResult):
                            temp_list.append(item_data)
                self.ocr_results = temp_list
            elif key == 'image_width' and image_width is None:
                setattr(self, key, value)
            elif key == 'image_height' and image_height is None:
                setattr(self, key, value)
            elif not hasattr(self, key): 
                setattr(self, key, value)

    def __str__(self):
        return (f"OCRResult(text='{self.text}', confidence={self.confidence:.3f}, "
                f"img_size=({self.image_width}x{self.image_height}), " # 修改
                f"direction='{self.direction}', column={self.column}, row={self.row}, "
                f"merged_count={self.merged_count}, sub_results_count={len(self.ocr_results)})")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，以便缓存。"""
        data = {
            'text': self.text,
            'bbox': self.bbox,
            'confidence': self.confidence,
            'direction': self.direction,
            'column': self.column,
            'row': self.row,
            'merged_count': self.merged_count,
            'image_width': self.image_width, # 新增
            'image_height': self.image_height, # 新增
            'ocr_results': [res.to_dict() for res in self.ocr_results] 
        }
        
        for key, value in self.__dict__.items():
            if key not in data and key not in ['translated_texts']: 
                if not isinstance(value, (list, dict, str, int, float, bool, type(None))):
                    if hasattr(value, 'to_dict') and callable(value.to_dict):
                        try:
                            data[key] = value.to_dict()
                        except Exception: 
                            pass 
                    else: # Fallback for other complex types not handled
                        data[key] = str(value) # Or skip
                else:
                    data[key] = value
        return data