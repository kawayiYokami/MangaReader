import os
import json
import sqlite3
from typing import Any, List, Optional, Dict, Tuple # Added Dict, Tuple, sqlite3
from utils import manga_logger as log
from core.cache_interface import CacheInterface

# Cache directory and database file name
CACHE_DIR = "app/config"
DB_NAME = "manga_list_cache.db"
DB_PATH = os.path.join(CACHE_DIR, DB_NAME)
TABLE_NAME = "manga_list_cache"

class MangaListCacheManager(CacheInterface):
    """漫画扫描结果缓存管理类，基于SQLite数据库。"""

    def __init__(self, db_path: str = DB_PATH):
        """初始化缓存管理器"""
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._ensure_cache_dir_exists()
        self._init_db()
        log.info(f"MangaListCacheManager 初始化完成，数据库路径: {self.db_path}")

    def _ensure_cache_dir_exists(self):
        """确保缓存目录存在"""
        directory = os.path.dirname(self.db_path)
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
                log.info(f"创建缓存目录: {directory}")
            except OSError as e:
                log.error(f"创建缓存目录 {directory} 失败: {e}")
                raise

    def _connect(self) -> sqlite3.Connection:
        """连接到 SQLite 数据库"""
        if self.conn is None or self._is_connection_closed():
            try:
                self.conn = sqlite3.connect(self.db_path)
                self.conn.row_factory = sqlite3.Row # Access columns by name
            except sqlite3.Error as e:
                log.error(f"连接到数据库 {self.db_path} 失败: {e}")
                raise
        return self.conn

    def _is_connection_closed(self) -> bool:
        """检查数据库连接是否已关闭"""
        if self.conn is None:
            return True
        try:
            self.conn.execute("SELECT 1").fetchone()
            return False
        except (sqlite3.ProgrammingError, sqlite3.OperationalError): # Connection closed or unusable
            return True

    def _init_db(self):
        """初始化数据库和表"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                directory_path TEXT PRIMARY KEY,
                manga_data TEXT NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.commit()
            log.info(f"漫画列表缓存数据库表 '{TABLE_NAME}' 已准备就绪")
        except sqlite3.Error as e:
            log.error(f"初始化数据库表 {TABLE_NAME} 失败: {e}")

    def generate_key(self, directory_path: str, *args, **kwargs) -> str:
        """对于漫画列表缓存，键就是目录路径。"""
        if not isinstance(directory_path, str):
            log.error("directory_path 必须是字符串")
            raise TypeError("directory_path 必须是字符串")
        return directory_path

    def get(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """获取指定目录（键）的漫画列表缓存。"""
        if not isinstance(key, str):
            log.warning(f"MangaListCacheManager.get 接收到非字符串键: {key}")
            return None
        
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"SELECT manga_data FROM {TABLE_NAME} WHERE directory_path = ?", (key,))
            row = cursor.fetchone()
            if row:
                manga_data_json = row["manga_data"]
                return json.loads(manga_data_json)
            return None
        except sqlite3.Error as e:
            log.error(f"从漫画列表缓存获取数据失败 (键: {key}): {e}")
            return None
        except json.JSONDecodeError as e:
            log.error(f"解析缓存的漫画列表数据失败 (键: {key}): {e}")
            return None

    def set(self, key: str, data: List[Any], **kwargs) -> None:
        """更新指定目录（键）的漫画列表缓存。"""
        if not isinstance(key, str):
            log.error(f"MangaListCacheManager.set 接收到非字符串键: {key}")
            return

        serializable_list: List[Dict[str, Any]] = []
        for manga_item in data:
            if isinstance(manga_item, dict):
                serializable_list.append(manga_item)
            elif hasattr(manga_item, "file_path") and hasattr(manga_item, "last_modified"):
                manga_info = {
                    "file_path": manga_item.file_path,
                    "title": getattr(manga_item, "title", os.path.basename(manga_item.file_path)),
                    "tags": list(getattr(manga_item, "tags", [])),
                    "total_pages": getattr(manga_item, "total_pages", 0),
                    "is_valid": getattr(manga_item, "is_valid", False),
                    "last_modified": manga_item.last_modified,
                    "pages": getattr(manga_item, "pages", []),
                    "is_translated": getattr(manga_item, "is_translated", False)
                }
                serializable_list.append(manga_info)
            else:
                log.warning(f"无法序列化漫画项目: {manga_item} (键: {key})")
        
        try:
            manga_data_json = json.dumps(serializable_list, ensure_ascii=False)
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"""
            INSERT OR REPLACE INTO {TABLE_NAME} (directory_path, manga_data, last_updated)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, manga_data_json))
            conn.commit()
            log.info(f"已更新目录 {key} 的漫画列表缓存，共 {len(serializable_list)} 本漫画")
        except sqlite3.Error as e:
            log.error(f"设置漫画列表缓存数据失败 (键: {key}): {e}")
        except TypeError as e: # Error during json.dumps
            log.error(f"序列化漫画列表数据失败 (键: {key}): {e}")

    def delete(self, key: str) -> None:
        """删除指定目录（键）的漫画列表缓存。"""
        if not isinstance(key, str):
            log.error(f"MangaListCacheManager.delete 接收到非字符串键: {key}")
            return
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE directory_path = ?", (key,))
            conn.commit()
            if cursor.rowcount > 0:
                log.info(f"已删除目录 {key} 的漫画列表缓存")
            else:
                log.info(f"尝试删除不存在的漫画列表缓存键: {key}")
        except sqlite3.Error as e:
            log.error(f"删除漫画列表缓存数据失败 (键: {key}): {e}")

    def clear(self) -> None:
        """清空所有漫画列表缓存"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {TABLE_NAME}")
            conn.commit()
            log.info(f"漫画列表缓存表 '{TABLE_NAME}' 已清空")
        except sqlite3.Error as e:
            log.error(f"清空漫画列表缓存失败: {e}")

    def close(self) -> None:
        """关闭数据库连接。"""
        if self.conn:
            try:
                self.conn.close()
                self.conn = None
                log.info("漫画列表缓存数据库连接已关闭")
            except sqlite3.Error as e:
                log.error(f"关闭漫画列表数据库连接失败: {e}")

    def __del__(self):
        self.close()

    def is_manga_modified(self, file_path: str) -> bool:
        """
        检查漫画文件是否被修改。
        注意: 此方法需要知道漫画文件所属的目录键，或者遍历所有缓存的目录来查找文件。
        当前实现需要调用者提供目录键，或者自行获取。
        为了简单起见，这里假设我们能获取到包含该文件的目录的缓存数据。
        如果需要全局检查，调用者需要迭代所有已知的目录键。
        """
        if not os.path.exists(file_path):
            return True  # 文件不存在，视为已修改

        try:
            current_mtime = os.path.getmtime(file_path)
        except OSError:
            log.warning(f"无法获取文件修改时间: {file_path}，视为已修改")
            return True

        # This method's effectiveness depends on how it's used.
        # If checking against a specific directory's cache:
        # parent_dir = os.path.dirname(file_path)
        # cached_manga_list = self.get(parent_dir)
        # if cached_manga_list:
        #     for manga_info in cached_manga_list:
        #         if manga_info.get("file_path") == file_path:
        #             return current_mtime > manga_info.get("last_modified", 0)
        # return True # Not found in specific directory's cache or cache miss

        # If iterating all cached directories (less efficient, as in original JSON version):
        log.warning("is_manga_modified: 正在遍历所有缓存目录检查文件修改状态，可能效率低下。")
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"SELECT manga_data FROM {TABLE_NAME}")
            all_cached_dirs = cursor.fetchall()
            for row in all_cached_dirs:
                manga_list_for_dir_json = row["manga_data"]
                try:
                    manga_list_for_dir = json.loads(manga_list_for_dir_json)
                    for manga_info in manga_list_for_dir:
                        if manga_info.get("file_path") == file_path:
                            return current_mtime > manga_info.get("last_modified", 0)
                except json.JSONDecodeError:
                    log.error(f"解析缓存的漫画列表数据时出错（在 is_manga_modified 中）")
                    continue # Skip corrupted entry
            return True # 缓存中没有找到，视为已修改
        except sqlite3.Error as e:
            log.error(f"is_manga_modified 查询数据库时出错: {e}")
            return True # Error, assume modified