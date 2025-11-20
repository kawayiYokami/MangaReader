"""
缩略图缓存管理模块 - V5.4
使用项目内文件夹持久化存储缩略图，支持智能容量管理和HTTP缓存。
"""

import os
import hashlib
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from PIL import Image, ImageOps
import logging
from io import BytesIO # 导入BytesIO

from src.backend.core.image import processor # 导入我们自己的图像处理器
from src.backend.core.config import config # 导入全局配置
from src.backend.core.core_cache.cache_key_generator import CacheKeyGenerator # 导入新的主键生成器

log = logging.getLogger(__name__)


class ThumbnailCache:
    """
    智能缩略图缓存管理器。
    - 持久化存储
    - 精确尺寸裁剪
    - 基于容量的智能清理
    """

    def __init__(self):
        """
        初始化智能缩略图缓存系统。
        """
        self.cache_dir = Path(config.thumbnail_cache_dir.value)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.output_size = (
            config.thumbnail_output_width.value,
            config.thumbnail_output_height.value,
        )
        self.webp_quality = config.thumbnail_quality.value
        self.max_cache_size_bytes = config.thumbnail_max_size_mb.value * 1024 * 1024

        self.metadata_file = self.cache_dir / "metadata.json"
        self.metadata = self._load_metadata()

        # 清理操作已移至缩略图生成时按需执行，以加速启动

        log.info(
            f"缩略图缓存初始化完成: {self.cache_dir}, "
            f"目标尺寸: {self.output_size}, "
            f"质量: {self.webp_quality}, "
            f"容量上限: {config.thumbnail_max_size_mb.value}MB"
        )

    def _load_metadata(self) -> Dict[str, Any]:
        """加载缓存元数据"""
        if not self.metadata_file.exists():
            log.warning(f"元数据文件不存在: {self.metadata_file}，将创建新的元数据。")
            return {}
        try:
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except json.JSONDecodeError as e:
            log.error(f"解析元数据文件失败: {e}。文件可能已损坏。将创建新的元数据。")
        except Exception as e:
            log.error(f"加载缓存元数据时发生未知错误: {e}")
        return {}

    def _save_metadata(self):
        """保存缓存元数据"""
        try:
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error(f"保存缓存元数据失败: {e}", exc_info=True)

    def _get_thumbnail_file_key(self, master_key: str, size: Tuple[int, int]) -> str:
        """根据主键和目标尺寸生成缩略图的文件名键"""
        content = f"{master_key}_{size[0]}x{size[1]}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def _get_cache_file_path(self, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{cache_key}.webp"

    def _cleanup_orphans(self) -> int:
        """
        清理孤立的缓存文件（源文件已不存在）。
        返回清理掉的文件大小。
        """
        orphaned_size = 0
        orphaned_keys = []
        # 使用.copy()来避免在迭代时修改字典
        for key, meta in self.metadata.copy().items():
            source_path = meta.get("source_path")
            if not source_path or not Path(source_path).exists():
                orphaned_keys.append(key)
                cache_file = self._get_cache_file_path(key)
                if cache_file.exists():
                    try:
                        file_size = cache_file.stat().st_size
                        cache_file.unlink()
                        orphaned_size += file_size
                    except OSError as e:
                        log.warning(f"删除孤立缓存文件失败 {cache_file}: {e}")

        if orphaned_keys:
            for key in orphaned_keys:
                if key in self.metadata:
                    del self.metadata[key]
            self._save_metadata()
            log.info(f"清理了 {len(orphaned_keys)} 个孤立的元数据条目。")

        return orphaned_size

    def _enforce_size_limit(self):
        """
        强制执行缓存大小限制。
        优先清理孤立文件，然后根据LRU策略清理最久未使用的文件。
        """
        try:
            current_size = sum(
                f.stat().st_size for f in self.cache_dir.glob("*.webp") if f.is_file()
            )

            if current_size <= self.max_cache_size_bytes:
                return

            log.info(
                f"缓存超出容量 ({current_size / 1024**2:.2f}MB > {self.max_cache_size_bytes / 1024**2:.2f}MB)，开始清理..."
            )

            # 第一步：清理孤立文件
            orphaned_size = self._cleanup_orphans()
            current_size -= orphaned_size

            if current_size <= self.max_cache_size_bytes:
                log.info("清理孤立文件后，缓存大小已达标。")
                return

            # 第二步：如果仍然超限，按LRU策略清理
            log.info("按LRU策略继续清理...")

            # 获取所有元数据并按最后访问时间排序
            sorted_metadata = sorted(
                self.metadata.items(), key=lambda item: item[1].get("last_accessed", 0)
            )

            cleaned_count = 0
            while current_size > self.max_cache_size_bytes and sorted_metadata:
                cache_key, meta = sorted_metadata.pop(0)
                cache_file = self._get_cache_file_path(cache_key)

                if cache_file.exists():
                    try:
                        file_size = meta.get("file_size", cache_file.stat().st_size)
                        cache_file.unlink()
                        current_size -= file_size
                        cleaned_count += 1
                        if cache_key in self.metadata:
                            del self.metadata[cache_key]
                    except OSError as e:
                        log.warning(f"LRU清理失败，无法删除文件 {cache_file}: {e}")

            if cleaned_count > 0:
                self._save_metadata()
                log.info(f"LRU策略清理了 {cleaned_count} 个文件。")

        except Exception as e:
            log.error(f"执行缓存大小限制失败: {e}")

    def get_thumbnail_path(self, manga_path: str) -> Optional[str]:
        """获取缩略图文件路径，如果不存在则生成"""
        try:
            if not os.path.exists(manga_path):
                return None

            master_key = CacheKeyGenerator.generate_master_key_for_path(manga_path)
            if not master_key:
                return None  # 无法获取文件信息

            master_metadata = self.metadata.get(master_key)
            
            # 如果主键存在，检查这个尺寸的缩略图是否存在
            if master_metadata:
                # 使用 str(self.output_size) 作为键
                size_key = str(self.output_size)
                if size_key in master_metadata.get("thumbnails", {}):
                    thumb_info = master_metadata["thumbnails"][size_key]
                    thumbnail_file_key = thumb_info.get("file_key")
                    cache_file_path = self._get_cache_file_path(thumbnail_file_key)

                    if cache_file_path.exists():
                        return str(cache_file_path)

                # 主键存在，但当前尺寸的缩略图不存在（需要生成，但无需分析）
                return self._generate_thumbnail(manga_path, master_key, needs_analysis=False)

            # 主键不存在，需要进行完整分析和生成
            return self._generate_thumbnail(manga_path, master_key, needs_analysis=True)

        except Exception as e:
            log.error(f"获取缩略图路径失败 {manga_path}: {e}", exc_info=True)
            return None

    def _generate_thumbnail(
        self, manga_path: str, master_key: str, needs_analysis: bool
    ) -> Optional[str]:
        """
        生成缩略图并按需执行压缩分析
        """
        try:
            # --- 步骤1: 获取源图像 ---
            source_bytes, first_page_image = self._get_first_page_bytes_and_image(manga_path)
            if not first_page_image or not source_bytes:
                return None
            
            # --- 步骤2: 按需执行一次性分析 ---
            if needs_analysis:
                # 分析过程即为模拟一次缩略图生成，以计算压缩比。
                # 因此，我们使用最终缩略图的尺寸和质量设置。

                # 线性估算法
                original_file_size = len(source_bytes)
                original_pixels = first_page_image.width * first_page_image.height

                # 步骤 A: 创建与最终缩略图完全相同的分析用图像
                analysis_image = self._create_thumbnail(first_page_image)
                if analysis_image is None:
                    raise ValueError("分析时创建缩略图失败")

                # 步骤 B: 使用最终的质量设置将其编码为 WebP
                import cv2
                import numpy as np
                cv2_image = cv2.cvtColor(np.array(analysis_image), cv2.COLOR_RGB2BGR)
                processed_bytes = processor.write_image(cv2_image, ext='.webp', quality=self.webp_quality)
                if not processed_bytes:
                    raise ValueError("分析时图像编码失败")

                final_processed_size = len(processed_bytes)

                # 步骤 C: 使用标准位图算法计算压缩比
                # 估算缩放后的传统编码文件大小
                original_file_size = len(source_bytes)
                original_pixels = first_page_image.width * first_page_image.height
                thumb_pixels = analysis_image.width * analysis_image.height
                estimated_scaled_size = original_file_size * (thumb_pixels / original_pixels) if original_pixels > 0 else 0

                compression_ratio = final_processed_size / estimated_scaled_size if estimated_scaled_size > 0 else float('inf')

                # 创建主元数据条目
                self.metadata[master_key] = {
                    "source_path": manga_path,
                    "analysis": {
                        "policy": "UNKNOWN",  # 缓存策略设置为未知，由其他模块决定
                        "compression_ratio": round(compression_ratio, 2),
                        "first_page_size": original_file_size,
                        "first_page_dimensions": (first_page_image.width, first_page_image.height),
                    },
                    "thumbnails": {}
                }
                

            # --- 步骤3: 生成当前请求的缩略图 ---
            thumbnail_file_key = self._get_thumbnail_file_key(master_key, self.output_size)
            cache_file_path = self._get_cache_file_path(thumbnail_file_key)
            
            # 只有在文件不存在时才创建
            if not cache_file_path.exists():
                thumbnail = self._create_thumbnail(first_page_image)
                if thumbnail is None:
                    return None
                
                # 统一使用WebP格式
                thumbnail.save(
                    cache_file_path,
                    format="WEBP",
                    quality=self.webp_quality,
                    method=6,
                )
            
            # --- 步骤4: 更新元数据并保存 ---
            current_time = time.time()
            thumbnail_metadata = {
                "file_key": thumbnail_file_key,
                "created": current_time,
                "last_accessed": current_time,
                "file_size": cache_file_path.stat().st_size
            }
            # 使用 str(self.output_size) 作为键，因为JSON的键必须是字符串
            self.metadata[master_key]["thumbnails"][str(self.output_size)] = thumbnail_metadata
            self._save_metadata()

            # --- 步骤5: 清理并返回 ---
            self._enforce_size_limit()
            return str(cache_file_path)

        except Exception as e:
            log.error(f"生成缩略图失败 {manga_path}: {e}", exc_info=True)
            # 如果分析失败，确保不会留下不完整的元数据条目
            if needs_analysis and master_key in self.metadata:
                del self.metadata[master_key]
            return None

    def _get_first_page_bytes_and_image(self, manga_path: str) -> Tuple[Optional[bytes], Optional[Image.Image]]:
        """获取漫画第一页的原始字节流和PIL Image对象"""
        try:
            file_ext = Path(manga_path).suffix.lower()
            supported_archives = ['.zip', '.cbz']

            if os.path.isdir(manga_path):
                return self._get_first_page_from_folder(manga_path)
            elif file_ext in supported_archives:
                return self._get_first_page_from_archive(manga_path)
            else:
                # 对于单个图片文件，直接读取
                with open(manga_path, 'rb') as f:
                    source_bytes = f.read()
                return source_bytes, Image.open(BytesIO(source_bytes))
        except Exception as e:
            log.error(f"获取第一页图片失败 {manga_path}: {e}")
            return None, None

    def _get_first_page_from_folder(self, folder_path: str) -> Tuple[Optional[bytes], Optional[Image.Image]]:
        """从文件夹获取第一页图片"""
        try:
            image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
            image_files = []
            for file_path in Path(folder_path).iterdir():
                if file_path.suffix.lower() in image_extensions:
                    image_files.append(file_path)
            if not image_files:
                return None, None
            image_files.sort(key=lambda x: x.name.lower())
            
            image_path = image_files[0]
            with open(image_path, 'rb') as f:
                source_bytes = f.read()
            return source_bytes, Image.open(BytesIO(source_bytes))
        except Exception as e:
            log.error(f"从文件夹获取第一页失败 {folder_path}: {e}")
            return None, None

    def _get_first_page_from_archive(self, archive_path: str) -> Tuple[Optional[bytes], Optional[Image.Image]]:
        """从压缩文件获取第一页图片 - 只支持ZIP格式，与核心代码保持一致"""
        try:
            import zipfile

            image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
            file_ext = Path(archive_path).suffix.lower()
            if file_ext in [".zip", ".cbz"]:
                with zipfile.ZipFile(archive_path, "r") as zf:
                    image_files = [
                        name
                        for name in zf.namelist()
                        if Path(name).suffix.lower() in image_extensions and not name.startswith('__MACOSX')
                    ]
                    if not image_files:
                        return None, None
                    image_files.sort()
                    with zf.open(image_files[0]) as img_file:
                        source_bytes = img_file.read()
                        return source_bytes, Image.open(BytesIO(source_bytes))
            else:
                log.warning(f"不支持的压缩格式: {file_ext}，只支持ZIP格式")
                return None, None
        except Exception as e:
            log.error(f"从压缩文件获取第一页失败 {archive_path}: {e}")
            return None, None

    def _create_thumbnail(self, image: Image.Image) -> Optional[Image.Image]:
        """
        使用“调整并居中裁剪”算法创建缩略图。
        """
        try:
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            thumbnail = ImageOps.fit(image, self.output_size, Image.Resampling.LANCZOS)
            return thumbnail
        except Exception as e:
            log.error(f"创建缩略图失败: {e}", exc_info=True)
            return None

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            total_size = sum(
                f.stat().st_size for f in self.cache_dir.glob("*.webp") if f.is_file()
            )
            file_count = len(self.metadata)
            return {
                "cache_dir": str(self.cache_dir),
                "total_files": file_count,
                "total_size_mb": round(total_size / 1024 / 1024, 2),
                "max_size_mb": round(self.max_cache_size_bytes / 1024 / 1024, 2),
                "metadata_entries": len(self.metadata),
            }
        except Exception as e:
            log.error(f"获取缓存统计失败: {e}")
            return {}

    def clear_cache(self):
        """清空所有缓存"""
        try:
            for cache_file in self.cache_dir.glob("*.webp"):
                try:
                    cache_file.unlink()
                except OSError:
                    continue
            self.metadata.clear()
            self._save_metadata()
            log.info("缓存已清空")
        except Exception as e:
            log.error(f"清空缓存失败: {e}")
