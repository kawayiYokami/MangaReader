# core/ocr_cache_manager.py
import sqlite3
import json
import os
import hashlib
from typing import Optional, Any, List, Dict
from utils import manga_logger as log
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
        log.info(f"OcrCacheManager 初始化完成，数据库路径: {self.db_path}")

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
                log.error(f"连接到数据库 {self.db_path} 失败: {e}")
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
        """初始化数据库和表"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.commit()
        except sqlite3.Error as e:
            log.error(f"初始化数据库表 {TABLE_NAME} 失败: {e}")

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
            log.error(f"从缓存获取数据失败 (键: {key}): {e}")
            return None
        except json.JSONDecodeError:
            log.error(f"解析缓存的OCR数据失败 (键: {key})，将清除损坏的缓存。")
            self.delete(key)
            return None

    def set(self, key: str, data: Any, **kwargs):
        """设置缓存数据"""
        try:
            value_json = json.dumps(data, ensure_ascii=False)
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"""
            INSERT OR REPLACE INTO {TABLE_NAME} (key, value, last_updated)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, value_json))
            conn.commit()
        except sqlite3.Error as e:
            log.error(f"设置缓存数据失败 (键: {key}): {e}")
        except TypeError as e:
            log.error(f"序列化OCR数据失败 (键: {key}): {e}")

    def delete(self, key: str):
        """删除缓存数据"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE key = ?", (key,))
            conn.commit()
        except sqlite3.Error as e:
            log.error(f"删除缓存数据失败 (键: {key}): {e}")

    def clear(self):
        """清空所有OCR缓存"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {TABLE_NAME}")
            conn.commit()
            log.info("OCR 缓存已清空")
        except sqlite3.Error as e:
            log.error(f"清空 OCR 缓存失败: {e}")

    def get_all_entries_for_display(self) -> List[Dict[str, Any]]:
        """获取所有缓存条目用于UI显示，并进行模式检查"""
        entries = []
        try:
            conn = self._connect()
            with conn:
                cursor = conn.cursor()
                
                # 模式健壮性检查
                cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
                columns = [info['name'] for info in cursor.fetchall()]
                if 'key' not in columns or 'value' not in columns:
                    log.error(f"数据库表 '{TABLE_NAME}' 模式不正确，缺少 'key' 或 'value' 列。文件路径: {self.db_path}")
                    log.error("请考虑删除此数据库文件以允许程序重新生成。")
                    return [] # 返回空列表以避免崩溃

                cursor.execute(f"SELECT key, value, last_updated FROM {TABLE_NAME}")
                rows = cursor.fetchall()
                for row in rows:
                    entries.append(dict(row))
                log.info(f"成功检索到 {len(entries)} 条OCR缓存条目以供显示。")
        except sqlite3.Error as e:
            log.error(f"获取所有OCR缓存条目失败: {e}")
        return entries
        
    def get_cache_size_bytes(self) -> int:
        """获取OCR缓存数据库文件大小"""
        try:
            if os.path.exists(self.db_path):
                return os.path.getsize(self.db_path)
            return 0
        except OSError as e:
            log.error(f"获取OCR缓存大小失败: {e}")
            return 0
            
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            try:
                self.conn.close()
                self.conn = None
            except sqlite3.Error as e:
                log.error(f"关闭数据库连接失败: {e}")

    def __del__(self):
        self.close()