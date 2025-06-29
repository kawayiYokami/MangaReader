#!/usr/bin/env python3
"""
批量压缩管理器模块 (管理层)
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from core.image.image_compressor import ImageCompressor, get_image_compressor
from core.utils.file_system import safe_replace_file
from utils import manga_logger as log

class BatchCompressionManager:
    """
    角色：压缩工厂/项目经理
    职责：管理整个批量压缩任务的生命周期。
    """

    def __init__(self, image_compressor: ImageCompressor):
        self.image_compressor = image_compressor
        self.is_running = False
        self._stop_event = threading.Event()

    def run_batch_compression(
        self,
        manga_files: List[str],
        webp_quality: int,
        min_compression_ratio: float,
        preserve_original_names: bool
    ):
        """
        该类的主要入口点，由 CoreInterface 调用。
        """
        if self.is_running:
            log.warning("一个批量压缩任务已经在运行中，请等待其完成。")
            return

        self.is_running = True
        self._stop_event.clear()
        # 重置 compressor 的取消标志，以防上次任务异常中断
        self.image_compressor.reset_cancel_flag()
        
        try:
            files_to_compress = self._parallel_analysis_phase(manga_files, webp_quality, min_compression_ratio)

            if self._stop_event.is_set():
                log.info("操作在分析阶段后被取消。")
                return
            
            if not files_to_compress:
                log.info("分析完成，没有文件需要压缩。")
                return

            self._parallel_compression_phase(files_to_compress, webp_quality, preserve_original_names)

        finally:
            self.is_running = False
            log.info("✅ 批量压缩任务已结束。")

    def _parallel_analysis_phase(self, all_files: List[str], webp_quality: int, min_compression_ratio: float) -> List[str]:
        """并行分析所有文件，决定哪些文件值得压缩。"""
        log.info("--- 阶段1: 并行分析 ---")
        eligible_files = []
        total_count = len(all_files)
        
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            future_to_file = {
                executor.submit(self.image_compressor.pre_test_compression, file_path, webp_quality, min_compression_ratio): file_path
                for file_path in all_files
            }

            for i, future in enumerate(as_completed(future_to_file)):
                if self._stop_event.is_set():
                    for f in future_to_file: f.cancel()
                    break

                file_path = future_to_file[future]
                try:
                    pre_test_result = future.result()
                    log.info(f"🔎 分析完成 ({i+1}/{total_count}): {os.path.basename(file_path)}")
                    if pre_test_result.get("should_compress"):
                        log.info(f"  👍 加入队列 (原因: {pre_test_result.get('reason', '未知')})")
                        eligible_files.append(file_path)
                    else:
                        log.info(f"  ⏭️ 跳过 (原因: {pre_test_result.get('reason', '压缩效果不佳')})")
                except Exception as e:
                    log.error(f"  ❌ 分析时发生错误 {os.path.basename(file_path)}: {e}")

        log.info(f"--- 分析阶段结束 ---, {len(eligible_files)} / {total_count} 个文件将被压缩。")
        return eligible_files

    def _parallel_compression_phase(self, files_to_compress: List[str], webp_quality: int, preserve_original_names: bool):
        """使用线程池并行压缩文件。"""
        log.info("--- 阶段2: 并行压缩 ---")
        total_count = len(files_to_compress)
        completed_count = 0
        
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            future_to_file = {
                executor.submit(self._compression_worker, file_path, webp_quality, preserve_original_names): file_path
                for file_path in files_to_compress
            }

            for future in as_completed(future_to_file):
                if self._stop_event.is_set():
                    # 尝试取消所有还未开始的future
                    for f in future_to_file: f.cancel()
                    # 通知正在运行的compressor也停止
                    self.image_compressor.cancel_compression()
                
                file_path = future_to_file[future]
                try:
                    success = future.result()
                    completed_count += 1
                    if success:
                        log.info(f"✅ ({completed_count}/{total_count}) 压缩成功: {os.path.basename(file_path)}")
                    else:
                        # 失败原因已在worker内部记录，这里只记录结果
                        log.error(f"❌ ({completed_count}/{total_count}) 压缩失败: {os.path.basename(file_path)}")
                except Exception as e:
                    completed_count += 1
                    log.error(f"❌ ({completed_count}/{total_count}) 处理文件时发生严重错误 {os.path.basename(file_path)}: {e}")

        log.info("--- 并行压缩阶段结束 ---")

    def _compression_worker(self, file_path: str, webp_quality: int, preserve_original_names: bool) -> bool:
        """每个工作线程执行的具体任务。"""
        if self._stop_event.is_set(): return False
        
        # 1. 调用“工人”进行重量级压缩，获取临时文件路径
        temp_file_path = self.image_compressor.compress_manga_file(file_path, webp_quality, preserve_original_names)
        if not temp_file_path:
            # 失败原因已在compressor内部记录
            return False

        # 2. 调用“文件替换工”完成替换
        success = safe_replace_file(temp_file_path, file_path)
        return success

    def cancel(self):
        """外部调用的取消方法。"""
        if not self.is_running:
            log.info("没有正在运行的压缩任务。")
            return
            
        log.info("收到取消批量压缩的请求，将会在当前任务完成后安全停止...")
        self._stop_event.set()
        # 同时通知ImageCompressor内部的循环也尽快停止
        self.image_compressor.cancel_compression()


# --- 单例模式 ---
_manager_instance = None
def get_batch_compression_manager() -> "BatchCompressionManager":
    """获取批量压缩管理器实例"""
    global _manager_instance
    if _manager_instance is None:
        image_compressor = get_image_compressor()
        _manager_instance = BatchCompressionManager(image_compressor)
    return _manager_instance