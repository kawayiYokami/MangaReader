#!/usr/bin/env python3
"""
实时翻译管理器 - 负责异步翻译当前漫画页面
"""

import os
import threading
import time
import queue
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

from core.image_translator import ImageTranslator
from core.manga_model import MangaLoader
from utils import manga_logger as log


class TranslationStatus(Enum):
    """翻译状态枚举"""
    PENDING = "pending"      # 等待翻译
    TRANSLATING = "translating"  # 正在翻译
    COMPLETED = "completed"  # 翻译完成
    FAILED = "failed"        # 翻译失败
    CANCELLED = "cancelled"  # 已取消


@dataclass
class TranslationTask:
    """翻译任务数据类"""
    manga_path: str
    page_index: int
    priority: int  # 优先级，数字越小优先级越高
    status: TranslationStatus = TranslationStatus.PENDING
    result_image: Optional[Any] = None
    error_message: Optional[str] = None
    created_time: float = 0.0
    
    def __post_init__(self):
        if self.created_time == 0.0:
            self.created_time = time.time()


class RealtimeTranslator:
    """实时翻译管理器"""
    
    def __init__(self):
        self.manga_loader = MangaLoader()
        self.image_translator = None
        
        # 翻译队列和状态管理
        self.task_queue = queue.PriorityQueue()
        self.completed_translations: Dict[str, Any] = {}  # key: "manga_path:page_index"
        self.current_task: Optional[TranslationTask] = None
        
        # 线程控制
        self.worker_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.stop_event = threading.Event()
        
        # 当前漫画状态
        self.current_manga_path: Optional[str] = None
        self.current_page_index: int = 0
        
        # 回调函数
        self.translation_completed_callback: Optional[Callable] = None
        self.translation_progress_callback: Optional[Callable] = None
        
        # 线程锁
        self.lock = threading.Lock()
        
        log.info("实时翻译管理器初始化完成")
    
    def set_translator_config(self, translator_type: str = "智谱", **kwargs):
        """设置翻译器配置"""
        try:
            self.image_translator = ImageTranslator(translator_type, **kwargs)
            log.info(f"翻译器配置完成: {translator_type}")
        except Exception as e:
            log.error(f"翻译器配置失败: {e}")
            self.image_translator = None
    
    def set_callbacks(self, 
                     completed_callback: Optional[Callable] = None,
                     progress_callback: Optional[Callable] = None):
        """设置回调函数"""
        self.translation_completed_callback = completed_callback
        self.translation_progress_callback = progress_callback
    
    def start_translation_service(self):
        """启动翻译服务"""
        if self.is_running:
            log.warning("翻译服务已在运行")
            return
        
        if not self.image_translator:
            log.error("翻译器未配置，无法启动翻译服务")
            return
        
        self.is_running = True
        self.stop_event.clear()
        
        self.worker_thread = threading.Thread(
            target=self._translation_worker,
            daemon=True,
            name="RealtimeTranslationWorker"
        )
        self.worker_thread.start()
        
        log.info("实时翻译服务已启动")
    
    def stop_translation_service(self):
        """停止翻译服务"""
        if not self.is_running:
            return
        
        log.info("正在停止实时翻译服务...")
        self.is_running = False
        self.stop_event.set()
        
        # 取消当前翻译
        if self.image_translator:
            self.image_translator.cancel_flag.set()
        
        # 等待工作线程结束
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5.0)
        
        # 清空队列
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
            except queue.Empty:
                break
        
        log.info("实时翻译服务已停止")
    
    def set_current_manga(self, manga_path: str, current_page: int = 0):
        """设置当前漫画和页面"""
        with self.lock:
            # 如果切换了漫画，清空相关缓存
            if self.current_manga_path != manga_path:
                log.info(f"切换漫画: {self.current_manga_path} -> {manga_path}")
                self._clear_manga_cache(self.current_manga_path)
            
            self.current_manga_path = manga_path
            self.current_page_index = current_page
            
            # 重新排列翻译队列
            self._reorder_translation_queue()
    
    def request_translation(self, manga_path: str, page_index: int, priority: int = 10):
        """请求翻译指定页面"""
        if not self.is_running:
            log.warning("翻译服务未启动，无法请求翻译")
            return
        
        # 检查是否已经翻译过
        cache_key = f"{manga_path}:{page_index}"
        if cache_key in self.completed_translations:
            log.debug(f"页面已翻译过，跳过: {cache_key}")
            return
        
        # 创建翻译任务
        task = TranslationTask(
            manga_path=manga_path,
            page_index=page_index,
            priority=priority
        )
        
        # 添加到队列
        self.task_queue.put((priority, time.time(), task))
        log.debug(f"添加翻译任务: {cache_key}, 优先级: {priority}")
    
    def get_translated_page(self, manga_path: str, page_index: int) -> Optional[Any]:
        """获取翻译后的页面图像"""
        cache_key = f"{manga_path}:{page_index}"
        return self.completed_translations.get(cache_key)
    
    def is_page_translated(self, manga_path: str, page_index: int) -> bool:
        """检查页面是否已翻译"""
        cache_key = f"{manga_path}:{page_index}"
        return cache_key in self.completed_translations
    
    def get_translation_status(self) -> Dict[str, Any]:
        """获取翻译状态"""
        with self.lock:
            return {
                "is_running": self.is_running,
                "current_manga": self.current_manga_path,
                "current_page": self.current_page_index,
                "queue_size": self.task_queue.qsize(),
                "completed_count": len(self.completed_translations),
                "current_task": {
                    "manga_path": self.current_task.manga_path if self.current_task else None,
                    "page_index": self.current_task.page_index if self.current_task else None,
                    "status": self.current_task.status.value if self.current_task else None
                } if self.current_task else None
            }
    
    def _reorder_translation_queue(self):
        """重新排列翻译队列，以当前页面为起点"""
        if not self.current_manga_path:
            return
        
        # 提取所有任务
        tasks = []
        while not self.task_queue.empty():
            try:
                _, _, task = self.task_queue.get_nowait()
                if task.manga_path == self.current_manga_path:
                    tasks.append(task)
            except queue.Empty:
                break
        
        # 重新计算优先级（距离当前页面越近优先级越高）
        for task in tasks:
            distance = abs(task.page_index - self.current_page_index)
            task.priority = distance
        
        # 重新添加到队列
        for task in tasks:
            self.task_queue.put((task.priority, task.created_time, task))
        
        log.debug(f"重新排列翻译队列，当前页面: {self.current_page_index}, 队列大小: {len(tasks)}")
    
    def _clear_manga_cache(self, manga_path: Optional[str]):
        """清空指定漫画的翻译缓存"""
        if not manga_path:
            return
        
        keys_to_remove = [key for key in self.completed_translations.keys() 
                         if key.startswith(f"{manga_path}:")]
        
        for key in keys_to_remove:
            del self.completed_translations[key]
        
        log.info(f"清空漫画翻译缓存: {manga_path}, 移除 {len(keys_to_remove)} 个缓存项")
    
    def _translation_worker(self):
        """翻译工作线程"""
        log.info("翻译工作线程启动")
        
        while self.is_running and not self.stop_event.is_set():
            try:
                # 获取翻译任务（超时1秒）
                try:
                    priority, created_time, task = self.task_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # 检查任务是否仍然有效
                if not self._is_task_valid(task):
                    continue
                
                # 执行翻译
                self._execute_translation(task)
                
            except Exception as e:
                log.error(f"翻译工作线程异常: {e}")
                import traceback
                log.error(traceback.format_exc())
        
        log.info("翻译工作线程结束")
    
    def _is_task_valid(self, task: TranslationTask) -> bool:
        """检查翻译任务是否仍然有效"""
        # 检查是否已经翻译过
        cache_key = f"{task.manga_path}:{task.page_index}"
        if cache_key in self.completed_translations:
            return False
        
        # 检查是否是当前漫画
        if task.manga_path != self.current_manga_path:
            return False
        
        return True
    
    def _execute_translation(self, task: TranslationTask):
        """执行翻译任务"""
        cache_key = f"{task.manga_path}:{task.page_index}"
        
        try:
            with self.lock:
                self.current_task = task
                task.status = TranslationStatus.TRANSLATING
            
            log.info(f"开始翻译: {cache_key}")
            
            # 加载漫画
            manga = self.manga_loader.load_manga(task.manga_path)
            if not manga:
                raise Exception(f"无法加载漫画: {task.manga_path}")
            
            # 获取页面图像
            image = self.manga_loader.get_page_image(manga, task.page_index)
            if image is None:
                raise Exception(f"无法获取页面图像: {task.page_index}")
            
            # 执行翻译
            if self.translation_progress_callback:
                self.translation_progress_callback(cache_key, "translating")
            
            translated_image = self.image_translator.translate_image(
                image_input=image,
                target_language="zh",
                file_path_for_cache=task.manga_path,
                page_num_for_cache=task.page_index
            )
            
            if translated_image is not None:
                # 保存翻译结果
                self.completed_translations[cache_key] = translated_image
                task.status = TranslationStatus.COMPLETED
                task.result_image = translated_image
                
                log.info(f"翻译完成: {cache_key}")
                
                # 调用完成回调
                if self.translation_completed_callback:
                    self.translation_completed_callback(
                        task.manga_path, 
                        task.page_index, 
                        translated_image
                    )
            else:
                raise Exception("翻译返回空结果")
                
        except Exception as e:
            task.status = TranslationStatus.FAILED
            task.error_message = str(e)
            log.error(f"翻译失败: {cache_key}, 错误: {e}")
            
        finally:
            with self.lock:
                self.current_task = None


# 全局实例
_realtime_translator_instance: Optional[RealtimeTranslator] = None


def get_realtime_translator() -> RealtimeTranslator:
    """获取实时翻译器全局实例"""
    global _realtime_translator_instance
    if _realtime_translator_instance is None:
        _realtime_translator_instance = RealtimeTranslator()
    return _realtime_translator_instance
