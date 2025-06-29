"""
Web UI 与 Core 模块的统一接口层

这个接口层负责：
1. 封装所有与core模块的交互
2. 统一数据格式转换
3. 统一错误处理
4. 为Web UI提供简洁的API

设计原则：
- Web UI只通过这个接口与core交互
- Core模块的任何变化只需要在这里适配
- 提供类型安全的接口定义
"""

from typing import List, Optional, Dict, Any, Union, Tuple
from pathlib import Path
import os
import time
from datetime import datetime
from dataclasses import dataclass, asdict
import traceback
import shutil
import tempfile
import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# 导入core模块
from core.manga.manga_manager import MangaManager
from core.manga.manga_model import MangaInfo, MangaLoader
from core.core_cache.thumbnail_cache import ThumbnailCache
from core.config import config
from core.core_cache.cache_factory import get_cache_factory_instance
from core.image.image_compressor import get_image_compressor, ImageCompressor
from core.manga.batch_compression_manager import get_batch_compression_manager, BatchCompressionManager
from utils import manga_logger as log


# 数据模型定义
@dataclass
class WebMangaInfo:
    """Web UI使用的漫画信息模型"""
    file_path: str
    title: str
    tags: List[str]
    total_pages: int
    is_valid: bool
    last_modified: str
    file_type: str  # 'folder' | 'zip' | 'unknown'
    file_size: Optional[int] = None


@dataclass
class WebDirectoryInfo:
    """Web UI使用的目录信息模型"""
    path: str
    exists: bool
    is_directory: bool
    manga_count: int
    last_scan_time: Optional[str] = None


@dataclass
class WebScanResult:
    """Web UI使用的扫描结果模型"""
    success: bool
    message: str
    manga_count: int
    tags_count: int
    scan_time: str
    errors: List[str] = None


class CoreInterfaceError(Exception):
    """接口层专用异常"""
    def __init__(self, message: str, original_error: Exception = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)








