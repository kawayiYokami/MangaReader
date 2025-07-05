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
import random
import uuid
from dataclasses import dataclass, asdict
import traceback
import shutil
import tempfile
import hashlib
import json
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

# 导入core模块
from core.manga.manga_manager import MangaManager
from core.manga.manga_model import MangaInfo
from core.manga.data_source import DataSourceFactory
from core.core_cache.thumbnail_cache import ThumbnailCache
from core.config import config
from core.core_cache.cache_factory import get_cache_factory_instance
from core.image import processor
import logging


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
        self._thumbnail_cache: Optional[ThumbnailCache] = None

        # 转换结果缓存机制
        self._conversion_cache: Dict[str, WebMangaInfo] = {}
        self._conversion_cache_timestamps: Dict[str, float] = {}
        self._cache_expire_time = 300  # 5分钟缓存过期时间

        # 随机阅读会话缓存
        self._random_sessions: Dict[str, Dict[str, Any]] = {}
        self._random_session_lock = threading.Lock()
        
    @property
    def manga_manager(self) -> MangaManager:
        """获取MangaManager实例（懒加载）"""
        if self._manga_manager is None:
            try:
                self._manga_manager = MangaManager()
                logging.info("MangaManager初始化成功")
            except Exception as e:
                logging.error(f"MangaManager初始化失败: {e}", exc_info=True)
                raise CoreInterfaceError("漫画管理器初始化失败", e)
        return self._manga_manager

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
                logging.info("缩略图缓存管理器初始化成功")
            except Exception as e:
                logging.error(f"缩略图缓存管理器初始化失败: {e}")
                raise CoreInterfaceError("缩略图缓存管理器初始化失败", e)
        return self._thumbnail_cache

    # ==================== 目录管理 ====================
    
    async def get_current_directory(self) -> WebDirectoryInfo:
        """获取当前漫画目录信息"""
        try:
            current_dir = config.manga_dir.value or ""
            manga_count = await self.manga_manager.get_manga_count() if current_dir else 0
            
            return WebDirectoryInfo(
                path=current_dir,
                exists=os.path.exists(current_dir) if current_dir else False,
                is_directory=os.path.isdir(current_dir) if current_dir else False,
                manga_count=manga_count
            )
        except Exception as e:
            logging.error(f"获取当前目录失败: {e}")
            raise CoreInterfaceError("获取当前目录失败", e)
    
    async def set_directory(self, directory_path: str) -> Dict[str, Any]:
        """设置漫画目录并进行全新的完整扫描。"""
        try:
            if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
                raise CoreInterfaceError(f"提供的路径不是一个有效的目录: {directory_path}")

            # 设置新目录并保存配置
            config.manga_dir.value = directory_path
            self.manga_manager.save_config()
            logging.info(f"漫画目录已成功设置为: {directory_path}")

            # 设置目录被视为一个重要操作，将触发一次全新的扫描
            # 首先清空现有数据
            await self.manga_manager.clear_all_data()
            logging.info("由于设置了新目录，已清空所有旧数据以进行全新扫描。")
            
            # 然后调用统一的添加方法进行扫描
            return await self.add_mangas_from_paths([directory_path])

        except CoreInterfaceError:
            raise
        except Exception as e:
            logging.error(f"设置目录时发生未知错误: {e}", exc_info=True)
            raise CoreInterfaceError("设置目录时发生严重错误", e)
    
    # ==================== 漫画列表管理 ====================
    
    async def get_manga_list(self, sort_by: str = "last_modified DESC", tag_filters: Optional[List[str]] = None) -> List[WebMangaInfo]:
        """从数据库获取漫画列表，并支持排序和过滤"""
        try:
            logging.info(f"获取漫画列表，排序: {sort_by}, 过滤: {tag_filters}")
            manga_dicts = await self.manga_manager.get_manga_list(sort_by=sort_by, tag_filters=tag_filters)
            
            web_manga_list = [self._convert_dict_to_web_manga(d) for d in manga_dicts]
            return web_manga_list

        except Exception as e:
            logging.error(f"获取漫画列表失败: {e}", exc_info=True)
            raise CoreInterfaceError("获取漫画列表失败", e)
    
    async def get_all_tags(self) -> List[str]:
        """从数据库获取所有标签"""
        try:
            return await self.manga_manager.get_all_tags()
        except Exception as e:
            logging.error(f"获取标签失败: {e}", exc_info=True)
            raise CoreInterfaceError("获取标签失败", e)
    
    # ==================== 漫画图片获取 ====================

    def get_manga_thumbnail_path(self, manga_path: str) -> Optional[str]:
        """
        获取漫画缩略图的文件路径。
        这是对 thumbnail_cache.get_thumbnail_path 的封装，用于统一接口。
        """
        try:
            # 注意：get_thumbnail_path 可能会触发生成操作，所以它不是纯粹的“获取”
            thumbnail_path = self.thumbnail_cache.get_thumbnail_path(manga_path)
            
            if thumbnail_path and os.path.exists(thumbnail_path):
                return thumbnail_path
            
            logging.warning(f"无法为漫画 '{manga_path}' 找到或生成有效的缩略图路径。")
            return None
        except Exception as e:
            logging.error(f"在 CoreInterface 中获取缩略图路径失败: {e}", exc_info=True)
            return None

    async def get_manga_page(self, manga_path: str, page_num: int, use_cache: bool = True) -> Optional[Tuple[str, int, int]]:
        """获取漫画指定页面的base64编码图片及其尺寸"""
        try:
            manga_info = await self.get_manga_by_path(manga_path) # 改为调用封装后的方法
            if not manga_info:
                logging.warning(f"无法在管理器中找到漫画信息: {manga_path}")
                return None
            
            if not (0 <= page_num < manga_info.total_pages):
                logging.warning(f"页码超出范围: {page_num}, 总页数: {manga_info.total_pages}")
                return None
            
            data_source = DataSourceFactory.create(manga_path)
            if not data_source:
                logging.warning(f"无法为路径创建数据源: {manga_path}")
                return None
            
            image_data = data_source.get_page_image_data(page_num)
            if not image_data:
                logging.warning(f"无法获取页面 {page_num} 的图像数据: {manga_path}")
                return None

            width, height = -1, -1
            if manga_info.page_dimensions and page_num < len(manga_info.page_dimensions):
                width, height = manga_info.page_dimensions[page_num]
            else:
                try:
                    img = processor.read_image(image_data)
                    if img is not None:
                        height, width, _ = img.shape
                except Exception as ex:
                    logging.warning(f"无法解码图像以获取尺寸: {ex}")

            import base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            if image_data.startswith(b'\xff\xd8'):
                mime_type = 'image/jpeg'
            elif image_data.startswith(b'\x89PNG\r\n\x1a\n'):
                mime_type = 'image/png'
            else:
                mime_type = 'image/jpeg'

            return f"data:{mime_type};base64,{image_base64}", width, height

        except Exception as e:
            logging.error(f"获取漫画页面失败 {manga_path}, 页码 {page_num}: {e}")
            return None

    # ==================== 漫画详情与缓存管理 (封装) ====================

    async def get_manga_by_path(self, manga_path: str) -> Optional[MangaInfo]:
        """
        通过路径获取单个漫画的完整信息 (封装MangaManager调用)。
        """
        try:
            return await self.manga_manager.get_manga_by_path(manga_path)
        except Exception as e:
            logging.error(f"通过路径 '{manga_path}' 获取漫画信息失败: {e}", exc_info=True)
            raise CoreInterfaceError(f"获取漫画信息失败: {manga_path}", e)

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缩略图缓存统计信息 (封装ThumbnailCache调用)。"""
        try:
            return self.thumbnail_cache.get_cache_stats()
        except Exception as e:
            logging.error(f"获取缓存统计信息失败: {e}", exc_info=True)
            raise CoreInterfaceError("获取缓存统计失败", e)

    def cleanup_cache(self, max_age_days: int) -> Dict[str, Any]:
        """清理过期的缩略图缓存 (封装ThumbnailCache调用)。"""
        try:
            self.thumbnail_cache.cleanup_expired_cache(max_age_days)
            # 返回清理后的状态
            return self.get_cache_stats()
        except Exception as e:
            logging.error(f"清理缓存失败: {e}", exc_info=True)
            raise CoreInterfaceError("清理缓存失败", e)

    def clear_cache(self) -> None:
        """清空所有缩略图缓存 (封装ThumbnailCache调用)。"""
        try:
            self.thumbnail_cache.clear_cache()
            logging.info("缩略图缓存已通过 CoreInterface 清空。")
        except Exception as e:
            logging.error(f"清空缓存失败: {e}", exc_info=True)
            raise CoreInterfaceError("清空缓存失败", e)

    async def get_page_dimensions(self, manga_path: str, page_num: int) -> Optional[Tuple[int, int]]:
        """高效获取漫画指定页面的尺寸 (width, height)"""
        try:
            manga_info = await self.manga_manager.get_manga_by_path(manga_path)
            if not manga_info:
                logging.warning(f"无法在管理器中找到漫画信息: {manga_path}")
                return None

            if not (0 <= page_num < manga_info.total_pages):
                logging.warning(f"页码超出范围: {page_num}, 总页数: {manga_info.total_pages}")
                return None
            
            if manga_info.page_dimensions and page_num < len(manga_info.page_dimensions):
                return manga_info.page_dimensions[page_num]
            else:
                logging.warning(f"漫画 {manga_path} 缺少页面 {page_num} 的尺寸信息。")
                return None

        except Exception as e:
            logging.error(f"高效获取页面尺寸失败 {manga_path}, 页码 {page_num}: {e}")
            return None

    async def get_all_page_dimensions(self, manga_path: str) -> Optional[List[Tuple[int, int]]]:
        """获取漫画所有页面的尺寸 (width, height) 列表"""
        try:
            data_source = await asyncio.to_thread(DataSourceFactory.create, manga_path)
            if not data_source:
                logging.warning(f"无法为路径创建数据源: {manga_path}")
                return None
            
            # get_all_page_dimensions 是一个I/O密集型操作，应在线程中运行
            return await asyncio.to_thread(data_source.get_all_page_dimensions)

        except Exception as e:
            logging.error(f"获取所有页面尺寸失败 {manga_path}: {e}", exc_info=True)
            return None

    # ==================== 数据转换工具 ====================

    def _convert_dict_to_web_manga(self, manga_dict: Dict[str, Any]) -> WebMangaInfo:
        """将从数据库获取的字典转换为WebMangaInfo"""
        try:
            # last_modified 可能是一个时间戳 (float/int) 或一个已格式化的字符串
            last_modified_val = manga_dict.get('last_modified')
            last_modified_str = ""
            if isinstance(last_modified_val, (int, float)):
                if last_modified_val > 0:
                    last_modified_str = datetime.fromtimestamp(last_modified_val).isoformat()
            elif isinstance(last_modified_val, str):
                last_modified_str = last_modified_val
            
            # 标签由 MangaRepository 返回时已经是列表
            tag_list = manga_dict.get('tags', [])
            if not isinstance(tag_list, list):
                # 添加一层保护，以防万一返回的是字符串
                tag_list = tag_list.split(',') if isinstance(tag_list, str) and tag_list else []

            return WebMangaInfo(
                file_path=manga_dict.get('file_path', ''),
                title=manga_dict.get('title', 'N/A'),
                tags=tag_list,
                total_pages=manga_dict.get('total_pages', 0),
                is_valid=manga_dict.get('is_valid', True), # 假设数据库中的都是有效的
                last_modified=last_modified_str,
                file_type=manga_dict.get('file_type', 'unknown'),
                file_size=manga_dict.get('file_size')
            )
        except Exception as e:
            logging.error(f"从字典转换漫画信息失败: {manga_dict.get('file_path')}, 错误: {e}", exc_info=True)
            return WebMangaInfo(
                file_path=manga_dict.get('file_path', ''),
                title='转换失败',
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
            expired_keys = [
                cache_key for cache_key, timestamp in self._conversion_cache_timestamps.items()
                if current_time - timestamp > self._cache_expire_time
            ]

            for key in expired_keys:
                self._conversion_cache.pop(key, None)
                self._conversion_cache_timestamps.pop(key, None)

            if expired_keys:
                logging.debug(f"清理了 {len(expired_keys)} 个过期的转换缓存项")

        except Exception as e:
            logging.warning(f"清理转换缓存失败: {e}")

    def clear_conversion_cache(self):
        """手动清空转换缓存"""
        self._conversion_cache.clear()
        self._conversion_cache_timestamps.clear()
        logging.info("转换缓存已清空")

    # ==================== 清理和关闭 ====================

    async def add_mangas_from_paths(self, paths: List[str]) -> Dict[str, Any]:
        """
        从多个路径（文件或文件夹）添加漫画，并返回详细的处理结果。
        这是对原 add_manga_from_path 的一个更上层的封装，包含了API层的逻辑。
        """
        added_count = 0
        failed_paths = []
        start_time = time.time()
        initial_count = await self.manga_manager.get_manga_count()

        for path in paths:
            try:
                if not os.path.exists(path):
                    failed_paths.append({"path": path, "reason": "路径不存在"})
                    continue

                if os.path.isdir(path):
                    await self.manga_manager.add_manga_from_path(path)
                elif path.lower().endswith(('.zip', '.cbz', '.cbr')):
                    await self.manga_manager.add_manga_from_path(path)
                else:
                    failed_paths.append({"path": path, "reason": "不支持的文件类型"})
            except Exception as e:
                logging.error(f"在 CoreInterface 中添加路径 '{path}' 失败: {e}", exc_info=True)
                failed_paths.append({"path": path, "reason": f"处理失败: {str(e)}"})
        
        final_count = await self.manga_manager.get_manga_count()
        added_count = final_count - initial_count
        scan_time = f"{time.time() - start_time:.2f}s"

        # 构建响应消息
        message_parts = []
        if added_count > 0:
            message_parts.append(f"成功扫描并处理了 {added_count} 本新漫画")
        if failed_paths:
            message_parts.append(f"有 {len(failed_paths)} 个路径处理失败")

        message = "，".join(message_parts) if message_parts else "未发现新的漫画或所有漫画都已存在"

        return {
            "success": added_count > 0 and not failed_paths,
            "message": message,
            "added_count": added_count,
            "failed_paths": failed_paths,
            "scan_time": scan_time
        }


    async def clear_all_data(self) -> bool:
        """清空所有漫画数据"""
        try:
            await self.manga_manager.clear_all_data()
            logging.info("所有漫画数据已清空")
            return True
        except Exception as e:
            logging.error(f"清空数据失败: {e}")
            raise CoreInterfaceError("清空数据失败", e)


    # ==================== 随机播放会话管理 ====================
    # ==================== 随机播放会话管理 ====================

    async def start_random_session(self, limit: int = 50) -> Tuple[Optional[str], List[WebMangaInfo]]:
        """
        启动一个新的随机漫画阅读会话。
        """
        try:
            # 从数据库获取所有漫画的路径
            all_manga_dicts = await self.manga_manager.get_manga_list(sort_by=None)
            all_manga_paths = [m['file_path'] for m in all_manga_dicts]
            if not all_manga_paths:
                return None, []
            
            random.shuffle(all_manga_paths)

            with self._random_session_lock:
                session_id = str(uuid.uuid4())
                self._random_sessions[session_id] = {
                    "shuffled_paths": all_manga_paths,
                    "timestamp": time.time()
                }

                logging.info(f"启动新的随机播放会话: {session_id}，包含 {len(all_manga_paths)} 个项目。")
                if len(self._random_sessions) % 10 == 0: self._cleanup_random_sessions()
            
            first_page_manga = await self.get_random_session_page(session_id, 1, limit)
            return session_id, first_page_manga

        except Exception as e:
            logging.error(f"启动随机播放会话失败: {e}", exc_info=True)
            raise CoreInterfaceError("启动随机播放会话失败", e)

    async def get_random_session_page(self, session_id: str, page: int, limit: int) -> List[WebMangaInfo]:
        """从缓存的随机播放会话中获取特定页面。"""
        try:
            with self._random_session_lock:
                session = self._random_sessions.get(session_id)
                if not session:
                    raise CoreInterfaceError("随机播放会话未找到或已过期。")
                
                session['timestamp'] = time.time()

            shuffled_paths = session["shuffled_paths"]
            
            start_index = (page - 1) * limit
            end_index = start_index + limit
            
            if start_index >= len(shuffled_paths):
                return []

            page_paths = shuffled_paths[start_index:end_index]
            
            # 由于不再有内存列表，我们需要为每个路径单独获取信息
            # 这效率不高，但对于随机功能是可接受的。
            # 更好的方法是在 MangaRepository 中添加一个 get_mangas_by_paths 方法。
            page_manga_info = []
            for path in page_paths:
                manga_info = await self.manga_manager.get_manga_by_path(path)
                if manga_info:
                    # get_manga_by_path 返回 MangaInfo 对象，我们需要将其转换为字典
                    # 以便 _convert_dict_to_web_manga 可以处理
                    manga_dict = asdict(manga_info)
                    # asdict 可能会丢失方法，但对数据转换足够了
                    # 我们需要手动处理 tags 和 last_modified 的格式
                    manga_dict['tags'] = ','.join(manga_info.tags)
                    if manga_info.last_modified:
                        manga_dict['last_modified'] = datetime.fromtimestamp(manga_info.last_modified).isoformat()
                    else:
                        manga_dict['last_modified'] = ""
                    page_manga_info.append(self._convert_dict_to_web_manga(manga_dict))

            
            return page_manga_info

        except CoreInterfaceError:
            raise
        except Exception as e:
            logging.error(f"获取随机播放会话页面失败: {e}", exc_info=True)
            raise CoreInterfaceError("获取随机播放会话页面失败", e)

    def _cleanup_random_sessions(self, max_age_seconds: int = 3600): # 1小时
        """清理过期的随机播放会话。"""
        with self._random_session_lock:
            current_time = time.time()
            expired_sessions = [
                sid for sid, data in self._random_sessions.items()
                if current_time - data.get("timestamp", 0) > max_age_seconds
            ]
            
            for sid in expired_sessions:
                del self._random_sessions[sid]
            
            if expired_sessions:
                logging.info(f"清理了 {len(expired_sessions)} 个过期的随机播放会话。")

    def close(self):
        """关闭接口，清理资源"""
        try:
            get_cache_factory_instance().close_all_managers()
            logging.info("Core接口已关闭")
        except Exception as e:
            logging.error(f"关闭Core接口时出错: {e}")


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
