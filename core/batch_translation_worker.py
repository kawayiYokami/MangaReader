# coding:utf-8
import os
import cv2
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Union # 导入 Union
import numpy as np # 导入 numpy
from PySide6.QtCore import QObject, Signal, QThread

from .image_translator import create_image_translator
from core.config import config # Import config
from utils import manga_logger as log

class TranslationTaskItem:
    """
    表示一个独立的翻译任务项（通常对应一张图片）
    """
    def __init__(self, task_id: Any, input_path: Optional[str] = None, output_path: Optional[str] = None, # input_path 和 output_path 改为可选
                 source_lang: str = "auto", target_lang: str = "zh-CN", # 添加默认语言
                 is_archive: bool = False,
                 original_archive_path: Optional[str] = None, page_index: Optional[int] = None, # 添加 page_index
                 image_data: Optional[np.ndarray] = None): # 添加 image_data 参数
        """
        Args:
            task_id: 任务的唯一标识符 (例如 "row0_img1")
            input_path: 待翻译图片的原始路径 (可选，如果提供了 image_data 则忽略)
            output_path: 翻译后图片（PNG格式）的临时保存路径 (在 batch_png_output_temp_dir 内, 如果 save_to_disk 为 True)
            source_lang: 源语言代码
            target_lang: 目标语言代码
            is_archive: 是否来自压缩包
            original_archive_path: 如果来自压缩包，记录原始压缩包路径
            page_index: 对应的页码 (用于缓存)
            image_data: 待翻译图片的原始数据 (numpy数组, 可选，如果提供了则优先使用)
        """
        self.task_id = task_id
        self.input_path = input_path
        self.output_path = output_path
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.status = "待处理" # 任务状态 (UI显示用)
        self.error_message = None # 任务失败时的错误信息
        self.is_archive_member = is_archive
        self.original_archive_path = original_archive_path
        self.page_index = page_index # 保存页码
        self.image_data = image_data # 保存图片数据

