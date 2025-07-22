# file: core/core_cache/translation_cache.py
"""
聚合式翻译结果缓存管理器
"""
import os
import json
import logging
from typing import Any, Optional, Dict
from filelock import FileLock

from .cache_interface import CacheInterface
from core.ai_translator.data_models import ImageTranslationResult

CACHE_DIR = "cache/translation_cache"

class TranslationCacheManager(CacheInterface):
    """
    一个聚合式的、基于JSON文件的缓存管理器。
    每本漫画的所有翻译结果存储在同一个JSON文件中。
    """

    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        logging.info(f"TranslationCacheManager 初始化完成，缓存目录: {self.cache_dir}")

    def _get_filepath(self, master_key: str) -> str:
        """根据漫画主键生成缓存文件路径。"""
        return os.path.join(self.cache_dir, f"{master_key}.json")

    def get(self, key: str, **kwargs) -> Optional[Any]:
        """
        从指定漫画的缓存文件中获取某一页的翻译结果。

        Args:
            key (str): 漫画的主键 (master_key)。
            **kwargs: 必须包含 page_index。
        """
        page_index = kwargs.get("page_index")

        if page_index is None:
            logging.error("获取翻译缓存时缺少必要参数 (page_index)。")
            return None

        filepath = self._get_filepath(key)
        if not os.path.exists(filepath):
            return None

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            page_key = str(page_index)
            page_data = cache_data.get(page_key)

            if page_data:
                # 返回整个列表，因为facade期望的是列表
                return [ImageTranslationResult.from_dict(page_data)]
            return None
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"读取或解析缓存文件失败: {filepath}, 错误: {e}")
            return None

    def set(self, key: str, data: Any, **kwargs) -> None:
        """
        将某一页的翻译结果设置到指定漫画的缓存文件中。

        Args:
            key (str): 漫画的主键 (master_key)。
            data (Any): 要缓存的数据 (通常是 ImageTranslationResult 列表)。
            **kwargs: 必须包含 page_index。
        """
        page_index = kwargs.get("page_index")

        if page_index is None or not data:
            logging.error("设置翻译缓存时缺少必要参数 (page_index, data)。")
            return
        
        # Facade 总是返回一个列表，我们只缓存第一个元素
        if isinstance(data, list) and len(data) > 0:
            result_to_cache = data[0]
        else:
            logging.warning("设置缓存时收到的数据格式不正确或为空。")
            return

        filepath = self._get_filepath(key)
        lock_path = f"{filepath}.lock"

        with FileLock(lock_path):
            try:
                cache_data: Dict[str, Any] = {}
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        # 避免读取空文件时出错
                        content = f.read()
                        if content:
                            cache_data = json.loads(content)

                page_key = str(page_index)
                cache_data[page_key] = result_to_cache.to_dict()

                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                logging.info(f"缓存已更新: master_key='{key}', page={page_index}")

            except (json.JSONDecodeError, IOError) as e:
                logging.error(f"写入或更新缓存文件失败: {filepath}, 错误: {e}")

    def delete(self, key: str) -> None:
        """删除指定主键的整个漫画缓存文件。"""
        filepath = self._get_filepath(key)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                logging.info(f"漫画缓存文件已删除: master_key='{key}'")
            except OSError as e:
                logging.error(f"删除漫画缓存文件失败: {filepath}, 错误: {e}")

    def clear(self) -> None:
        """清空所有翻译缓存。"""
        for filename in os.listdir(self.cache_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.cache_dir, filename)
                try:
                    os.remove(filepath)
                except OSError as e:
                    logging.error(f"清空缓存时删除文件失败: {filepath}, 错误: {e}")
        logging.info("所有翻译缓存已清空。")

    def close(self) -> None:
        """基于文件的缓存无需关闭资源。"""
        pass

    def get_cache_size_bytes(self) -> int:
        """获取缓存目录的总大小。"""
        total_size = 0
        try:
            for f in os.listdir(self.cache_dir):
                if f.endswith(".json"):
                    fp = os.path.join(self.cache_dir, f)
                    if not os.path.islink(fp):
                        total_size += os.path.getsize(fp)
        except OSError as e:
            logging.error(f"计算缓存大小时出错: {e}")
        return total_size
    
    def generate_key(self, **kwargs) -> str:
        """此方法由 cache_key_generator.py 统一管理，这里不实现。"""
        raise NotImplementedError("Key generation is handled by CacheKeyGenerator.")
