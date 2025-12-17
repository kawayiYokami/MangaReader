"""
漫画查看管理器 - 会话级别的查看器控制器

负责管理用户单次阅读会话的生命周期，包括：
- 会话内存缓存管理（原图）
- 智能预载策略实现
"""

import threading
import asyncio
import uuid
from typing import Dict, List, Optional, Tuple, Any
import io
from enum import Enum
from pathlib import Path

from src.backend.core.core_cache.cache_key_generator import get_cache_key_generator
from src.backend.core.manga.page_loader import get_page_loader
from src.backend.web.dependencies import core_interface
import logging
from PIL import Image


class DisplayMode(Enum):
    """显示模式枚举"""
    SINGLE = "single"  # 单页模式
    DOUBLE = "double"  # 双页模式


class PageLoadStrategy:
    """页面加载策略"""

    @staticmethod
    def get_pages_to_load(current_page: int, display_mode: DisplayMode, total_pages: int) -> Tuple[List[int], List[int]]:
        """
        根据显示模式和当前页面计算需要加载的页面

        Args:
            current_page: 当前页面索引
            display_mode: 显示模式
            total_pages: 总页数

        Returns:
            (当前需要显示的页面列表, 需要预载的页面列表)
        """
        current_pages = []
        preload_pages = []

        if display_mode == DisplayMode.SINGLE:
            # 单页模式：显示当前页，预载下一页
            current_pages = [current_page]
            if current_page + 1 < total_pages:
                preload_pages = [current_page + 1]
        else:
            # 双页模式：显示当前页和下一页，预载后两页
            current_pages = [current_page]
            if current_page + 1 < total_pages:
                current_pages.append(current_page + 1)

            # 预载后两页
            for i in range(2):
                next_page = current_page + len(current_pages) + i
                if next_page < total_pages:
                    preload_pages.append(next_page)

        return current_pages, preload_pages


