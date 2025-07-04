# core/core_cache/page_policy_cache.py
import sqlite3
import threading
from pathlib import Path
from typing import List, Tuple, Optional, Any
from datetime import datetime
import logging
import os
import asyncio

from core.core_cache.cache_interface import CacheInterface
from core.manga.policy_constants import POLICY_CACHED

# 线程局部存储，确保每个线程拥有自己独立的数据库连接
thread_local = threading.local()

class PagePolicyCacheManager(CacheInterface):
    """
    管理页面预缓存策略。
    此类完全封装了与 'precache_policy.db' 的所有交互，
    包括连接管理、表创建和所有 CRUD 操作。
    它实现了 CacheInterface，使其可以被 CacheFactory 管理。
    """

    def __init__(self, db_path: str = "cache/precache_policy.db"):
        self.logger = logging.getLogger('PagePolicyCacheManager')
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()
        self.logger.info(f"页面策略缓存管理器初始化，数据库路径: {self.db_path.resolve()}")

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(thread_local, 'policy_connection'):
            thread_local.policy_connection = sqlite3.connect(self.db_path, check_same_thread=False)
            thread_local.policy_connection.row_factory = sqlite3.Row
        return thread_local.policy_connection

    def close(self) -> None:
        """关闭当前线程的数据库连接。"""
        if hasattr(thread_local, 'policy_connection'):
            thread_local.policy_connection.close()
            del thread_local.policy_connection

    def _create_tables(self):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS page_policy (
                    manga_path TEXT NOT NULL,
                    page_index INTEGER NOT NULL,
                    policy TEXT NOT NULL,
                    last_updated TIMESTAMP,
                    PRIMARY KEY (manga_path, page_index)
                )
            """)
            conn.commit()
            self.logger.info("表 'page_policy' 已成功创建或确认存在。")
        except sqlite3.Error as e:
            self.logger.error(f"创建 'page_policy' 表时发生错误: {e}")
            raise

    def generate_key(self, **kwargs) -> str:
        """
        必需关键字参数: 'manga_path', 'page_index'
        """
        if 'manga_path' not in kwargs or 'page_index' not in kwargs:
            raise TypeError("generate_key() 缺少必需的关键字参数: 'manga_path' 或 'page_index'")
        
        manga_path = kwargs['manga_path']
        page_index = kwargs['page_index']
        return f"{manga_path}::{page_index}"

    def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError("请使用 get_policy()。")

    def set(self, key: str, data: Any, **kwargs) -> None:
        raise NotImplementedError("请使用 set_policy() 或 set_policies_batch()。")

    def delete(self, key: str) -> None:
        try:
            manga_path, page_index_str = key.split('::', 1)
            page_index = int(page_index_str)
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM page_policy WHERE manga_path = ? AND page_index = ?", (manga_path, page_index))
            conn.commit()
        except (ValueError, IndexError) as e:
            self.logger.error(f"删除策略时提供了无效的键 '{key}': {e}")
        except sqlite3.Error as e:
            self.logger.error(f"删除页面策略时出错 (键: {key}): {e}")

    def clear(self) -> None:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM page_policy")
            conn.commit()
            self.logger.info("已清空 'page_policy' 表。")
        except sqlite3.Error as e:
            self.logger.error(f"清空 'page_policy' 表时出错: {e}")

    def get_cache_size_bytes(self) -> int:
        try:
            return os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        except OSError as e:
            self.logger.error(f"无法获取数据库文件大小: {e}")
            return 0
    
    # --- 专用方法 ---
    
    async def get_policy(self, manga_path: str, page_index: int) -> Optional[str]:
        return await asyncio.to_thread(self._get_policy_sync, manga_path, page_index)

    def _get_policy_sync(self, manga_path: str, page_index: int) -> Optional[str]:
        sql = "SELECT policy FROM page_policy WHERE manga_path = ? AND page_index = ?;"
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(sql, (manga_path, page_index))
            result = cursor.fetchone()
            return result['policy'] if result else None
        except sqlite3.Error as e:
            self.logger.error(f"获取页面策略时出错 (路径: {manga_path}, 页码: {page_index}): {e}")
            return None

    async def set_policy(self, manga_path: str, page_index: int, policy: str):
        await asyncio.to_thread(self._set_policy_sync, manga_path, page_index, policy)

    def _set_policy_sync(self, manga_path: str, page_index: int, policy: str):
        sql = """
            INSERT INTO page_policy (manga_path, page_index, policy, last_updated)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(manga_path, page_index) DO UPDATE SET
                policy = excluded.policy,
                last_updated = excluded.last_updated;
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(sql, (manga_path, page_index, policy, datetime.now()))
            conn.commit()
        except sqlite3.Error as e:
            self.logger.error(f"设置页面策略时出错 (路径: {manga_path}, 页码: {page_index}): {e}")

    async def set_policies_batch(self, policies: List[Tuple[str, int, str]]) -> None:
        await asyncio.to_thread(self._set_policies_batch_sync, policies)

    def _set_policies_batch_sync(self, policies: List[Tuple[str, int, str]]):
        # The incoming policies are now dictionaries, adjust accordingly
        sql = """
            INSERT INTO page_policy (manga_path, page_index, policy, last_updated)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(manga_path, page_index) DO UPDATE SET
                policy = excluded.policy,
                last_updated = excluded.last_updated;
        """
        # 为每个策略添加当前时间
        policies_with_timestamp = [
            (p['manga_path'], p['page_index'], p['policy'], datetime.now())
            for p in policies
        ]
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.executemany(sql, policies_with_timestamp)
            conn.commit()
            self.logger.info(f"批量插入或更新了 {len(policies)} 条页面策略。")
        except sqlite3.Error as e:
            self.logger.error(f"批量设置页面策略时出错: {e}")

    async def update_policy_to_cached(self, manga_path: str, page_index: int):
        """将指定页面的策略更新为 'CACHED'"""
        await self.set_policy(manga_path, page_index, POLICY_CACHED)
