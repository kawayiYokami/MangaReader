import os
import json
import sqlite3
import asyncio
import logging
from typing import Any, List, Optional, Dict, Tuple, TYPE_CHECKING # Added Dict, Tuple, sqlite3
from core.core_cache.cache_interface import CacheInterface

if TYPE_CHECKING:
    from core.manga.manga_model import MangaInfo


# Cache directory and database file name
CACHE_DIR = "app/config"
DB_NAME = "manga_list_cache.db"
DB_PATH = os.path.join(CACHE_DIR, DB_NAME)
TABLE_NAME = "manga_list_cache"
LIBRARY_KEY = "user_main_library" # 代表整个用户库的唯一键

class MangaListCacheManager(CacheInterface):
    """漫画扫描结果缓存管理类，基于SQLite数据库。"""

    def __init__(self, db_path: str = DB_PATH):
        """初始化缓存管理器"""
        self.db_path = db_path
        # self.conn is no longer used. Each thread will have its own connection.
        self._ensure_cache_dir_exists()
        self._init_db()
        logging.info(f"MangaListCacheManager 初始化完成，数据库路径: {self.db_path}")

    def _ensure_cache_dir_exists(self):
        """确保缓存目录存在"""
        # 如果是内存数据库，则无需创建目录
        if self.db_path == ":memory:":
            return
            
        directory = os.path.dirname(self.db_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory)
                logging.info(f"创建缓存目录: {directory}")
            except OSError as e:
                logging.error(f"创建缓存目录 {directory} 失败: {e}")
                raise

    def _init_db(self):
        """
        初始化数据库和所有需要的表。
        此操作在启动时执行，可以是同步的。
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 1. 漫画主表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS mangas (
                file_path TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                last_modified REAL NOT NULL,
                total_pages INTEGER,
                file_size INTEGER,
                file_type TEXT,
                is_valid BOOLEAN,
                pages_json TEXT,
                page_dimensions_json TEXT,
                dimension_variance REAL,
                is_likely_manga BOOLEAN
            )
            """)

            # 2. 标签表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
            """)

            # 3. 漫画与标签的关联表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS manga_tags (
                manga_path TEXT,
                tag_id INTEGER,
                PRIMARY KEY (manga_path, tag_id),
                FOREIGN KEY (manga_path) REFERENCES mangas (file_path) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
            )
            """)
            logging.info("结构化的漫画缓存数据库表已准备就绪。")
        except sqlite3.Error as e:
            logging.error(f"初始化数据库表失败: {e}")


    async def add_or_update_manga_batch(self, mangas: List['MangaInfo']):
        """
        批量添加或更新漫画到数据库。
        使用事务以确保操作的原子性和性能。
        在独立的线程中运行以避免阻塞事件循环。
        """
        from core.manga.manga_model import MangaInfo # 避免循环导入

        def _db_operation():
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    
                    all_tags = set()
                    for manga in mangas:
                        logging.info(f"[CacheManager] Preparing to cache '{manga.file_path}' with last_modified: {manga.last_modified}")
                        all_tags.update(manga.tags)
                    
                    if all_tags:
                        cursor.executemany("INSERT OR IGNORE INTO tags (name) VALUES (?)", [(tag,) for tag in all_tags])
                        
                    manga_data_to_upsert = [
                        (
                            m.file_path, m.title, m.last_modified, m.total_pages, m.file_size, m.file_type,
                            m.is_valid,
                            json.dumps(m.pages) if m.pages else None,
                            json.dumps(m.page_dimensions) if m.page_dimensions else None,
                            m.dimension_variance, m.is_likely_manga
                        ) for m in mangas
                    ]
                    
                    manga_sql = """
                    INSERT INTO mangas (
                        file_path, title, last_modified, total_pages, file_size, file_type,
                        is_valid, pages_json, page_dimensions_json, dimension_variance, is_likely_manga
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(file_path) DO UPDATE SET
                        title = excluded.title, last_modified = excluded.last_modified,
                        total_pages = excluded.total_pages, file_size = excluded.file_size,
                        file_type = excluded.file_type, is_valid = excluded.is_valid,
                        pages_json = excluded.pages_json, page_dimensions_json = excluded.page_dimensions_json,
                        dimension_variance = excluded.dimension_variance, is_likely_manga = excluded.is_likely_manga;
                    """
                    cursor.executemany(manga_sql, manga_data_to_upsert)

                    manga_paths = [m.file_path for m in mangas]
                    placeholders = ','.join('?' for _ in manga_paths)
                    cursor.execute(f"DELETE FROM manga_tags WHERE manga_path IN ({placeholders})", manga_paths)
                    
                    tag_to_id_map = {row['name']: row['id'] for row in cursor.execute("SELECT id, name FROM tags")}
                    
                    manga_tags_to_insert = []
                    for manga in mangas:
                        for tag_name in manga.tags:
                            if tag_id := tag_to_id_map.get(tag_name):
                                manga_tags_to_insert.append((manga.file_path, tag_id))
                    
                    if manga_tags_to_insert:
                        cursor.executemany("INSERT INTO manga_tags (manga_path, tag_id) VALUES (?, ?)", manga_tags_to_insert)

                logging.info(f"成功批量添加/更新 {len(mangas)} 本漫画到数据库。")
            except sqlite3.Error as e:
                logging.error(f"批量更新漫画时发生数据库错误: {e}", exc_info=True)
        
        await asyncio.to_thread(_db_operation)

    async def get_manga_list_for_display(self, sort_by="last_modified DESC", tag_filters: List[str] = None) -> List[Dict]:
        """一个非常高效的查询，直接返回前端所需的数据字典列表"""
        def _db_operation():
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    base_sql = """
                    SELECT
                        m.file_path, m.title, m.last_modified, m.total_pages, m.file_size, m.file_type,
                        GROUP_CONCAT(t.name) as tags
                    FROM mangas m
                    LEFT JOIN manga_tags mt ON m.file_path = mt.manga_path
                    LEFT JOIN tags t ON mt.tag_id = t.id
                    """
                    params = []
                    
                    if tag_filters:
                        placeholders = ','.join('?' for _ in tag_filters)
                        base_sql += f"""
                        WHERE m.file_path IN (
                            SELECT manga_path FROM manga_tags
                            JOIN tags ON manga_tags.tag_id = tags.id
                            WHERE tags.name IN ({placeholders})
                            GROUP BY manga_path
                            HAVING COUNT(DISTINCT tags.name) = ?
                        )
                        """
                        params.extend(tag_filters)
                        params.append(len(tag_filters))

                    base_sql += " GROUP BY m.file_path"

                    allowed_orders = ["last_modified DESC", "last_modified ASC", "title ASC", "title DESC", "file_size DESC", "file_size ASC"]
                    if sort_by in allowed_orders:
                        base_sql += f" ORDER BY {sort_by}"

                    cursor = conn.cursor()
                    cursor.execute(base_sql, params)
                    rows = cursor.fetchall()

                    result = []
                    for row in rows:
                        row_dict = dict(row)
                        row_dict['tags'] = row_dict['tags'].split(',') if row_dict['tags'] else []
                        result.append(row_dict)
                    return result
            except sqlite3.Error as e:
                logging.error(f"从数据库获取漫画列表时出错: {e}", exc_info=True)
                return []
        
        return await asyncio.to_thread(_db_operation)

    async def get_manga_count(self) -> int:
        """获取数据库中漫画的总数"""
        def _db_operation():
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM mangas")
                    count = cursor.fetchone()[0]
                    return count if count is not None else 0
            except sqlite3.Error as e:
                logging.error(f"获取漫画总数时出错: {e}", exc_info=True)
                return 0
        
        return await asyncio.to_thread(_db_operation)

    async def get_all_tags(self) -> List[str]:
        """从 tags 表中获取所有不重复的标签"""
        def _db_operation():
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM tags ORDER BY name")
                    return [row['name'] for row in cursor.fetchall()]
            except sqlite3.Error as e:
                logging.error(f"获取所有标签时出错: {e}", exc_info=True)
                return []
        
        return await asyncio.to_thread(_db_operation)

    async def clear(self) -> None:
        """清空所有漫画相关的表"""
        def _db_operation():
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("DELETE FROM manga_tags")
                    conn.execute("DELETE FROM tags")
                    conn.execute("DELETE FROM mangas")
                logging.info("所有漫画缓存表已清空。")
            except sqlite3.Error as e:
                logging.error(f"清空漫画缓存表时发生错误: {e}")
        
        await asyncio.to_thread(_db_operation)

    def get_cache_size_bytes(self) -> int:
        """
        获取漫画列表缓存的总大小（字节）。
        返回SQLite数据库文件的大小。
        """
        try:
            if os.path.exists(self.db_path):
                size_bytes = os.path.getsize(self.db_path)
                logging.debug(f"漫画列表缓存数据库大小: {size_bytes} 字节")
                return size_bytes
            else:
                logging.debug("漫画列表缓存数据库文件不存在")
                return 0
        except OSError as e:
            logging.error(f"获取漫画列表缓存大小失败: {e}")
            return 0

    def close(self) -> None:
        """
        关闭缓存资源。对于当前的实现，连接是按需创建和销毁的，
        因此这个方法可以为空，但必须存在以满足接口契约。
        """
        pass

    # --- Methods from CacheInterface that are no longer applicable ---
    # The following methods are part of the CacheInterface contract but are
    # not semantically applicable to this specialized repository. They are
    # implemented to raise NotImplementedError to prevent accidental use.

    def generate_key(self, *args, **kwargs) -> str:
        """This method is not applicable to MangaListCacheManager."""
        raise NotImplementedError("MangaListCacheManager does not use generated keys.")

    def get(self, key: str) -> Optional[Any]:
        """Use specific getter methods like get_manga_by_path() instead."""
        raise NotImplementedError("Generic 'get' is not supported. Use specific repository methods.")

    def set(self, key: str, data: Any, **kwargs) -> None:
        """Use specific methods like add_or_update_manga_batch() instead."""
        raise NotImplementedError("Generic 'set' is not supported. Use specific repository methods.")

    def delete(self, key: str) -> None:
        """Deletion should be handled by specific methods, e.g., by manga path."""
        raise NotImplementedError("Generic 'delete' by key is not supported.")

    async def get_manga_by_path(self, file_path: str) -> Optional['MangaInfo']:
        """通过路径高效获取单个漫画的完整信息"""
        from core.manga.manga_model import MangaInfo

        def _db_operation():
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    sql = """
                    SELECT
                        m.*,
                        GROUP_CONCAT(t.name) as tags
                    FROM mangas m
                    LEFT JOIN manga_tags mt ON m.file_path = mt.manga_path
                    LEFT JOIN tags t ON mt.tag_id = t.id
                    WHERE m.file_path = ?
                    GROUP BY m.file_path
                    """
                    cursor = conn.cursor()
                    cursor.execute(sql, (file_path,))
                    row = cursor.fetchone()

                    if not row:
                        return None
                    
                    manga_data = dict(row)
                    
                    pages_json = manga_data.pop('pages_json', None)
                    page_dimensions_json = manga_data.pop('page_dimensions_json', None)
                    
                    manga_data['pages'] = json.loads(pages_json) if pages_json else []
                    manga_data['page_dimensions'] = json.loads(page_dimensions_json) if page_dimensions_json else []
                    
                    tags_str = manga_data.get('tags')
                    manga_data['tags'] = set(tags_str.split(',')) if tags_str else set()

                    return MangaInfo(**manga_data)
            except sqlite3.Error as e:
                logging.error(f"从数据库获取漫画 '{file_path}' 时出错: {e}", exc_info=True)
                return None
        
        return await asyncio.to_thread(_db_operation)