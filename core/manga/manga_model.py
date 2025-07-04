import os
import re
from utils import manga_logger as log
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

    def analyze_page_dimensions(self):
        """分析页面尺寸一致性，计算方差分数"""
        if not self.page_dimensions or len(self.page_dimensions) < 2:
            self.dimension_variance = 0.0
            self.is_likely_manga = True
            return

        try:
            import numpy as np

            # 转换为numpy数组便于计算
            dimensions = np.array(self.page_dimensions)
            widths = dimensions[:, 0]
            heights = dimensions[:, 1]

            # 计算宽高比
            aspect_ratios = widths / heights

            # 计算面积
            areas = widths * heights

            # 使用变异系数 (CV = std/mean) 来衡量一致性
            # 变异系数对尺寸大小不敏感，更适合评估相对变化

            # 宽度变异系数
            width_cv = np.std(widths) / np.mean(widths) if np.mean(widths) > 0 else 0

            # 高度变异系数
            height_cv = np.std(heights) / np.mean(heights) if np.mean(heights) > 0 else 0

            # 宽高比变异系数
            ratio_cv = np.std(aspect_ratios) / np.mean(aspect_ratios) if np.mean(aspect_ratios) > 0 else 0

            # 面积变异系数
            area_cv = np.std(areas) / np.mean(areas) if np.mean(areas) > 0 else 0

            # 综合方差分数：取各项变异系数的加权平均
            # 宽高比权重最高，因为漫画页面宽高比通常很一致
            # 面积权重次之，宽高权重较低
            variance_score = (
                ratio_cv * 0.4 +      # 宽高比权重40%
                area_cv * 0.3 +       # 面积权重30%
                width_cv * 0.15 +     # 宽度权重15%
                height_cv * 0.15      # 高度权重15%
            )

            # 限制分数在0-1范围内
            self.dimension_variance = min(variance_score, 1.0)

            # 判断是否可能是漫画
            # 使用配置中的阈值
            from core.config import config
            manga_threshold = config.dimension_variance_threshold.value
            self.is_likely_manga = self.dimension_variance < manga_threshold

            log.debug(f"尺寸分析完成 {self.file_path}: "
                     f"方差分数={self.dimension_variance:.3f}, "
                     f"可能是漫画={self.is_likely_manga}, "
                     f"页数={len(self.page_dimensions)}")

        except Exception as e:
            log.warning(f"页面尺寸分析失败 {self.file_path}: {e}")
            # 分析失败时保守处理
            self.dimension_variance = 0.0
            self.is_likely_manga = True