class MangaViewerManager:
    """漫画查看管理器 - 会话级别"""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.key_generator = get_cache_key_generator()
        self.core_interface = core_interface
        self.page_loader = get_page_loader() # 使用新的PageLoader

        # 会话内存缓存 (缓存元组: (image_data, width, height))
        self.original_cache: Dict[str, Tuple[str, int, int]] = {}  # 原图缓存

        # 当前状态
        self.current_manga_path: Optional[str] = None
        self.current_page: int = 0
        self.display_mode: DisplayMode = DisplayMode.SINGLE
        self.total_pages: int = 0

        # 页面加载状态跟踪
        self.loaded_pages: set = set()
        self.preloaded_pages: set = set()



        # 线程安全锁
        self.cache_lock = threading.RLock()

        logging.info(f"漫画查看管理器创建: 会话ID={self.session_id}")

    async def set_current_manga(self, manga_path: str, page: int = 0, force_rescan: bool = False) -> Dict[str, Any]:
        """
        设置当前查看的漫画

        Args:
            manga_path: 漫画文件路径
            page: 起始页面
            force_rescan: 是否强制重新扫描漫画库

        Returns:
            操作结果
        """
        try:
            # 验证文件存在
            if not Path(manga_path).exists():
                logging.warning(f"漫画文件不存在，自动删除数据库记录: {manga_path}")
                # 删除数据库中的无效记录
                try:
                    success = await self.core_interface.manga_manager.manga_repo.delete_manga_by_path(manga_path)
                    if success:
                        logging.info(f"已删除不存在的漫画记录: {manga_path}")
                        # 触发刷新事件，通知前端更新画廊
                        manga_count = await self.core_interface.manga_manager.get_manga_count()
                        tags_count = await self.core_interface.manga_manager.get_tags_count()
                        self.core_interface.manga_manager._emit_event('data_loaded', {
                            'manga_count': manga_count,
                            'tags_count': tags_count
                        })
                except Exception as e:
                    logging.error(f"删除无效漫画记录失败: {e}")
                return {"success": False, "message": f"漫画文件不存在: {manga_path}"}

            # 切换漫画时清空缓存
            if self.current_manga_path != manga_path:
                self._clear_caches()
                logging.info(f"会话 {self.session_id}: 切换漫画，清空缓存")

            # 获取漫画信息
            manga_info = await self._get_manga_info(manga_path, force_rescan=force_rescan)
            if not manga_info:
                return {"success": False, "message": "无法获取漫画信息"}

            # 更新状态
            self.current_manga_path = manga_path
            self.current_page = max(0, min(page, manga_info["total_pages"] - 1))
            self.total_pages = manga_info["total_pages"]

            logging.info(f"会话 {self.session_id}: 设置当前漫画 {manga_path}, 页面 {self.current_page}")

            # ThumbnailCache 和 MangaPageLoader 会自动处理首次分析，这里无需任何操作

            return {
                "success": True,
                "manga_info": manga_info,
                "current_page": self.current_page
            }

        except Exception as e:
            logging.error(f"设置当前漫画失败: {e}")
            return {"success": False, "message": str(e)}


    async def get_page_image_bytes(self, page_index: int) -> Optional[Tuple[bytes, str]]:
        """
        获取单个页面的原始图像字节和 MIME 类型。
        """
        if not self.current_manga_path:
            return None

        image_bytes = await self.page_loader.get_page(self.current_manga_path, page_index)

        if not image_bytes:
            logging.error(f"无法为页面 {page_index} 获取任何图像数据。")
            return None

        # 统一获取 MIME 类型
        try:
            from PIL import Image
            import io
            # 使用 Pillow 从字节流中动态识别图像格式
            image_format = Image.open(io.BytesIO(image_bytes)).format.lower()
            # 常见的格式映射
            if image_format == 'jpeg':
                mime_type = 'image/jpeg'
            elif image_format == 'png':
                mime_type = 'image/png'
            elif image_format == 'webp':
                mime_type = 'image/webp'
            elif image_format == 'gif':
                mime_type = 'image/gif'
            else:
                mime_type = f"image/{image_format}"
        except Exception:
            # 如果 Pillow 失败，回退到通用 MIME 类型
            mime_type = "application/octet-stream"
            logging.warning(f"无法确定页面 {page_index} 的MIME类型，回退到 application/octet-stream")

        return image_bytes, mime_type


    def _preload_pages_async(self, page_indices: List[int]):
        """异步预载页面"""
        async def preload_worker():
            for page_idx in page_indices:
                if page_idx not in self.preloaded_pages:
                    try:
                        # 直接调用核心方法来触发缓存（如果有），忽略返回值
                        await self.get_page_image_bytes(page_idx)
                        self.preloaded_pages.add(page_idx)
                        logging.debug(f"预载页面完成: {page_idx}")
                    except Exception as e:
                        logging.warning(f"预载页面失败 {page_idx}: {e}")
        # 在事件循环中创建后台任务
        asyncio.create_task(preload_worker())

    @staticmethod
    def _get_dimensions_from_bytes(image_bytes: bytes) -> Tuple[int, int]:
        """从图像字节流中获取尺寸"""
        if not image_bytes:
            return 0, 0
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                return img.width, img.height
        except Exception as e:
            logging.warning(f"无法从字节流中解析图像尺寸: {e}")
            return 0, 0

    async def get_page_metadata(self, page_index: int) -> Optional[Dict[str, Any]]:
        """获取单个页面的元数据，包括尺寸。"""
        if not self.current_manga_path:
            return None

        # 获取图像字节流
        image_data = await self.get_page_image_bytes(page_index)
        if not image_data:
            return None

        image_bytes, _ = image_data

        # 从字节流中分析尺寸
        width, height = self._get_dimensions_from_bytes(image_bytes)

        return {
            "pageIndex": page_index,
            "width": width,
            "height": height,
            "url": f"/api/viewer/image/{page_index}?session_id={self.session_id}"
        }

    async def _get_manga_info(self, manga_path: str, force_rescan: bool = False) -> Optional[Dict[str, Any]]:
        """获取漫画信息"""
        try:
            # 通过核心接口获取漫画列表
            manga_list = await self.core_interface.get_manga_list()
            for manga in manga_list:
                if manga.file_path == manga_path:
                    return {
                        "title": manga.title,
                        "file_path": manga.file_path,
                        "total_pages": manga.total_pages,
                        "file_size": getattr(manga, 'file_size', 0),
                        "tags": getattr(manga, 'tags', [])
                    }
        except Exception as e:
            logging.error(f"获取漫画信息失败: {e}")
        return None



    def _clear_caches(self):
        """清空会话缓存"""
        with self.cache_lock:
            self.original_cache.clear()
            self.loaded_pages.clear()
            self.preloaded_pages.clear()
        logging.debug(f"会话 {self.session_id}: 缓存已清空")

    def get_session_info(self) -> Dict[str, Any]:
        """获取会话信息"""
        with self.cache_lock:
            return {
                "session_id": self.session_id,
                "current_manga_path": self.current_manga_path,
                "current_page": self.current_page,
                "total_pages": self.total_pages,
                "display_mode": self.display_mode.value,
                "cache_stats": {
                    "original_cache_size": len(self.original_cache),
                    "loaded_pages": len(self.loaded_pages),
                    "preloaded_pages": len(self.preloaded_pages)
                }
            }

    def cleanup(self):
        """清理会话资源"""
        self._clear_caches()
        logging.info(f"会话 {self.session_id}: 资源清理完成")


# 会话管理器字典
_session_managers: Dict[str, MangaViewerManager] = {}
_session_lock = threading.RLock()

def get_viewer_manager(session_id: Optional[str] = None) -> MangaViewerManager:
    """获取或创建查看器管理器实例"""
    with _session_lock:
        if session_id is None:
            session_id = str(uuid.uuid4())

        if session_id not in _session_managers:
            _session_managers[session_id] = MangaViewerManager(session_id)

        return _session_managers[session_id]

def cleanup_session(session_id: str):
    """清理指定会话"""
    with _session_lock:
        if session_id in _session_managers:
            _session_managers[session_id].cleanup()
            del _session_managers[session_id]
            logging.info(f"会话已清理: {session_id}")

def get_active_sessions() -> List[str]:
    """获取活跃会话列表"""
    with _session_lock:
        return list(_session_managers.keys())