class BatchTranslationWorker(QObject):
    """
    批量翻译工作线程，负责执行图片翻译和最终打包任务
    """
    task_started = Signal(object) # 发送单个任务开始信号 (task_id)
    task_progress = Signal(object, int, str) # 发送单个任务进度信号 (task_id, percent, message) - 暂未使用
    task_finished = Signal(object, bool, str) # 发送单个任务完成信号 (task_id, success, result_message)

    overall_progress = Signal(int, str) # 发送整体进度信号 (percent, message)
    all_tasks_finished = Signal(str) # 发送所有任务完成信号 (final_result_message: zip path or error)
    log_message = Signal(str) # 发送日志信息到UI
    single_page_translated = Signal(int, object) # 发送单页翻译完成信号 (page_index, translated_image_data)
    error_occurred = Signal(str) # 添加错误信号

    def __init__(self, tasks: List[TranslationTaskItem],
                 final_zip_output_dir: Optional[str] = None, # 允许为 None
                 base_zip_name: Optional[str] = None, # 允许为 None
                 default_source_lang: str = "auto", # 添加默认值
                 default_target_lang: str = "zh-CN", # 添加默认值
                 translator_engine: str = "智谱",
                 save_to_disk: bool = True): # 添加 save_to_disk 参数
        """
        初始化批量翻译工作线程

        Args:
            tasks: 待处理的 TranslationTaskItem 列表
            final_zip_output_dir: 最终ZIP文件的保存目录 (如果 save_to_disk 为 True)
            base_zip_name: 最终ZIP文件的基础名称 (不含扩展名, 如果 save_to_disk 为 True)
            default_source_lang: 默认源语言
            default_target_lang: 默认目标语言
            translator_engine: 使用的翻译引擎名称
            save_to_disk: 是否将翻译结果保存到磁盘并打包成ZIP
        """
        super().__init__()
        self.tasks = tasks
        self.final_zip_output_dir = final_zip_output_dir
        self.base_zip_name = base_zip_name
        self.default_source_lang = default_source_lang
        self.default_target_lang = default_target_lang
        self.translator_engine_name = translator_engine
        self.save_to_disk = save_to_disk # 保存 save_to_disk 状态
        # self.png_compression_level = config.png_compression_level.value #不再需要PNG压缩级别

        self.translator = None
        self._is_cancelled = False

        # 如果需要保存到磁盘，创建缓存目录结构
        if self.save_to_disk:
            if not self.final_zip_output_dir:
                 raise ValueError("final_zip_output_dir 必须在 save_to_disk 为 True 时提供")
            self.translation_cache_dir = os.path.join(final_zip_output_dir, 'cache')
            self.translated_cache_dir = os.path.join(self.translation_cache_dir, 'translated')
            os.makedirs(self.translated_cache_dir, exist_ok=True) # 创建翻译后的图片存储目录
        else:
            self.translation_cache_dir = None
            self.translated_cache_dir = None


    def run(self):
        """
        执行批量翻译任务
        """
        final_result_message = "任务因未知错误结束。"

        try:
            self.log_message.emit(f"开始批量翻译任务，共 {len(self.tasks)} 张图片。")
            self.overall_progress.emit(0, "初始化翻译器...")

            # 初始化翻译器
            self.translator = create_image_translator(self.translator_engine_name)
            if not self.translator:
                error_msg = f"错误：无法初始化翻译引擎 '{self.translator_engine_name}'。"
                self.log_message.emit(error_msg)
                self.overall_progress.emit(100, error_msg)
                final_result_message = error_msg
                self.error_occurred.emit(error_msg) # 发射错误信号
                return

            self.overall_progress.emit(5, "翻译器已初始化。")

            # 清空翻译后的图片存储目录 (如果需要保存到磁盘)
            if self.save_to_disk and self.translated_cache_dir: # 确保 translated_cache_dir 已定义
                if os.path.exists(self.translated_cache_dir):
                    self.log_message.emit(f"正在清空翻译输出缓存目录: {self.translated_cache_dir}")
                    try:
                        shutil.rmtree(self.translated_cache_dir)
                        self.log_message.emit("翻译输出缓存目录清空完成。")
                    except Exception as e:
                        error_msg = f"清空翻译输出缓存目录失败: {self.translated_cache_dir} - {e}"
                        self.log_message.emit(error_msg)
                        self.error_occurred.emit(error_msg)
                        # 即使清空失败，也尝试继续，但记录错误
                
                # 重新创建翻译后的图片存储目录
                try:
                    os.makedirs(self.translated_cache_dir, exist_ok=True) # 确保目录存在
                    self.log_message.emit(f"翻译输出缓存目录已创建/确保存在: {self.translated_cache_dir}")
                except Exception as e:
                    error_msg = f"创建翻译输出缓存目录失败: {self.translated_cache_dir} - {e}"
                    self.log_message.emit(error_msg)
                    self.error_occurred.emit(error_msg)
                    # 如果创建失败，后续保存可能会出问题，但还是尝试继续

            # 开始处理每个任务
            processed_count = 0
            successful_tasks = 0

            for task in self.tasks:
                if self._is_cancelled:
                    self.log_message.emit("翻译任务已取消。")
                    final_result_message = "任务已取消。"
                    break

                try:
                    self.task_started.emit(task.task_id)
                    # 使用 task_id 作为日志信息中的图片标识符
                    input_identifier = task.task_id
                    self.log_message.emit(f"开始处理图片: {input_identifier}")

                    # 调用翻译器处理图片，优先使用 image_data
                    image_input_data = task.image_data if task.image_data is not None else task.input_path

                    if image_input_data is None:
                         error_msg = f"任务 {task.task_id} 没有提供图片数据或路径。"
                         self.task_finished.emit(task.task_id, False, error_msg)
                         self.log_message.emit(error_msg)
                         self.error_occurred.emit(error_msg) # 发射错误信号
                         processed_count += 1
                         continue # 跳过当前任务

                    self.log_message.emit(f"执行翻译: {input_identifier}")
                    # 调用翻译器处理图片，传入缓存相关参数
                    translated_image_data = self.translator.translate_image(
                        image_input=image_input_data, # 使用 image_input_data
                        target_language=task.target_lang,
                        output_path=None,  # 不让translate_image负责保存
                        file_path_for_cache=task.input_path, # Pass for caching
                        page_num_for_cache=task.page_index, # Pass for caching
                        original_archive_path_for_cache=task.original_archive_path # Pass original archive path
                    )

                    # 验证翻译结果
                    if translated_image_data is not None:
                        # 始终发射 single_page_translated 信号
                        if task.page_index is not None:
                             self.single_page_translated.emit(task.page_index, translated_image_data)
                             self.log_message.emit(f"已发射 single_page_translated 信号，页码: {task.page_index}")

                        if self.save_to_disk:
                            # 如果需要保存到磁盘
                            # 更新输出路径到翻译缓存目录
                            # 修改：使用 task_id 作为输出文件名
                            output_filename = f"{task.task_id}.webp" # 固定使用 .webp 作为文件名
                            task.output_path = os.path.join(self.translated_cache_dir, output_filename)

                            # 保存翻译后的图片为 WebP
                            params = [cv2.IMWRITE_WEBP_QUALITY, config.webp_quality.value]
                            self.log_message.emit(f"使用WebP质量 {config.webp_quality.value} 保存图片: {Path(task.output_path).name}")
                            
                            success = cv2.imwrite(task.output_path, translated_image_data, params)

                            # 验证保存的文件
                            if success and self._check_image_file(task.output_path):
                                self.task_finished.emit(task.task_id, True, task.output_path)
                                self.log_message.emit(f"图片翻译完成并已保存: {Path(task.output_path).name}")
                                successful_tasks += 1
                            else:
                                error_msg = f"图片保存失败: {input_identifier}"
                                self.task_finished.emit(task.task_id, False, error_msg)
                                self.log_message.emit(error_msg)
                                self.error_occurred.emit(error_msg) # 发射错误信号

                                # 删除保存失败的文件
                                if os.path.exists(task.output_path):
                                    try:
                                        os.remove(task.output_path)
                                        self.log_message.emit(f"已删除无效的输出文件: {task.output_path}")
                                    except Exception as del_e:
                                        self.log_message.emit(f"警告：无法删除无效的输出文件: {task.output_path} - {del_e}")
                        else:
                            # 如果不需要保存到磁盘，任务视为成功
                            self.task_finished.emit(task.task_id, True, "翻译完成 (未保存到磁盘)")
                            self.log_message.emit(f"图片翻译完成 (未保存到磁盘): {input_identifier}")
                            successful_tasks += 1 # 即使不保存，也算成功处理

                    else:
                        error_msg = f"图片翻译失败: {input_identifier}"
                        self.task_finished.emit(task.task_id, False, error_msg)
                        self.log_message.emit(error_msg)
                        self.error_occurred.emit(error_msg) # 发射错误信号


                except Exception as e:
                    error_msg = f"处理图片时出错: {input_identifier} - {e}"
                    self.task_finished.emit(task.task_id, False, error_msg)
                    self.log_message.emit(error_msg)
                    self.error_occurred.emit(error_msg) # 发射错误信号
                    log.MangaLogger.get_instance().logger.exception(error_msg)

                processed_count += 1
                progress = int((processed_count / len(self.tasks)) * 100)
                self.overall_progress.emit(progress, f"已处理 {processed_count}/{len(self.tasks)} 张图片")

            # 处理完所有任务后的操作
            if self.save_to_disk:
                # 如果需要保存到磁盘，则创建ZIP文件
                if not self._is_cancelled and successful_tasks > 0:
                    self.log_message.emit(f"图片处理完成，成功 {successful_tasks}/{len(self.tasks)} 张。创建ZIP文件...")
                    self.overall_progress.emit(95, "正在打包ZIP文件...")

                    zip_result_path = self._create_output_zip()
                    if zip_result_path:
                        final_result_message = zip_result_path
                        self.log_message.emit(f"ZIP打包完成: {zip_result_path}")
                        self.overall_progress.emit(100, "ZIP打包完成")
                    else:
                        final_result_message = "ZIP打包失败。"
                        self.log_message.emit(final_result_message)
                        self.overall_progress.emit(100, final_result_message)
                elif not self._is_cancelled and successful_tasks == 0:
                    final_result_message = "没有图片成功翻译，未生成ZIP包。"
                    self.log_message.emit(final_result_message)
                    self.overall_progress.emit(100, final_result_message)
                elif self._is_cancelled:
                     final_result_message = "任务已取消。"
                     self.log_message.emit(final_result_message)
                     self.overall_progress.emit(100, final_result_message)
            else:
                # 如果不需要保存到磁盘，任务完成
                if not self._is_cancelled:
                    final_result_message = "批量翻译任务完成 (未保存到磁盘)。"
                    self.log_message.emit(final_result_message)
                    self.overall_progress.emit(100, final_result_message)
                else:
                    final_result_message = "任务已取消。"
                    self.log_message.emit(final_result_message)
                    self.overall_progress.emit(100, final_result_message)


        except Exception as e:
            err_msg_critical = f"批量翻译任务发生严重错误: {e}"
            log.MangaLogger.get_instance().logger.exception(err_msg_critical)
            self.log_message.emit(err_msg_critical)
            final_result_message = err_msg_critical
            self.error_occurred.emit(err_msg_critical) # 发射错误信号
        finally:
            self.all_tasks_finished.emit(final_result_message)


    def _create_output_zip(self) -> Optional[str]:
        """
        将翻译后的图片打包成ZIP文件
        """
        if not self.save_to_disk:
             self.log_message.emit("警告：save_to_disk 为 False，跳过ZIP打包。")
             return None

        if not os.path.isdir(self.translated_cache_dir):
            self.log_message.emit(f"错误：翻译缓存目录不存在或不是目录: {self.translated_cache_dir}")
            return None

        # 确保输出目录存在
        try:
            os.makedirs(self.final_zip_output_dir, exist_ok=True)
        except Exception as e:
            self.log_message.emit(f"错误：创建最终输出目录失败: {self.final_zip_output_dir} - {e}")
            return None

        # 收集并验证所有翻译后的图片文件
        translated_files = []
        total_size = 0
        # 修改：按文件名排序，确保ZIP内的图片顺序正确
        for file in sorted(os.listdir(self.translated_cache_dir)):
            file_path = os.path.join(self.translated_cache_dir, file)
            if os.path.isfile(file_path):
                # 验证每个图片文件
                if self._check_image_file(file_path):
                    file_size = os.path.getsize(file_path)
                    total_size += file_size
                    self.log_message.emit(f"已验证翻译文件: {file}, 大小: {file_size} 字节")
                    translated_files.append((file_path, file_size))
                else:
                    self.log_message.emit(f"警告：跳过无效的图片文件: {file}")

        if not translated_files:
            self.log_message.emit("错误：没有找到有效的已翻译图片文件")
            return None

        self.log_message.emit(f"准备打包 {len(translated_files)} 个文件，总大小: {total_size} 字节")

        # 处理ZIP文件重名
        zip_filename = f"{self.base_zip_name}.zip"
        final_zip_path = os.path.join(self.final_zip_output_dir, zip_filename)
        counter = 1
        while os.path.exists(final_zip_path):
            zip_filename = f"{self.base_zip_name}_{counter}.zip"
            final_zip_path = os.path.join(self.final_zip_output_dir, zip_filename)
            counter += 1

        self.log_message.emit(f"最终ZIP文件路径: {final_zip_path}")

        try:
            with zipfile.ZipFile(final_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path, file_size in translated_files:
                    # 计算文件在ZIP中的相对路径，保持原始文件名
                    arcname = os.path.basename(file_path)
                    self.log_message.emit(f"正在添加到ZIP: {arcname} (大小: {file_size} 字节)")
                    zipf.write(file_path, arcname)

            # 验证ZIP文件
            if os.path.exists(final_zip_path):
                zip_size = os.path.getsize(final_zip_path)
                if zip_size > 0:
                    # 验证ZIP文件完整性
                    try:
                        with zipfile.ZipFile(final_zip_path, 'r') as zipf:
                            # 检查文件列表
                            zip_files = zipf.namelist()
                            if len(zip_files) == len(translated_files):
                                self.log_message.emit(f"ZIP文件创建成功: {final_zip_path}, 大小: {zip_size} 字节, 包含 {len(zip_files)} 个文件")
                                return final_zip_path
                            else:
                                self.log_message.emit(f"错误：ZIP文件文件数量不匹配，期望 {len(translated_files)} 个，实际 {len(zip_files)} 个")
                    except zipfile.BadZipFile:
                        self.log_message.emit(f"错误：创建的ZIP文件无效: {final_zip_path}")
                else:
                    self.log_message.emit(f"错误：创建的ZIP文件大小为0: {final_zip_path}")
            else:
                self.log_message.emit("错误：ZIP文件创建失败，文件不存在")

            # 如果执行到这里，说明验证失败，删除无效的ZIP文件
            if os.path.exists(final_zip_path):
                try:
                    os.remove(final_zip_path)
                except Exception as e:
                    self.log_message.emit(f"警告：无法删除无效的ZIP文件: {e}")
            return None

        except Exception as e:
            self.log_message.emit(f"错误：创建ZIP文件时发生异常: {e}")
            # 清理可能不完整的ZIP文件
            if os.path.exists(final_zip_path):
                try:
                    os.remove(final_zip_path)
                except Exception as del_e:
                    self.log_message.emit(f"警告：无法删除不完整的ZIP文件: {del_e}")
            return None

    def _check_image_file(self, file_path: str) -> bool:
        """检查图片文件是否有效

        Args:
            file_path (str): 图片文件路径

        Returns:
            bool: 是否是有效的图片文件
        """
        if not os.path.exists(file_path):
            self.log_message.emit(f"文件不存在: {file_path}")
            return False

        try:
            # 尝试读取图片
            img = cv2.imread(file_path)
            if img is None:
                self.log_message.emit(f"无法读取图片文件: {file_path}")
                return False

            # 检查图片尺寸
            height, width = img.shape[:2]
            file_size = os.path.getsize(file_path)
            self.log_message.emit(f"图片信息 - 路径: {file_path}, 尺寸: {width}x{height}, 大小: {file_size} 字节")
            return True

        except Exception as e:
            self.log_message.emit(f"检查图片文件时出错: {file_path} - {e}")
            return False

    def cancel(self):
        """
        请求取消当前正在进行的翻译任务
        """
        self._is_cancelled = True
        self.log_message.emit("收到取消请求...")
        # TODO: Add mechanism to signal cancellation to the translator if it supports it

    def set_task_list(self, tasks: List[TranslationTaskItem]):
        """
        设置任务列表
        """
        self.tasks = tasks

if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication
    import time

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    def on_task_started(task_id): print(f"Test: Task started: {task_id}")
    def on_task_progress(task_id, p, msg): print(f"Test: Task progress: {task_id} - {p}% - {msg}")
    def on_task_finished(task_id, success, res): print(f"Test: Task finished: {task_id} - Success: {success} - Result: {res}")
    def on_overall_progress(p, msg): print(f"Test: Overall progress: {p}% - {msg}")
    def on_all_finished(result_msg): print(f"Test: All tasks finished. Result: {result_msg}"); app.quit()
    def on_log(msg): print(f"Test Log: {msg}")
    def on_single_page_translated(page_index, image_data): print(f"Test: Single page translated: {page_index}")

    print("BatchTranslationWorker模块定义完成。请在主应用中集成并进行实际测试。")
