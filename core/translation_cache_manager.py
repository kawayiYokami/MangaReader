# core/translation_cache_manager.py
import os
import json
import sqlite3
import hashlib # Added for key generation
from typing import Any, Optional, Dict, List # Added List
from utils import manga_logger as log
from core.cache_interface import CacheInterface

# Cache directory and database file name
CACHE_DIR = "app/config"
DB_NAME = "translation_cache.db"
DB_PATH = os.path.join(CACHE_DIR, DB_NAME)
TABLE_NAME = "translation_cache"

class TranslationCacheManager(CacheInterface):
    """
    翻译结果缓存管理类，基于SQLite数据库。
    缓存的键是基于原文、翻译器类型和目标语言生成的。
    值是一个包含翻译后文本和是否敏感标记的字典。
    """

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
            # 检查表结构是否需要更新
            cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
            columns = [column['name'] for column in cursor.fetchall()]

            if 'is_sensitive' not in columns:
                log.info(f"表 '{TABLE_NAME}' 中缺少 'is_sensitive' 列，正在添加...")
                try:
                    cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN is_sensitive INTEGER DEFAULT 0")
                    conn.commit()
                    log.info(f"成功向表 '{TABLE_NAME}' 添加 'is_sensitive' 列。")
                except sqlite3.OperationalError as alter_e: # Catch specific error for ALTER TABLE
                    log.warning(f"尝试添加 'is_sensitive' 列时发生错误 (可能是列已存在于并发操作中): {alter_e}")
                    # If alter fails, assume it might be due to concurrent creation or already exists
                    # We will proceed with the CREATE TABLE IF NOT EXISTS which handles this.

            cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                cache_key TEXT PRIMARY KEY,
                translated_text TEXT NOT NULL,
                is_sensitive INTEGER DEFAULT 0, -- 0 for False, 1 for True
                original_text_sample TEXT, 
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.commit()
            log.info(f"翻译缓存数据库表 '{TABLE_NAME}' 已准备就绪")
        except sqlite3.Error as e:
            log.error(f"初始化数据库表 {TABLE_NAME} 失败: {e}")

    def generate_key(self, original_text: str, *args, **kwargs) -> str:
        """
        生成翻译缓存的键。
        键的组成: "translator_type::original_text_hash::target_lang"
        """
        if not isinstance(original_text, str):
            log.error("original_text 必须是字符串")
            raise TypeError("original_text 必须是字符串")

        translator_type = kwargs.get("translator_type", "unknown_translator")
        target_lang = kwargs.get("target_lang", "unknown_lang")
        
        text_hash = hashlib.sha256(original_text.encode('utf-8')).hexdigest()
        
        key_string = f"{translator_type}::{text_hash}::{target_lang}"
        return key_string

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        根据生成的键获取翻译结果。
        返回一个包含 'text' 和 'is_sensitive' 的字典，如果未找到则返回 None。
        """
        if not isinstance(key, str):
            log.warning(f"TranslationCacheManager.get 接收到非字符串键: {key}")
            return None
        
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"SELECT translated_text, is_sensitive FROM {TABLE_NAME} WHERE cache_key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return {"text": row["translated_text"], "is_sensitive": bool(row["is_sensitive"])}
            return None
        except sqlite3.Error as e:
            log.error(f"从翻译缓存获取数据失败 (键: {key}): {e}")
            return None

    def set(self, key: str, data: str, **kwargs) -> None:
        """
        设置翻译结果。
        Args:
            key (str): 缓存键。
            data (str): 翻译后的文本字符串。
            **kwargs:
                is_sensitive (bool): 标记此翻译是否为敏感内容，默认为 False。
                original_text (str, optional): 用于存储样本的原文。
        """
        if not isinstance(key, str):
            log.error(f"TranslationCacheManager.set 接收到非字符串键: {key}")
            return
        if not isinstance(data, str):
            log.error(f"TranslationCacheManager.set 接收到非字符串数据 (应为翻译文本): {data}")
            return
            
        is_sensitive = kwargs.get("is_sensitive", False)
        original_text_input = kwargs.get("original_text") # Get original_text from kwargs
        original_text_sample = original_text_input[:100] if original_text_input else None

        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"""
            INSERT OR REPLACE INTO {TABLE_NAME} (cache_key, translated_text, is_sensitive, original_text_sample, last_updated)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (key, data, 1 if is_sensitive else 0, original_text_sample))
            conn.commit()
        except sqlite3.Error as e:
            log.error(f"设置翻译缓存数据失败 (键: {key}): {e}")

    def delete(self, key: str) -> None:
        """删除指定键的翻译缓存。"""
        if not isinstance(key, str):
            log.error(f"TranslationCacheManager.delete 接收到非字符串键: {key}")
            return
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE cache_key = ?", (key,))
            conn.commit()
            if cursor.rowcount > 0:
                log.info(f"已删除翻译缓存: '{key}'")
            else:
                log.info(f"尝试删除不存在的翻译缓存键: {key}")
        except sqlite3.Error as e:
            log.error(f"删除翻译缓存数据失败 (键: {key}): {e}")

    def clear(self) -> None:
        """清空所有翻译缓存"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {TABLE_NAME}")
            conn.commit()
            log.info(f"翻译缓存表 '{TABLE_NAME}' 已清空")
        except sqlite3.Error as e:
            log.error(f"清空翻译缓存失败: {e}")

    def get_all_entries_for_display(self) -> List[Dict[str, Any]]:
        """
        获取所有翻译缓存条目，用于在界面中显示。
        返回包含 cache_key, original_text_sample, translated_text (sample), is_sensitive, last_updated 的字典列表。
        """
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"SELECT cache_key, original_text_sample, translated_text, is_sensitive, last_updated FROM {TABLE_NAME}")
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                entry = dict(row)
                entry["is_sensitive"] = bool(entry.get("is_sensitive", 0)) # Ensure boolean
                # Optionally, add a sample of translated_text if needed for display
                # entry["translated_text_sample"] = entry.get("translated_text", "")[:50] + "..." if entry.get("translated_text") else ""
                results.append(entry)
            return results
        except sqlite3.Error as e:
            log.error(f"获取所有翻译缓存条目失败: {e}")
            return []

    def get_cache_size_bytes(self) -> int:
        """
        获取翻译缓存的总大小（字节）。
        返回SQLite数据库文件的大小。
        """
        try:
            if os.path.exists(self.db_path):
                size_bytes = os.path.getsize(self.db_path)
                log.debug(f"翻译缓存数据库大小: {size_bytes} 字节")
                return size_bytes
            else:
                log.debug("翻译缓存数据库文件不存在")
                return 0
        except OSError as e:
            log.error(f"获取翻译缓存大小失败: {e}")
            return 0

    def close(self) -> None:
        """关闭数据库连接。"""
        if self.conn:
            try:
                self.conn.close()
                self.conn = None
                log.info("翻译缓存数据库连接已关闭")
            except sqlite3.Error as e:
                log.error(f"关闭翻译数据库连接失败: {e}")

    def __del__(self):
        self.close()