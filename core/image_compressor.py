#!/usr/bin/env python3
"""
图片压缩模块 - 负责将漫画文件中的图片转换为WebP格式
"""

import os
import tempfile
import zipfile
import cv2
import shutil
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime
import threading
import time

from utils import manga_logger as log


class ImageCompressor:
    """图片压缩器"""
    
    def __init__(self):
        self.is_compressing = False
        self.current_task = None
        self.progress_callback = None
        self.cancel_flag = threading.Event()
        
    def compress_manga_file(
        self,
        file_path: str,
        webp_quality: int = 100,
        preserve_original_names: bool = False,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        压缩漫画文件（Web版本仅支持下载模式）

        Args:
            file_path: 漫画文件路径
            webp_quality: WebP质量 (0-100)
            progress_callback: 进度回调函数

        Returns:
            压缩结果字典
        """
        try:
            log.info(f"🔧 [压缩器调试] 开始压缩任务:")
            log.info(f"  - 文件路径: {file_path}")
            log.info(f"  - WebP质量: {webp_quality}")
            log.info(f"  - 压缩模式: download (Web版本固定)")
            log.info(f"  - 进度回调: {'有' if progress_callback else '无'}")

            self.is_compressing = True
            self.progress_callback = progress_callback
            self.cancel_flag.clear()

            # 验证参数
            log.info(f"🔧 [压缩器调试] 验证参数...")
            if not file_path:
                log.error(f"🔧 [压缩器调试] 文件路径为空")
                raise ValueError("文件路径不能为空")

            if not os.path.exists(file_path):
                log.error(f"🔧 [压缩器调试] 文件不存在: {file_path}")
                raise FileNotFoundError(f"文件不存在: {file_path}")

            file_size = os.path.getsize(file_path)
            log.info(f"🔧 [压缩器调试] 文件大小: {file_size:,} bytes")

            if not file_path.lower().endswith(('.zip', '.cbz', '.cbr')):
                log.error(f"🔧 [压缩器调试] 不支持的文件格式: {file_path}")
                raise ValueError("只支持ZIP、CBZ、CBR格式的压缩文件")

            webp_quality = max(0, min(100, webp_quality))
            log.info(f"🔧 [压缩器调试] 调整后的WebP质量: {webp_quality}")

            log.info(f"开始压缩漫画文件: {file_path}")
            log.info(f"WebP质量: {webp_quality}, 模式: download (Web版本固定)")
            
            # 报告开始状态
            self._report_progress({
                "status": "starting",
                "message": "开始解压文件...",
                "progress": 0,
                "total_steps": 4,
                "current_step": 1
            })
            
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                extract_dir = os.path.join(temp_dir, "extracted")
                output_dir = os.path.join(temp_dir, "compressed")
                os.makedirs(extract_dir, exist_ok=True)
                os.makedirs(output_dir, exist_ok=True)
                
                # 步骤1: 解压文件
                image_files = self._extract_images(file_path, extract_dir)
                if self.cancel_flag.is_set():
                    return {"success": False, "message": "操作已取消"}

                # 步骤1.5: 压缩预检测
                should_compress = self._test_compression_effectiveness(image_files[0], webp_quality)
                if not should_compress:
                    log.info("🔧 [压缩预检测] 压缩效果不理想，跳过压缩")
                    return {
                        "success": False,
                        "message": "压缩包内图片已经高度压缩，无需再次压缩",
                        "skip_reason": "compression_not_effective"
                    }

                # 步骤2: 转换图片
                converted_files = self._convert_images(image_files, output_dir, webp_quality, preserve_original_names)
                if self.cancel_flag.is_set():
                    return {"success": False, "message": "操作已取消"}
                
                # 步骤3: 创建输出文件（Web版本仅支持下载模式）
                result = self._create_output(file_path, converted_files)
                if self.cancel_flag.is_set():
                    return {"success": False, "message": "操作已取消"}
                
                # 步骤4: 完成
                self._report_progress({
                    "status": "completed",
                    "message": "压缩完成",
                    "progress": 100,
                    "total_steps": 4,
                    "current_step": 4
                })
                
                log.info(f"压缩完成: {file_path}")
                return result
                
        except Exception as e:
            log.error(f"压缩失败: {e}")
            self._report_progress({
                "status": "error",
                "message": f"压缩失败: {str(e)}",
                "progress": 0
            })
            return {"success": False, "message": str(e)}
        finally:
            self.is_compressing = False
            self.current_task = None
            self.progress_callback = None
    
    def _extract_images(self, file_path: str, extract_dir: str) -> List[str]:
        """解压并获取图片文件列表"""
        self._report_progress({
            "status": "extracting",
            "message": "正在解压文件...",
            "progress": 10,
            "total_steps": 4,
            "current_step": 1
        })
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        except Exception as e:
            raise Exception(f"解压文件失败: {e}")
        
        # 获取所有图片文件
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.gif'}
        image_files = []
        
        for root, _, files in os.walk(extract_dir):
            for file in files:
                if Path(file).suffix.lower() in image_extensions:
                    image_files.append(os.path.join(root, file))
        
        if not image_files:
            raise Exception("压缩包中没有找到图片文件")
        
        # 按文件名排序
        image_files.sort()
        
        log.info(f"找到 {len(image_files)} 个图片文件")
        
        self._report_progress({
            "status": "extracted",
            "message": f"解压完成，找到 {len(image_files)} 个图片",
            "progress": 25,
            "total_steps": 4,
            "current_step": 1,
            "total_images": len(image_files)
        })
        
        return image_files

    def _test_compression_effectiveness(self, first_image_path: str, webp_quality: int) -> bool:
        """
        测试第一张图片的压缩效果

        Args:
            first_image_path: 第一张图片的路径
            webp_quality: WebP质量设置

        Returns:
            bool: True表示应该进行压缩，False表示跳过压缩
        """
        try:
            log.info(f"🔧 [压缩预检测] 开始测试第一张图片的压缩效果...")
            log.info(f"🔧 [压缩预检测] 测试图片: {os.path.basename(first_image_path)}")

            # 报告预检测进度
            self._report_progress({
                "status": "testing",
                "message": "正在测试压缩效果...",
                "progress": 20,
                "total_steps": 4,
                "current_step": 1
            })

            # 获取原始文件大小
            original_size = os.path.getsize(first_image_path)
            log.info(f"🔧 [压缩预检测] 原始文件大小: {original_size:,} bytes")

            # 读取图片
            img = cv2.imread(first_image_path, cv2.IMREAD_UNCHANGED)
            if img is None:
                log.warning(f"🔧 [压缩预检测] 无法读取测试图片，跳过预检测")
                return True  # 无法读取时默认进行压缩

            # 创建临时文件进行压缩测试
            with tempfile.NamedTemporaryFile(suffix='.webp', delete=False) as temp_file:
                temp_webp_path = temp_file.name

            try:
                # 设置WebP压缩参数
                if webp_quality == 100:
                    # 无损压缩 - 使用WebP无损模式
                    encode_params = [cv2.IMWRITE_WEBP_QUALITY, 101]  # 101表示无损模式
                else:
                    # 有损压缩
                    encode_params = [cv2.IMWRITE_WEBP_QUALITY, webp_quality]

                # 压缩为WebP
                success = cv2.imwrite(temp_webp_path, img, encode_params)
                if not success:
                    log.warning(f"🔧 [压缩预检测] WebP压缩失败，跳过预检测")
                    return True  # 压缩失败时默认进行压缩

                # 获取压缩后文件大小
                compressed_size = os.path.getsize(temp_webp_path)
                log.info(f"🔧 [压缩预检测] 压缩后文件大小: {compressed_size:,} bytes")

                # 计算压缩率
                if original_size > 0:
                    compression_ratio = (original_size - compressed_size) / original_size
                    compression_percentage = compression_ratio * 100

                    log.info(f"🔧 [压缩预检测] 压缩率: {compression_percentage:.1f}%")
                    log.info(f"🔧 [压缩预检测] 文件大小变化: {original_size:,} -> {compressed_size:,} bytes")

                    # 判断是否值得压缩（压缩后文件大小减少25%以上才进行压缩）
                    threshold = 0.25  # 25%阈值
                    should_compress = compression_ratio >= threshold

                    if should_compress:
                        log.info(f"🔧 [压缩预检测] ✅ 压缩效果良好 ({compression_percentage:.1f}% >= 25%)，继续压缩")
                    else:
                        log.info(f"🔧 [压缩预检测] ❌ 压缩效果不理想 ({compression_percentage:.1f}% < 25%)，跳过压缩")

                    return should_compress
                else:
                    log.warning(f"🔧 [压缩预检测] 原始文件大小为0，跳过预检测")
                    return True

            finally:
                # 清理临时文件
                try:
                    if os.path.exists(temp_webp_path):
                        os.unlink(temp_webp_path)
                except Exception as e:
                    log.warning(f"🔧 [压缩预检测] 清理临时文件失败: {e}")

        except Exception as e:
            log.error(f"🔧 [压缩预检测] 预检测过程出错: {e}")
            return True  # 出错时默认进行压缩

    def _convert_images(self, image_files: List[str], output_dir: str, webp_quality: int, preserve_original_names: bool = False) -> List[str]:
        """转换图片为WebP格式（支持多线程）"""
        self._report_progress({
            "status": "converting",
            "message": "开始转换图片格式...",
            "progress": 30,
            "total_steps": 4,
            "current_step": 2,
            "converted_images": 0,
            "total_images": len(image_files)
        })

        # 根据图片数量和CPU核心数决定是否使用多线程
        import multiprocessing
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        cpu_count = multiprocessing.cpu_count()
        total_images = len(image_files)

        # 如果图片数量少于10张或CPU核心数少于2，使用单线程
        if total_images < 10 or cpu_count < 2:
            return self._convert_images_single_thread(image_files, output_dir, webp_quality, preserve_original_names)

        # 使用多线程处理
        max_workers = min(cpu_count, 16)  # 最多8个线程
        log.info(f"使用多线程压缩: {max_workers} 个线程处理 {total_images} 张图片")

        converted_files = []
        converted_files_lock = threading.Lock()
        progress_lock = threading.Lock()
        completed_count = [0]  # 使用列表以便在闭包中修改

        def convert_single_image(args):
            """转换单张图片的工作函数"""
            i, img_path = args

            if self.cancel_flag.is_set():
                return None

            try:
                # 读取图片，忽略颜色配置文件警告
                import warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning, message=".*iCCP.*")
                    img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)

                if img is None:
                    log.warning(f"无法读取图片: {img_path}")
                    return None

                # 生成输出文件名，确保唯一性
                if preserve_original_names:
                    # 保留原始文件名，只改变扩展名
                    original_name = Path(img_path).stem
                    output_filename = f"{original_name}.webp"

                    # 检查文件名冲突，如果存在则添加序号
                    counter = 1
                    base_output_path = os.path.join(output_dir, output_filename)
                    output_path = base_output_path

                    while os.path.exists(output_path):
                        name_without_ext = Path(output_filename).stem
                        output_filename = f"{name_without_ext}_{counter}.webp"
                        output_path = os.path.join(output_dir, output_filename)
                        counter += 1

                        # 防止无限循环
                        if counter > 1000:
                            log.error(f"文件名冲突过多，跳过: {original_name}")
                            return None
                else:
                    # 使用序列命名
                    output_filename = f"page_{i+1:03d}.webp"
                    output_path = os.path.join(output_dir, output_filename)

                # 设置WebP压缩参数
                if webp_quality == 100:
                    # 无损压缩 - 使用WebP无损模式
                    encode_params = [cv2.IMWRITE_WEBP_QUALITY, 101]  # 101表示无损模式
                else:
                    # 有损压缩
                    encode_params = [cv2.IMWRITE_WEBP_QUALITY, webp_quality]

                # 保存为WebP格式，忽略颜色配置文件警告
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning, message=".*iCCP.*")
                    success = cv2.imwrite(output_path, img, encode_params)

                if success:
                    log.debug(f"转换完成: {os.path.basename(img_path)} -> {output_filename}")
                    return output_path
                else:
                    log.warning(f"转换失败: {img_path}")
                    return None

            except Exception as e:
                log.error(f"处理图片 {img_path} 时出错: {e}")
                return None

        # 使用线程池执行转换
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_index = {
                executor.submit(convert_single_image, (i, img_path)): i
                for i, img_path in enumerate(image_files)
            }

            # 收集结果
            for future in as_completed(future_to_index):
                if self.cancel_flag.is_set():
                    break

                result = future.result()
                if result:
                    with converted_files_lock:
                        converted_files.append(result)

                # 更新进度
                with progress_lock:
                    completed_count[0] += 1
                    progress = 30 + completed_count[0] / total_images * 40  # 30-70%
                    self._report_progress({
                        "status": "converting",
                        "message": f"正在转换图片 {completed_count[0]}/{total_images} (多线程)",
                        "progress": int(progress),
                        "total_steps": 4,
                        "current_step": 2,
                        "converted_images": completed_count[0],
                        "total_images": total_images
                    })

        if not converted_files:
            raise Exception("没有成功转换任何图片")

        # 按原始顺序排序（如果使用序列命名）
        if not preserve_original_names:
            converted_files.sort()

        log.info(f"多线程转换完成: {len(converted_files)} 个图片")

        self._report_progress({
            "status": "converted",
            "message": f"图片转换完成，共 {len(converted_files)} 个",
            "progress": 70,
            "total_steps": 4,
            "current_step": 2,
            "converted_images": len(converted_files),
            "total_images": total_images
        })

        return converted_files

    def _convert_images_single_thread(self, image_files: List[str], output_dir: str, webp_quality: int, preserve_original_names: bool = False) -> List[str]:
        """单线程转换图片（原始实现）"""
        converted_files = []

        for i, img_path in enumerate(image_files):
            if self.cancel_flag.is_set():
                break

            try:
                # 读取图片
                img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
                if img is None:
                    log.warning(f"无法读取图片: {img_path}")
                    continue

                # 生成输出文件名
                if preserve_original_names:
                    # 保留原始文件名，只改变扩展名
                    original_name = Path(img_path).stem
                    output_filename = f"{original_name}.webp"
                else:
                    # 使用序列命名
                    output_filename = f"page_{i+1:03d}.webp"
                output_path = os.path.join(output_dir, output_filename)

                # 设置WebP压缩参数
                if webp_quality == 100:
                    # 无损压缩 - 使用WebP无损模式
                    encode_params = [cv2.IMWRITE_WEBP_QUALITY, 101]  # 101表示无损模式
                else:
                    # 有损压缩
                    encode_params = [cv2.IMWRITE_WEBP_QUALITY, webp_quality]

                # 保存为WebP格式
                success = cv2.imwrite(output_path, img, encode_params)
                if success:
                    converted_files.append(output_path)
                    log.debug(f"转换完成: {os.path.basename(img_path)} -> {output_filename}")
                else:
                    log.warning(f"转换失败: {img_path}")

                # 报告进度
                progress = 30 + (i + 1) / len(image_files) * 40  # 30-70%
                self._report_progress({
                    "status": "converting",
                    "message": f"正在转换图片 {i+1}/{len(image_files)}",
                    "progress": int(progress),
                    "total_steps": 4,
                    "current_step": 2,
                    "converted_images": i + 1,
                    "total_images": len(image_files)
                })

            except Exception as e:
                log.error(f"处理图片 {img_path} 时出错: {e}")
                continue

        return converted_files
    
    def _create_output(self, original_file_path: str, converted_files: List[str]) -> Dict[str, Any]:
        """创建输出文件（Web版本仅支持下载模式）"""
        self._report_progress({
            "status": "packaging",
            "message": "正在打包文件...",
            "progress": 75,
            "total_steps": 4,
            "current_step": 3
        })
        
        # Web版本只支持下载模式，不支持文件替换
        # 创建临时ZIP文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in converted_files:
                    arcname = os.path.basename(file_path)
                    zipf.write(file_path, arcname)

            # 生成下载文件名
            original_name = Path(original_file_path).stem
            safe_name = "".join(c for c in original_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            download_name = f"{safe_name}_compressed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

            self._report_progress({
                "status": "packaged",
                "message": "文件打包完成，准备下载",
                "progress": 95,
                "total_steps": 4,
                "current_step": 3
            })

            return {
                "success": True,
                "message": "无损压缩完成",
                "mode": "download",
                "converted_files": len(converted_files),
                "temp_file": temp_zip.name,
                "download_name": download_name
            }
    
    def _report_progress(self, progress_data: Dict[str, Any]):
        """报告进度"""
        if self.progress_callback:
            try:
                self.progress_callback(progress_data)
            except Exception as e:
                log.error(f"进度回调失败: {e}")
    
    def cancel_compression(self):
        """取消压缩操作"""
        log.info("收到取消压缩请求")
        self.cancel_flag.set()
    
    def get_compression_status(self) -> Dict[str, Any]:
        """获取压缩状态"""
        return {
            "is_compressing": self.is_compressing,
            "current_task": self.current_task
        }


# 全局压缩器实例
_compressor_instance = None

def get_image_compressor() -> ImageCompressor:
    """获取图片压缩器实例（单例模式）"""
    global _compressor_instance
    if _compressor_instance is None:
        _compressor_instance = ImageCompressor()
    return _compressor_instance
