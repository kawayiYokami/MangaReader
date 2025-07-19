#!/usr/bin/env python3
"""
页面缓存管理模块 - V6

负责管理标准尺寸（如2000px高度）的页面图像缓存。
- WebP格式持久化存储
- 统一缓存键管理
- 基于容量和LRU策略的智能清理
"""

import os
import time
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from core.core_cache.cache_key_generator import get_cache_key_generator


class PageCache:
    """标准尺寸页面缓存管理器"""

    def __init__(
        self,
        cache_dir: str = "cache/pages",
        quality: int = 85,
        max_cache_size_mb: int = 2048,  # 默认2GB
    ):
        """
        初始化页面缓存系统。

        Args:
            cache_dir: 缓存文件存储目录。
            quality: 生成的 WebP 图像质量 (1-100)。
            max_cache_size_mb: 缓存目录允许的最大总大小 (MB)。
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.webp_quality = quality
        self.max_cache_size_bytes = max_cache_size_mb * 1024 * 1024
        self.key_generator = get_cache_key_generator()

        self.metadata_file = self.cache_dir / "metadata.json"
        self.metadata = self._load_metadata()

        logging.info(
            f"页面缓存初始化完成: {self.cache_dir}, "
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
            logging.warning(f"加载页面缓存元数据失败: {e}")
        return {}

    def _save_metadata(self):
        """保存缓存元数据"""
        try:
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存页面缓存元数据失败: {e}")

    def _get_cache_file_path(self, cache_key: str) -> Path:
        """
        根据缓存键获取文件路径，使用两级目录结构。
        """
        file_hash = hashlib.md5(cache_key.encode('utf-8')).hexdigest()
        subdir = file_hash[:2]
        cache_dir = self.cache_dir / subdir
        cache_dir.mkdir(exist_ok=True)
        return cache_dir / f"{file_hash}.webp"

    def get_page(self, manga_path: str, page_index: int) -> Optional[bytes]:
        """
        获取缓存的页面。

        Args:
            manga_path: 漫画文件路径。
            page_index: 页面索引。

        Returns:
            WebP格式的图像数据，如果未缓存则返回None。
        """
        cache_key = self.key_generator.generate_original_key(manga_path, page_index)
        cache_file = self._get_cache_file_path(cache_key)

        if cache_file.exists() and cache_key in self.metadata:
            # 不再更新 last_accessed
            return cache_file.read_bytes()

        logging.debug(f"页面缓存未命中: {manga_path} [Page {page_index}]")
        return None

    def store_page(self, manga_path: str, page_index: int, image_bytes: bytes):
        """
        存储一个标准尺寸的页面到缓存中。

        Args:
            manga_path: 漫画文件路径。
            page_index: 页面索引。
            image_bytes: 已编码为WebP格式的图像数据。
        """
        cache_key = self.key_generator.generate_original_key(manga_path, page_index)
        cache_file = self._get_cache_file_path(cache_key)

        try:
            cache_file.write_bytes(image_bytes)
            
            self.metadata[cache_key] = {
                "source_path": manga_path,
                "page_index": page_index,
                "created": time.time(),
                "file_size": len(image_bytes),
            }
            self._save_metadata()
            logging.info(f"页面已存入缓存: {cache_file.name}")

            # 每次生成新文件后，检查缓存容量
            self._enforce_size_limit()
            
        except Exception as e:
            logging.error(f"存储页面到缓存失败: {cache_file}, 错误: {e}")

    def _enforce_size_limit(self):
        """强制执行缓存大小限制"""
        try:
            current_size = sum(item.get("file_size", 0) for item in self.metadata.values())
            if current_size <= self.max_cache_size_bytes:
                return

            logging.info(
                f"页面缓存超出容量 ({current_size / 1024**2:.2f}MB > {self.max_cache_size_bytes / 1024**2:.2f}MB)，开始清理..."
            )

            # 第一步：清理孤立文件
            orphaned_size = self._cleanup_orphans()
            current_size -= orphaned_size
            if current_size <= self.max_cache_size_bytes:
                logging.info("清理孤立文件后，页面缓存大小已达标。")
                return

            # 第二步：按创建时间策略清理 (FIFO)
            sorted_metadata = sorted(
                self.metadata.items(), key=lambda item: item[1].get("created", 0)
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
                        logging.warning(f"LRU清理页面缓存失败 {cache_file}: {e}")
            
            if cleaned_count > 0:
                self._save_metadata()
                logging.info(f"LRU策略清理了 {cleaned_count} 个页面缓存文件。")

        except Exception as e:
            logging.error(f"执行页面缓存大小限制失败: {e}")

    def _cleanup_orphans(self) -> int:
        """清理源文件已不存在的缓存条目"""
        orphaned_size = 0
        orphaned_keys = []
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
                        logging.warning(f"删除孤立页面缓存文件失败 {cache_file}: {e}")

        if orphaned_keys:
            for key in orphaned_keys:
                if key in self.metadata:
                    del self.metadata[key]
            self._save_metadata()
            logging.info(f"清理了 {len(orphaned_keys)} 个孤立的页面缓存元数据。")

        return orphaned_size


# 全局实例
_page_cache_instance: Optional[PageCache] = None

def get_page_cache() -> PageCache:
    """获取全局页面缓存实例"""
    global _page_cache_instance
    if _page_cache_instance is None:
        # 可以在这里从全局配置模块中读取参数
        from core.config import config
        _page_cache_instance = PageCache(
            quality=config.page_cache_quality.value,
            max_cache_size_mb=config.page_cache_max_size_mb.value
        )
    return _page_cache_instance