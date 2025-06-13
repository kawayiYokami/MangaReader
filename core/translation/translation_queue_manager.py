# core/translation_queue_manager.py
"""
翻译队列管理器

负责统一协调所有翻译请求的核心管理类。
"""

import threading
import time
import json
import os
from typing import List, Dict, Optional, Callable, Set, Any
from datetime import datetime, timedelta
from collections import defaultdict
import sqlite3
from pathlib import Path

from .translation_queue_models import (
    TranslationTask, TaskStatus, TaskPriority, QueueStatistics, 
    QueueConfig, QueueEvent
)
from utils import manga_logger as log


class TranslationQueueManager:
    """翻译队列管理器"""
    
    def __init__(self, config: Optional[QueueConfig] = None, db_path: Optional[str] = None):
        """
        初始化队列管理器
        
        Args:
            config: 队列配置
            db_path: 数据库路径
        """
        self.config = config or QueueConfig()
        self.db_path = db_path or "app/config/translation_queue.db"
        
        # 队列存储
        self._queue: List[TranslationTask] = []
        self._processing_tasks: Dict[str, TranslationTask] = {}
        self._completed_tasks: Dict[str, TranslationTask] = {}
        self._failed_tasks: Dict[str, TranslationTask] = {}
        
        # 线程安全锁
        self._lock = threading.RLock()
        
        # 事件回调
        self._event_callbacks: List[Callable[[QueueEvent], None]] = []
        
        # 去重集合
        self._task_keys: Set[str] = set()  # manga_path:page_index:target_language
        
        # 后台线程
        self._cleanup_thread: Optional[threading.Thread] = None
        self._persistence_thread: Optional[threading.Thread] = None
        self._running = False
        
        # 统计信息
        self._statistics = QueueStatistics()

        # 初始化数据库
        self._init_database()

    @property
    def processing_tasks(self) -> Dict[str, TranslationTask]:
        """获取正在处理的任务"""
        return self._processing_tasks
        
        # 加载持久化数据
        if self.config.enable_persistence:
            self._load_from_database()
        
        # 启动后台线程
        self.start()
    
    def _init_database(self):
        """初始化数据库"""
        try:
            # 确保数据目录存在
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS translation_tasks (
                        task_id TEXT PRIMARY KEY,
                        manga_path TEXT NOT NULL,
                        page_index INTEGER NOT NULL,
                        target_language TEXT NOT NULL,
                        priority INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        user_id TEXT,
                        request_time TEXT NOT NULL,
                        start_time TEXT,
                        end_time TEXT,
                        processing_duration REAL,
                        retry_count INTEGER DEFAULT 0,
                        max_retries INTEGER DEFAULT 3,
                        last_error TEXT,
                        image_hash TEXT,
                        cache_key TEXT,
                        force_retranslate BOOLEAN DEFAULT 0,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 创建索引
                conn.execute('CREATE INDEX IF NOT EXISTS idx_manga_page ON translation_tasks(manga_path, page_index)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_status ON translation_tasks(status)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_priority ON translation_tasks(priority)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_request_time ON translation_tasks(request_time)')
                
                conn.commit()
                
            log.info(f"翻译队列数据库初始化完成: {self.db_path}")
            
        except Exception as e:
            log.error(f"初始化翻译队列数据库失败: {e}")
            raise
    
    def _load_from_database(self):
        """从数据库加载任务"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM translation_tasks 
                    WHERE status IN ('pending', 'processing')
                    ORDER BY priority ASC, request_time ASC
                ''')
                
                for row in cursor:
                    task_data = dict(row)
                    # 解析metadata
                    if task_data['metadata']:
                        task_data['metadata'] = json.loads(task_data['metadata'])
                    else:
                        task_data['metadata'] = {}
                    
                    task = TranslationTask.from_dict(task_data)
                    
                    # 重置处理中的任务为等待状态
                    if task.status == TaskStatus.PROCESSING:
                        task.status = TaskStatus.PENDING
                        task.start_time = None
                    
                    self._queue.append(task)
                    self._task_keys.add(self._get_task_key(task))
                
                log.info(f"从数据库加载了 {len(self._queue)} 个翻译任务")
                
        except Exception as e:
            log.error(f"从数据库加载翻译任务失败: {e}")
    
    def _get_task_key(self, task: TranslationTask) -> str:
        """获取任务唯一键"""
        return f"{task.manga_path}:{task.page_index}:{task.target_language}"

    def _sort_queue(self):
        """对队列进行排序"""
        self._queue.sort(key=lambda task: (
            task.priority.value,  # 优先级
            task.request_time     # 请求时间
        ))
    
    def start(self):
        """启动队列管理器"""
        if self._running:
            return
        
        self._running = True
        
        # 启动清理线程
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        
        # 启动持久化线程
        if self.config.enable_persistence:
            self._persistence_thread = threading.Thread(target=self._persistence_worker, daemon=True)
            self._persistence_thread.start()
        
        log.info("翻译队列管理器已启动")
    
    def stop(self):
        """停止队列管理器"""
        self._running = False
        
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        
        if self._persistence_thread:
            self._persistence_thread.join(timeout=5)
        
        # 保存当前状态
        if self.config.enable_persistence:
            self._save_to_database()
        
        log.info("翻译队列管理器已停止")
    
    def add_task(self, manga_path: str, page_index: int, target_language: str = "zh",
                 priority: Optional[TaskPriority] = None, user_id: Optional[str] = None,
                 force_retranslate: bool = False, metadata: Optional[Dict] = None) -> Optional[str]:
        """
        添加翻译任务
        
        Args:
            manga_path: 漫画路径
            page_index: 页面索引
            target_language: 目标语言
            priority: 任务优先级
            user_id: 用户ID
            force_retranslate: 强制重新翻译
            metadata: 元数据
            
        Returns:
            任务ID，如果任务已存在则返回None
        """
        with self._lock:
            # 检查队列是否已满
            if len(self._queue) >= self.config.max_queue_size:
                log.warning(f"翻译队列已满，无法添加新任务: {manga_path}:{page_index}")
                return None
            
            # 生成任务键
            task_key = f"{manga_path}:{page_index}:{target_language}"
            
            # 检查是否已存在（去重）
            if not force_retranslate and task_key in self._task_keys:
                log.debug(f"翻译任务已存在，跳过添加: {task_key}")
                return None
            
            # 创建任务
            task = TranslationTask(
                manga_path=manga_path,
                page_index=page_index,
                target_language=target_language,
                priority=priority or TaskPriority.P3_OTHER_MANGA,
                user_id=user_id,
                force_retranslate=force_retranslate,
                metadata=metadata or {}
            )
            
            # 添加到队列
            self._queue.append(task)
            self._task_keys.add(task_key)
            
            # 重新排序
            self._sort_queue()
            
            # 触发事件
            self._emit_event(QueueEvent(QueueEvent.TASK_ADDED, task))
            
            log.info(f"添加翻译任务: {task.task_id} - {manga_path}:{page_index} (优先级: {task.priority.name})")
            
            return task.task_id

    def is_task_in_queue(self, manga_path: str, page_index: int, target_language: str = "zh") -> bool:
        """
        检查任务是否已在队列中（包括等待队列和处理中任务）

        Args:
            manga_path: 漫画路径
            page_index: 页面索引
            target_language: 目标语言

        Returns:
            是否在队列中
        """
        with self._lock:
            task_key = f"{manga_path}:{page_index}:{target_language}"

            # 检查是否在任务键集合中
            if task_key in self._task_keys:
                return True

            # 检查是否在处理中任务中
            for task in self._processing_tasks.values():
                if (task.manga_path == manga_path and
                    task.page_index == page_index and
                    task.target_language == target_language):
                    return True

            return False

    def get_next_task(self) -> Optional[TranslationTask]:
        """获取下一个待处理的任务"""
        with self._lock:
            if not self._queue:
                return None

            # 检查并发限制
            if len(self._processing_tasks) >= self.config.max_concurrent_tasks:
                return None

            # 获取第一个任务
            task = self._queue.pop(0)
            task_key = self._get_task_key(task)
            self._task_keys.discard(task_key)

            # 更新任务状态
            task.status = TaskStatus.PROCESSING
            task.start_time = datetime.now()

            # 添加到处理中任务
            self._processing_tasks[task.task_id] = task

            # 触发事件
            self._emit_event(QueueEvent(QueueEvent.TASK_STARTED, task))

            log.info(f"开始处理翻译任务: {task.task_id}")

            return task

    def complete_task(self, task_id: str, success: bool = True, error_message: Optional[str] = None,
                     result_data: Optional[Dict] = None):
        """
        完成翻译任务

        Args:
            task_id: 任务ID
            success: 是否成功
            error_message: 错误信息
            result_data: 结果数据
        """
        with self._lock:
            task = self._processing_tasks.pop(task_id, None)
            if not task:
                log.warning(f"尝试完成不存在的任务: {task_id}")
                return

            # 更新任务状态
            task.end_time = datetime.now()
            if task.start_time:
                task.processing_duration = (task.end_time - task.start_time).total_seconds()

            if success:
                task.status = TaskStatus.COMPLETED
                self._completed_tasks[task_id] = task

                # 更新元数据
                if result_data:
                    task.metadata.update(result_data)

                # 触发事件
                self._emit_event(QueueEvent(QueueEvent.TASK_COMPLETED, task))

                log.info(f"翻译任务完成: {task_id} (耗时: {task.processing_duration:.2f}秒)")

            else:
                task.status = TaskStatus.FAILED
                task.last_error = error_message
                task.retry_count += 1

                # 检查是否可以重试
                if task.can_retry:
                    # 重新添加到队列
                    task.status = TaskStatus.PENDING
                    task.start_time = None
                    task.end_time = None

                    self._queue.append(task)
                    task_key = self._get_task_key(task)
                    self._task_keys.add(task_key)
                    self._sort_queue()

                    # 触发重试事件
                    self._emit_event(QueueEvent(QueueEvent.TASK_RETRIED, task))

                    log.info(f"翻译任务重试: {task_id} (第{task.retry_count}次重试)")

                else:
                    # 标记为最终失败
                    self._failed_tasks[task_id] = task

                    # 触发失败事件
                    self._emit_event(QueueEvent(QueueEvent.TASK_FAILED, task))

                    log.error(f"翻译任务失败: {task_id} - {error_message}")

    def cancel_task(self, task_id: str) -> bool:
        """
        取消翻译任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功取消
        """
        with self._lock:
            # 从队列中查找并移除
            for i, task in enumerate(self._queue):
                if task.task_id == task_id:
                    task = self._queue.pop(i)
                    task_key = self._get_task_key(task)
                    self._task_keys.discard(task_key)

                    task.status = TaskStatus.CANCELLED
                    task.end_time = datetime.now()

                    # 触发事件
                    self._emit_event(QueueEvent(QueueEvent.TASK_CANCELLED, task))

                    log.info(f"取消翻译任务: {task_id}")
                    return True

            # 从处理中任务查找
            task = self._processing_tasks.get(task_id)
            if task:
                # 注意：正在处理的任务需要外部处理器配合取消
                task.status = TaskStatus.CANCELLED
                log.warning(f"任务正在处理中，需要外部配合取消: {task_id}")
                return True

            log.warning(f"未找到要取消的任务: {task_id}")
            return False

    def get_task(self, task_id: str) -> Optional[TranslationTask]:
        """获取指定任务"""
        with self._lock:
            # 在队列中查找
            for task in self._queue:
                if task.task_id == task_id:
                    return task

            # 在处理中任务查找
            if task_id in self._processing_tasks:
                return self._processing_tasks[task_id]

            # 在已完成任务查找
            if task_id in self._completed_tasks:
                return self._completed_tasks[task_id]

            # 在失败任务查找
            if task_id in self._failed_tasks:
                return self._failed_tasks[task_id]

            return None

    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        with self._lock:
            return {
                'queue_length': len(self._queue),
                'processing_count': len(self._processing_tasks),
                'completed_count': len(self._completed_tasks),
                'failed_count': len(self._failed_tasks),
                'max_concurrent': self.config.max_concurrent_tasks,
                'max_queue_size': self.config.max_queue_size,
                'queue_tasks': [task.to_dict() for task in self._queue[:10]],  # 只返回前10个
                'processing_tasks': [task.to_dict() for task in self._processing_tasks.values()],
                'statistics': self._get_statistics().to_dict()
            }

    def get_detailed_status(self) -> Dict[str, Any]:
        """获取详细队列状态"""
        with self._lock:
            stats = self._get_statistics()

            return {
                'queue_length': len(self._queue),
                'processing_count': len(self._processing_tasks),
                'completed_count': len(self._completed_tasks),
                'failed_count': len(self._failed_tasks),
                'max_concurrent': self.config.max_concurrent_tasks,
                'max_queue_size': self.config.max_queue_size,
                'queue_tasks': [task.to_dict() for task in self._queue],  # 返回所有队列任务
                'processing_tasks': [task.to_dict() for task in self._processing_tasks.values()],
                'completed_tasks': [task.to_dict() for task in list(self._completed_tasks.values())[-10:]],  # 最近10个
                'failed_tasks': [task.to_dict() for task in list(self._failed_tasks.values())[-10:]],  # 最近10个
                'statistics': stats.to_dict(),
                'config': {
                    'max_concurrent_tasks': self.config.max_concurrent_tasks,
                    'max_queue_size': self.config.max_queue_size,
                    'task_timeout_seconds': self.config.task_timeout_seconds,
                    'enable_persistence': self.config.enable_persistence
                }
            }

    def reorder_queue(self, current_manga_path: str, current_page_index: int):
        """
        重新排序队列，基于当前阅读位置调整优先级

        Args:
            current_manga_path: 当前漫画路径
            current_page_index: 当前页面索引
        """
        with self._lock:
            updated_count = 0

            for task in self._queue:
                old_priority = task.priority

                # 计算新优先级
                if task.manga_path == current_manga_path:
                    page_diff = abs(task.page_index - current_page_index)

                    if page_diff == 0:
                        # 当前页面
                        task.priority = TaskPriority.P0_CURRENT
                    elif page_diff <= 2:
                        # 相邻页面
                        task.priority = TaskPriority.P1_ADJACENT
                    else:
                        # 同一漫画其他页面
                        task.priority = TaskPriority.P2_SAME_MANGA
                else:
                    # 其他漫画
                    task.priority = TaskPriority.P3_OTHER_MANGA

                if old_priority != task.priority:
                    updated_count += 1

            if updated_count > 0:
                # 重新排序
                self._sort_queue()

                # 触发事件
                self._emit_event(QueueEvent(QueueEvent.QUEUE_UPDATED, data={
                    'updated_count': updated_count,
                    'current_manga': current_manga_path,
                    'current_page': current_page_index
                }))

                log.info(f"重新排序队列，更新了 {updated_count} 个任务的优先级")

    def clear_queue(self, status_filter: Optional[List[TaskStatus]] = None):
        """
        清空队列

        Args:
            status_filter: 状态过滤器，None表示清空所有
        """
        with self._lock:
            if status_filter is None:
                # 清空所有
                cleared_count = len(self._queue)
                self._queue.clear()
                self._task_keys.clear()
                self._completed_tasks.clear()
                self._failed_tasks.clear()
            else:
                # 按状态过滤清空
                cleared_count = 0

                # 清空队列中的指定状态任务
                if TaskStatus.PENDING in status_filter:
                    cleared_count += len(self._queue)
                    for task in self._queue:
                        task_key = self._get_task_key(task)
                        self._task_keys.discard(task_key)
                    self._queue.clear()

                # 清空已完成任务
                if TaskStatus.COMPLETED in status_filter:
                    cleared_count += len(self._completed_tasks)
                    self._completed_tasks.clear()

                # 清空失败任务
                if TaskStatus.FAILED in status_filter:
                    cleared_count += len(self._failed_tasks)
                    self._failed_tasks.clear()

            # 触发事件
            self._emit_event(QueueEvent(QueueEvent.QUEUE_CLEARED, data={
                'cleared_count': cleared_count,
                'status_filter': [s.value for s in status_filter] if status_filter else None
            }))

            log.info(f"清空队列，移除了 {cleared_count} 个任务")



    def add_event_callback(self, callback: Callable[[QueueEvent], None]):
        """添加事件回调"""
        self._event_callbacks.append(callback)

    def remove_event_callback(self, callback: Callable[[QueueEvent], None]):
        """移除事件回调"""
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)

    def _emit_event(self, event: QueueEvent):
        """触发事件"""
        for callback in self._event_callbacks:
            try:
                callback(event)
            except Exception as e:
                log.error(f"事件回调执行失败: {e}")

    def _get_statistics(self) -> QueueStatistics:
        """获取队列统计信息"""
        stats = QueueStatistics()

        # 基本计数
        stats.pending_tasks = len(self._queue)
        stats.processing_tasks = len(self._processing_tasks)
        stats.completed_tasks = len(self._completed_tasks)
        stats.failed_tasks = len(self._failed_tasks)
        stats.total_tasks = stats.pending_tasks + stats.processing_tasks + stats.completed_tasks + stats.failed_tasks

        # 优先级分布
        for task in self._queue:
            if task.priority == TaskPriority.P0_CURRENT:
                stats.p0_tasks += 1
            elif task.priority == TaskPriority.P1_ADJACENT:
                stats.p1_tasks += 1
            elif task.priority == TaskPriority.P2_SAME_MANGA:
                stats.p2_tasks += 1
            elif task.priority == TaskPriority.P3_OTHER_MANGA:
                stats.p3_tasks += 1

        # 性能指标
        all_tasks = list(self._completed_tasks.values()) + list(self._failed_tasks.values())

        if all_tasks:
            # 平均等待时间
            wait_times = [task.wait_time for task in all_tasks if task.start_time]
            if wait_times:
                stats.average_wait_time = sum(wait_times) / len(wait_times)

            # 平均处理时间
            processing_times = [task.processing_duration for task in all_tasks if task.processing_duration]
            if processing_times:
                stats.average_processing_time = sum(processing_times) / len(processing_times)

            # 成功率
            if stats.completed_tasks + stats.failed_tasks > 0:
                stats.success_rate = stats.completed_tasks / (stats.completed_tasks + stats.failed_tasks)

        stats.last_updated = datetime.now()
        self._statistics = stats

        return stats

    def _cleanup_worker(self):
        """清理工作线程"""
        while self._running:
            try:
                self._cleanup_expired_tasks()
                time.sleep(self.config.cleanup_interval_seconds)
            except Exception as e:
                log.error(f"清理工作线程异常: {e}")
                time.sleep(5)

    def _cleanup_expired_tasks(self):
        """清理过期任务"""
        current_time = datetime.now()
        timeout_delta = timedelta(seconds=self.config.task_timeout_seconds)

        with self._lock:
            # 清理超时的处理中任务
            expired_tasks = []
            for task_id, task in self._processing_tasks.items():
                if task.start_time and (current_time - task.start_time) > timeout_delta:
                    expired_tasks.append(task_id)

            for task_id in expired_tasks:
                task = self._processing_tasks.pop(task_id)
                task.status = TaskStatus.FAILED
                task.last_error = "任务超时"
                task.end_time = current_time

                self._failed_tasks[task_id] = task

                # 触发事件
                self._emit_event(QueueEvent(QueueEvent.TASK_FAILED, task))

                log.warning(f"清理超时任务: {task_id}")

            # 清理旧的已完成和失败任务（保留最近24小时的）
            cutoff_time = current_time - timedelta(hours=24)

            # 清理已完成任务
            completed_to_remove = [
                task_id for task_id, task in self._completed_tasks.items()
                if task.end_time and task.end_time < cutoff_time
            ]
            for task_id in completed_to_remove:
                del self._completed_tasks[task_id]

            # 清理失败任务
            failed_to_remove = [
                task_id for task_id, task in self._failed_tasks.items()
                if task.end_time and task.end_time < cutoff_time
            ]
            for task_id in failed_to_remove:
                del self._failed_tasks[task_id]

            if completed_to_remove or failed_to_remove:
                log.info(f"清理旧任务: {len(completed_to_remove)} 个已完成, {len(failed_to_remove)} 个失败")

    def _persistence_worker(self):
        """持久化工作线程"""
        while self._running:
            try:
                self._save_to_database()
                time.sleep(self.config.persistence_interval_seconds)
            except Exception as e:
                log.error(f"持久化工作线程异常: {e}")
                time.sleep(5)

    def _save_to_database(self):
        """保存到数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 清空现有数据
                conn.execute('DELETE FROM translation_tasks')

                # 保存所有活跃任务
                all_tasks = (
                    self._queue +
                    list(self._processing_tasks.values()) +
                    list(self._completed_tasks.values()) +
                    list(self._failed_tasks.values())
                )

                for task in all_tasks:
                    conn.execute('''
                        INSERT INTO translation_tasks (
                            task_id, manga_path, page_index, target_language, priority, status,
                            user_id, request_time, start_time, end_time, processing_duration,
                            retry_count, max_retries, last_error, image_hash, cache_key,
                            force_retranslate, metadata, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        task.task_id, task.manga_path, task.page_index, task.target_language,
                        task.priority.value, task.status.value, task.user_id,
                        task.request_time.isoformat(),
                        task.start_time.isoformat() if task.start_time else None,
                        task.end_time.isoformat() if task.end_time else None,
                        task.processing_duration, task.retry_count, task.max_retries,
                        task.last_error, task.image_hash, task.cache_key,
                        task.force_retranslate, json.dumps(task.metadata),
                        datetime.now().isoformat()
                    ))

                conn.commit()

        except Exception as e:
            log.error(f"保存翻译队列到数据库失败: {e}")

    def __del__(self):
        """析构函数"""
        try:
            self.stop()
        except:
            pass