class CoreInterface:
    """Web UI与Core模块的统一接口"""

    def __init__(self):
        self._manga_manager: Optional[MangaManager] = None
        self._manga_loader: Optional[MangaLoader] = None
        self._thumbnail_cache: Optional[ThumbnailCache] = None
        self._batch_compression_manager: Optional[BatchCompressionManager] = None

        # 转换结果缓存机制
        self._conversion_cache: Dict[str, WebMangaInfo] = {}
        self._conversion_cache_timestamps: Dict[str, float] = {}
        self._cache_expire_time = 300  # 5分钟缓存过期时间
        
    @property
    def manga_manager(self) -> MangaManager:
        """获取MangaManager实例（懒加载）"""
        if self._manga_manager is None:
            try:
                self._manga_manager = MangaManager()
                log.info("MangaManager初始化成功")
            except Exception as e:
                log.error(f"MangaManager初始化失败: {e}", exc_info=True)
                raise CoreInterfaceError("漫画管理器初始化失败", e)
        return self._manga_manager
    
    @property
    def manga_loader(self) -> MangaLoader:
        """获取MangaLoader实例（懒加载）"""
        if self._manga_loader is None:
            try:
                self._manga_loader = MangaLoader()
                log.info("MangaLoader初始化成功")
            except Exception as e:
                log.error(f"MangaLoader初始化失败: {e}")
                raise CoreInterfaceError("漫画加载器初始化失败", e)
        return self._manga_loader

    @property
    def thumbnail_cache(self) -> ThumbnailCache:
        """获取缩略图缓存管理器实例（懒加载）"""
        if self._thumbnail_cache is None:
            try:
                self._thumbnail_cache = ThumbnailCache(
                    cache_dir=config.thumbnail_cache_dir.value,
                    output_size=(
                        config.thumbnail_output_width.value,
                        config.thumbnail_output_height.value
                    ),
                    quality=config.thumbnail_quality.value,
                    max_cache_size_mb=config.thumbnail_max_size_mb.value
                )
                log.info("缩略图缓存管理器初始化成功")
            except Exception as e:
                log.error(f"缩略图缓存管理器初始化失败: {e}")
                raise CoreInterfaceError("缩略图缓存管理器初始化失败", e)
        return self._thumbnail_cache

    @property
    def batch_compression_manager(self) -> BatchCompressionManager:
        """获取BatchCompressionManager实例（懒加载）"""
        if self._batch_compression_manager is None:
            self._batch_compression_manager = get_batch_compression_manager()
            log.info("BatchCompressionManager初始化成功")
        return self._batch_compression_manager
    
    # ==================== 目录管理 ====================
    
    def get_current_directory(self) -> WebDirectoryInfo:
        """获取当前漫画目录信息"""
        try:
            current_dir = config.manga_dir.value or ""
            manga_count = len(self.manga_manager.manga_list) if current_dir else 0
            
            return WebDirectoryInfo(
                path=current_dir,
                exists=os.path.exists(current_dir) if current_dir else False,
                is_directory=os.path.isdir(current_dir) if current_dir else False,
                manga_count=manga_count
            )
        except Exception as e:
            log.error(f"获取当前目录失败: {e}")
            raise CoreInterfaceError("获取当前目录失败", e)
    
    def set_directory(self, directory_path: str, force_rescan: bool = True) -> WebScanResult:
        """设置漫画目录并扫描"""
        try:
            # 验证目录
            if not os.path.exists(directory_path):
                raise CoreInterfaceError("目录不存在")
            
            if not os.path.isdir(directory_path):
                raise CoreInterfaceError("路径不是目录")
            
            # 设置目录
            config.manga_dir.value = directory_path
            self.manga_manager.save_config()
            log.info(f"设置漫画目录: {directory_path}")
            
            # 扫描文件
            return self.scan_manga_files(force_rescan)
            
        except CoreInterfaceError:
            raise
        except Exception as e:
            log.error(f"设置目录失败: {e}")
            raise CoreInterfaceError("设置目录失败", e)
    
    # ==================== 文件扫描 ====================
    
    def scan_manga_files(self, force_rescan: bool = False) -> WebScanResult:
        """扫描漫画文件"""
        try:
            scan_start = datetime.now()
            errors = []
            
            # 执行扫描
            try:
                self.manga_manager.scan_manga_files(force_rescan=force_rescan)
            except Exception as e:
                errors.append(f"扫描过程中出现错误: {str(e)}")
                log.warning(f"扫描过程中出现错误: {e}")
            
            scan_end = datetime.now()
            manga_count = len(self.manga_manager.manga_list)
            tags_count = len(self.manga_manager.tags)
            
            log.info(f"扫描完成: 找到{manga_count}个漫画, {tags_count}个标签")
            
            return WebScanResult(
                success=True,
                message=f"扫描完成，找到 {manga_count} 个漫画",
                manga_count=manga_count,
                tags_count=tags_count,
                scan_time=scan_end.isoformat(),
                errors=errors if errors else None
            )
            
        except Exception as e:
            log.error(f"扫描文件失败: {e}")
            return WebScanResult(
                success=False,
                message=f"扫描失败: {str(e)}",
                manga_count=0,
                tags_count=0,
                scan_time=datetime.now().isoformat(),
                errors=[str(e)]
            )
    
    # ==================== 漫画列表管理 ====================
    
    def get_manga_list(self) -> List[WebMangaInfo]:
        """获取漫画列表"""
        try:
            web_manga_list = []

            # # DEBUG: 检查manga_manager返回的数据 (Startup performance optimization)
            # for i, manga_info in enumerate(self.manga_manager.manga_list[:5]):  # 只检查前5个
            #     log.debug(f"DEBUG 接口层原始 {i}: title={manga_info.title}, dimension_variance={getattr(manga_info, 'dimension_variance', 'N/A')}, 类型={type(getattr(manga_info, 'dimension_variance', None))}")

            for manga_info in self.manga_manager.manga_list:
                web_manga = self._convert_manga_info(manga_info)
                web_manga_list.append(web_manga)

            # 按最后修改时间排序（最新的在前）
            web_manga_list.sort(key=lambda x: x.last_modified, reverse=True)

            log.debug(f"返回漫画列表: {len(web_manga_list)} 个项目")
            return web_manga_list

        except Exception as e:
            log.error(f"获取漫画列表失败: {e}")
            raise CoreInterfaceError("获取漫画列表失败", e)
    
    def get_all_tags(self) -> List[str]:
        """获取所有标签"""
        try:
            return sorted(list(self.manga_manager.tags))
        except Exception as e:
            log.error(f"获取标签失败: {e}")
            raise CoreInterfaceError("获取标签失败", e)
    
    def filter_manga_by_tags(self, tags: List[str]) -> List[WebMangaInfo]:
        """根据标签过滤漫画"""
        try:
            filtered_manga = self.manga_manager.filter_manga_by_tags(tags)
            
            web_manga_list = []
            for manga_info in filtered_manga:
                web_manga = self._convert_manga_info(manga_info)
                web_manga_list.append(web_manga)
            
            # 按最后修改时间排序
            web_manga_list.sort(key=lambda x: x.last_modified, reverse=True)
            
            log.debug(f"标签过滤结果: {len(web_manga_list)} 个项目")
            return web_manga_list
            
        except Exception as e:
            log.error(f"标签过滤失败: {e}")
            raise CoreInterfaceError("标签过滤失败", e)
    
    # ==================== 漫画图片获取 ====================

    def get_manga_cover(self, manga_path: str) -> Optional[str]:
        """获取漫画封面（第一页）的base64编码"""
        try:
            # 加载漫画
            manga_data = self.manga_loader.load_manga(manga_path)
            if not manga_data or not manga_data.pages or manga_data.total_pages == 0:
                return None

            # 获取第一页图片数据
            first_page_image = self.manga_loader.get_page_image(manga_data, 0)
            if first_page_image is None:
                return None

            # 使用PIL转换numpy数组为图片
            from PIL import Image
            import io
            import base64

            # 将numpy数组转换为PIL图片
            if first_page_image.dtype != 'uint8':
                first_page_image = (first_page_image * 255).astype('uint8')

            # 创建PIL图片（注意：OpenCV使用BGR，PIL使用RGB）
            pil_image = Image.fromarray(first_page_image)

            # 转换为JPEG格式
            output = io.BytesIO()
            if pil_image.mode in ('RGBA', 'LA', 'P'):
                # 转换为RGB模式
                rgb_image = Image.new('RGB', pil_image.size, (255, 255, 255))
                if pil_image.mode == 'P':
                    pil_image = pil_image.convert('RGBA')
                rgb_image.paste(pil_image, mask=pil_image.split()[-1] if pil_image.mode in ('RGBA', 'LA') else None)
                pil_image = rgb_image

            pil_image.save(output, format='JPEG', quality=90)
            image_base64 = base64.b64encode(output.getvalue()).decode('utf-8')

            return f"data:image/jpeg;base64,{image_base64}"

        except Exception as e:
            log.error(f"获取漫画封面失败 {manga_path}: {e}")
            return None

    def get_manga_thumbnail(self, manga_path: str) -> Optional[str]:
        """获取漫画缩略图的base64编码（使用缓存）"""
        try:
            # 获取缩略图文件路径
            thumbnail_path = self.thumbnail_cache.get_thumbnail_path(manga_path)
            if not thumbnail_path:
                return None

            # 读取缩略图文件并转换为base64
            import base64
            with open(thumbnail_path, 'rb') as f:
                image_data = f.read()

            image_base64 = base64.b64encode(image_data).decode('utf-8')
            return f"data:image/webp;base64,{image_base64}"

        except Exception as e:
            log.error(f"获取漫画缩略图失败 {manga_path}: {e}")
            return None



    def get_manga_page(self, manga_path: str, page_num: int) -> Optional[Tuple[str, int, int]]:
        """获取漫画指定页面的base64编码图片及其尺寸"""
        try:
            # 加载漫画
            manga_data = self.manga_loader.load_manga(manga_path)
            if not manga_data or not manga_data.pages or manga_data.total_pages == 0:
                log.warning(f"无法加载漫画或漫画为空: {manga_path}")
                return None

            # 检查页码范围
            if page_num < 0 or page_num >= manga_data.total_pages:
                log.warning(f"页码超出范围: {page_num}, 总页数: {manga_data.total_pages}")
                return None

            # 获取指定页面图片数据
            page_image = self.manga_loader.get_page_image(manga_data, page_num)
            if page_image is None:
                log.warning(f"无法获取页面图片: {manga_path}, 页码: {page_num}")
                return None

            # 使用PIL转换numpy数组为图片
            from PIL import Image
            import io
            import base64

            # 将numpy数组转换为PIL图片
            if page_image.dtype != 'uint8':
                page_image = (page_image * 255).astype('uint8')

            # 创建PIL图片（注意：core返回的是RGB格式）
            pil_image = Image.fromarray(page_image)
            width, height = pil_image.size

            # 转换为JPEG格式
            output = io.BytesIO()
            if pil_image.mode in ('RGBA', 'LA', 'P'):
                # 转换为RGB模式
                rgb_image = Image.new('RGB', pil_image.size, (255, 255, 255))
                if pil_image.mode == 'P':
                    pil_image = pil_image.convert('RGBA')
                rgb_image.paste(pil_image, mask=pil_image.split()[-1] if pil_image.mode in ('RGBA', 'LA') else None)
                pil_image = rgb_image

            pil_image.save(output, format='JPEG', quality=95)
            image_base64 = base64.b64encode(output.getvalue()).decode('utf-8')

            return f"data:image/jpeg;base64,{image_base64}", width, height

        except Exception as e:
            log.error(f"获取漫画页面失败 {manga_path}, 页码 {page_num}: {e}")
            return None

    # ==================== 数据转换工具 ====================

    def _convert_manga_info(self, manga_info: MangaInfo) -> WebMangaInfo:
        """将Core的MangaInfo转换为Web的WebMangaInfo（带缓存优化）"""
        try:
            # 生成缓存键（基于文件路径和最后修改时间）
            cache_key = f"{manga_info.file_path}:{manga_info.last_modified}"
            current_time = time.time()

            # 检查缓存是否存在且未过期
            if (cache_key in self._conversion_cache and
                cache_key in self._conversion_cache_timestamps and
                current_time - self._conversion_cache_timestamps[cache_key] < self._cache_expire_time):

                # 缓存命中，直接返回
                return self._conversion_cache[cache_key]

            # 缓存未命中或已过期，执行转换
            # 处理last_modified字段
            last_modified_str = ""
            if manga_info.last_modified:
                if hasattr(manga_info.last_modified, 'isoformat'):
                    last_modified_str = manga_info.last_modified.isoformat()
                else:
                    last_modified_str = str(manga_info.last_modified)

            # 确定文件类型
            file_type = "unknown"
            file_size = None

            if os.path.isdir(manga_info.file_path):
                file_type = "folder"
            elif manga_info.file_path.lower().endswith(('.zip', '.cbz', '.cbr')):
                file_type = "zip"
                try:
                    file_size = os.path.getsize(manga_info.file_path)
                except:
                    pass

            # 处理标签，保留原始格式（包含前缀）
            clean_tags = list(manga_info.tags)

            web_manga = WebMangaInfo(
                file_path=manga_info.file_path,
                title=manga_info.title,
                tags=clean_tags,
                total_pages=manga_info.total_pages,
                is_valid=manga_info.is_valid,
                last_modified=last_modified_str,
                file_type=file_type,
                file_size=file_size
            )

            # 添加缓存相关属性（尺寸分析数据）
            if hasattr(manga_info, 'dimension_variance'):
                web_manga.dimension_variance = manga_info.dimension_variance
            if hasattr(manga_info, 'is_likely_manga'):
                web_manga.is_likely_manga = manga_info.is_likely_manga
            if hasattr(manga_info, 'page_dimensions'):
                web_manga.page_dimensions = manga_info.page_dimensions

            # 保存到缓存
            self._conversion_cache[cache_key] = web_manga
            self._conversion_cache_timestamps[cache_key] = current_time

            # 清理过期缓存（每100次转换清理一次）
            if len(self._conversion_cache) % 100 == 0:
                self._cleanup_expired_cache()

            # 只在首次转换时输出DEBUG日志
            if cache_key not in self._conversion_cache_timestamps or current_time - self._conversion_cache_timestamps.get(cache_key, 0) > self._cache_expire_time:
                log.debug(f"转换完成（新转换）: {manga_info.file_path}, dimension_variance={getattr(web_manga, 'dimension_variance', 'N/A')}")

            return web_manga

        except Exception as e:
            log.error(f"转换漫画信息失败: {e}")
            # 返回一个基本的错误信息
            return WebMangaInfo(
                file_path=getattr(manga_info, 'file_path', ''),
                title=getattr(manga_info, 'title', '转换失败'),
                tags=[],
                total_pages=0,
                is_valid=False,
                last_modified="",
                file_type="unknown"
            )
    
    # ==================== 缓存管理 ====================

    def _cleanup_expired_cache(self):
        """清理过期的转换缓存"""
        try:
            current_time = time.time()
            expired_keys = []

            for cache_key, timestamp in self._conversion_cache_timestamps.items():
                if current_time - timestamp > self._cache_expire_time:
                    expired_keys.append(cache_key)

            for key in expired_keys:
                self._conversion_cache.pop(key, None)
                self._conversion_cache_timestamps.pop(key, None)

            if expired_keys:
                log.debug(f"清理了 {len(expired_keys)} 个过期的转换缓存项")

        except Exception as e:
            log.warning(f"清理转换缓存失败: {e}")

    def clear_conversion_cache(self):
        """手动清空转换缓存"""
        self._conversion_cache.clear()
        self._conversion_cache_timestamps.clear()
        log.info("转换缓存已清空")

    # ==================== 清理和关闭 ====================
    
    def add_manga_from_path(self, path: str) -> WebScanResult:
        """从指定路径添加漫画到缓存"""
        try:
            import os
            from core.manga.manga_model import MangaLoader

            if not os.path.exists(path):
                return WebScanResult(
                    success=False,
                    message=f"路径不存在: {path}",
                    manga_count=0,
                    tags_count=0,
                    scan_time="0s",
                    errors=[f"路径不存在: {path}"]
                )

            start_time = time.time()

            # 使用MangaLoader加载漫画
            manga = MangaLoader.load_manga(path)

            if manga and manga.is_valid:
                # 将漫画添加到管理器的列表中
                existing_paths = {m.file_path for m in self.manga_manager.manga_list}

                if manga.file_path not in existing_paths:
                    self.manga_manager.manga_list.append(manga)

                    # 更新缓存
                    cache_key = self.manga_manager.manga_list_cache_manager.generate_key("all_manga")
                    self.manga_manager.manga_list_cache_manager.set(cache_key, self.manga_manager.manga_list)

                    scan_time = f"{time.time() - start_time:.2f}s"

                    return WebScanResult(
                        success=True,
                        message=f"成功添加漫画: {manga.title}",
                        manga_count=1,
                        tags_count=len(manga.tags),
                        scan_time=scan_time,
                        errors=[]
                    )
                else:
                    return WebScanResult(
                        success=False,
                        message=f"漫画已存在: {manga.title}",
                        manga_count=0,
                        tags_count=0,
                        scan_time="0s",
                        errors=[f"漫画已存在: {path}"]
                    )
            else:
                return WebScanResult(
                    success=False,
                    message=f"无法加载漫画: {path}",
                    manga_count=0,
                    tags_count=0,
                    scan_time="0s",
                    errors=[f"无法加载漫画: {path}"]
                )

        except Exception as e:
            log.error(f"添加漫画失败 {path}: {e}")
            return WebScanResult(
                success=False,
                message=f"添加漫画失败: {str(e)}",
                manga_count=0,
                tags_count=0,
                scan_time="0s",
                errors=[str(e)]
            )

    def scan_directory_for_manga(self, directory_path: str) -> WebScanResult:
        """扫描指定目录中的所有漫画文件"""
        try:
            import os
            from core.manga.manga_model import MangaLoader

            if not os.path.exists(directory_path):
                return WebScanResult(
                    success=False,
                    message=f"目录不存在: {directory_path}",
                    manga_count=0,
                    tags_count=0,
                    scan_time="0s",
                    errors=[f"目录不存在: {directory_path}"]
                )

            if not os.path.isdir(directory_path):
                return WebScanResult(
                    success=False,
                    message=f"路径不是目录: {directory_path}",
                    manga_count=0,
                    tags_count=0,
                    scan_time="0s",
                    errors=[f"路径不是目录: {directory_path}"]
                )

            start_time = time.time()
            added_count = 0
            errors = []

            # 使用核心的find_manga_files方法递归扫描目录
            manga_files = MangaLoader.find_manga_files(directory_path)
            log.info(f"在目录 {directory_path} 中找到 {len(manga_files)} 个漫画文件")

            existing_paths = {m.file_path for m in self.manga_manager.manga_list}

            for file_path in manga_files:
                try:
                    # 检查是否已存在
                    if file_path in existing_paths:
                        log.info(f"漫画已存在，跳过: {file_path}")
                        continue

                    # 加载漫画
                    manga = MangaLoader.load_manga(file_path)
                    if manga and manga.is_valid:
                        self.manga_manager.manga_list.append(manga)
                        existing_paths.add(file_path)  # 更新已存在路径集合
                        added_count += 1
                        log.info(f"成功添加漫画: {manga.title}")
                    else:
                        error_msg = f"无法加载漫画: {file_path}"
                        errors.append(error_msg)
                        log.warning(error_msg)

                except Exception as e:
                    error_msg = f"处理 {file_path} 失败: {str(e)}"
                    errors.append(error_msg)
                    log.error(error_msg)

            # 更新缓存
            if added_count > 0:
                cache_key = self.manga_manager.manga_list_cache_manager.generate_key("all_manga")
                self.manga_manager.manga_list_cache_manager.set(cache_key, self.manga_manager.manga_list)

            scan_time = f"{time.time() - start_time:.2f}s"

            if added_count > 0:
                message = f"成功扫描目录，添加了 {added_count} 本漫画"
                if errors:
                    message += f"，{len(errors)} 个文件处理失败"
            else:
                message = f"目录扫描完成，未发现新的漫画文件"
                if errors:
                    message += f"，{len(errors)} 个文件处理失败"

            return WebScanResult(
                success=added_count > 0 or len(errors) == 0,
                message=message,
                manga_count=added_count,
                tags_count=0,  # 这里可以统计新增的标签数量
                scan_time=scan_time,
                errors=errors
            )

        except Exception as e:
            log.error(f"扫描目录失败 {directory_path}: {e}")
            return WebScanResult(
                success=False,
                message=f"扫描目录失败: {str(e)}",
                manga_count=0,
                tags_count=0,
                scan_time="0s",
                errors=[str(e)]
            )

    def clear_all_data(self) -> bool:
        """清空所有漫画数据"""
        try:
            self.manga_manager.clear_all_data()
            log.info("所有漫画数据已清空")
            return True
        except Exception as e:
            log.error(f"清空数据失败: {e}")
            raise CoreInterfaceError("清空数据失败", e)

    # ==================== 批量压缩功能 ====================

    def batch_compress_manga(
        self,
        webp_quality: int = 85,
        min_compression_ratio: float = 0.25,
        preserve_original_names: bool = True,
        manga_files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        启动批量压缩任务。
        此方法会立即返回，并在后台线程中执行实际的压缩任务。
        """
        try:
            if self.batch_compression_manager.is_running:
                return {"success": False, "message": "一个批量压缩任务已经在运行中。"}

            files_to_process = manga_files
            if files_to_process is None:
                files_to_process = [m.file_path for m in self.get_manga_list()]
            
            # 在后台线程中运行管理器，以避免阻塞API
            thread = threading.Thread(
                target=self.batch_compression_manager.run_batch_compression,
                args=(files_to_process, webp_quality, min_compression_ratio, preserve_original_names)
            )
            thread.start()
            
            log.info(f"批量压缩任务已在后台启动，将处理 {len(files_to_process)} 个文件。")

            return {
                "success": True,
                "message": "批量压缩任务已成功启动，正在后台运行。"
            }
        except Exception as e:
            log.error(f"启动批量压缩任务失败: {e}", exc_info=True)
            raise CoreInterfaceError("启动批量压缩任务失败", e)

    def cancel_batch_compression(self):
        """请求取消正在进行的批量压缩任务。"""
        log.info("CoreInterface: 正在请求取消批量压缩任务...")
        self.batch_compression_manager.cancel()

    # ==================== 自动过滤功能 ====================

    def auto_filter_manga(self, filter_method: str = "dimension_analysis",
                         threshold: float = 0.15, force_reanalyze: bool = False) -> Dict[str, Any]:
        """
        自动过滤漫画文件，识别哪些是真正的漫画

        Args:
            filter_method: 过滤方法 ("dimension_analysis", "tag_based", "hybrid")
            threshold: 过滤阈值

        Returns:
            过滤结果字典
        """
        try:
            from core.config import config

            log.info(f"开始自动过滤漫画，方法: {filter_method}, 阈值: {threshold}")

            # 如果使用尺寸分析，先确保所有漫画都有尺寸分析数据
            if filter_method in ["dimension_analysis", "hybrid"]:
                log.info("检查尺寸分析数据...")

                # 检查是否需要进行尺寸分析（仅对ZIP文件）
                manga_list = self.manga_manager.manga_list
                zip_manga_list = [m for m in manga_list if not os.path.isdir(m.file_path)]

                if not zip_manga_list:
                    log.info("没有ZIP格式的漫画需要进行尺寸分析")
                elif force_reanalyze:
                    # 强制重新分析所有ZIP漫画
                    log.info(f"强制重新分析所有 {len(zip_manga_list)} 本ZIP漫画的尺寸数据...")
                    analyzed_count = self.manga_manager.analyze_manga_dimensions(force_reanalyze=True)
                    log.info(f"强制尺寸分析完成，重新分析了 {analyzed_count} 本ZIP漫画")
                else:
                    # 只分析缺少数据的ZIP漫画
                    need_analysis = [m for m in zip_manga_list if m.dimension_variance is None]

                    if need_analysis:
                        log.info(f"发现 {len(need_analysis)} 本ZIP漫画缺少尺寸分析数据，开始分析...")
                        # 调用MangaManager的分析方法，它会正确调用MangaLoader._analyze_manga_dimensions
                        analyzed_count = self.manga_manager.analyze_manga_dimensions(force_reanalyze=False)
                        log.info(f"尺寸分析完成，分析了 {analyzed_count} 本ZIP漫画")
                    else:
                        log.info("所有ZIP漫画都已有尺寸分析数据，无需重新分析")

            all_manga = self.get_manga_list()
            filtered_manga = []
            removed_manga = []

            for manga in all_manga:
                is_manga = True
                reason = ""

                if filter_method == "dimension_analysis":
                    # 基于页面尺寸分析（仅对ZIP文件进行过滤）
                    if os.path.isdir(manga.file_path):
                        # 文件夹漫画自动保留，不进行过滤
                        pass
                    elif hasattr(manga, 'dimension_variance') and manga.dimension_variance is not None:
                        if manga.dimension_variance > threshold:
                            is_manga = False
                            reason = f"ZIP文件尺寸方差过大: {manga.dimension_variance:.3f} > {threshold}"
                    elif hasattr(manga, 'is_likely_manga') and manga.is_likely_manga is not None:
                        if not manga.is_likely_manga:
                            is_manga = False
                            reason = "ZIP文件尺寸分析判定为非漫画"

                elif filter_method == "tag_based":
                    # 基于标签过滤
                    required_tags = ["作者:", "标题:"]
                    has_required_tags = any(
                        any(tag.startswith(req) for tag in manga.tags)
                        for req in required_tags
                    )
                    if not has_required_tags:
                        is_manga = False
                        reason = "缺少必要标签（作者或标题）"

                elif filter_method == "hybrid":
                    # 混合方法：同时检查尺寸和标签
                    dimension_ok = True
                    tag_ok = True

                    # 检查尺寸（仅对ZIP文件）
                    if os.path.isdir(manga.file_path):
                        # 文件夹漫画在尺寸检查中自动通过
                        dimension_ok = True
                    elif hasattr(manga, 'dimension_variance') and manga.dimension_variance is not None:
                        if manga.dimension_variance > threshold:
                            dimension_ok = False
                    elif hasattr(manga, 'is_likely_manga') and manga.is_likely_manga is not None:
                        if not manga.is_likely_manga:
                            dimension_ok = False

                    # 检查标签
                    required_tags = ["作者:", "标题:"]
                    has_required_tags = any(
                        any(tag.startswith(req) for tag in manga.tags)
                        for req in required_tags
                    )
                    if not has_required_tags:
                        tag_ok = False

                    if not dimension_ok and not tag_ok:
                        is_manga = False
                        reason = "尺寸分析和标签检查均未通过"
                    elif not dimension_ok:
                        is_manga = False
                        reason = "尺寸分析未通过"
                    elif not tag_ok:
                        is_manga = False
                        reason = "标签检查未通过"

                if is_manga:
                    filtered_manga.append(manga)
                else:
                    removed_manga.append({
                        "file_path": manga.file_path,
                        "title": manga.title,
                        "reason": reason
                    })

            log.info(f"过滤完成: 保留 {len(filtered_manga)} 个，移除 {len(removed_manga)} 个")

            return {
                "success": True,
                "filter_method": filter_method,
                "threshold": threshold,
                "total_files": len(all_manga),
                "filtered_count": len(filtered_manga),
                "removed_count": len(removed_manga),
                "filtered_manga": [self._convert_manga_info(manga) for manga in filtered_manga],
                "removed_manga": removed_manga
            }

        except Exception as e:
            log.error(f"自动过滤失败: {e}")
            raise CoreInterfaceError("自动过滤失败", e)

    def apply_filter_results(self, filter_results: Dict[str, Any]) -> bool:
        """
        应用过滤结果，实际移除被过滤的文件

        Args:
            filter_results: auto_filter_manga 返回的结果

        Returns:
            是否成功应用
        """
        try:
            removed_manga = filter_results.get("removed_manga", [])

            for removed in removed_manga:
                file_path = removed["file_path"]
                # 从漫画管理器中移除
                self.manga_manager.manga_list = [
                    manga for manga in self.manga_manager.manga_list
                    if manga.file_path != file_path
                ]

            # 重新构建标签集合
            self.manga_manager.tags = set()
            for manga in self.manga_manager.manga_list:
                self.manga_manager.tags.update(manga.tags)

            log.info(f"已应用过滤结果，移除了 {len(removed_manga)} 个文件")
            return True

        except Exception as e:
            log.error(f"应用过滤结果失败: {e}")
            raise CoreInterfaceError("应用过滤结果失败", e)

    def close(self):
        """关闭接口，清理资源"""
        try:
            # 清理缓存管理器
            get_cache_factory_instance().close_all_managers()
            log.info("Core接口已关闭")
        except Exception as e:
            log.error(f"关闭Core接口时出错: {e}")


# 全局接口实例
_core_interface: Optional[CoreInterface] = None


def get_core_interface() -> CoreInterface:
    """获取全局Core接口实例"""
    global _core_interface
    if _core_interface is None:
        _core_interface = CoreInterface()
    return _core_interface


# 导出
__all__ = [
    'CoreInterface',
    'WebMangaInfo', 
    'WebDirectoryInfo', 
    'WebScanResult',
    'CoreInterfaceError',
    'get_core_interface'
]
