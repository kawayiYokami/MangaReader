"""
缩略图缓存管理模块
使用临时文件夹存储缩略图，支持HTTP缓存
"""

import os
import hashlib
import tempfile
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any
from PIL import Image
import logging

log = logging.getLogger(__name__)


class ThumbnailCache:
    """缩略图缓存管理器 - 使用临时文件夹存储"""
    
    def __init__(self):
        # 使用系统临时目录下的专用文件夹
        self.cache_dir = Path(tempfile.gettempdir()) / "manga_reader_thumbnails"
        self.cache_dir.mkdir(exist_ok=True)
        
        # 元数据文件
        self.metadata_file = self.cache_dir / "metadata.json"
        self.metadata = self._load_metadata()
        
        # 清理过期缓存
        self._cleanup_expired_cache()
        
        log.info(f"缩略图缓存初始化完成: {self.cache_dir}")
    
    def _load_metadata(self) -> Dict[str, Any]:
        """加载缓存元数据"""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
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
    
    def _get_cache_key(self, manga_path: str, size: int) -> str:
        """生成缓存键"""
        # 使用文件路径和大小生成唯一键
        content = f"{manga_path}_{size}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _get_cache_file_path(self, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{cache_key}.webp"
    
    def _cleanup_expired_cache(self, max_age_days: int = 7):
        """清理过期缓存"""
        try:
            current_time = time.time()
            max_age_seconds = max_age_days * 24 * 60 * 60
            
            # 清理过期的缓存文件
            for cache_file in self.cache_dir.glob("*.webp"):
                try:
                    file_age = current_time - cache_file.stat().st_mtime
                    if file_age > max_age_seconds:
                        cache_file.unlink()
                        log.debug(f"删除过期缓存: {cache_file.name}")
                except OSError:
                    continue
            
            # 清理无效的元数据条目
            valid_keys = set()
            for cache_file in self.cache_dir.glob("*.webp"):
                cache_key = cache_file.stem
                valid_keys.add(cache_key)
            
            # 移除无效的元数据条目
            invalid_keys = set(self.metadata.keys()) - valid_keys
            for key in invalid_keys:
                del self.metadata[key]
            
            if invalid_keys:
                self._save_metadata()
                log.info(f"清理了 {len(invalid_keys)} 个无效的元数据条目")
                
        except Exception as e:
            log.error(f"清理过期缓存失败: {e}")
    
    def get_thumbnail_path(self, manga_path: str, size: int = 300) -> Optional[str]:
        """获取缩略图文件路径，如果不存在则生成"""
        try:
            # 检查源文件是否存在
            if not os.path.exists(manga_path):
                return None
            
            cache_key = self._get_cache_key(manga_path, size)
            cache_file_path = self._get_cache_file_path(cache_key)
            
            # 获取源文件修改时间
            source_mtime = os.path.getmtime(manga_path)
            
            # 检查缓存是否有效
            if cache_file_path.exists() and cache_key in self.metadata:
                cached_mtime = self.metadata[cache_key].get('source_mtime', 0)
                cached_size = self.metadata[cache_key].get('size', 0)
                
                if cached_mtime == source_mtime and cached_size == size:
                    # 更新访问时间
                    self.metadata[cache_key]['last_accessed'] = time.time()
                    self._save_metadata()
                    return str(cache_file_path)
            
            # 缓存无效或不存在，生成新的缩略图
            return self._generate_thumbnail(manga_path, cache_key, size, source_mtime)
            
        except Exception as e:
            log.error(f"获取缩略图路径失败 {manga_path}: {e}")
            return None
    
    def _generate_thumbnail(self, manga_path: str, cache_key: str, size: int, source_mtime: float) -> Optional[str]:
        """生成缩略图文件"""
        try:
            # 获取第一页图片
            first_page_image = self._get_first_page_image(manga_path)
            if first_page_image is None:
                return None
            
            # 创建缩略图
            thumbnail = self._create_thumbnail(first_page_image, size)
            if thumbnail is None:
                return None
            
            # 保存缓存文件
            cache_file_path = self._get_cache_file_path(cache_key)
            thumbnail.save(cache_file_path, format='WEBP', quality=85, method=6)
            
            # 更新元数据
            current_time = time.time()
            self.metadata[cache_key] = {
                'source_path': manga_path,
                'source_mtime': source_mtime,
                'size': size,
                'created': current_time,
                'last_accessed': current_time,
                'file_size': cache_file_path.stat().st_size
            }
            self._save_metadata()
            
            log.debug(f"生成缩略图: {manga_path} -> {cache_file_path.name}")
            return str(cache_file_path)
            
        except Exception as e:
            log.error(f"生成缩略图失败 {manga_path}: {e}")
            return None
    
    def _get_first_page_image(self, manga_path: str):
        """获取漫画第一页图片，不触发整本漫画缓存"""
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
            # 支持的图片格式
            image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}
            
            # 获取所有图片文件并排序
            image_files = []
            for file_path in Path(folder_path).iterdir():
                if file_path.suffix.lower() in image_extensions:
                    image_files.append(file_path)
            
            if not image_files:
                return None
            
            # 按文件名排序
            image_files.sort(key=lambda x: x.name.lower())
            
            # 打开第一张图片
            return Image.open(image_files[0])
            
        except Exception as e:
            log.error(f"从文件夹获取第一页失败 {folder_path}: {e}")
            return None
    
    def _get_first_page_from_archive(self, archive_path: str):
        """从压缩文件获取第一页图片 - 只支持ZIP格式，与核心代码保持一致"""
        try:
            import zipfile
            from io import BytesIO

            # 支持的图片格式
            image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}

            # 根据文件扩展名选择解压方式
            file_ext = Path(archive_path).suffix.lower()

            if file_ext in ['.zip', '.cbz']:
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    # 获取所有图片文件并排序
                    image_files = [name for name in zf.namelist()
                                 if Path(name).suffix.lower() in image_extensions]
                    if not image_files:
                        return None

                    image_files.sort()

                    # 读取第一张图片
                    with zf.open(image_files[0]) as img_file:
                        return Image.open(BytesIO(img_file.read()))

            else:
                log.warning(f"不支持的压缩格式: {file_ext}，只支持ZIP格式")
                return None

        except Exception as e:
            log.error(f"从压缩文件获取第一页失败 {archive_path}: {e}")
            return None
    
    def _create_thumbnail(self, image: Image.Image, size: int) -> Optional[Image.Image]:
        """创建缩略图"""
        try:
            # 转换为RGB模式（如果需要）
            if image.mode in ('RGBA', 'LA', 'P'):
                # 创建白色背景
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 创建缩略图，保持宽高比
            image.thumbnail((size, size), Image.Resampling.LANCZOS)
            
            return image
            
        except Exception as e:
            log.error(f"创建缩略图失败: {e}")
            return None
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            total_size = 0
            file_count = 0
            
            for cache_file in self.cache_dir.glob("*.webp"):
                try:
                    total_size += cache_file.stat().st_size
                    file_count += 1
                except OSError:
                    continue
            
            return {
                'cache_dir': str(self.cache_dir),
                'total_files': file_count,
                'total_size_mb': total_size / 1024 / 1024,
                'metadata_entries': len(self.metadata)
            }
        except Exception as e:
            log.error(f"获取缓存统计失败: {e}")
            return {}
    
    def clear_cache(self):
        """清空所有缓存"""
        try:
            # 删除所有缓存文件
            for cache_file in self.cache_dir.glob("*.webp"):
                try:
                    cache_file.unlink()
                except OSError:
                    continue
            
            # 清空元数据
            self.metadata.clear()
            self._save_metadata()
            
            log.info("缓存已清空")
        except Exception as e:
            log.error(f"清空缓存失败: {e}")
