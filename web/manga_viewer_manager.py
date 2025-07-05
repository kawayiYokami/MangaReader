"""
漫画查看管理器 - 会话级别的查看器控制器

负责管理用户单次阅读会话的生命周期，包括：
- 会话内存缓存管理（原图和翻译图）
- 请求路由（原图 vs 翻译图）
- 智能预载策略实现
"""

import threading
import asyncio
import uuid
from typing import Dict, List, Optional, Tuple, Any
from core.image import processor
import io
from enum import Enum
from pathlib import Path
import base64

from core.translation.translation_factory import get_translation_factory, PageStatus
from core.core_cache.cache_key_generator import get_cache_key_generator
from core.core_cache.page_cache import get_page_cache
from core.manga.precache_manager import (
    precache_manager, POLICY_PENDING, POLICY_CACHED, POLICY_NOT_REQUIRED
)
from core.core_cache.cache_factory import get_cache_factory_instance
from core.manga.data_source import _get_image_dimensions_fast
from core.config import config
from web.core_interface import get_core_interface
import logging


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
        self.translation_factory = get_translation_factory()
        self.core_interface = get_core_interface()
        self.page_cache = get_page_cache()
        self.precache_manager = precache_manager # 旧的管理器，主要用于访问常量
        self.policy_manager = get_cache_factory_instance().get_manager('page_policy')

        # 会话内存缓存 (缓存元组: (image_data, width, height))
        self.original_cache: Dict[str, Tuple[str, int, int]] = {}  # 原图缓存
        self.translated_cache: Dict[str, Tuple[bytes, int, int]] = {}  # 翻译图缓存
        
        # 当前状态
        self.current_manga_path: Optional[str] = None
        self.current_page: int = 0
        self.display_mode: DisplayMode = DisplayMode.SINGLE
        self.translation_enabled: bool = False
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
            
            # V5 核心逻辑: 检查是否存在页面策略，如果不存在，则启动后台分析
            # 注意：这里需要 await，因为 get_policy 是异步的
            policy = await self.policy_manager.get_policy(manga_path, 0)
            if policy is None:
                logging.info(f"'{manga_path}' 首次打开，启动后台页面分析任务。")
                asyncio.create_task(self._analyze_and_create_policies_async(manga_path))
            
            return {
                "success": True,
                "manga_info": manga_info,
                "current_page": self.current_page
            }
            
        except Exception as e:
            logging.error(f"设置当前漫画失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def get_page_images(self, page: int, display_mode: str = "single",
                           translation_enabled: bool = False) -> Dict[str, Any]:
        """
        获取页面图像（主要接口）
        
        Args:
            page: 页面索引
            display_mode: 显示模式
            translation_enabled: 是否启用翻译
            
        Returns:
            页面图像数据和状态信息
        """
        try:
            if not self.current_manga_path:
                return {"success": False, "message": "未设置当前漫画"}
            
            # 更新状态
            self.current_page = max(0, min(page, self.total_pages - 1))
            self.display_mode = DisplayMode.SINGLE if display_mode == "single" else DisplayMode.DOUBLE
            self.translation_enabled = translation_enabled
            
            # 计算需要加载的页面
            current_pages, preload_pages = PageLoadStrategy.get_pages_to_load(
                self.current_page, self.display_mode, self.total_pages
            )
            
            # 加载当前页面
            current_images = []
            for page_idx in current_pages:
                image_info = await self._get_page_image(page_idx, translation_enabled)
                if image_info:
                    image_data, width, height = image_info
                    current_images.append({
                        "page_index": page_idx,
                        "image_data": image_data,
                        "width": width,
                        "height": height,
                        "is_translated": translation_enabled and self._is_page_translated(page_idx)
                    })
            
            # 异步预载页面
            self._preload_pages_async(preload_pages, translation_enabled)
            
            return {
                "success": True,
                "images": current_images,
                "current_page": self.current_page,
                "total_pages": self.total_pages,
                "display_mode": display_mode,
                "translation_enabled": translation_enabled
            }
            
        except Exception as e:
            logging.error(f"获取页面图像失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def _get_page_image(self, page_index: int, use_translation: bool) -> Optional[Tuple[str, int, int]]:
        """获取单个页面图像及其尺寸"""
        try:
            if use_translation:
                return await self._get_translated_page(page_index)
            else:
                return await self._get_original_page(page_index)
        except Exception as e:
            logging.error(f"获取页面图像失败 (页面 {page_index}): {e}")
            return None

    async def _get_original_page(self, page_index: int) -> Optional[Tuple[str, int, int]]:
        """
        获取原图页面及其尺寸, 实现V5架构中的“按需分析+预缓存”策略。
        """
        policy_str = await self.policy_manager.get_policy(self.current_manga_path, page_index)
        logging.debug(f"页面 {page_index} 的策略: {policy_str}")

        # 情况1：策略明确为已缓存，尝试从持久化缓存中获取
        if policy_str == POLICY_CACHED:
            cached_page_bytes = self.page_cache.get_page(self.current_manga_path, page_index)
            if cached_page_bytes:
                logging.debug(f"页面缓存命中（策略：CACHED）：{self.current_manga_path} [页面 {page_index}]")
                try:
                    img = processor.read_image(cached_page_bytes)
                    if img is None: raise ValueError("无法解码缓存的JPEG")
                    encoded_str = base64.b64encode(cached_page_bytes).decode('utf-8')
                    return f"data:image/jpeg;base64,{encoded_str}", img.shape[1], img.shape[0]
                except Exception as e:
                    logging.warning(f"Failed to decode cached page '{self.current_manga_path}' [Page {page_index}], resetting policy to PENDING and regenerating.")
                    await self.policy_manager.set_policy(self.current_manga_path, page_index, POLICY_PENDING)
                    policy_str = POLICY_PENDING # 更新状态以便进入情况3
            else:
                logging.warning(f"Policy is CACHED but cache file is missing for '{self.current_manga_path}' [Page {page_index}], resetting policy to PENDING.")
                await self.policy_manager.set_policy(self.current_manga_path, page_index, POLICY_PENDING)
                policy_str = POLICY_PENDING # 更新状态以便进入情况3

        # 情况2：策略明确为不需要，直接获取原图，不缓存
        if policy_str == POLICY_NOT_REQUIRED:
            logging.debug(f"策略 '{policy_str}': 直接获取 {self.current_manga_path} [页面 {page_index}]")
            return await self.core_interface.get_manga_page(self.current_manga_path, page_index, use_cache=False)

        # 情况3：策略是 PENDING 或 None（表示需要分析和缓存）
        # 立即获取原图返回给前端，然后启动后台任务生成缓存
        logging.debug(f"策略是 '{policy_str}': 返回原图并为 {self.current_manga_path} [页面 {page_index}] 启动后台缓存生成")
        
        original_image_info = await self.core_interface.get_manga_page(self.current_manga_path, page_index, use_cache=True)
        if not original_image_info:
            logging.error(f"无法获取页面 {page_index} 的原始图像信息。")
            return None
        
        # 对于 policy is None 的情况，我们需要进行一次即时分析来决定是否启动缓存任务
        if policy_str is None:
            logging.debug(f"即时分析页面 {page_index} 以决定是否需要缓存...")
            image_data_str, _, _ = original_image_info
            header, encoded = image_data_str.split(",", 1)
            image_bytes = base64.b64decode(encoded)
            dims = _get_image_dimensions_fast(image_bytes)
            if dims and dims[1] > config.page_cache_standard_height.value:
                 # 只有在需要缩放时才启动后台缓存任务
                 asyncio.create_task(self._generate_page_cache_async(self.current_manga_path, page_index, original_image_info))
        else: # policy_str == POLICY_PENDING
             asyncio.create_task(self._generate_page_cache_async(self.current_manga_path, page_index, original_image_info))
        
        # 立即返回原始（可能已通过核心缓存缩放的）图像
        return original_image_info

    async def _generate_page_cache_async(self, manga_path: str, page_index: int, image_info_tuple: Tuple[str, int, int]):
        """
        [后台任务] 生成页面的标准尺寸缓存，并更新其策略为 'CACHED'。
        """
        try:
            image_data_str, _, _ = image_info_tuple
            standard_height = config.page_cache_standard_height.value

            logging.debug(f"后台任务: 开始为页面 {page_index} 生成标准尺寸缓存。")
            header, encoded = image_data_str.split(",", 1)
            image_bytes = base64.b64decode(encoded)
            img = processor.read_image(image_bytes)

            if img is None: raise ValueError("从base64解码图像失败")
            
            # 如果图像本身已经小于或等于标准高度，则无需缩放，直接缓存
            if img.shape[0] <= standard_height:
                 scaled_image_bytes = processor.write_image(img, ext='.jpg', quality=config.page_cache_quality.value)
            else:
                scale = standard_height / img.shape[0]
                new_width = int(img.shape[1] * scale)
                scaled_img = processor.resize(img, (new_width, standard_height))
                if scaled_img is None: raise ValueError("图像缩放失败")

                scaled_image_bytes = processor.write_image(scaled_img, ext='.jpg', quality=config.page_cache_quality.value)
            
            if not scaled_image_bytes: raise ValueError("编码为JPEG失败")

            # 存入PageCache
            self.page_cache.store_page(manga_path, page_index, scaled_image_bytes)
            
            # 更新数据库中的策略
            await self.policy_manager.update_policy_to_cached(manga_path, page_index)
            logging.info(f"后台任务: 成功为 '{manga_path}' [Page {page_index}] 生成缓存并更新策略为 CACHED。")

        except Exception as e:
            logging.error(f"后台任务: 生成标准尺寸缓存失败 (页面 {page_index}): {e}", exc_info=True)

    async def _analyze_and_create_policies_async(self, manga_path: str):
        """
        [后台任务] V5核心逻辑: 分析整本漫画的所有页面，并批量生成和存储预缓存策略。
        """
        try:
            logging.info(f"后台分析任务开始: {manga_path}")
            
            # 1. 获取所有页面的原始尺寸
            dimensions = await self.core_interface.get_all_page_dimensions(manga_path)
            if not dimensions:
                logging.warning(f"无法获取 '{manga_path}' 的页面尺寸，分析任务中止。")
                return

            # 2. 生成策略列表
            policies = []
            threshold = config.page_cache_standard_height.value
            for i, dim in enumerate(dimensions):
                if dim and dim[1] > threshold:
                    policy_status = POLICY_PENDING
                else:
                    policy_status = POLICY_NOT_REQUIRED
                
                policies.append({
                    "manga_path": manga_path,
                    "page_index": i,
                    "policy": policy_status,
                    "width": dim[0] if dim else 0,
                    "height": dim[1] if dim else 0,
                })
            
            # 3. 批量写入数据库
            if policies:
                await self.policy_manager.set_policies_batch(policies)
                logging.info(f"后台分析任务完成: 为 '{manga_path}' 批量设置了 {len(policies)} 条页面策略。")

        except Exception as e:
            logging.error(f"后台分析任务失败: {manga_path}, 错误: {e}", exc_info=True)

    async def _get_translated_page(self, page_index: int) -> Optional[Tuple[str, int, int]]:
        """获取翻译页面及其尺寸"""
        translator_id = config.translator_type.value
        cache_key = self.key_generator.generate_translation_key(
            self.current_manga_path, page_index, translator_id
        )

        with self.cache_lock:
            if cache_key in self.translated_cache:
                logging.debug(f"会话翻译缓存命中: {cache_key}")
                return self.translated_cache[cache_key]

        try:
            # 获取原始翻译图像
            translated_data_bytes = self.translation_factory.get_translated_page(
                self.current_manga_path, page_index, translator_id
            )

            if not translated_data_bytes:
                logging.info(f"翻译失败或超时，返回原图: {page_index}")
                return await self._get_original_page(page_index)

            img = processor.read_image(translated_data_bytes)
            if img is None:
                raise ValueError("解码翻译图像失败")

            # 直接编码为WebP，不再进行缩放
            final_image_bytes = processor.write_image(img, ext=".webp", quality=85)
            if not final_image_bytes:
                raise ValueError("编码翻译图像为WEBP失败")

            # 生成base64 data URL
            encoded_data = base64.b64encode(final_image_bytes).decode('utf-8')
            image_data_url = f"data:image/webp;base64,{encoded_data}"
            
            final_image_info = (image_data_url, img.shape[1], img.shape[0])

            with self.cache_lock:
                self.translated_cache[cache_key] = final_image_info
                self.loaded_pages.add(page_index)
            
            logging.debug(f"会话 {self.session_id}: 加载翻译页面 {page_index}")
            return final_image_info

        except Exception as e:
            logging.error(f"获取翻译页面失败: {e}")
            return await self._get_original_page(page_index)
    
    def _preload_pages_async(self, page_indices: List[int], use_translation: bool):
        """异步预载页面"""
        async def preload_worker():
            for page_idx in page_indices:
                if page_idx not in self.preloaded_pages:
                    try:
                        await self._get_page_image(page_idx, use_translation)
                        self.preloaded_pages.add(page_idx)
                        logging.debug(f"预载页面完成: {page_idx}")
                    except Exception as e:
                        logging.warning(f"预载页面失败 {page_idx}: {e}")
        
        # 在事件循环中创建后台任务
        asyncio.create_task(preload_worker())
    
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
    
    def _is_page_translated(self, page_index: int) -> bool:
        """检查页面是否已翻译"""
        try:
            translator_id = config.translator_type.value
            status = self.translation_factory.get_page_status(
                self.current_manga_path, page_index, translator_id
            )
            return status == PageStatus.TRANSLATED
        except Exception as e:
            logging.warning(f"检查翻译状态失败: {e}")
            return False
    


    def _clear_caches(self):
        """清空会话缓存"""
        with self.cache_lock:
            self.original_cache.clear()
            self.translated_cache.clear()
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
                "translation_enabled": self.translation_enabled,
                "cache_stats": {
                    "original_cache_size": len(self.original_cache),
                    "translated_cache_size": len(self.translated_cache),
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


