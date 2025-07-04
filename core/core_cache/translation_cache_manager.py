import os
import json
import sqlite3
import hashlib
from typing import Any, List, Optional, Dict
from utils import manga_logger as log
from .cache_interface import CacheInterface

# 缓存目录和数据库文件名
CACHE_DIR = "app/config"
DB_NAME = "translation_cache.db"
DB_PATH = os.path.join(CACHE_DIR, DB_NAME)
TABLE_NAME = "translation_cache"

class TranslationCacheManager(CacheInterface):
    """翻译结果缓存管理类"""

    def __init__(self, db_path: str = DB_PATH):
        """初始化缓存管理器"""
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._ensure_cache_dir_exists()
        self._init_db()
        log.info(f"TranslationCacheManager 初始化完成，数据库路径: {self.db_path}")

    def _ensure_cache_dir_exists(self):
        """确保缓存目录存在"""
        directory = os.path.dirname(self.db_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except OSError as e:
                log.error(f"创建缓存目录 {directory} 失败: {e}")
                raise

    def _connect(self) -> sqlite3.Connection:
        """连接到 SQLite 数据库"""
        if self.conn is None or self._is_connection_closed():
            try:
                self.conn = sqlite3.connect(self.db_path)
                self.conn.row_factory = sqlite3.Row
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
        except (sqlite3.ProgrammingError, sqlite3.OperationalError):
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
                is_sensitive BOOLEAN DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # 兼容旧版本，检查并添加 is_sensitive 列
            cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
            columns = [info['name'] for info in cursor.fetchall()]
            if 'is_sensitive' not in columns:
                try:
                    cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN is_sensitive BOOLEAN DEFAULT 0")
                    log.info(f"成功向表 '{TABLE_NAME}' 添加 'is_sensitive' 列。")
                except sqlite3.OperationalError as alter_e:
                    log.warning(f"尝试添加 'is_sensitive' 列时发生错误: {alter_e}")

            conn.commit()
            log.info(f"翻译缓存数据库表 '{TABLE_NAME}' 已准备就绪")
        except sqlite3.Error as e:
            log.error(f"初始化数据库表 {TABLE_NAME} 失败: {e}")

    def generate_key(self, **kwargs) -> str:
        """
        根据文本和其他可选参数生成缓存键。
        必需关键字参数: 'text'
        可选关键字参数: 'target_lang', 'translator_type', 等
        """
        if 'text' not in kwargs:
            raise TypeError("generate_key() 缺少必需的关键字参数: 'text'")
        
        # 为了保持一致性，从kwargs中提取'text'，其余的动态处理
        key_string = f"text:{kwargs['text']}"
        
        # 对剩余的kwargs进行排序和拼接
        other_kwargs = {k: v for k, v in kwargs.items() if k != 'text'}
        for k, v in sorted(other_kwargs.items()):
            key_string += f"|{k}:{v}"
            
        return hashlib.sha256(key_string.encode('utf-8')).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """根据键获取缓存数据"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"SELECT value FROM {TABLE_NAME} WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                # 数据以JSON编码的字符串形式存储。我们需要对其进行解码。
                return json.loads(row["value"])
            return None
        except sqlite3.Error as e:
            log.error(f"从翻译缓存获取数据失败 (键: {key}): {e}")
            return None
        except json.JSONDecodeError:
            log.error(f"解析缓存的翻译数据失败 (键: {key})，将清除损坏的缓存。")
            self.delete(key)
            return None

    def set(self, key: str, data: Any, is_sensitive: bool = False, **kwargs):
        """设置缓存数据"""
        try:
            # 缓存管理器负责序列化。
            value_json = json.dumps(data, ensure_ascii=False)
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"""
            INSERT OR REPLACE INTO {TABLE_NAME} (key, value, is_sensitive, last_updated)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (key, value_json, is_sensitive))
            conn.commit()
        except sqlite3.Error as e:
            log.error(f"设置翻译缓存数据失败 (键: {key}): {e}")
        except TypeError as e:
            log.error(f"序列化翻译数据失败 (键: {key}): {e}")

    def delete(self, key: str) -> None:
        """删除缓存数据"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE key = ?", (key,))
            conn.commit()
        except sqlite3.Error as e:
            log.error(f"删除翻译缓存数据失败 (键: {key}): {e}")

    def clear(self) -> None:
        """清空所有缓存"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {TABLE_NAME}")
            conn.commit()
            log.info(f"翻译缓存表 '{TABLE_NAME}' 已清空")
        except sqlite3.Error as e:
            log.error(f"清空翻译缓存失败: {e}")

    def get_all_entries_for_display(self) -> List[Dict[str, Any]]:
        """获取所有条目用于UI显示，并进行模式检查"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            
            # 模式健壮性检查
            cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
            columns = [info['name'] for info in cursor.fetchall()]
            if 'key' not in columns or 'value' not in columns:
                log.error(f"数据库表 '{TABLE_NAME}' 模式不正确，缺少 'key' 或 'value' 列。文件路径: {self.db_path}")
                log.error("请考虑删除此数据库文件以允许程序重新生成。")
                return [] # 返回空列表以避免崩溃

            cursor.execute(f"SELECT key, value, is_sensitive, last_updated FROM {TABLE_NAME}")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            log.error(f"获取所有翻译缓存条目失败: {e}")
            return []

    def get_cache_size_bytes(self) -> int:
        """获取缓存数据库文件大小"""
        try:
            if os.path.exists(self.db_path):
                return os.path.getsize(self.db_path)
            return 0
        except OSError as e:
            log.error(f"获取翻译缓存大小失败: {e}")
            return 0

    def close(self) -> None:
        """关闭数据库连接"""
        if self.conn:
            try:
                self.conn.close()
                self.conn = None
            except sqlite3.Error as e:
                log.error(f"关闭翻译数据库连接失败: {e}")

    def __del__(self):
        self.close()