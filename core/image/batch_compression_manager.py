"""
批量压缩管理器 - 处理漫画文件的批量压缩任务
"""

import os
import time
import uuid
import threading
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import logging
from enum import Enum

from core.image.image_compressor import get_image_compressor


class CoreInterfaceError(Exception):
    """接口层专用异常"""
    def __init__(self, message: str, original_error: Exception = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)


class CompressionStatus(Enum):
    """压缩任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class CompressionTask:
    """压缩任务信息"""
    task_id: str
    total_files: int
    processed_files: int = 0
    successful_files: int = 0
    failed_files: int = 0
    status: CompressionStatus = CompressionStatus.PENDING
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error_message: Optional[str] = None
    current_file: Optional[str] = None
    cancel_flag: threading.Event = field(default_factory=threading.Event)


@dataclass
class CompressionResult:
    """压缩结果信息"""
    original_path: str
    compressed_path: Optional[str]
    success: bool
    error_message: Optional[str] = None
    compression_ratio: Optional[float] = None


class BatchCompressionManager:
    """批量压缩管理器"""

    def __init__(self):
        self.tasks: Dict[str, CompressionTask] = {}
        self.results: Dict[str, List[CompressionResult]] = {}
        self._lock = threading.Lock()

    def create_task(self, total_files: int) -> str:
        """创建新的压缩任务"""
        task_id = str(uuid.uuid4())

        with self._lock:
            self.tasks[task_id] = CompressionTask(
                task_id=task_id,
                total_files=total_files
            )
            self.results[task_id] = []

        logging.info(f"创建批量压缩任务: {task_id}, 文件总数: {total_files}")
        return task_id

    def get_task(self, task_id: str) -> Optional[CompressionTask]:
        """获取任务信息"""
        with self._lock:
            return self.tasks.get(task_id)

    def update_task_progress(self, task_id: str, processed: int, successful: int,
                           current_file: Optional[str] = None):
        """更新任务进度"""
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                task.processed_files = processed
                task.successful_files = successful
                task.failed_files = processed - successful
                task.current_file = current_file

    def complete_task(self, task_id: str, success: bool = True,
                     error_message: Optional[str] = None):
        """完成任务"""
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                task.status = CompressionStatus.COMPLETED if success else CompressionStatus.FAILED
                task.end_time = time.time()
                if error_message:
                    task.error_message = error_message

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self._lock:
            task = self.tasks.get(task_id)
            if task and task.status in [CompressionStatus.PENDING, CompressionStatus.RUNNING]:
                task.status = CompressionStatus.CANCELLED
                task.cancel_flag.set()
                task.end_time = time.time()
                logging.info(f"任务 {task_id} 已取消")
                return True
            return False

    def add_result(self, task_id: str, result: CompressionResult):
        """添加压缩结果"""
        with self._lock:
            if task_id in self.results:
                self.results[task_id].append(result)

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                raise CoreInterfaceError(f"任务 {task_id} 不存在")

            results = self.results.get(task_id, [])

            return {
                "task_id": task.task_id,
                "status": task.status.value,
                "total_files": task.total_files,
                "processed_files": task.processed_files,
                "successful_files": task.successful_files,
                "failed_files": task.failed_files,
                "progress": (task.processed_files / task.total_files * 100) if task.total_files > 0 else 0,
                "current_file": task.current_file,
                "start_time": task.start_time,
                "end_time": task.end_time,
                "duration": (task.end_time - task.start_time) if task.start_time and task.end_time else None,
                "error_message": task.error_message,
                "results": [
                    {
                        "original_path": r.original_path,
                        "compressed_path": r.compressed_path,
                        "success": r.success,
                        "error_message": r.error_message,
                        "compression_ratio": r.compression_ratio
                    }
                    for r in results[-10:]  # 只返回最近10个结果，避免响应过大
                ]
            }


# 全局批量压缩管理器实例
_batch_compression_manager = None

def get_batch_compression_manager() -> BatchCompressionManager:
    """获取批量压缩管理器实例"""
    global _batch_compression_manager
    if _batch_compression_manager is None:
        _batch_compression_manager = BatchCompressionManager()
    return _batch_compression_manager