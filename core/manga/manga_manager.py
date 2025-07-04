# core/manga_manager.py

import os
import asyncio
from typing import List, Set, Dict, Optional, TYPE_CHECKING

from core.manga.manga_model import MangaInfo
from core.config import config

if TYPE_CHECKING:
    from core.core_cache.manga_cache import MangaListCacheManager
from utils import manga_logger as log
from core.translation.translator import TranslatorFactory
from core.core_cache.cache_factory import get_cache_factory_instance
from core.core_cache.cache_interface import CacheInterface
from core.manga.data_source import DataSourceFactory
from core.manga.metadata_parser import MetadataParser


class MangaManager:
    def __init__(self):
        # 异步事件队列
        self.update_queue = asyncio.Queue()

        self.manga_repo: 'MangaListCacheManager' = get_cache_factory_instance().get_manager("manga_list")
        self.translation_cache_manager: CacheInterface = get_cache_factory_instance().get_manager("translation")
        self.update_queue = asyncio.Queue()
        self.current_manga: MangaInfo | None = None
        log.info("MangaManager (v2) 初始化完成。")
            
    def save_config(self):
        """保存配置到文件"""
        try:
            config.save()
            log.info("配置已保存")
        except Exception as e:
            log.error(f"保存配置时发生错误: {str(e)}")
            
    def create_translator(self):
        """根据配置创建翻译器实例"""
        try:
            translator_type = config.translator_type.value
            log.info(f"创建翻译器: {translator_type}")
            
            if translator_type == "智谱":
                return TranslatorFactory.create_translator(
                    translator_type=translator_type,
                    api_key=config.zhipu_api_key.value,
                    model=config.zhipu_model.value
                )
            elif translator_type == "Google":
                return TranslatorFactory.create_translator(
                    translator_type=translator_type,
                    api_key=config.google_api_key.value
                )
            else:
                log.warning(f"未知的翻译器类型: {translator_type}，使用Google翻译作为默认选项")
                return TranslatorFactory.create_translator("Google")
        except Exception as e:
            log.error(f"创建翻译器时发生错误: {str(e)}，使用Google翻译作为备选")
            return TranslatorFactory.create_translator("Google")
            
    def clear_translation_cache(self):
        """清空翻译缓存"""
        try:
            self.translation_cache_manager.clear()
            log.info("翻译缓存已通过 TranslationCacheManager 清空")
        except Exception as e:
            log.error(f"通过 TranslationCacheManager 清空翻译缓存时发生错误: {str(e)}")
            
    async def clear_manga_cache(self):
        """清空漫画扫描缓存"""
        try:
            await self.manga_repo.clear()
            log.info("漫画扫描缓存已通过 MangaListCacheManager (manga_repo) 清空")
        except Exception as e:
            log.error(f"通过 MangaListCacheManager (manga_repo) 清空漫画扫描缓存时发生错误: {str(e)}")

    async def clear_all_data(self):
        """清空数据库中的所有漫画数据"""
        log.info("开始清空所有漫画数据...")
        await self.manga_repo.clear()
        self.current_manga = None
        
        config.current_manga_path.value = ""
        config.current_page.value = 0
        self.save_config()

        # 假设 translation_cache_manager.clear() 也是异步的，如果不是，需要进一步修改
        # 在这个重构阶段，我们先保持调用接口不变，但假设其行为是异步的
        # 如果 translation_cache_manager 不是异步的，正确的做法是 await asyncio.to_thread(self.translation_cache_manager.clear)
        self.clear_translation_cache()

        self._emit_event('data_loaded', {'manga_count': 0, 'tags_count': 0})
        log.info("所有漫画数据已清空。")

    async def add_manga_from_path(self, path: str):
        """扫描路径，并将发现的漫画信息存入数据库。"""
        if not os.path.exists(path):
            log.error(f"路径不存在，无法添加: {path}")
            return

        self._emit_event('data_loading')
        log.info(f"开始扫描路径并更新数据库: {path}")

        try:
            # 1. 扫描文件系统获取 MangaInfo 对象列表
            newly_scanned_mangas = await asyncio.to_thread(self._scan_and_load_mangas, path)

            if not newly_scanned_mangas:
                log.warning(f"路径 {path} 中未找到有效漫画。")
                manga_count = await self.get_manga_count()
                tags_count = await self.get_tags_count()
                self._emit_event('data_loaded', {'manga_count': manga_count, 'tags_count': tags_count})
                return
            
            # 2. 将每个 MangaInfo 对象交给 Repository 处理
            await self.manga_repo.add_or_update_manga_batch(newly_scanned_mangas)

            log.info(f"路径 {path} 的数据库更新完成。")
            # 3. 发送一个简单的通知，让前端知道需要刷新了
            manga_count = await self.get_manga_count()
            tags_count = await self.get_tags_count()
            self._emit_event('data_loaded', {'manga_count': manga_count, 'tags_count': tags_count})

        except Exception as e:
            error_msg = f"从路径 {path} 添加漫画时发生错误: {e}"
            log.error(error_msg, exc_info=True)
            self._emit_event('data_load_failed', {'error': error_msg})

    def _scan_and_load_mangas(self, root_path: str) -> List[MangaInfo]:
        """
        扫描路径并使用新架构加载漫画。
        """
        loaded_mangas = []
        
        image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

        if os.path.isfile(root_path):
            if root_path.lower().endswith('.zip'):
                manga = self._load_single_manga(root_path)
                if manga:
                    loaded_mangas.append(manga)
            else:
                 log.warning(f"不支持的单个文件扫描类型: {root_path}")
            return loaded_mangas
            
        for root, dirs, files in os.walk(root_path):
            # 1. 处理ZIP文件
            for file in files:
                if file.lower().endswith(".zip"):
                    full_path = os.path.join(root, file)
                    manga = self._load_single_manga(full_path)
                    if manga:
                        loaded_mangas.append(manga)
            
            # 2. 处理图片文件夹
            if any(f.lower().endswith(tuple(image_extensions)) for f in files):
                manga = self._load_single_manga(root)
                if manga:
                    loaded_mangas.append(manga)

            dirs[:] = [d for d in dirs if not os.path.isdir(os.path.join(root, d)) or not any(f.lower().endswith(tuple(image_extensions)) for f in os.listdir(os.path.join(root, d)))]

        return loaded_mangas

    def _load_single_manga(self, path: str) -> MangaInfo | None:
        """使用新架构加载单个漫画"""
        try:
            log.info(f"[_load_single_manga] 收到路径: '{path}'")
            data_source = DataSourceFactory.create(path)
            if not data_source:
                log.error(f"[_load_single_manga] DataSourceFactory failed to create a source for path: {path}")
                return None
            
            properties = data_source.get_properties()
            log.info(f"[_load_single_manga] 从数据源收到的属性: {properties}")

            if not properties:
                log.warning(f"数据源无效，跳过: {path}")
                return None

            file_basename = os.path.basename(path)
            title, tags = MetadataParser.parse(file_basename)

            manga = MangaInfo(
                file_path=path,
                title=title,
                tags=tags,
                file_size=properties.get('file_size', 0),
                last_modified=properties.get('last_modified', 0.0),
                total_pages=properties.get('total_pages', 0),
                pages=properties.get('pages', []),
                file_type=properties.get('file_type', 'unknown')
            )
            
            if config.enable_dimension_analysis.value and manga.page_dimensions:
                 manga.analyze_page_dimensions()

            if manga.is_valid:
                log.info(f"成功加载漫画: {manga.title} ({manga.file_path})")
                return manga
            else:
                log.warning(f"加载的漫画无效，已跳过: {path}, Tags: {tags}")
                return None

        except Exception as e:
            log.error(f"加载单个漫画失败: {path}, 原因: {e}", exc_info=True)
            return None

    async def get_manga_list(self, **kwargs) -> List[Dict]:
        """从数据库获取用于显示的漫画列表"""
        return await self.manga_repo.get_manga_list_for_display(**kwargs)

    async def get_manga_by_path(self, file_path: str) -> Optional[MangaInfo]:
        """从数据库获取单个漫画的完整信息"""
        return await self.manga_repo.get_manga_by_path(file_path)

    async def get_all_tags(self) -> List[str]:
        """从数据库获取所有标签"""
        return await self.manga_repo.get_all_tags()

    async def get_manga_count(self) -> int:
        """获取数据库中的漫画总数"""
        return await self.manga_repo.get_manga_count()

    async def get_tags_count(self) -> int:
        """获取数据库中的标签总数"""
        return len(await self.manga_repo.get_all_tags())

    def _emit_event(self, event_type: str, data: dict = None):
        """将事件放入异步队列"""
        event = {'type': event_type, 'data': data or {}}
        try:
            self.update_queue.put_nowait(event)
        except asyncio.QueueFull:
            log.warning(f"MangaManager 事件队列已满，无法发送事件: {event_type}")

    def change_page(self, page_number):
        if self.current_manga is None:
            log.warning("未选择漫画，无法改变页码")
            return

        total_pages = self.current_manga.total_pages
        if 0 <= page_number < total_pages:
            config.current_page.value = page_number
            # self.page_changed.emit(page_number) # 页面切换暂时不广播
        else:
            log.warning(f"页码超出范围: {page_number + 1}, 总页数: {total_pages}")

    # TODO: [重构] 以下方法 (`filter_manga_by_tags`, `translate_titles`, `optimize_tags`, `analyze_and_merge_tags`)
    # 已被移除，因为它们依赖于一个内存中的 manga_list，这与新的数据库驱动架构不兼容。
    # 过滤应通过 get_manga_list(tag_filters=...) 直接在数据库层面完成。
    # 翻译和标签优化需要重新设计为对数据库进行操作的独立批处理过程。

    def rename_manga_file(self, manga: MangaInfo, new_name: str):
        # TODO: [重构] 此功能的实现需要一个能在数据库中更新主键（file_path）的 repository 方法。
        # 这通常需要 "DELETE old" + "INSERT new" 事务操作。
        # 在 repository 层实现该功能前，此方法暂时禁用。
        log.warning("rename_manga_file 功能正在重构中，暂时禁用。")
        return False
        # old_path = manga.file_path
        # new_path = ...
        # self.manga_repo.rename_manga(old_path, new_path, new_name)
        # self._emit_event(...)

    async def set_current_manga(self, manga):
        if manga == self.current_manga:
            return
            
        log.info(f"切换当前漫画: {manga.title if manga else 'None'}")
        
        if manga and not os.path.exists(manga.file_path):
            log.warning(f"漫画文件不存在: {manga.file_path}，将从数据库中移除。")
            # TODO: [重构] 需要一个 repository 方法来从数据库中删除漫画。
            # await self.manga_repo.delete_manga_by_path(manga.file_path)
            self.current_manga = None
            config.current_manga_path.value = ""
            self._emit_event('current_manga_changed', {'manga': None})
            manga_count = await self.get_manga_count()
            tags_count = await self.get_tags_count()
            self._emit_event('data_loaded', {'manga_count': manga_count, 'tags_count': tags_count})
            return
        
        self.current_manga = manga
        new_path = manga.file_path if manga else ""
        if config.current_manga_path.value != new_path:
            config.current_manga_path.value = new_path
            self.change_page(0)

        self._emit_event('current_manga_changed', {'manga': manga.__dict__ if manga else None})

    async def get_manga_info_by_path(self, file_path: str) -> MangaInfo | None:
        """通过文件路径从数据库查找漫画信息 (get_manga_by_path 的别名)"""
        return await self.manga_repo.get_manga_by_path(file_path)

    async def set_current_manga_by_path(self, file_path: str):
        found_manga = await self.get_manga_info_by_path(file_path)
        if found_manga:
            await self.set_current_manga(found_manga)
            self.change_page(config.current_page.value)
