#!/usr/bin/env python3
"""
持久化翻译缓存管理模块

负责管理翻译后图像的文件系统缓存，包括：
1. WebP格式压缩存储
2. 文件命名和组织
3. 缓存检索和验证
4. 启动时缓存发现
"""

import os
import hashlib
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from PIL import Image
import numpy as np
from datetime import datetime

from utils import manga_logger as log


class PersistentTranslationCache:
    """持久化翻译缓存管理器"""
    
    def __init__(self, cache_root: str = "cache/translated"):
        """
        初始化持久化缓存管理器
        
        Args:
            cache_root: 缓存根目录
        """
        self.cache_root = Path(cache_root)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        
        # 缓存配置
        self.config = {
            'webp_quality': 80,  # WebP压缩质量
            'max_cache_size_gb': 5,  # 最大缓存大小（GB）
            'cleanup_threshold': 0.9,  # 清理阈值（90%时开始清理）
            'metadata_file': 'cache_metadata.json'
        }
        
        # 元数据文件路径
        self.metadata_file = self.cache_root / self.config['metadata_file']
        
        # 加载缓存元数据
        self.metadata = self._load_metadata()
        
        log.info(f"持久化翻译缓存初始化完成: {self.cache_root}")
    
    def _load_metadata(self) -> Dict[str, Any]:
        """加载缓存元数据"""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                log.info(f"加载缓存元数据: {len(metadata)} 项")
                return metadata
        except Exception as e:
            log.warning(f"加载缓存元数据失败: {e}")
        
        return {}
    
    def _save_metadata(self):
        """保存缓存元数据"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error(f"保存缓存元数据失败: {e}")
    
    def _generate_cache_key(self, manga_path: str, page_index: int, target_language: str = "zh") -> str:
        """
        生成缓存键
        
        Args:
            manga_path: 漫画路径
            page_index: 页面索引
            target_language: 目标语言
            
        Returns:
            缓存键
        """
        # 使用漫画路径、页面索引和语言生成唯一键
        key_string = f"{manga_path}:{page_index}:{target_language}"
        cache_key = hashlib.md5(key_string.encode('utf-8')).hexdigest()
        return cache_key
    
    def _get_cache_file_path(self, cache_key: str) -> Path:
        """
        获取缓存文件路径
        
        Args:
            cache_key: 缓存键
            
        Returns:
            缓存文件路径
        """
        # 使用前两个字符作为子目录，避免单个目录文件过多
        subdir = cache_key[:2]
        cache_dir = self.cache_root / subdir
        cache_dir.mkdir(exist_ok=True)
        
        return cache_dir / f"{cache_key}.webp"
    
    def has_cached_translation(self, manga_path: str, page_index: int, target_language: str = "zh") -> bool:
        """
        检查是否存在缓存的翻译
        
        Args:
            manga_path: 漫画路径
            page_index: 页面索引
            target_language: 目标语言
            
        Returns:
            是否存在缓存
        """
        cache_key = self._generate_cache_key(manga_path, page_index, target_language)
        cache_file = self._get_cache_file_path(cache_key)
        
        # 检查文件是否存在且有效
        if cache_file.exists() and cache_file.stat().st_size > 0:
            # 检查元数据中的记录
            if cache_key in self.metadata:
                return True
            else:
                # 文件存在但元数据缺失，重建元数据
                self._rebuild_metadata_for_file(cache_key, cache_file, manga_path, page_index, target_language)
                return True
        
        return False
    
    def get_cached_translation(self, manga_path: str, page_index: int, target_language: str = "zh") -> Optional[bytes]:
        """
        获取缓存的翻译图像
        
        Args:
            manga_path: 漫画路径
            page_index: 页面索引
            target_language: 目标语言
            
        Returns:
            图像数据（WebP格式）或None
        """
        cache_key = self._generate_cache_key(manga_path, page_index, target_language)
        cache_file = self._get_cache_file_path(cache_key)
        
        try:
            if cache_file.exists():
                # 更新访问时间
                self._update_access_time(cache_key)
                
                # 读取文件
                with open(cache_file, 'rb') as f:
                    image_data = f.read()
                
                log.debug(f"持久化WebP缓存命中: {manga_path}:{page_index} (文件: {cache_file.name})")
                return image_data
        except Exception as e:
            log.error(f"读取缓存文件失败: {cache_file}, 错误: {e}")
        
        return None
    
    def save_translated_image(self, manga_path: str, page_index: int, image_array: np.ndarray, 
                            target_language: str = "zh") -> bool:
        """
        保存翻译后的图像
        
        Args:
            manga_path: 漫画路径
            page_index: 页面索引
            image_array: 图像数组
            target_language: 目标语言
            
        Returns:
            是否保存成功
        """
        cache_key = self._generate_cache_key(manga_path, page_index, target_language)
        cache_file = self._get_cache_file_path(cache_key)
        
        try:
            # 转换为PIL图像
            if image_array.dtype != np.uint8:
                image_array = (image_array * 255).astype(np.uint8)
            
            # 确保是RGB格式
            if len(image_array.shape) == 3 and image_array.shape[2] == 3:
                image = Image.fromarray(image_array, 'RGB')
            elif len(image_array.shape) == 3 and image_array.shape[2] == 4:
                image = Image.fromarray(image_array, 'RGBA').convert('RGB')
            else:
                image = Image.fromarray(image_array)
                if image.mode != 'RGB':
                    image = image.convert('RGB')
            
            # 保存为WebP格式
            image.save(cache_file, 'WEBP', quality=self.config['webp_quality'], optimize=True)
            
            # 更新元数据
            self._update_metadata(cache_key, manga_path, page_index, target_language, cache_file)
            
            log.info(f"翻译图像已保存到持久化WebP缓存: {cache_file} (大小: {cache_file.stat().st_size}字节)")
            return True
            
        except Exception as e:
            log.error(f"保存翻译图像失败: {cache_file}, 错误: {e}")
            return False
    
    def _update_metadata(self, cache_key: str, manga_path: str, page_index: int, 
                        target_language: str, cache_file: Path):
        """更新缓存元数据"""
        try:
            file_size = cache_file.stat().st_size
            current_time = datetime.now().isoformat()
            
            self.metadata[cache_key] = {
                'manga_path': manga_path,
                'page_index': page_index,
                'target_language': target_language,
                'file_path': str(cache_file),
                'file_size': file_size,
                'created_at': current_time,
                'last_accessed': current_time,
                'access_count': 1
            }
            
            self._save_metadata()
        except Exception as e:
            log.error(f"更新元数据失败: {e}")
    
    def _update_access_time(self, cache_key: str):
        """更新访问时间"""
        if cache_key in self.metadata:
            self.metadata[cache_key]['last_accessed'] = datetime.now().isoformat()
            self.metadata[cache_key]['access_count'] = self.metadata[cache_key].get('access_count', 0) + 1
    
    def _rebuild_metadata_for_file(self, cache_key: str, cache_file: Path, 
                                  manga_path: str, page_index: int, target_language: str):
        """为现有文件重建元数据"""
        try:
            file_size = cache_file.stat().st_size
            current_time = datetime.now().isoformat()
            
            self.metadata[cache_key] = {
                'manga_path': manga_path,
                'page_index': page_index,
                'target_language': target_language,
                'file_path': str(cache_file),
                'file_size': file_size,
                'created_at': current_time,
                'last_accessed': current_time,
                'access_count': 1
            }
            
            log.info(f"重建缓存元数据: {cache_key}")
        except Exception as e:
            log.error(f"重建元数据失败: {e}")
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_files = len(self.metadata)
        total_size = sum(item.get('file_size', 0) for item in self.metadata.values())
        
        return {
            'total_files': total_files,
            'total_size_mb': total_size / (1024 * 1024),
            'cache_root': str(self.cache_root),
            'webp_quality': self.config['webp_quality']
        }
    
    def cleanup_old_cache(self, max_age_days: int = 30):
        """清理旧缓存文件"""
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        removed_count = 0
        
        for cache_key, metadata in list(self.metadata.items()):
            try:
                last_accessed = datetime.fromisoformat(metadata.get('last_accessed', ''))
                if last_accessed < cutoff_date:
                    cache_file = Path(metadata['file_path'])
                    if cache_file.exists():
                        cache_file.unlink()
                    del self.metadata[cache_key]
                    removed_count += 1
            except Exception as e:
                log.warning(f"清理缓存项失败: {cache_key}, 错误: {e}")
        
        if removed_count > 0:
            self._save_metadata()
            log.info(f"清理了 {removed_count} 个旧缓存文件")
        
        return removed_count


# 全局实例
_persistent_cache = None

def get_persistent_translation_cache() -> PersistentTranslationCache:
    """获取持久化翻译缓存实例"""
    global _persistent_cache
    if _persistent_cache is None:
        _persistent_cache = PersistentTranslationCache()
    return _persistent_cache
