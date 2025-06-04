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


class ThumbnailCacheManager:
    """缩略图缓存管理器"""

    def __init__(self, cache_dir: Optional[str] = None):
        # 设置缓存目录
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(tempfile.gettempdir()) / "manga_thumbnails"

        # 创建缓存目录
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 元数据文件
        self.metadata_file = self.cache_dir / "metadata.json"
        self.metadata = self._load_metadata()

        log.info(f"缩略图缓存目录: {self.cache_dir}")

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

    def _get_cache_key(self, manga_path: str) -> str:
        """生成缓存键"""
        # 使用文件路径的MD5作为缓存键
        return hashlib.md5(manga_path.encode('utf-8')).hexdigest()

    def _get_cache_path(self, cache_key: str, size: int) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{cache_key}_{size}.webp"

    def get_thumbnail(self, manga_path: str, size: int = 300) -> Optional[str]:
        """获取缩略图，优先从缓存读取"""
        try:
            # 检查文件是否存在
            if not os.path.exists(manga_path):
                return None

            cache_key = self._get_cache_key(manga_path)
            cache_path = self._get_cache_path(cache_key, size)

            # 获取文件修改时间
            file_mtime = os.path.getmtime(manga_path)

            # 检查缓存是否有效
            if cache_path.exists() and cache_key in self.metadata:
                cached_mtime = self.metadata[cache_key].get('mtime', 0)
                cached_size = self.metadata[cache_key].get('size', 0)

                if cached_mtime == file_mtime and cached_size == size:
                    # 缓存有效，直接返回
                    return self._load_thumbnail_from_cache(cache_path)

            # 缓存无效或不存在，生成新的缩略图
            return self._generate_and_cache_thumbnail(manga_path, cache_key, size, file_mtime)

        except Exception as e:
            log.error(f"获取缩略图失败 {manga_path}: {e}")
            return None

    def _load_thumbnail_from_cache(self, cache_path: Path) -> str:
        """从缓存文件加载缩略图"""
        import base64

        with open(cache_path, 'rb') as f:
            image_data = f.read()

        image_base64 = base64.b64encode(image_data).decode('utf-8')
        return f"data:image/webp;base64,{image_base64}"

    def _generate_and_cache_thumbnail(self, manga_path: str, cache_key: str, size: int, file_mtime: float) -> Optional[str]:
        """生成并缓存缩略图"""
        try:
            # 这里需要访问MangaLoader来生成缩略图
            # 我们将在CoreInterface中调用这个方法
            return None
        except Exception as e:
            log.error(f"生成缩略图失败 {manga_path}: {e}")
            return None

    def clear_cache(self):
        """清空所有缓存"""
        try:
            import shutil
            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.metadata = {}
            self._save_metadata()
            log.info("缩略图缓存已清空")
        except Exception as e:
            log.error(f"清空缓存失败: {e}")

    def cleanup_old_cache(self, max_age_days: int = 30):
        """清理过期缓存"""
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_days * 24 * 3600

            removed_count = 0
            for cache_file in self.cache_dir.glob("*.webp"):
                if current_time - cache_file.stat().st_mtime > max_age_seconds:
                    cache_file.unlink()
                    removed_count += 1

            # 清理元数据中的过期条目
            valid_keys = set()
            for cache_file in self.cache_dir.glob("*.webp"):
                cache_key = cache_file.stem.split('_')[0]
                valid_keys.add(cache_key)

            old_metadata = self.metadata.copy()
            self.metadata = {k: v for k, v in old_metadata.items() if k in valid_keys}

            if len(old_metadata) != len(self.metadata):
                self._save_metadata()

            if removed_count > 0:
                log.info(f"清理了 {removed_count} 个过期缓存文件")

        except Exception as e:
            log.error(f"清理缓存失败: {e}")


class CoreInterface:
    """Web UI与Core模块的统一接口"""

    def __init__(self):
        self._manga_manager: Optional[MangaManager] = None
        self._manga_loader: Optional[MangaLoader] = None
        self._thumbnail_cache: Optional[ThumbnailCacheManager] = None
        
    @property
    def manga_manager(self) -> MangaManager:
        """获取MangaManager实例（懒加载）"""
        if self._manga_manager is None:
            try:
                self._manga_manager = MangaManager()
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
    def thumbnail_cache(self) -> ThumbnailCacheManager:
        """获取缩略图缓存管理器实例（懒加载）"""
        if self._thumbnail_cache is None:
            try:
                self._thumbnail_cache = ThumbnailCacheManager()
                # 启动时清理过期缓存
                self._thumbnail_cache.cleanup_old_cache()
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

    def get_manga_thumbnail(self, manga_path: str, max_size: int = 300) -> Optional[str]:
        """获取漫画缩略图的base64编码（使用缓存）"""
        try:
            # 首先尝试从缓存获取
            cached_thumbnail = self.thumbnail_cache.get_thumbnail(manga_path, max_size)
            if cached_thumbnail:
                return cached_thumbnail

            # 缓存未命中，生成新的缩略图
            return self._generate_thumbnail(manga_path, max_size)

        except Exception as e:
            log.error(f"获取漫画缩略图失败 {manga_path}: {e}")
            return None

    def _generate_thumbnail(self, manga_path: str, max_size: int) -> Optional[str]:
        """生成缩略图并保存到缓存"""
        try:
            # 加载漫画
            manga_data = self.manga_loader.load_manga(manga_path)
            if not manga_data or not manga_data.pages or manga_data.total_pages == 0:
                return None

            # 获取第一页图片数据
            first_page_image = self.manga_loader.get_page_image(manga_data, 0)
            if first_page_image is None:
                return None

            # 使用PIL创建缩略图
            from PIL import Image
            import io
            import base64

            # 将numpy数组转换为PIL图片
            if first_page_image.dtype != 'uint8':
                first_page_image = (first_page_image * 255).astype('uint8')

            # 创建PIL图片（注意：core返回的是RGB格式）
            pil_image = Image.fromarray(first_page_image)

            # 创建缩略图，保持宽高比
            pil_image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # 转换为WebP格式以减小大小
            output = io.BytesIO()

            # WebP支持透明度，不需要强制转换为RGB
            # 但如果是调色板模式，还是需要转换
            if pil_image.mode == 'P':
                pil_image = pil_image.convert('RGBA')

            # 保存为WebP格式，质量80，启用有损压缩
            pil_image.save(output, format='WEBP', quality=80, method=6)

            # 保存到缓存
            cache_key = self.thumbnail_cache._get_cache_key(manga_path)
            cache_path = self.thumbnail_cache._get_cache_path(cache_key, max_size)

            # 保存缓存文件
            with open(cache_path, 'wb') as f:
                f.write(output.getvalue())

            # 更新元数据
            file_mtime = os.path.getmtime(manga_path)
            self.thumbnail_cache.metadata[cache_key] = {
                'mtime': file_mtime,
                'size': max_size,
                'path': manga_path
            }
            self.thumbnail_cache._save_metadata()

            # 返回base64编码
            image_base64 = base64.b64encode(output.getvalue()).decode('utf-8')
            return f"data:image/webp;base64,{image_base64}"

        except Exception as e:
            log.error(f"生成缩略图失败 {manga_path}: {e}")
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

            return WebMangaInfo(
                file_path=manga_info.file_path,
                title=manga_info.title,
                tags=clean_tags,
                total_pages=manga_info.total_pages,
                is_valid=manga_info.is_valid,
                last_modified=last_modified_str,
                file_type=file_type,
                file_size=file_size
            )
            
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
