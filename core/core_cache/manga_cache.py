import os
import json
import sqlite3
from typing import Any, List, Optional, Dict, Tuple # Added Dict, Tuple, sqlite3
from utils import manga_logger as log
from core.core_cache.cache_interface import CacheInterface

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
        self.conn: Optional[sqlite3.Connection] = None
        self._ensure_cache_dir_exists()
        self._init_db()
        log.info(f"MangaListCacheManager 初始化完成，数据库路径: {self.db_path}")

    def _ensure_cache_dir_exists(self):
        """确保缓存目录存在"""
        # 如果是内存数据库，则无需创建目录
        if self.db_path == ":memory:":
            return
            
        directory = os.path.dirname(self.db_path)
        if directory and not os.path.exists(directory):
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
                library_id TEXT PRIMARY KEY,
                manga_data TEXT NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.commit()
            log.info(f"漫画列表缓存数据库表 '{TABLE_NAME}' 已准备就绪")
        except sqlite3.Error as e:
            log.error(f"初始化数据库表 {TABLE_NAME} 失败: {e}")

    def generate_key(self, *args, **kwargs) -> str:
        """
        对于统一漫画库缓存，键是固定的。
        忽略所有参数，始终返回代表主库的唯一键。
        """
        return LIBRARY_KEY

    def get(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """
        获取主漫画库的缓存。
        注意：'key' 参数被忽略，因为此缓存只管理一个单一的实体。
        """
        # 始终使用固定的库键
        library_key = LIBRARY_KEY
        
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"SELECT manga_data FROM {TABLE_NAME} WHERE library_id = ?", (library_key,))
            row = cursor.fetchone()
            if row:
                manga_data_json = row["manga_data"]
                return json.loads(manga_data_json)
            log.info(f"漫画库缓存未找到 (键: {library_key})")
            return None
        except sqlite3.Error as e:
            log.error(f"从漫画列表缓存获取数据失败 (键: {library_key}): {e}")
            return None
        except json.JSONDecodeError as e:
            log.error(f"解析缓存的漫画列表数据失败 (键: {library_key}): {e}")
            return None

    def set(self, key: str, data: List[Any], **kwargs) -> None:
        """
        更新主漫画库的缓存。
        注意：'key' 参数被忽略，因为此缓存只管理一个单一的实体。
        """
        library_key = LIBRARY_KEY # 始终使用固定的库键

        serializable_list: List[Dict[str, Any]] = []
        for manga_item in data:
            if isinstance(manga_item, dict):
                serializable_list.append(manga_item)
            elif hasattr(manga_item, "file_path") and hasattr(manga_item, "last_modified"):
                # 确保所有值都是JSON可序列化的
                dimension_variance = getattr(manga_item, "dimension_variance", None)
                is_likely_manga = getattr(manga_item, "is_likely_manga", None)

                # 处理特殊的数值类型
                if dimension_variance is not None:
                    try:
                        dimension_variance = float(dimension_variance)
                    except (TypeError, ValueError):
                        dimension_variance = None

                # 确保布尔值是标准Python布尔类型
                if is_likely_manga is not None:
                    is_likely_manga = bool(is_likely_manga)

                manga_info = {
                    "file_path": manga_item.file_path,
                    "title": getattr(manga_item, "title", os.path.basename(manga_item.file_path)),
                    "tags": list(getattr(manga_item, "tags", [])),
                    "total_pages": getattr(manga_item, "total_pages", 0),
                    "is_valid": bool(getattr(manga_item, "is_valid", False)),
                    "last_modified": manga_item.last_modified,
                    "pages": getattr(manga_item, "pages", []),
                    "is_translated": bool(getattr(manga_item, "is_translated", False)),
                    # 页面尺寸分析相关数据
                    "page_dimensions": getattr(manga_item, "page_dimensions", []),
                    "dimension_variance": dimension_variance,
                    "is_likely_manga": is_likely_manga
                }
                serializable_list.append(manga_info)
            else:
                log.warning(f"无法序列化漫画项目: {manga_item} (库: {library_key})")
        
        try:
            manga_data_json = json.dumps(serializable_list, ensure_ascii=False)
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"""
            INSERT OR REPLACE INTO {TABLE_NAME} (library_id, manga_data, last_updated)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (library_key, manga_data_json))
            conn.commit()
            log.info(f"已更新主漫画库缓存，共 {len(serializable_list)} 本漫画")
        except sqlite3.Error as e:
            log.error(f"设置主漫画库缓存失败 (键: {library_key}): {e}")
        except TypeError as e: # Error during json.dumps
            log.error(f"序列化主漫画库数据失败 (键: {library_key}): {e}")

    def delete(self, key: str) -> None:
        """
        删除主漫画库的缓存。
        注意：'key' 参数被忽略，此操作将始终删除主库。
        """
        library_key = LIBRARY_KEY
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE library_id = ?", (library_key,))
            conn.commit()
            if cursor.rowcount > 0:
                log.info(f"已删除主漫画库缓存 (键: {library_key})")
            else:
                log.info(f"尝试删除主漫画库缓存，但缓存不存在。")
        except sqlite3.Error as e:
            log.error(f"删除主漫画库缓存失败 (键: {library_key}): {e}")

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

    def get_all_entries_for_display(self) -> List[Dict[str, Any]]:
        """
        获取主漫画库的缓存条目信息，用于在界面中显示。
        """
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"SELECT library_id, last_updated FROM {TABLE_NAME}")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            log.error(f"获取所有漫画列表缓存条目失败: {e}")
            return []

    def get_cache_size_bytes(self) -> int:
        """
        获取漫画列表缓存的总大小（字节）。
        返回SQLite数据库文件的大小。
        """
        try:
            if os.path.exists(self.db_path):
                size_bytes = os.path.getsize(self.db_path)
                log.debug(f"漫画列表缓存数据库大小: {size_bytes} 字节")
                return size_bytes
            else:
                log.debug("漫画列表缓存数据库文件不存在")
                return 0
        except OSError as e:
            log.error(f"获取漫画列表缓存大小失败: {e}")
            return 0

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
        """检查指定漫画文件相对于缓存中的记录是否已被修改。"""
        if not os.path.exists(file_path):
            return True  # 文件不存在，视为已修改

        try:
            current_mtime = os.path.getmtime(file_path)
        except OSError:
            log.warning(f"无法获取文件修改时间: {file_path}，视为已修改")
            return True

        cached_library = self.get(LIBRARY_KEY)
        if cached_library:
            for manga_info in cached_library:
                if manga_info.get("file_path") == file_path:
                    # 找到记录，比较修改时间
                    return current_mtime > manga_info.get("last_modified", 0)
        
        # 如果缓存中没有找到该文件，视为新文件/已修改
        return True