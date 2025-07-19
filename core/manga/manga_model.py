import os
import re
import logging
from dataclasses import dataclass, field
from typing import List, Set, Optional, Tuple


@dataclass
class MangaInfo:
    """一个纯粹的漫画信息数据类"""
    file_path: str
    title: str
    tags: Set[str] = field(default_factory=set)
    total_pages: int = 0
    is_valid: bool = False
    pages: List[str] = field(default_factory=list)
    last_modified: float = 0.0
    file_size: int = 0
    file_type: str = 'unknown'

    # 页面尺寸分析相关属性
    page_dimensions: List[Tuple[int, int]] = field(default_factory=list)
    dimension_variance: Optional[float] = None
    is_likely_manga: Optional[bool] = None

    def __post_init__(self):
        # 修改验证逻辑：只要有标题标签，就认为漫画是有效的。
        # 对作者的校验过于严格，可能导致很多文件被跳过。
        has_title = any(tag.startswith("标题:") for tag in self.tags)
        self.is_valid = has_title
    def __lt__(self, other):
        """
        重载小于运算符，用于排序和bisect。
        我们希望按 last_modified 降序排列（最新的在前），
        所以当 self 的时间戳更大时，它应该被认为是“更小”的，以便排在前面。
        """
        if not isinstance(other, MangaInfo):
            return NotImplemented
        return self.last_modified > other.last_modified


    def get_page_path(self, page_index):
        """获取指定页码的图像路径（兼容方法）"""
        if 0 <= page_index < len(self.pages):
            return self.pages[page_index]
        return None

