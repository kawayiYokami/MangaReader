# core/translation_priority_calculator.py
"""
翻译优先级计算器

基于阅读权重算法计算翻译任务的优先级。
"""

from typing import Dict, List, Tuple, Optional
import os
from .translation_queue_models import TaskPriority
from utils import manga_logger as log


class TranslationPriorityCalculator:
    """翻译优先级计算器"""
    
    def __init__(self):
        """初始化优先级计算器"""
        # 优先级权重配置
        self.priority_weights = {
            TaskPriority.P0_CURRENT: 1000,    # 当前页面 - 最高权重
            TaskPriority.P1_ADJACENT: 100,    # 相邻页面 - 高权重
            TaskPriority.P2_SAME_MANGA: 10,   # 同一漫画 - 中权重
            TaskPriority.P3_OTHER_MANGA: 1    # 其他漫画 - 低权重
        }
        
        # 距离衰减因子
        self.distance_decay_factor = 0.8
        
        # 最大预加载距离
        self.max_preload_distance = 5
    
    def calculate_priority(self, manga_path: str, page_index: int, 
                          current_manga_path: str, current_page_index: int,
                          reading_direction: str = "ltr") -> TaskPriority:
        """
        计算翻译任务的优先级
        
        Args:
            manga_path: 任务漫画路径
            page_index: 任务页面索引
            current_manga_path: 当前阅读漫画路径
            current_page_index: 当前阅读页面索引
            reading_direction: 阅读方向 ("ltr": 从左到右, "rtl": 从右到左)
            
        Returns:
            任务优先级
        """
        # 不同漫画的任务优先级最低
        if manga_path != current_manga_path:
            return TaskPriority.P3_OTHER_MANGA
        
        # 计算页面距离
        page_distance = abs(page_index - current_page_index)
        
        # 当前页面
        if page_distance == 0:
            return TaskPriority.P0_CURRENT
        
        # 相邻页面（考虑阅读方向）
        if page_distance <= 2:
            return TaskPriority.P1_ADJACENT
        
        # 同一漫画的其他页面
        return TaskPriority.P2_SAME_MANGA
    
    def calculate_reading_weight(self, manga_path: str, page_index: int,
                               current_manga_path: str, current_page_index: int,
                               reading_direction: str = "ltr") -> float:
        """
        计算阅读权重（参考缓存池算法）
        
        Args:
            manga_path: 任务漫画路径
            page_index: 任务页面索引
            current_manga_path: 当前阅读漫画路径
            current_page_index: 当前阅读页面索引
            reading_direction: 阅读方向
            
        Returns:
            阅读权重值（越高越重要）
        """
        # 不同漫画的权重很低
        if manga_path != current_manga_path:
            return 0.1
        
        # 计算页面距离
        page_distance = abs(page_index - current_page_index)
        
        # 当前页面权重最高
        if page_distance == 0:
            return 1000.0
        
        # 超出预加载范围的页面权重很低
        if page_distance > self.max_preload_distance:
            return 0.5
        
        # 基础权重
        base_weight = 100.0
        
        # 距离衰减
        distance_weight = base_weight * (self.distance_decay_factor ** page_distance)
        
        # 阅读方向加权
        direction_multiplier = 1.0
        if reading_direction == "ltr":
            # 从左到右阅读，后续页面权重稍高
            if page_index > current_page_index:
                direction_multiplier = 1.2
            else:
                direction_multiplier = 0.8
        elif reading_direction == "rtl":
            # 从右到左阅读，前面页面权重稍高
            if page_index < current_page_index:
                direction_multiplier = 1.2
            else:
                direction_multiplier = 0.8
        
        return distance_weight * direction_multiplier
    
    def get_preload_pages(self, current_manga_path: str, current_page_index: int,
                         total_pages: int, reading_direction: str = "ltr",
                         preload_count: int = 5) -> List[Tuple[int, TaskPriority]]:
        """
        获取需要预加载的页面列表
        
        Args:
            current_manga_path: 当前漫画路径
            current_page_index: 当前页面索引
            total_pages: 总页面数
            reading_direction: 阅读方向
            preload_count: 预加载页面数量
            
        Returns:
            (页面索引, 优先级) 的列表，按优先级排序
        """
        preload_pages = []
        
        # 生成候选页面
        candidates = []
        
        # 相邻页面
        for offset in range(1, self.max_preload_distance + 1):
            # 前面的页面
            prev_page = current_page_index - offset
            if prev_page >= 0:
                priority = self.calculate_priority(
                    current_manga_path, prev_page, 
                    current_manga_path, current_page_index, 
                    reading_direction
                )
                weight = self.calculate_reading_weight(
                    current_manga_path, prev_page,
                    current_manga_path, current_page_index,
                    reading_direction
                )
                candidates.append((prev_page, priority, weight))
            
            # 后面的页面
            next_page = current_page_index + offset
            if next_page < total_pages:
                priority = self.calculate_priority(
                    current_manga_path, next_page,
                    current_manga_path, current_page_index,
                    reading_direction
                )
                weight = self.calculate_reading_weight(
                    current_manga_path, next_page,
                    current_manga_path, current_page_index,
                    reading_direction
                )
                candidates.append((next_page, priority, weight))
        
        # 按权重排序
        candidates.sort(key=lambda x: x[2], reverse=True)
        
        # 选择前N个页面
        for page_index, priority, weight in candidates[:preload_count]:
            preload_pages.append((page_index, priority))
        
        return preload_pages
    
    def should_preload(self, manga_path: str, page_index: int,
                      current_manga_path: str, current_page_index: int,
                      reading_direction: str = "ltr") -> bool:
        """
        判断是否应该预加载指定页面
        
        Args:
            manga_path: 页面漫画路径
            page_index: 页面索引
            current_manga_path: 当前漫画路径
            current_page_index: 当前页面索引
            reading_direction: 阅读方向
            
        Returns:
            是否应该预加载
        """
        # 不同漫画不预加载
        if manga_path != current_manga_path:
            return False
        
        # 当前页面不需要预加载
        if page_index == current_page_index:
            return False
        
        # 计算距离
        page_distance = abs(page_index - current_page_index)
        
        # 超出预加载范围
        if page_distance > self.max_preload_distance:
            return False
        
        # 计算权重
        weight = self.calculate_reading_weight(
            manga_path, page_index,
            current_manga_path, current_page_index,
            reading_direction
        )
        
        # 权重阈值
        return weight >= 10.0
    
    def update_priorities_for_reading_position(self, tasks: List[Dict], 
                                             current_manga_path: str, 
                                             current_page_index: int,
                                             reading_direction: str = "ltr") -> List[Dict]:
        """
        根据当前阅读位置更新任务优先级
        
        Args:
            tasks: 任务列表
            current_manga_path: 当前漫画路径
            current_page_index: 当前页面索引
            reading_direction: 阅读方向
            
        Returns:
            更新后的任务列表
        """
        updated_tasks = []
        
        for task in tasks:
            # 计算新优先级
            new_priority = self.calculate_priority(
                task['manga_path'], task['page_index'],
                current_manga_path, current_page_index,
                reading_direction
            )
            
            # 更新任务
            updated_task = task.copy()
            updated_task['priority'] = new_priority
            updated_task['reading_weight'] = self.calculate_reading_weight(
                task['manga_path'], task['page_index'],
                current_manga_path, current_page_index,
                reading_direction
            )
            
            updated_tasks.append(updated_task)
        
        # 按优先级和权重排序
        updated_tasks.sort(key=lambda x: (x['priority'].value, -x['reading_weight']))
        
        return updated_tasks
    
    def get_priority_description(self, priority: TaskPriority) -> str:
        """获取优先级描述"""
        descriptions = {
            TaskPriority.P0_CURRENT: "当前页面 - 立即处理",
            TaskPriority.P1_ADJACENT: "相邻页面 - 高优先级预加载",
            TaskPriority.P2_SAME_MANGA: "同一漫画 - 中优先级预加载",
            TaskPriority.P3_OTHER_MANGA: "其他漫画 - 低优先级后台处理"
        }
        return descriptions.get(priority, "未知优先级")
    
    def get_statistics(self, tasks: List[Dict]) -> Dict[str, int]:
        """获取优先级统计"""
        stats = {
            'p0_count': 0,
            'p1_count': 0,
            'p2_count': 0,
            'p3_count': 0,
            'total_count': len(tasks)
        }
        
        for task in tasks:
            priority = task.get('priority', TaskPriority.P3_OTHER_MANGA)
            if priority == TaskPriority.P0_CURRENT:
                stats['p0_count'] += 1
            elif priority == TaskPriority.P1_ADJACENT:
                stats['p1_count'] += 1
            elif priority == TaskPriority.P2_SAME_MANGA:
                stats['p2_count'] += 1
            elif priority == TaskPriority.P3_OTHER_MANGA:
                stats['p3_count'] += 1
        
        return stats
