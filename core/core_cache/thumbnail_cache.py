"""
缩略图缓存管理模块 - V5.4
使用项目内文件夹持久化存储缩略图，支持智能容量管理和HTTP缓存。
"""

import os
import hashlib
import time
import json
import traceback  # 导入traceback用于打印堆栈
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from PIL import Image, ImageOps
import logging

log = logging.getLogger(__name__)


class ThumbnailCache:
    """
    智能缩略图缓存管理器。
    - 持久化存储
    - 精确尺寸裁剪
    - 基于容量的智能清理
    """

    def __init__(
        self,
        cache_dir: str = "cache/thumbnails",
        output_size: Tuple[int, int] = (256, 342),
        quality: int = 75,
        max_cache_size_mb: int = 500,
    ):
        """
        初始化智能缩略图缓存系统。

        :param cache_dir: 缓存文件存储目录。
        :param output_size: 缩略图的目标尺寸 (宽, 高)。
        :param quality: 生成的 WebP 图像质量 (1-100)。
        :param max_cache_size_mb: 缓存目录允许的最大总大小 (单位: MB)。
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.output_size = output_size
        self.webp_quality = quality
        self.max_cache_size_bytes = max_cache_size_mb * 1024 * 1024

        self.metadata_file = self.cache_dir / "metadata.json"
        self.metadata = self._load_metadata()

        # 清理操作已移至缩略图生成时按需执行，以加速启动

        log.info(
            f"缩略图缓存初始化完成: {self.cache_dir}, "
            f"目标尺寸: {self.output_size}, "
            f"质量: {self.webp_quality}, "
            f"容量上限: {max_cache_size_mb}MB"
        )

    def _load_metadata(self) -> Dict[str, Any]:
        """加载缓存元数据"""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            log.warning(f"加载缓存元数据失败: {e}")
        return {}

    def _save_metadata(self):
        """保存缓存元数据"""
        try:
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error(f"保存缓存元数据失败: {e}")

    def _get_cache_key(self, manga_path: str) -> str:
        """根据漫画路径和固定的输出尺寸生成缓存键"""
        content = f"{manga_path}_{self.output_size[0]}x{self.output_size[1]}"
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
                        log.debug(f"删除孤立缓存: {cache_file.name}")
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

            cache_key = self._get_cache_key(manga_path)
            cache_file_path = self._get_cache_file_path(cache_key)
            source_mtime = os.path.getmtime(manga_path)

            if cache_file_path.exists() and cache_key in self.metadata:
                cached_mtime = self.metadata[cache_key].get("source_mtime", 0)
                if cached_mtime == source_mtime:
                    self.metadata[cache_key]["last_accessed"] = time.time()
                    self._save_metadata()
                    return str(cache_file_path)

            return self._generate_thumbnail(manga_path, cache_key, source_mtime)

        except Exception as e:
            log.error(f"获取缩略图路径失败 {manga_path}: {e}")
            return None

    def _generate_thumbnail(
        self, manga_path: str, cache_key: str, source_mtime: float
    ) -> Optional[str]:
        """生成并保存缩略图文件"""
        try:
            first_page_image = self._get_first_page_image(manga_path)
            if first_page_image is None:
                return None

            thumbnail = self._create_thumbnail(first_page_image)
            if thumbnail is None:
                return None

            cache_file_path = self._get_cache_file_path(cache_key)
            thumbnail.save(
                cache_file_path,
                format="WEBP",
                quality=self.webp_quality,
                method=6,  # method=6 for best quality/compression ratio
            )

            current_time = time.time()
            self.metadata[cache_key] = {
                "source_path": manga_path,
                "source_mtime": source_mtime,
                "size": self.output_size,  # 保存尺寸元数据
                "created": current_time,
                "last_accessed": current_time,
                "file_size": cache_file_path.stat().st_size,
            }
            self._save_metadata()

            # 每次生成新文件后，检查缓存容量
            self._enforce_size_limit()

            log.debug(f"生成缩略图: {manga_path} -> {cache_file_path.name}")
            return str(cache_file_path)

        except Exception as e:
            log.error(f"生成缩略图失败 {manga_path}: {e}", exc_info=True)
            return None

    def _get_first_page_image(self, manga_path: str) -> Optional[Image.Image]:
        """获取漫画第一页的PIL Image对象"""
        try:
            if os.path.isdir(manga_path):
                return self._get_first_page_from_folder(manga_path)
            else:
                return self._get_first_page_from_archive(manga_path)
        except Exception as e:
            log.error(f"获取第一页图片失败 {manga_path}: {e}")
            return None

    def _get_first_page_from_folder(self, folder_path: str):
        """从文件夹获取第一页图片"""
        try:
            image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
            image_files = []
            for file_path in Path(folder_path).iterdir():
                if file_path.suffix.lower() in image_extensions:
                    image_files.append(file_path)
            if not image_files:
                return None
            image_files.sort(key=lambda x: x.name.lower())
            return Image.open(image_files[0])
        except Exception as e:
            log.error(f"从文件夹获取第一页失败 {folder_path}: {e}")
            return None

    def _get_first_page_from_archive(self, archive_path: str):
        """从压缩文件获取第一页图片 - 只支持ZIP格式，与核心代码保持一致"""
        try:
            import zipfile
            from io import BytesIO

            image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
            file_ext = Path(archive_path).suffix.lower()
            if file_ext in [".zip", ".cbz"]:
                with zipfile.ZipFile(archive_path, "r") as zf:
                    image_files = [
                        name
                        for name in zf.namelist()
                        if Path(name).suffix.lower() in image_extensions
                    ]
                    if not image_files:
                        return None
                    image_files.sort()
                    with zf.open(image_files[0]) as img_file:
                        return Image.open(BytesIO(img_file.read()))
            else:
                log.warning(f"不支持的压缩格式: {file_ext}，只支持ZIP格式")
                return None
        except Exception as e:
            log.error(f"从压缩文件获取第一页失败 {archive_path}: {e}")
            return None

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
