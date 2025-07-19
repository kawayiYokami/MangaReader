#!/usr/bin/env python3
"""
Manga Page Loader - V1

独立的漫画页面加载器，采用同步阻塞模型。
"""
import asyncio
import base64
import logging
from typing import Optional

from core.core_cache.cache_factory import get_cache_factory_instance
from core.core_cache.page_cache import PageCache
from core.core_cache.thumbnail_cache import ThumbnailCache # 引入ThumbnailCache
from core.core_cache.cache_key_generator import CacheKeyGenerator
from core.image import processor
from core.manga.policy_constants import POLICY_PENDING, POLICY_CACHED, POLICY_NOT_REQUIRED
from core.manga.data_source import DataSourceFactory


class MangaPageLoader:
    """
    负责根据缓存策略获取页面。
    如果需要缓存但缓存不存在，则同步生成缓存，并从缓存中返回数据。
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.logger = logging.getLogger(self.__class__.__name__)
            
            # 依赖注入
            self.policy_manager = get_cache_factory_instance().get_manager("page_policy")
            self.page_cache: PageCache = get_cache_factory_instance().get_manager("page_cache")
            self.thumbnail_cache: ThumbnailCache = get_cache_factory_instance().get_manager("thumbnail_cache")
            # 移除 core_interface
            
            self._initialized = True
            self.logger.info("MangaPageLoader (同步模型) 初始化完成。")

    async def get_original_page(self, manga_path: str, page_index: int) -> Optional[bytes]:
        """
        总是直接获取、返回原始的、未经处理的页面图像数据。
        """
        data_source = DataSourceFactory.create(manga_path)
        if not data_source:
            self.logger.error(f"无法为路径创建数据源: {manga_path}")
            return None
        
        # DataSource 直接返回 bytes
        return data_source.get_page_image_data(page_index)


    async def _manga_requires_caching(self, manga_path: str) -> bool:
        """
        判定指定漫画是否需要缓存。
        如果策略未知，则根据预存的分析数据进行决策，并回写策略。
        """
        from core.config import config
        if not config.page_cache_enabled.value:
            return False
            
        try:
            master_key = CacheKeyGenerator.generate_master_key_for_path(manga_path)
            if not master_key: return False

            metadata_entry = self.thumbnail_cache.metadata.get(master_key)
            if not metadata_entry or "analysis" not in metadata_entry:
                self.logger.info(f"漫画 {manga_path} 在ThumbnailCache中无分析结果，禁用缓存。")
                return False

            analysis = metadata_entry["analysis"]
            policy = analysis.get("policy")

            # 如果策略已知，直接返回结果
            if policy == "PROCESS": return True
            if policy == "SKIP": return False

            # 如果策略为 UNKNOWN，则进行决策
            if policy == "UNKNOWN":
                self.logger.info(f"策略未知，开始为 {manga_path} 进行页面缓存决策...")
                
                # 从预存数据中获取分析结果
                ratio = analysis.get("compression_ratio", 1.0)
                size_bytes = analysis.get("first_page_size", 0)
                dims = analysis.get("first_page_dimensions", (0, 0))

                # 从配置中获取决策阈值
                from core.config import config
                ratio_threshold = config.page_cache_decision_ratio.value
                size_threshold_bytes = config.page_cache_decision_size_mb.value * 1024 * 1024
                dim_threshold = config.page_cache_decision_dimension.value

                # 根据配置的规则进行决策
                should_process = False
                if ratio < ratio_threshold:
                    should_process = True
                elif size_bytes > size_threshold_bytes:
                    should_process = True
                elif dims[0] > dim_threshold or dims[1] > dim_threshold:
                    should_process = True
                
                # 最终决策
                new_policy = "PROCESS" if should_process else "SKIP"
                self.logger.info(f"决策完成: {manga_path} 的页面缓存策略为 {new_policy}")

                # 回写策略到ThumbnailCache的元数据中
                self.thumbnail_cache.metadata[master_key]["analysis"]["policy"] = new_policy
                self.thumbnail_cache._save_metadata()
                
                return should_process
            
            # 对于其他未知策略值，默认为不处理
            return False

        except Exception as e:
            self.logger.error(f"查询漫画缓存需求时出错: {manga_path}, Error: {e}", exc_info=True)
            return False

    async def get_page(self, manga_path: str, page_index: int) -> Optional[bytes]:
        """
        根据缓存策略获取页面。如果需要缓存但缓存不存在，则同步生成缓存，并从缓存中返回数据。
        """
        # 1. 判定此漫画是否需要走缓存流程
        if not await self._manga_requires_caching(manga_path):
            return await self.get_original_page(manga_path, page_index)

        # 2. 漫画需要缓存，直接检查此页面的缓存文件
        cached_data = self.page_cache.get_page(manga_path, page_index)
        if cached_data:
            return cached_data
            
        # 3. 缓存未命中，调用内部方法生成缓存
        cache_generated = await self._generate_cache(manga_path, page_index)

        # 4. 根据生成结果，自行获取
        if cache_generated:
            return self.page_cache.get_page(manga_path, page_index)
        else:
            self.logger.error(f"缓存生成失败，降级为获取原图: {manga_path} [Page {page_index}]")
            return await self.get_original_page(manga_path, page_index)

    async def _generate_cache(self, manga_path: str, page_index: int) -> bool:
        """
        生成缓存并返回是否成功。
        """
        self.logger.info(f"开始为页面生成缓存: {manga_path} [Page {page_index}]")
        original_bytes = await self.get_original_page(manga_path, page_index)
        if not original_bytes:
            self.logger.error("无法获取原图，生成缓存失败。")
            return False
        
        try:
            img = processor.read_image(original_bytes)
            if img is None: raise ValueError("无法解码原图")

            from core.config import config
            standard_height = config.page_cache_standard_height.value
            
            if img.shape[0] > standard_height:
                scale = standard_height / img.shape[0]
                new_width = int(img.shape[1] * scale)
                scaled_img = processor.resize(img, (new_width, standard_height))
                if scaled_img is None: raise ValueError("图像缩放失败")
                processed_bytes = processor.write_image(scaled_img, ext='.webp', quality=config.page_cache_quality.value)
            else:
                processed_bytes = processor.write_image(img, ext='.webp', quality=config.page_cache_quality.value)

            if not processed_bytes: raise ValueError("编码为WEBP失败")
        except Exception as e:
            self.logger.error(f"处理图像时出错: {e}", exc_info=True)
            return False

        self.page_cache.store_page(manga_path, page_index, processed_bytes)
        
        # 缓存生成后，更新页面策略为CACHED
        page_policy = await self.policy_manager.get_policy(manga_path, page_index)
        if page_policy == POLICY_PENDING:
            await self.policy_manager.update_policy_to_cached(manga_path, page_index)
        
        self.logger.info(f"页面缓存生成成功: {manga_path} [Page {page_index}]")
        return True


def get_page_loader() -> MangaPageLoader:
    """获取全局 MangaPageLoader 实例"""
    return MangaPageLoader()
