# core/ocr_cache_manager.py
import sqlite3
import json
import os
import hashlib
import logging
from typing import Optional, Any, List, Dict
from .cache_interface import CacheInterface

# Cache directory and database file name
CACHE_DIR = "app/config"
DB_NAME = "ocr_cache.db"
DB_PATH = os.path.join(CACHE_DIR, DB_NAME)
TABLE_NAME = "ocr_cache"

class OcrCacheManager(CacheInterface):
    """OCR结果缓存管理类"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_cache_dir_exists()
        self.conn: Optional[sqlite3.Connection] = None
        self._init_db()
        logging.info(f"OcrCacheManager 初始化完成，数据库路径: {self.db_path}")

    def _ensure_cache_dir_exists(self):
        directory = os.path.dirname(self.db_path)
        if not os.path.exists(directory):
            os.makedirs(directory)

    def _connect(self) -> sqlite3.Connection:
        """连接到 SQLite 数据库"""
        if self.conn is None or self._is_connection_closed():
            try:
                self.conn = sqlite3.connect(self.db_path)
                self.conn.row_factory = sqlite3.Row # Access columns by name
            except sqlite3.Error as e:
                logging.error(f"连接到数据库 {self.db_path} 失败: {e}")
                raise
        return self.conn
    
    def _is_connection_closed(self) -> bool:
        if self.conn is None:
            return True
        try:
            self.conn.execute("SELECT 1")
            return False
        except sqlite3.ProgrammingError:
            return True
        except sqlite3.OperationalError:
            return True

    def _init_db(self):
        """初始化数据库和表，并确保向后兼容。"""
        try:
            conn = self._connect()
            cursor = conn.cursor()

            # 创建表
            cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                manga_path TEXT,
                page_index INTEGER,
                manga_name TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # 检查并添加新列以实现向后兼容
            cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
            columns = [info['name'] for info in cursor.fetchall()]
            
            new_columns = {
                "manga_path": "TEXT",
                "page_index": "INTEGER",
                "manga_name": "TEXT"
            }

            for col, col_type in new_columns.items():
                if col not in columns:
                    try:
                        cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {col} {col_type}")
                        logging.info(f"成功向表 '{TABLE_NAME}' 添加 '{col}' 列。")
                    except sqlite3.OperationalError as e:
                        logging.warning(f"尝试添加 '{col}' 列时出错 (可能是并发操作): {e}")

            conn.commit()
        except sqlite3.Error as e:
            logging.error(f"初始化数据库表 {TABLE_NAME} 失败: {e}")

    def generate_key(self, **kwargs) -> str:
        """
        根据图像路径和页码生成缓存键
        必需关键字参数: 'image_path', 'page_index'
        """
        if 'image_path' not in kwargs or 'page_index' not in kwargs:
            raise TypeError("generate_key() 缺少必需的关键字参数: 'image_path' 或 'page_index'")
            
        key_string = f"path:{kwargs['image_path']}|page:{kwargs['page_index']}"
        return hashlib.sha256(key_string.encode('utf-8')).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """根据键获取缓存数据"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"SELECT value FROM {TABLE_NAME} WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row["value"])
            return None
        except sqlite3.Error as e:
            logging.error(f"从缓存获取数据失败 (键: {key}): {e}")
            return None
        except json.JSONDecodeError:
            logging.error(f"解析缓存的OCR数据失败 (键: {key})，将清除损坏的缓存。")
            self.delete(key)
            return None

    def set(self, key: str, data: Any, manga_path: str, page_index: int, manga_name: Optional[str] = None):
        """
        设置缓存数据，并包含丰富的元数据。
        """
        try:
            value_json = json.dumps(data, ensure_ascii=False)
            conn = self._connect()
            cursor = conn.cursor()
            
            # 如果未提供 manga_name，则从路径中提取
            display_manga_name = manga_name or os.path.basename(manga_path)

            cursor.execute(f"""
            INSERT OR REPLACE INTO {TABLE_NAME} (key, value, manga_path, page_index, manga_name, last_updated)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (key, value_json, manga_path, page_index, display_manga_name))
            conn.commit()
        except sqlite3.Error as e:
            logging.error(f"设置OCR缓存数据失败 (键: {key}): {e}")
        except TypeError as e:
            logging.error(f"序列化OCR数据失败 (键: {key}): {e}")

    def delete(self, key: str):
        """删除缓存数据"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE key = ?", (key,))
            conn.commit()
        except sqlite3.Error as e:
            logging.error(f"删除缓存数据失败 (键: {key}): {e}")

    def clear(self):
        """清空所有OCR缓存"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {TABLE_NAME}")
            conn.commit()
            logging.info("OCR 缓存已清空")
        except sqlite3.Error as e:
            logging.error(f"清空 OCR 缓存失败: {e}")

    def get_all_entries_for_display(self) -> List[Dict[str, Any]]:
        """获取所有缓存条目及其元数据用于UI显示。"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            
            # 选择所有需要的列
            cursor.execute(f"SELECT key, value, manga_path, page_index, manga_name, last_updated FROM {TABLE_NAME} ORDER BY last_updated DESC")
            
            rows = cursor.fetchall()
            entries = [dict(row) for row in rows]
            
            logging.info(f"成功检索到 {len(entries)} 条OCR缓存条目以供显示。")
            return entries
        except sqlite3.Error as e:
            # 如果出现 no such column 错误，可能是旧版数据库，返回空列表
            if "no such column" in str(e):
                logging.warning(f"数据库 '{self.db_path}' 模式过时，缺少元数据列。将返回空列表。请考虑重建缓存。")
                return []
            logging.error(f"获取所有OCR缓存条目失败: {e}")
            return []
        
    def get_cache_size_bytes(self) -> int:
        """获取OCR缓存数据库文件大小"""
        try:
            if os.path.exists(self.db_path):
                return os.path.getsize(self.db_path)
            return 0
        except OSError as e:
            logging.error(f"获取OCR缓存大小失败: {e}")
            return 0
            
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            try:
                self.conn.close()
                self.conn = None
            except sqlite3.Error as e:
                logging.error(f"关闭数据库连接失败: {e}")

    def __del__(self):
        self.close()