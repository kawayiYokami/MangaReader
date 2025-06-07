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
import tempfile
import hashlib
import json

# 导入core模块
from core.manga_manager import MangaManager
from core.manga_model import MangaInfo, MangaLoader
from core.thumbnail_cache import ThumbnailCache
from core.config import config
from core.cache_factory import get_cache_factory_instance
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
        
    @property
    def manga_manager(self) -> MangaManager:
        """获取MangaManager实例（懒加载）"""
        if self._manga_manager is None:
            try:
                self._manga_manager = MangaManager()

                # 如果漫画列表为空，尝试从缓存加载
                if len(self._manga_manager.manga_list) == 0:
                    manga_dir = config.manga_dir.value
                    if manga_dir:
                        log.info(f"尝试从缓存加载漫画数据: {manga_dir}")
                        try:
                            # 尝试加载缓存
                            cache_key = self._manga_manager.manga_list_cache_manager.generate_key(manga_dir)
                            cached_manga = self._manga_manager.manga_list_cache_manager.get(cache_key)

                            if cached_manga:
                                # 将字典转换为MangaInfo对象
                                manga_objects = []
                                for manga_data in cached_manga:
                                    try:
                                        from core.manga_model import MangaInfo
                                        file_path = manga_data.get("file_path")
                                        if file_path and os.path.exists(file_path):
                                            manga = MangaInfo(file_path)
                                            manga.title = manga_data.get("title", os.path.basename(file_path))
                                            manga.tags = set(manga_data.get("tags", []))
                                            manga.total_pages = manga_data.get("total_pages", 0)
                                            manga.is_valid = manga_data.get("is_valid", False)
                                            manga.last_modified = manga_data.get("last_modified", 0)
                                            manga.pages = manga_data.get("pages", [])

                                            # 恢复页面尺寸分析数据
                                            manga.page_dimensions = manga_data.get("page_dimensions", [])
                                            manga.dimension_variance = manga_data.get("dimension_variance", None)
                                            manga.is_likely_manga = manga_data.get("is_likely_manga", None)

                                            manga_objects.append(manga)
                                    except Exception as e:
                                        log.warning(f"转换缓存数据失败: {manga_data.get('file_path', 'unknown')}, 错误: {e}")

                                self._manga_manager.manga_list = manga_objects
                                # 重新收集标签
                                self._manga_manager.tags.clear()
                                for manga in self._manga_manager.manga_list:
                                    self._manga_manager.tags.update(manga.tags)
                                log.info(f"从缓存加载了 {len(manga_objects)} 个漫画")
                            else:
                                log.info("缓存中没有找到漫画数据")
                        except Exception as e:
                            log.warning(f"从缓存加载漫画数据失败: {e}")

                log.info("MangaManager初始化成功")
            except Exception as e:
                log.error(f"MangaManager初始化失败: {e}")
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
                self._thumbnail_cache = ThumbnailCache()
                log.info("缩略图缓存管理器初始化成功")
            except Exception as e:
                log.error(f"缩略图缓存管理器初始化失败: {e}")
                raise CoreInterfaceError("缩略图缓存管理器初始化失败", e)
        return self._thumbnail_cache
    
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

            # DEBUG: 检查manga_manager返回的数据
            for i, manga_info in enumerate(self.manga_manager.manga_list[:5]):  # 只检查前5个
                log.debug(f"DEBUG 接口层原始 {i}: title={manga_info.title}, dimension_variance={getattr(manga_info, 'dimension_variance', 'N/A')}, 类型={type(getattr(manga_info, 'dimension_variance', None))}")

            for manga_info in self.manga_manager.manga_list:
                web_manga = self._convert_manga_info(manga_info)

                # DEBUG: 检查转换后的数据
                if not manga_info.file_path.endswith('/') and len(web_manga_list) < 5:  # 只检查前5个ZIP文件
                    log.debug(f"DEBUG 接口层转换后: file_path={manga_info.file_path}, dimension_variance={getattr(web_manga, 'dimension_variance', 'N/A')}, 类型={type(getattr(web_manga, 'dimension_variance', None))}")

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

    def get_manga_thumbnail(self, manga_path: str, max_size: int = 300) -> Optional[str]:
        """获取漫画缩略图的base64编码（使用缓存）"""
        try:
            # 获取缩略图文件路径
            thumbnail_path = self.thumbnail_cache.get_thumbnail_path(manga_path, max_size)
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



    def get_manga_page(self, manga_path: str, page_num: int) -> Optional[str]:
        """获取漫画指定页面的base64编码图片"""
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

            return f"data:image/jpeg;base64,{image_base64}"

        except Exception as e:
            log.error(f"获取漫画页面失败 {manga_path}, 页码 {page_num}: {e}")
            return None

    # ==================== 数据转换工具 ====================

    def _convert_manga_info(self, manga_info: MangaInfo) -> WebMangaInfo:
        """将Core的MangaInfo转换为Web的WebMangaInfo"""
        try:
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

            # DEBUG: 检查属性复制
            log.debug(f"DEBUG 转换完成: {manga_info.file_path}, dimension_variance={getattr(web_manga, 'dimension_variance', 'N/A')}")

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
    
    # ==================== 清理和关闭 ====================
    
    def add_manga_from_path(self, path: str) -> WebScanResult:
        """从指定路径添加漫画到缓存"""
        try:
            import os
            from core.manga_model import MangaLoader

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
            from core.manga_model import MangaLoader

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

    def batch_compress_manga(self, webp_quality: int = 85,
                           min_compression_ratio: float = 0.25,
                           preserve_original_names: bool = True) -> Dict[str, Any]:
        """
        批量压缩漫画库中的所有漫画文件

        Args:
            webp_quality: WebP质量 (75-100)
            min_compression_ratio: 最小压缩比例 (0.25 = 25%)
            preserve_original_names: 是否保留原始文件名

        Returns:
            包含压缩结果的字典
        """
        try:
            from core.image_compressor import ImageCompressor
            import tempfile
            import shutil
            from datetime import datetime

            compressor = ImageCompressor()

            # 获取所有漫画文件
            all_manga = self.get_manga_list()

            # 过滤出需要压缩的文件（跳过.webp文件）
            files_to_compress = []
            skipped_files = []

            for manga in all_manga:
                file_path = manga.file_path
                file_ext = os.path.splitext(file_path)[1].lower()

                # 跳过已经是webp格式的文件
                if file_ext == '.webp':
                    skipped_files.append({
                        "file_path": file_path,
                        "reason": "已是WebP格式，跳过处理"
                    })
                    continue

                # 只处理常见的漫画压缩包格式
                if file_ext in ['.zip', '.rar', '.7z', '.cbz', '.cbr']:
                    files_to_compress.append(file_path)
                else:
                    skipped_files.append({
                        "file_path": file_path,
                        "reason": f"不支持的格式: {file_ext}"
                    })

            log.info(f"开始批量压缩 {len(files_to_compress)} 个文件，跳过 {len(skipped_files)} 个文件")

            successful_compressions = 0
            failed_files = []
            total_size_saved = 0

            for i, file_path in enumerate(files_to_compress):
                try:
                    log.info(f"压缩文件 {i+1}/{len(files_to_compress)}: {file_path}")

                    # 获取原始文件大小
                    original_size = os.path.getsize(file_path)

                    # 执行单个文件压缩
                    result = compressor.compress_manga_file(
                        file_path=file_path,
                        webp_quality=webp_quality,
                        preserve_original_names=preserve_original_names
                    )

                    if result["success"]:
                        compressed_size = os.path.getsize(result["temp_file"])
                        compression_ratio = (original_size - compressed_size) / original_size

                        if compression_ratio >= min_compression_ratio:
                            # 验证压缩文件的完整性
                            if self._verify_compressed_file(file_path, result["temp_file"]):
                                # 备份原文件
                                backup_path = file_path + ".backup"
                                shutil.copy2(file_path, backup_path)

                                try:
                                    # 替换原文件
                                    shutil.move(result["temp_file"], file_path)

                                    # 删除备份文件
                                    os.remove(backup_path)

                                    successful_compressions += 1
                                    size_saved = original_size - compressed_size
                                    total_size_saved += size_saved

                                    log.info(f"成功压缩并替换文件: {file_path}, 节省空间: {size_saved} 字节")

                                except Exception as e:
                                    # 如果替换失败，恢复备份
                                    if os.path.exists(backup_path):
                                        shutil.move(backup_path, file_path)
                                    failed_files.append({
                                        "file_path": file_path,
                                        "reason": f"文件替换失败: {str(e)}"
                                    })
                            else:
                                failed_files.append({
                                    "file_path": file_path,
                                    "reason": "压缩文件验证失败"
                                })
                        else:
                            # 压缩效果不佳，删除临时文件
                            if os.path.exists(result["temp_file"]):
                                os.remove(result["temp_file"])
                            skipped_files.append({
                                "file_path": file_path,
                                "reason": f"压缩效果不佳，仅减少 {compression_ratio:.1%}"
                            })
                    else:
                        failed_files.append({
                            "file_path": file_path,
                            "reason": result.get("message", "压缩失败")
                        })

                except Exception as e:
                    log.error(f"压缩文件失败 {file_path}: {e}")
                    failed_files.append({
                        "file_path": file_path,
                        "reason": str(e)
                    })

            return {
                "success": True,
                "total_files": len(files_to_compress),
                "successful_compressions": successful_compressions,
                "skipped_files": len(skipped_files),
                "failed_files": failed_files,
                "total_size_saved": total_size_saved,
                "skipped_details": skipped_files
            }

        except Exception as e:
            log.error(f"批量压缩失败: {e}")
            raise CoreInterfaceError("批量压缩失败", e)

    def _verify_compressed_file(self, original_path: str, compressed_path: str) -> bool:
        """
        验证压缩文件的完整性

        Args:
            original_path: 原始文件路径
            compressed_path: 压缩后文件路径

        Returns:
            验证是否通过
        """
        try:
            import zipfile
            import random
            from PIL import Image
            import io

            # 1. 检查文件数量是否一致
            original_files = []
            compressed_files = []

            # 读取原始文件内容
            with zipfile.ZipFile(original_path, 'r') as original_zip:
                original_files = [f for f in original_zip.namelist() if not f.endswith('/')]

            # 读取压缩文件内容
            with zipfile.ZipFile(compressed_path, 'r') as compressed_zip:
                compressed_files = [f for f in compressed_zip.namelist() if not f.endswith('/')]

            # 检查文件数量
            if len(original_files) != len(compressed_files):
                log.error(f"文件数量不一致: 原始 {len(original_files)}, 压缩后 {len(compressed_files)}")
                return False

            # 2. 随机选择3个图片文件进行质量对比
            image_files = [f for f in original_files if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif'))]

            if len(image_files) >= 3:
                # 随机选择3个文件
                sample_files = random.sample(image_files, min(3, len(image_files)))

                with zipfile.ZipFile(original_path, 'r') as original_zip, \
                     zipfile.ZipFile(compressed_path, 'r') as compressed_zip:

                    for file_name in sample_files:
                        try:
                            # 读取原始图片
                            original_data = original_zip.read(file_name)
                            original_img = Image.open(io.BytesIO(original_data))

                            # 查找对应的压缩图片（只比较文件名部分，不包括扩展名）
                            original_stem = os.path.splitext(file_name)[0]
                            compressed_file_name = None

                            # 在压缩文件中查找对应的文件
                            for compressed_file in compressed_files:
                                compressed_stem = os.path.splitext(compressed_file)[0]
                                if compressed_stem == original_stem:
                                    compressed_file_name = compressed_file
                                    break

                            if not compressed_file_name:
                                log.error(f"在压缩文件中找不到对应的文件: {file_name}")
                                return False

                            # 读取压缩图片
                            compressed_data = compressed_zip.read(compressed_file_name)
                            compressed_img = Image.open(io.BytesIO(compressed_data))

                            # 检查尺寸是否一致
                            if original_img.size != compressed_img.size:
                                log.error(f"图片尺寸不一致: {file_name}")
                                return False

                            # 检查图片是否能正常打开（基本完整性检查）
                            compressed_img.verify()

                        except Exception as e:
                            log.error(f"验证图片失败 {file_name}: {e}")
                            return False

            log.info("压缩文件验证通过")
            return True

        except Exception as e:
            log.error(f"文件验证失败: {e}")
            return False

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
