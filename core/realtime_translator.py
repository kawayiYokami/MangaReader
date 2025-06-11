#!/usr/bin/env python3
"""
实时翻译管理器 - 负责异步翻译当前漫画页面

重构版本：使用队列管理器和缓存检查器
"""

import os
import threading
import time
import numpy as np
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass

from core.image_translator import ImageTranslator
from core.manga_model import MangaLoader
from core.translation_queue_manager import TranslationQueueManager
from core.translation_queue_models import TaskPriority, TaskStatus, QueueConfig
from core.translation_cache_checker import TranslationCacheChecker
from core.translation_priority_calculator import TranslationPriorityCalculator
from core.cache_factory import get_cache_factory_instance
from core.realtime_translation_cache_utils import RealtimeTranslationCacheUtils
from core.persistent_translation_cache import get_persistent_translation_cache
from utils import manga_logger as log
from utils.image_compression import get_image_compressor


# 移除旧的数据类，使用新的队列管理器中的模型


class RealtimeTranslator:
    """实时翻译管理器 - 重构版本"""

    def __init__(self, queue_config: Optional[QueueConfig] = None):
        """
        初始化实时翻译管理器

        Args:
            queue_config: 队列配置
        """
        self.manga_loader = MangaLoader()
        self.image_translator = None

        # 核心组件
        self.queue_manager = TranslationQueueManager(
            config=queue_config or QueueConfig(),
            db_path="data/translation_queue.db"
        )
        self.cache_checker = TranslationCacheChecker()
        self.priority_calculator = TranslationPriorityCalculator()

        # 持久化缓存和图像压缩
        self.persistent_cache = get_persistent_translation_cache()
        self.image_compressor = get_image_compressor()

        # 内存缓存（快速访问）
        self.completed_translations: Dict[str, Any] = {}  # key: "manga_path:page_index"
        self.preloaded_cache: Dict[str, Any] = {}  # 预加载的缓存数据
        self.cache_preload_lock = threading.Lock()  # 缓存预加载锁

        # 线程控制
        self.worker_threads: List[threading.Thread] = []
        self.is_running = False
        self.stop_event = threading.Event()

        # 当前漫画状态
        self.current_manga_path: Optional[str] = None
        self.current_page_index: int = 0
        self.reading_direction: str = "ltr"  # 阅读方向

        # 回调函数
        self.translation_completed_callback: Optional[Callable] = None
        self.translation_progress_callback: Optional[Callable] = None

        # 线程锁
        self.lock = threading.Lock()

        # 注册队列事件回调
        self.queue_manager.add_event_callback(self._on_queue_event)

        log.info("实时翻译管理器初始化完成（重构版本）")
    
    def set_translator_config(self, translator_type: str = "智谱", **kwargs):
        """设置翻译器配置"""
        try:
            log.info(f"开始配置翻译器: {translator_type}, 参数: {kwargs}")
            self.image_translator = ImageTranslator(translator_type, **kwargs)

            # 检查翻译器是否准备就绪
            if self.image_translator.is_ready():
                log.info(f"翻译器配置完成并准备就绪: {translator_type}")
            else:
                log.warning(f"翻译器配置完成但未完全准备就绪: {translator_type}")

        except Exception as e:
            log.error(f"翻译器配置失败: {e}")
            import traceback
            log.error(traceback.format_exc())
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

        # 启动多个工作线程
        max_workers = self.queue_manager.config.max_concurrent_tasks
        for i in range(max_workers):
            worker_thread = threading.Thread(
                target=self._translation_worker,
                daemon=True,
                name=f"RealtimeTranslationWorker-{i+1}"
            )
            worker_thread.start()
            self.worker_threads.append(worker_thread)

        log.info(f"实时翻译服务已启动，工作线程数: {max_workers}")
    
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

        # 等待所有工作线程结束
        for worker_thread in self.worker_threads:
            if worker_thread.is_alive():
                worker_thread.join(timeout=5.0)

        self.worker_threads.clear()

        # 停止队列管理器
        self.queue_manager.stop()

        log.info("实时翻译服务已停止")
    
    def set_current_manga(self, manga_path: str, current_page: int = 0, reading_direction: str = "ltr") -> bool:
        """设置当前漫画和页面"""
        try:
            with self.lock:
                # 如果切换了漫画，清空相关缓存
                if self.current_manga_path != manga_path:
                    log.info(f"切换漫画: {self.current_manga_path} -> {manga_path}")
                    self._clear_manga_cache(self.current_manga_path)

                    # 为新漫画批量预加载缓存到内存
                    try:
                        preloaded_count = self._batch_preload_manga_cache(manga_path)
                        if preloaded_count > 0:
                            log.info(f"为新漫画批量预加载了 {preloaded_count} 个缓存页面到内存")
                    except Exception as e:
                        log.debug(f"批量预加载缓存失败: {e}")

                self.current_manga_path = manga_path
                self.current_page_index = current_page
                self.reading_direction = reading_direction

                # 重新排序队列
                self.queue_manager.reorder_queue(manga_path, current_page)

                # 自动添加预加载任务
                self._add_preload_tasks()

                return True
        except Exception as e:
            log.error(f"设置当前漫画失败: {e}")
            return False
    
    def request_translation(self, manga_path: str, page_index: int,
                           force_retranslate: bool = False, user_id: Optional[str] = None,
                           priority: Optional[int] = None) -> Optional[str]:
        """
        请求翻译指定页面 - 优化版本，增强缓存检查

        Args:
            manga_path: 漫画路径
            page_index: 页面索引
            force_retranslate: 强制重新翻译
            user_id: 用户ID
            priority: 优先级（可选，如果不提供则自动计算）

        Returns:
            任务ID，如果不需要翻译则返回None
        """
        if not self.is_running:
            log.warning("翻译服务未启动，无法请求翻译")
            return None

        # 优化的缓存检查机制
        cache_result = self._check_translation_cache_optimized(manga_path, page_index, force_retranslate)
        if cache_result['skip_translation']:
            log.debug(f"页面已翻译过，跳过: {manga_path}:{page_index} (原因: {cache_result['reason']})")
            return None

        # 计算或使用提供的优先级
        if priority is not None:
            # 使用提供的优先级，需要转换为TaskPriority枚举
            from core.translation_queue_models import TaskPriority
            if isinstance(priority, int):
                # 将整数优先级映射到TaskPriority枚举
                if priority == 0:
                    calculated_priority = TaskPriority.P0_CURRENT
                elif priority <= 2:
                    calculated_priority = TaskPriority.P1_ADJACENT
                elif priority <= 5:
                    calculated_priority = TaskPriority.P2_SAME_MANGA
                else:
                    calculated_priority = TaskPriority.P3_OTHER_MANGA
            else:
                calculated_priority = priority
        else:
            # 自动计算优先级
            calculated_priority = self.priority_calculator.calculate_priority(
                manga_path, page_index,
                self.current_manga_path or manga_path,
                self.current_page_index,
                self.reading_direction
            )

        # 添加到队列
        task_id = self.queue_manager.add_task(
            manga_path=manga_path,
            page_index=page_index,
            target_language="zh",
            priority=calculated_priority,
            user_id=user_id,
            force_retranslate=force_retranslate
        )

        if task_id:
            log.debug(f"添加翻译任务: {manga_path}:{page_index}, 优先级: {calculated_priority.name}")

        return task_id

    def _check_translation_cache_optimized(self, manga_path: str, page_index: int,
                                         force_retranslate: bool = False) -> Dict[str, Any]:
        """
        优化的翻译缓存检查机制

        Args:
            manga_path: 漫画路径
            page_index: 页面索引
            force_retranslate: 强制重新翻译

        Returns:
            包含检查结果的字典
        """
        result = {
            'skip_translation': False,
            'reason': '',
            'cache_hit': False,
            'memory_cache_hit': False,
            'disk_cache_hit': False
        }

        if force_retranslate:
            result['reason'] = '强制重新翻译'
            return result

        cache_key = f"{manga_path}:{page_index}"

        # 1. 检查后端内存缓存
        if cache_key in self.completed_translations:
            result['skip_translation'] = True
            result['reason'] = '后端内存缓存命中'
            result['cache_hit'] = True
            result['memory_cache_hit'] = True
            log.debug(f"后端内存缓存命中: {cache_key}")
            return result

        # 2. 检查持久化WebP缓存（优先级高于传统磁盘缓存）
        if self.persistent_cache.has_cached_translation(manga_path, page_index, "zh"):
            result['skip_translation'] = True
            result['reason'] = '持久化WebP缓存命中'
            result['cache_hit'] = True
            result['disk_cache_hit'] = True
            log.debug(f"持久化WebP缓存命中: {cache_key}")

            # 预加载到后端内存缓存以提升后续访问速度
            try:
                cached_image_data = self.persistent_cache.get_cached_translation(
                    manga_path, page_index, "zh"
                )
                if cached_image_data is not None:
                    # 将WebP数据转换为base64格式存储在内存中
                    import base64
                    base64_data = base64.b64encode(cached_image_data).decode('utf-8')
                    self.completed_translations[cache_key] = base64_data
                    log.debug(f"持久化WebP缓存预加载到后端内存: {cache_key}")
            except Exception as e:
                log.warning(f"持久化WebP缓存预加载失败: {e}")

            return result

        # 3. 检查传统磁盘缓存
        if not self.cache_checker.is_translation_needed(manga_path, page_index, "zh", force_retranslate):
            result['skip_translation'] = True
            result['reason'] = '传统磁盘缓存命中'
            result['cache_hit'] = True
            result['disk_cache_hit'] = True
            log.debug(f"传统磁盘缓存命中: {cache_key}")

            # 预加载到后端内存缓存以提升后续访问速度
            try:
                translated_image = self.cache_checker.get_cached_translation_result(
                    manga_path, page_index, "zh"
                )
                if translated_image is not None:
                    self.completed_translations[cache_key] = translated_image
                    log.debug(f"传统磁盘缓存预加载到后端内存: {cache_key}")
            except Exception as e:
                log.warning(f"传统磁盘缓存预加载失败: {e}")

            return result

        # 3. 检查是否已在队列中
        if self.queue_manager.is_task_in_queue(manga_path, page_index, "zh"):
            result['skip_translation'] = True
            result['reason'] = '任务已在队列中'
            log.debug(f"任务已在队列中: {cache_key}")
            return result

        return result

    def get_translated_page(self, manga_path: str, page_index: int) -> Optional[Any]:
        """获取翻译后的页面图像（优化版本，支持持久化缓存）"""
        cache_key = f"{manga_path}:{page_index}"

        # 1. 首先检查后端内存缓存
        if cache_key in self.completed_translations:
            log.debug(f"后端内存缓存命中: {cache_key}")
            return self.completed_translations[cache_key]

        # 2. 检查持久化WebP缓存
        try:
            cached_image_data = self.persistent_cache.get_cached_translation(
                manga_path, page_index, "zh"
            )
            if cached_image_data is not None:
                # 将WebP数据转换为base64格式
                import base64
                base64_data = base64.b64encode(cached_image_data).decode('utf-8')

                # 保存到后端内存缓存
                self.completed_translations[cache_key] = base64_data
                log.info(f"从持久化WebP缓存获取翻译页面: {cache_key}")
                return base64_data
        except Exception as e:
            log.warning(f"持久化WebP缓存获取失败: {e}")

        # 3. 使用传统磁盘缓存检查器获取翻译结果
        translated_image = self.cache_checker.get_cached_translation_result(
            manga_path, page_index, "zh"
        )

        if translated_image is not None:
            # 保存到后端内存缓存以便下次快速访问
            self.completed_translations[cache_key] = translated_image
            log.info(f"从传统磁盘缓存获取翻译页面: {cache_key}")
            return translated_image

        return None
    
    def is_page_translated(self, manga_path: str, page_index: int) -> bool:
        """检查页面是否已翻译"""
        cache_key = f"{manga_path}:{page_index}"

        # 检查内存缓存
        if cache_key in self.completed_translations:
            return True

        # 使用缓存检查器检查
        return not self.cache_checker.is_translation_needed(manga_path, page_index, "zh")

    def _preload_memory_cache(self, manga_path: str, page_range: Optional[tuple] = None) -> int:
        """预加载缓存到内存"""
        try:
            cache_info = self.cache_checker.preload_cache_info(manga_path, page_range)
            preloaded_count = 0

            for page_index, info in cache_info.items():
                cache_key = f"{manga_path}:{page_index}"

                # 如果内存中还没有，尝试加载
                if cache_key not in self.completed_translations and info.get('has_result_image'):
                    translated_image = self.cache_checker.get_cached_translation_result(
                        manga_path, page_index, info['target_language']
                    )

                    if translated_image is not None:
                        self.completed_translations[cache_key] = translated_image
                        preloaded_count += 1

            return preloaded_count

        except Exception as e:
            log.error(f"预加载内存缓存失败: {e}")
            return 0

    def _batch_preload_manga_cache(self, manga_path: str) -> int:
        """批量预加载漫画的所有翻译缓存到内存"""
        with self.cache_preload_lock:
            try:
                start_time = time.time()

                # 获取实时翻译缓存管理器
                cache_factory = get_cache_factory_instance()
                realtime_cache_manager = cache_factory.get_manager("realtime_translation")

                # 批量获取该漫画的所有缓存数据
                cached_pages = realtime_cache_manager.get_cache_by_manga(manga_path)

                if not cached_pages:
                    log.debug(f"漫画 {manga_path} 没有缓存数据")
                    return 0

                preloaded_count = 0

                # 批量处理缓存数据
                for cached_data in cached_pages:
                    page_index = cached_data.page_index
                    cache_key = f"{manga_path}:{page_index}"

                    # 检查是否已在内存缓存中
                    if cache_key in self.completed_translations:
                        continue

                    # 如果有翻译结果图像，直接加载到内存
                    if cached_data.result_image_data:
                        try:
                            translated_image = RealtimeTranslationCacheUtils.decode_result_image(
                                cached_data.result_image_data
                            )

                            if translated_image is not None:
                                self.completed_translations[cache_key] = translated_image
                                preloaded_count += 1
                                log.debug(f"批量预加载缓存页面: {cache_key}")
                        except Exception as e:
                            log.debug(f"解码缓存图像失败 {page_index}: {e}")
                            continue

                elapsed_time = time.time() - start_time

                if preloaded_count > 0:
                    log.info(f"批量预加载完成: {manga_path}, 加载 {preloaded_count} 个页面, 耗时 {elapsed_time:.2f}秒")

                return preloaded_count

            except Exception as e:
                log.error(f"批量预加载漫画缓存失败: {e}")
                return 0

    def _add_preload_tasks(self):
        """添加预加载任务"""
        if not self.current_manga_path:
            return

        try:
            # 获取需要预加载的页面
            manga = self.manga_loader.load_manga(self.current_manga_path)
            if not manga:
                return

            total_pages = len(manga.pages) if hasattr(manga, 'pages') else 100  # 默认值

            preload_pages = self.priority_calculator.get_preload_pages(
                self.current_manga_path,
                self.current_page_index,
                total_pages,
                self.reading_direction,
                preload_count=5
            )

            for page_index, priority in preload_pages:
                # 检查是否需要翻译
                if self.cache_checker.is_translation_needed(
                    self.current_manga_path, page_index, "zh"
                ):
                    self.queue_manager.add_task(
                        manga_path=self.current_manga_path,
                        page_index=page_index,
                        target_language="zh",
                        priority=priority
                    )

        except Exception as e:
            log.debug(f"添加预加载任务失败: {e}")

    def _on_queue_event(self, event):
        """队列事件回调"""
        try:
            if event.event_type == "task_completed" and event.task:
                # 任务完成，更新内存缓存
                cache_key = f"{event.task.manga_path}:{event.task.page_index}"

                # 从缓存获取翻译结果
                translated_image = self.cache_checker.get_cached_translation_result(
                    event.task.manga_path, event.task.page_index, event.task.target_language
                )

                if translated_image is not None:
                    self.completed_translations[cache_key] = translated_image
                    log.info(f"翻译完成并缓存: {cache_key}")

                    # 调用完成回调
                    if self.translation_completed_callback:
                        try:
                            self.translation_completed_callback(
                                event.task.manga_path,
                                event.task.page_index,
                                translated_image
                            )
                        except Exception as e:
                            log.error(f"翻译完成回调执行失败: {e}")

        except Exception as e:
            log.error(f"队列事件处理失败: {e}")

    def preload_cache_for_manga(self, manga_path: str, page_range: Optional[tuple] = None) -> int:
        """
        为指定漫画预加载缓存

        Args:
            manga_path: 漫画路径
            page_range: 页面范围 (start, end)，None表示所有页面

        Returns:
            预加载的页面数量
        """
        try:
            realtime_cache_manager = get_cache_factory_instance().get_manager("realtime_translation")

            # 获取漫画的所有缓存
            cached_pages = realtime_cache_manager.get_cache_by_manga(manga_path)

            if not cached_pages:
                log.debug(f"漫画 {manga_path} 没有缓存数据")
                return 0

            # 加载漫画
            manga = self.manga_loader.load_manga(manga_path)
            if not manga:
                log.warning(f"无法加载漫画: {manga_path}")
                return 0

            preloaded_count = 0

            for cached_data in cached_pages:
                page_index = cached_data.page_index

                # 检查页面范围
                if page_range:
                    start, end = page_range
                    if page_index < start or page_index > end:
                        continue

                # 检查是否已在内存缓存中
                cache_key = f"{manga_path}:{page_index}"
                if cache_key in self.completed_translations:
                    continue

                # 验证缓存数据
                try:
                    image = self.manga_loader.get_page_image(manga, page_index)
                    if image is not None and RealtimeTranslationCacheUtils.validate_cache_data(cached_data, image):
                        # 恢复翻译结果到内存缓存
                        if cached_data.result_image_data:
                            translated_image = RealtimeTranslationCacheUtils.decode_result_image(
                                cached_data.result_image_data
                            )

                            if translated_image is not None:
                                self.completed_translations[cache_key] = translated_image
                                preloaded_count += 1
                                log.debug(f"预加载缓存页面: {cache_key}")
                except Exception as e:
                    log.debug(f"预加载页面 {page_index} 失败: {e}")
                    continue

            if preloaded_count > 0:
                log.info(f"为漫画 {manga_path} 预加载了 {preloaded_count} 个缓存页面")

            return preloaded_count

        except Exception as e:
            log.error(f"预加载缓存失败: {e}")
            return 0
    
    def get_translation_status(self) -> Dict[str, Any]:
        """获取翻译状态"""
        with self.lock:
            queue_status = self.queue_manager.get_queue_status()

            return {
                "is_running": self.is_running,
                "current_manga": self.current_manga_path,
                "current_page": self.current_page_index,
                "reading_direction": self.reading_direction,
                "queue_size": queue_status['queue_length'],
                "processing_count": queue_status['processing_count'],
                "completed_count": len(self.completed_translations),
                "memory_cache_count": len(self.completed_translations),
                "queue_statistics": queue_status['statistics'],
                "worker_threads": len(self.worker_threads)
            }
    
    # 移除旧的队列重排序方法，现在由队列管理器处理
    
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
        """翻译工作线程 - 重构版本"""
        thread_name = threading.current_thread().name
        log.info(f"翻译工作线程启动: {thread_name}")

        while self.is_running and not self.stop_event.is_set():
            try:
                # 从队列管理器获取下一个任务
                task = self.queue_manager.get_next_task()

                if task is None:
                    # 没有任务，等待一下
                    time.sleep(1.0)
                    continue

                # 执行翻译
                self._execute_translation_new(task)

            except Exception as e:
                log.error(f"翻译工作线程异常 ({thread_name}): {e}")
                import traceback
                log.error(traceback.format_exc())

                # 等待一下再继续
                time.sleep(1.0)

        log.info(f"翻译工作线程结束: {thread_name}")

    def _execute_translation_new(self, task):
        """执行翻译任务 - 异步流水线版本"""
        cache_key = f"{task.manga_path}:{task.page_index}"
        start_time = time.time()

        try:
            log.info(f"开始处理翻译任务: {task.task_id}")
            log.info(f"开始翻译: {cache_key} (任务ID: {task.task_id})")

            # 再次检查缓存（可能在等待期间已被其他线程翻译）
            if not task.force_retranslate:
                cache_info = self.cache_checker.check_cache_exists(
                    task.manga_path, task.page_index, task.target_language
                )

                if cache_info:
                    log.info(f"发现缓存，跳过翻译: {cache_key}")

                    # 从缓存获取结果
                    translated_image = self.cache_checker.get_cached_translation_result(
                        task.manga_path, task.page_index, task.target_language
                    )

                    if translated_image is not None:
                        # 保存到内存缓存
                        self.completed_translations[cache_key] = translated_image

                        # 记录详细日志
                        elapsed_time = time.time() - start_time
                        log.info(f"翻译任务完成: {task.task_id} (耗时: {elapsed_time:.2f}秒)")
                        log.info(f"页面 {task.page_index}: 处理耗时={elapsed_time:.2f}秒, OCR文本=0, 翻译文本=0, 使用缓存=是, 状态=成功")

                        # 标记任务完成
                        self.queue_manager.complete_task(task.task_id, success=True, result_data={
                            'cache_hit': True,
                            'image_shape': translated_image.shape,
                            'processing_time': elapsed_time,
                            'ocr_text_count': 0,
                            'translated_text_count': 0,
                            'used_cache': True
                        })

                        return

            # 检查翻译器是否准备就绪
            if not self.image_translator or not self.image_translator.is_ready():
                self._initialize_translator()

            # 加载漫画和图像
            manga = self.manga_loader.load_manga(task.manga_path)
            if not manga:
                raise Exception(f"无法加载漫画: {task.manga_path}")

            image = self.manga_loader.get_page_image(manga, task.page_index)
            if image is None:
                raise Exception(f"无法获取页面图像: {task.page_index}")

            # 执行异步流水线翻译
            log.debug(f"开始翻译图像: {cache_key}")
            # 检查翻译器准备状态
            if hasattr(self.image_translator, 'get_readiness_status'):
                log.debug(f"翻译器准备状态检查通过: {self.image_translator.get_readiness_status()}")
            else:
                log.debug("翻译器准备状态检查: 使用简化检查")

            # 使用增强的翻译方法，收集翻译过程中的所有数据
            translation_result = self.image_translator.translate_image_with_cache_data(
                image_input=image,
                target_language=task.target_language,
                file_path_for_cache=task.manga_path,
                page_num_for_cache=task.page_index
            )

            if translation_result and translation_result.get("translated_image") is not None:
                translated_image = translation_result["translated_image"]

                # 保存翻译结果到内存缓存
                self.completed_translations[cache_key] = translated_image

                # 保存到持久化缓存（WebP格式）- 修复版本
                try:
                    # translation_result是字典，检查是否有translated_image键
                    if "translated_image" in translation_result and translation_result["translated_image"] is not None:
                        translated_image_array = translation_result["translated_image"]

                        # 验证图像数组格式
                        if isinstance(translated_image_array, np.ndarray) and translated_image_array.size > 0:
                            log.debug(f"准备保存翻译图像到持久化缓存: {cache_key}")
                            log.debug(f"图像形状: {translated_image_array.shape}")

                            success = self.persistent_cache.save_translated_image(
                                task.manga_path,
                                task.page_index,
                                translated_image_array,
                                task.target_language
                            )

                            if success:
                                log.info(f"翻译结果已保存到持久化WebP缓存: {cache_key}")
                            else:
                                log.warning(f"持久化WebP缓存保存失败: {cache_key}")
                        else:
                            log.warning(f"翻译图像数组格式无效，跳过持久化缓存保存: {cache_key}, 类型: {type(translated_image_array)}")
                    else:
                        log.warning(f"翻译结果中无translated_image键，跳过持久化缓存保存: {cache_key}")
                        log.debug(f"翻译结果键值: {list(translation_result.keys()) if isinstance(translation_result, dict) else 'Not a dict'}")
                except Exception as e:
                    log.error(f"持久化WebP缓存保存异常: {cache_key}, 错误: {e}")
                    import traceback
                    log.error(f"详细错误信息: {traceback.format_exc()}")

                # 计算处理时间和统计信息
                elapsed_time = time.time() - start_time
                ocr_text_count = len(translation_result.get("original_texts", []))
                translated_text_count = len(translation_result.get("translated_texts", []))
                used_cache = translation_result.get("used_cache", False)

                log.info(f"翻译完成: {cache_key}")
                log.info(f"页面 {task.page_index}: 处理耗时={elapsed_time:.2f}秒, OCR文本={ocr_text_count}, 翻译文本={translated_text_count}, 使用缓存={'是' if used_cache else '否'}, 状态=成功")

                # 标记任务完成
                self.queue_manager.complete_task(task.task_id, success=True, result_data={
                    'cache_hit': False,
                    'image_shape': translated_image.shape,
                    'processing_time': elapsed_time,
                    'ocr_text_count': ocr_text_count,
                    'translated_text_count': translated_text_count,
                    'used_cache': used_cache
                })

            else:
                raise Exception("翻译返回空结果")

        except Exception as e:
            error_message = str(e)
            elapsed_time = time.time() - start_time

            log.error(f"翻译任务失败: {cache_key} - {error_message}")
            log.info(f"页面 {task.page_index}: 处理耗时={elapsed_time:.2f}秒, OCR文本=0, 翻译文本=0, 使用缓存=否, 状态=失败")

            # 标记任务失败
            self.queue_manager.complete_task(task.task_id, success=False, error_message=error_message, result_data={
                'processing_time': elapsed_time,
                'error_message': error_message
            })

    def _initialize_translator(self):
        """初始化翻译器"""
        try:
            from core.config import config
            translator_type = config.translator_type.value

            # 根据翻译器类型设置参数
            if translator_type == "智谱":
                self.image_translator = ImageTranslator(
                    translator_type=translator_type,
                    api_key=config.zhipu_api_key.value,
                    model=config.zhipu_model.value
                )
            elif translator_type == "Google":
                self.image_translator = ImageTranslator(
                    translator_type=translator_type,
                    api_key=config.google_api_key.value
                )
            else:
                # 默认使用Google翻译器
                self.image_translator = ImageTranslator(
                    translator_type="Google"
                )

            if not self.image_translator.is_ready():
                raise Exception("翻译器初始化后仍未准备就绪")

            log.info("图片翻译器初始化成功")

        except Exception as e:
            raise Exception(f"图片翻译器初始化失败: {e}")


# 全局实例
_realtime_translator_instance: Optional[RealtimeTranslator] = None


# 移除旧的翻译执行方法，使用新的队列驱动版本


# 全局实例
_realtime_translator_instance: Optional[RealtimeTranslator] = None


def get_realtime_translator() -> RealtimeTranslator:
    """获取实时翻译器全局实例"""
    global _realtime_translator_instance
    if _realtime_translator_instance is None:
        _realtime_translator_instance = RealtimeTranslator()
    return _realtime_translator_instance
