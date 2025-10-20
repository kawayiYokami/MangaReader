#!/usr/bin/env python3
"""
图片压缩模块 - 负责将漫画文件中的图片转换为WebP格式 (工具层)
"""

import os
import tempfile
import zipfile
import cv2
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import threading
import warnings
import numpy as np
import logging

class ImageCompressor:
    """
    图片压缩器 (专职工匠)
    职责:
    1. 提供对单个文件进行压缩预测试的功能。
    2. 提供对单个文件进行完整压缩、验证并返回临时压缩包路径的功能。
    此类应该是无状态的，所有任务相关状态由调用方（Manager）管理。
    """
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif', '.webp'}

    def __init__(self):
        self.cancel_flag = threading.Event()

    def pre_test_compression(self, file_path: str, webp_quality: int, min_compression_ratio: float) -> Dict[str, Any]:
        """
        对漫画文件进行快速预检测，判断是否值得压缩。
        只解压和测试第一张图片。
        """
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                extract_dir = os.path.join(temp_dir, "pretest_extracted")
                os.makedirs(extract_dir, exist_ok=True)

                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    first_image_member = None
                    first_image_path = None

                    for member_info in zip_ref.infolist():
                        if member_info.is_dir():
                            continue

                        # --- 复用健壮的文件名解码逻辑 ---
                        original_filename = member_info.filename
                        decoded_filename = None
                        encodings_to_try = ['utf-8', 'gbk', 'shift-jis']
                        for encoding in encodings_to_try:
                            try:
                                decoded_filename = original_filename.encode('cp437').decode(encoding)
                                break
                            except (UnicodeEncodeError, UnicodeDecodeError):
                                continue

                        if decoded_filename is None:
                            decoded_filename = original_filename

                        suffix = Path(decoded_filename).suffix.lower()
                        if suffix in self.IMAGE_EXTENSIONS:
                            member_info.filename = decoded_filename
                            first_image_member = member_info
                            first_image_path = os.path.join(extract_dir, first_image_member.filename)
                            break

                    if not first_image_member or not first_image_path:
                        return {"should_compress": False, "reason": "压缩包中没有找到可测试的图片文件"}

                    # 使用修改了filename的member_info来解压
                    zip_ref.extract(first_image_member, path=extract_dir)

                    original_size = os.path.getsize(first_image_path)
                    if original_size == 0:
                        return {"should_compress": True, "reason": "无法评估大小为0的图片，默认压缩"}

                    img = self._read_image_robustly(first_image_path)
                    if img is None:
                        return {"should_compress": True, "reason": "无法读取测试图片，默认压缩"}

                    temp_webp_path = None
                    try:
                        with tempfile.NamedTemporaryFile(suffix='.webp', delete=False) as temp_webp_file:
                            temp_webp_path = temp_webp_file.name

                        encode_params = [cv2.IMWRITE_WEBP_QUALITY, 101 if webp_quality == 100 else webp_quality]
                        success = cv2.imwrite(temp_webp_path, img, encode_params)

                        if not success:
                            return {"should_compress": True, "reason": "WebP压缩测试失败，默认压缩"}

                        compressed_size = os.path.getsize(temp_webp_path)
                    finally:
                        if temp_webp_path and os.path.exists(temp_webp_path):
                            os.remove(temp_webp_path)
                        compression_ratio = (original_size - compressed_size) / original_size

                        if compression_ratio >= min_compression_ratio:
                            return {"should_compress": True, "reason": f"预检测通过 (压缩率 {compression_ratio:.1%})"}
                        else:
                            return {"should_compress": False, "reason": f"压缩效果不佳 ({compression_ratio:.1%})"}

        except Exception as e:
            logging.error(f"预检测过程出错 {os.path.basename(file_path)}: {e}")
            return {"should_compress": True, "reason": "预检测异常，默认压缩"}

    def compress_manga_file(
        self,
        file_path: str,
        webp_quality: int = 100,
        preserve_original_names: bool = True
    ) -> Optional[str]:
        """
        压缩漫画文件，并返回一个经过严格验证的临时压缩包路径。
        如果操作失败或被取消，则返回 None。
        """
        if self.is_cancellation_requested():
            logging.warning("Operation cancelled before starting.")
            return None

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                extract_dir = os.path.join(temp_dir, "extracted")
                output_dir = os.path.join(temp_dir, "compressed")
                os.makedirs(extract_dir, exist_ok=True)
                os.makedirs(output_dir, exist_ok=True)

                image_files = self._extract_images(file_path, extract_dir)
                if self.is_cancellation_requested() or not image_files:
                    return None

                # 步骤2: 转换图片，现在会返回成功列表和坏图列表
                converted_files, bad_files = self._convert_images(image_files, output_dir, webp_quality, preserve_original_names)
                if self.is_cancellation_requested():
                    return None
                # 如果所有图片都转换失败，则中止
                if not converted_files:
                    logging.error(f"未能成功转换任何图片: {Path(file_path).name}")
                    return None

                temp_zip_path = self._create_output_package(converted_files)
                if self.is_cancellation_requested() or not temp_zip_path:
                    return None

                # 步骤4: 严格验证, 现在会考虑坏图
                if not self._verify_compressed_package(file_path, temp_zip_path, bad_files):
                    os.remove(temp_zip_path)
                    return None

                return temp_zip_path

        except Exception as e:
            logging.error(f"压缩文件 '{Path(file_path).name}' 失败: {e}", exc_info=True)
            return None

    def _extract_images(self, file_path: str, extract_dir: str) -> List[str]:
        """最终版健壮解压，实现解码链尝试解决所有编码问题。"""
        image_files = []

        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                for member_info in zip_ref.infolist():
                    if member_info.is_dir():
                        continue

                    # --- 终极文件名编码处理 ---
                    original_filename = member_info.filename
                    decoded_filename = None

                    # 尝试不同的解码策略
                    encodings_to_try = ['utf-8', 'gbk', 'shift-jis']
                    # cp437是zip规范的默认值，很多windows工具会错误地用它打包本地编码（如gbk）
                    # 所以先用cp437编码回bytes，再用目标编码解码
                    for encoding in encodings_to_try:
                        try:
                            decoded_filename = original_filename.encode('cp437').decode(encoding)
                            break # 成功解码，跳出循环
                        except (UnicodeEncodeError, UnicodeDecodeError):
                            continue

                    # 如果所有尝试都失败，则使用原始文件名
                    if decoded_filename is None:
                        decoded_filename = original_filename

                    if Path(decoded_filename).suffix.lower() not in self.IMAGE_EXTENSIONS:
                        continue

                    member_info.filename = decoded_filename
                    try:
                        extracted_path = zip_ref.extract(member_info, path=extract_dir)
                        image_files.append(extracted_path)
                    except Exception as extract_error:
                        logging.warning(f"Failed to extract file '{decoded_filename}': {extract_error}")

        except Exception as e:
            raise Exception(f"打开或读取zip文件失败: {e}")

        if not image_files:
            raise Exception("压缩包中没有找到可处理的图片文件")

        image_files.sort()
        logging.debug(f"在 {Path(file_path).name} 中找到 {len(image_files)} 个图片文件")
        return image_files

    def _convert_images(self, image_files: List[str], output_dir: str, webp_quality: int, preserve_original_names: bool) -> Tuple[List[str], List[str]]:
        """转换图片为WebP格式（多线程），返回成功和失败的文件列表。"""
        import multiprocessing
        from concurrent.futures import ThreadPoolExecutor, as_completed

        total_images = len(image_files)
        # 返回 (converted_files, bad_files)
        if total_images < 10 or multiprocessing.cpu_count() < 2:
            return self._convert_images_single_thread(image_files, output_dir, webp_quality, preserve_original_names)

        max_workers = min(multiprocessing.cpu_count(), 16)
        converted_files = []
        bad_files = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {executor.submit(self._convert_single_image, img_path, output_dir, webp_quality, preserve_original_names, i): img_path for i, img_path in enumerate(image_files)}

            for future in as_completed(future_to_path):
                if self.cancel_flag.is_set():
                    for f in future_to_path:
                        f.cancel()
                    return [], image_files  # 如果取消，所有文件都算未处理

                original_path = future_to_path[future]
                result = future.result()
                if result:
                    converted_files.append(result)
                else:
                    bad_files.append(original_path)

        if not preserve_original_names:
            converted_files.sort()
        logging.debug(f"多线程转换完成: {len(converted_files)} 成功, {len(bad_files)} 失败 / 总计 {total_images} 个图片")
        return converted_files, bad_files

    def _convert_single_image(self, img_path: str, output_dir: str, webp_quality: int, preserve_original_names: bool, index: int) -> Optional[str]:
        """单个图片转换的工作函数"""
        if self.cancel_flag.is_set():
            return None
        try:
            img = self._read_image_robustly(img_path)
            if img is None:
                logging.warning(f"Could not read image {img_path}, skipping.")
                return None

            output_filename = f"{Path(img_path).stem}.webp" if preserve_original_names else f"page_{index+1:03d}.webp"
            output_path = os.path.join(output_dir, output_filename)

            encode_params = [cv2.IMWRITE_WEBP_QUALITY, 101 if webp_quality == 100 else webp_quality]
            success = cv2.imwrite(output_path, img, encode_params)
            return output_path if success else None
        except Exception as e:
            logging.error(f"处理图片时发生错误 {img_path}: {e}")
            return None

    def _convert_images_single_thread(self, image_files: List[str], output_dir: str, webp_quality: int, preserve_original_names: bool) -> Tuple[List[str], List[str]]:
        """单线程转换图片，返回成功和失败的文件列表。"""
        converted_files = []
        bad_files = []
        for i, img_path in enumerate(image_files):
            if self.cancel_flag.is_set():
                # 如果取消，所有剩余文件都视为“坏”文件，以便验证逻辑能正确处理
                bad_files.extend(image_files[i:])
                break
            result = self._convert_single_image(img_path, output_dir, webp_quality, preserve_original_names, i)
            if result:
                converted_files.append(result)
            else:
                bad_files.append(img_path)
        return converted_files, bad_files

    def _create_output_package(self, converted_files: List[str]) -> Optional[str]:
        """将转换后的文件打包成一个临时的zip文件"""
        try:
            temp_zip_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip', prefix='manga_comp_')
            with zipfile.ZipFile(temp_zip_file.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in converted_files:
                    zipf.write(file_path, os.path.basename(file_path))
            return temp_zip_file.name
        except Exception as e:
            logging.error(f"创建临时压缩包失败: {e}")
            return None

    def _verify_compressed_package(self, original_path: str, compressed_temp_path: str, bad_files: List[str]) -> bool:
        """对新生成的压缩包执行严格验证，会考虑转换失败的坏图。"""
        try:
            with zipfile.ZipFile(original_path, 'r') as original_zip, zipfile.ZipFile(compressed_temp_path, 'r') as compressed_zip:
                original_file_infos = [info for info in original_zip.infolist() if not info.is_dir()]
                compressed_file_infos = compressed_zip.infolist()

                expected_count = len(original_file_infos) - len(bad_files)
                actual_count = len(compressed_file_infos)

                if expected_count != actual_count:
                    logging.error(f"验证失败: 文件数量不一致。预期: {expected_count} (原始: {len(original_file_infos)} - 坏图: {len(bad_files)}), 实际压缩: {actual_count}")
                    return False

            logging.info(f"文件 {Path(original_path).name} 的压缩验证通过 (已跳过 {len(bad_files)} 个坏图)。")
            return True
        except Exception as e:
            logging.error(f"验证压缩包时发生严重错误: {e}")
            return False

    def _read_image_robustly(self, img_path: str) -> Optional[np.ndarray]:
        """健壮地读取图片文件，抑制iCCP警告。"""
        try:
            # 统一使用OpenCV读取，移除Pillow回退
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning, message=".*iCCP.*")
                img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)

            if img is None:
                logging.warning(f"OpenCV could not read {img_path}")
                return None

            # 保持原有的通道转换逻辑，确保输出是BGR
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            elif img.shape[2] == 4: # 如果是BGRA, 转换为BGR
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            return img

        except Exception as e:
            logging.error(f"读取图片时发生意外错误 {img_path}: {e}")
            return None

    def cancel_compression(self):
        """(由Manager调用) 取消所有正在进行的操作"""
        logging.info("ImageCompressor 收到取消请求")
        self.cancel_flag.set()

    def reset_cancel_flag(self):
        """(由Manager调用) 重置取消标志，为下一次任务做准备"""
        self.cancel_flag.clear()

    def is_cancellation_requested(self) -> bool:
        """检查是否已请求取消"""
        return self.cancel_flag.is_set()

# --- 单例模式 ---
_compressor_instance = None
def get_image_compressor() -> ImageCompressor:
    """获取图片压缩器实例"""
    global _compressor_instance
    if _compressor_instance is None:
        _compressor_instance = ImageCompressor()
    return _compressor_instance
