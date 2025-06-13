# core/translation_queue_models.py
"""
翻译队列数据模型

定义翻译队列系统的核心数据结构。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid


class TaskStatus(Enum):
    """翻译任务状态枚举"""
    PENDING = "pending"           # 等待中
    PROCESSING = "processing"     # 进行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"       # 已取消


class TaskPriority(Enum):
    """翻译任务优先级枚举"""
    P0_CURRENT = 0    # 当前阅读页面 - 最高优先级
    P1_ADJACENT = 1   # 相邻页面 - 高优先级
    P2_SAME_MANGA = 2 # 同一漫画其他页面 - 中优先级
    P3_OTHER_MANGA = 3 # 其他漫画页面 - 低优先级


@dataclass
class TranslationTask:
    """翻译任务数据模型"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    manga_path: str = ""
    page_index: int = 0
    target_language: str = "zh"
    priority: TaskPriority = TaskPriority.P3_OTHER_MANGA
    status: TaskStatus = TaskStatus.PENDING
    
    # 请求信息
    user_id: Optional[str] = None
    request_time: datetime = field(default_factory=datetime.now)
    
    # 处理信息
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    processing_duration: Optional[float] = None
    
    # 重试信息
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    
    # 缓存信息
    image_hash: Optional[str] = None
    cache_key: Optional[str] = None
    force_retranslate: bool = False
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理"""
        if isinstance(self.request_time, str):
            self.request_time = datetime.fromisoformat(self.request_time)
        if isinstance(self.start_time, str) and self.start_time:
            self.start_time = datetime.fromisoformat(self.start_time)
        if isinstance(self.end_time, str) and self.end_time:
            self.end_time = datetime.fromisoformat(self.end_time)
    
    @property
    def is_active(self) -> bool:
        """任务是否处于活跃状态"""
        return self.status in [TaskStatus.PENDING, TaskStatus.PROCESSING]
    
    @property
    def is_completed(self) -> bool:
        """任务是否已完成"""
        return self.status == TaskStatus.COMPLETED
    
    @property
    def is_failed(self) -> bool:
        """任务是否失败"""
        return self.status == TaskStatus.FAILED
    
    @property
    def can_retry(self) -> bool:
        """任务是否可以重试"""
        return self.is_failed and self.retry_count < self.max_retries
    
    @property
    def wait_time(self) -> float:
        """等待时间（秒）"""
        if self.start_time:
            return (self.start_time - self.request_time).total_seconds()
        return (datetime.now() - self.request_time).total_seconds()
    
    @property
    def total_time(self) -> float:
        """总处理时间（秒）"""
        if self.end_time:
            return (self.end_time - self.request_time).total_seconds()
        return (datetime.now() - self.request_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'task_id': self.task_id,
            'manga_path': self.manga_path,
            'page_index': self.page_index,
            'target_language': self.target_language,
            'priority': self.priority.value,
            'status': self.status.value,
            'user_id': self.user_id,
            'request_time': self.request_time.isoformat(),
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'processing_duration': self.processing_duration,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'last_error': self.last_error,
            'image_hash': self.image_hash,
            'cache_key': self.cache_key,
            'force_retranslate': self.force_retranslate,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TranslationTask':
        """从字典创建任务对象"""
        task = cls()
        task.task_id = data.get('task_id', task.task_id)
        task.manga_path = data.get('manga_path', '')
        task.page_index = data.get('page_index', 0)
        task.target_language = data.get('target_language', 'zh')
        task.priority = TaskPriority(data.get('priority', TaskPriority.P3_OTHER_MANGA.value))
        task.status = TaskStatus(data.get('status', TaskStatus.PENDING.value))
        task.user_id = data.get('user_id')
        task.request_time = datetime.fromisoformat(data['request_time']) if data.get('request_time') else datetime.now()
        task.start_time = datetime.fromisoformat(data['start_time']) if data.get('start_time') else None
        task.end_time = datetime.fromisoformat(data['end_time']) if data.get('end_time') else None
        task.processing_duration = data.get('processing_duration')
        task.retry_count = data.get('retry_count', 0)
        task.max_retries = data.get('max_retries', 3)
        task.last_error = data.get('last_error')
        task.image_hash = data.get('image_hash')
        task.cache_key = data.get('cache_key')
        task.force_retranslate = data.get('force_retranslate', False)
        task.metadata = data.get('metadata', {})
        return task


@dataclass
class QueueStatistics:
    """队列统计信息"""
    total_tasks: int = 0
    pending_tasks: int = 0
    processing_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    cancelled_tasks: int = 0
    
    # 优先级分布
    p0_tasks: int = 0
    p1_tasks: int = 0
    p2_tasks: int = 0
    p3_tasks: int = 0
    
    # 性能指标
    average_wait_time: float = 0.0
    average_processing_time: float = 0.0
    success_rate: float = 0.0
    
    # 时间统计
    last_updated: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'total_tasks': self.total_tasks,
            'pending_tasks': self.pending_tasks,
            'processing_tasks': self.processing_tasks,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'cancelled_tasks': self.cancelled_tasks,
            'p0_tasks': self.p0_tasks,
            'p1_tasks': self.p1_tasks,
            'p2_tasks': self.p2_tasks,
            'p3_tasks': self.p3_tasks,
            'average_wait_time': self.average_wait_time,
            'average_processing_time': self.average_processing_time,
            'success_rate': self.success_rate,
            'last_updated': self.last_updated.isoformat()
        }


@dataclass
class QueueConfig:
    """队列配置"""
    max_concurrent_tasks: int = 3        # 最大并发任务数
    max_queue_size: int = 100           # 最大队列长度
    task_timeout_seconds: int = 300     # 任务超时时间（秒）
    cleanup_interval_seconds: int = 60  # 清理间隔（秒）
    retry_delay_seconds: int = 30       # 重试延迟（秒）
    enable_persistence: bool = True     # 启用持久化
    persistence_interval_seconds: int = 10  # 持久化间隔（秒）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'max_concurrent_tasks': self.max_concurrent_tasks,
            'max_queue_size': self.max_queue_size,
            'task_timeout_seconds': self.task_timeout_seconds,
            'cleanup_interval_seconds': self.cleanup_interval_seconds,
            'retry_delay_seconds': self.retry_delay_seconds,
            'enable_persistence': self.enable_persistence,
            'persistence_interval_seconds': self.persistence_interval_seconds
        }


class QueueEvent:
    """队列事件类"""
    
    # 事件类型
    TASK_ADDED = "task_added"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"
    TASK_RETRIED = "task_retried"
    QUEUE_UPDATED = "queue_updated"
    QUEUE_CLEARED = "queue_cleared"
    
    def __init__(self, event_type: str, task: Optional[TranslationTask] = None, 
                 data: Optional[Dict[str, Any]] = None):
        self.event_type = event_type
        self.task = task
        self.data = data or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'event_type': self.event_type,
            'task': self.task.to_dict() if self.task else None,
            'data': self.data,
            'timestamp': self.timestamp.isoformat()
        }
