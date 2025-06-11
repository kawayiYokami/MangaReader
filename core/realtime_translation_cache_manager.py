# core/realtime_translation_cache_manager.py
"""
实时翻译缓存管理器

专门为实时翻译功能设计的缓存系统，缓存完整的翻译数据结构，
包括OCR结果、翻译映射、图像处理元数据等，支持快速复用。
"""

import os
import json
import sqlite3
import hashlib
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

from core.cache_interface import CacheInterface
from core.data_models import OCRResult
from utils import manga_logger as log

# 缓存数据库路径
CACHE_DIR = "app\config"
DB_PATH = os.path.join(CACHE_DIR, "realtime_translation_cache.db")
TABLE_NAME = "realtime_translation_cache"


@dataclass
class RealtimeTranslationCacheData:
    """实时翻译缓存数据结构"""
    
    # 基本信息
    manga_path: str
    page_index: int
    target_language: str
    
    # 原始图像信息
    image_hash: str  # 图像内容的MD5哈希
    image_width: int
    image_height: int
    
    # OCR识别结果
    ocr_results: List[Dict[str, Any]]  # OCRResult对象的字典表示
    structured_texts: List[Dict[str, Any]]  # 结构化文本数据
    
    # 翻译数据
    original_texts: List[str]  # 原始文本列表
    translated_texts: List[str]  # 翻译文本列表
    translation_mappings: Dict[str, str]  # 原文到译文的映射
    
    # 和谐化处理
    harmonized_texts: List[str]  # 和谐化后的文本
    harmonization_applied: bool  # 是否应用了和谐化
    
    # 图像处理元数据
    text_regions: List[Dict[str, Any]]  # 文本区域信息
    inpaint_regions: List[Dict[str, Any]]  # 需要修复的区域
    font_settings: Dict[str, Any]  # 字体设置
    
    # 翻译结果图像
    result_image_data: Optional[str] = None  # base64编码的结果图像
    
    # 缓存元数据
    created_at: str = ""
    last_accessed: str = ""
    access_count: int = 0
    cache_version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RealtimeTranslationCacheData':
        """从字典创建实例"""
        return cls(**data)


class RealtimeTranslationCacheManager(CacheInterface):
    """实时翻译缓存管理器"""
    
    def __init__(self, db_path: str = DB_PATH):
        """初始化缓存管理器"""
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._ensure_cache_dir_exists()
        self._init_db()
        log.info(f"RealtimeTranslationCacheManager 初始化完成，数据库路径: {self.db_path}")
    
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
    
    def _init_db(self):
        """初始化数据库表"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            
            # 创建实时翻译缓存表
            cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                cache_key TEXT PRIMARY KEY,
                manga_path TEXT NOT NULL,
                page_index INTEGER NOT NULL,
                target_language TEXT NOT NULL,
                image_hash TEXT NOT NULL,
                cache_data TEXT NOT NULL,  -- JSON格式的完整缓存数据
                created_at TEXT NOT NULL,
                last_accessed TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                cache_version TEXT DEFAULT '1.0'
            )
            """)
            
            # 创建索引以提高查询性能
            cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_manga_page 
            ON {TABLE_NAME} (manga_path, page_index)
            """)
            
            cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_image_hash 
            ON {TABLE_NAME} (image_hash)
            """)
            
            cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_last_accessed 
            ON {TABLE_NAME} (last_accessed)
            """)
            
            conn.commit()
            log.debug(f"实时翻译缓存数据库表 '{TABLE_NAME}' 初始化完成")
            
        except sqlite3.Error as e:
            log.error(f"初始化实时翻译缓存数据库失败: {e}")
            raise
    
    def _connect(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self.conn is None or self.conn.execute("SELECT 1").fetchone() is None:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def generate_key(self, manga_path: str, page_index: int, target_language: str = "zh", 
                    image_hash: Optional[str] = None) -> str:
        """生成缓存键"""
        # 使用漫画路径、页面索引、目标语言和图像哈希生成唯一键
        key_components = [
            str(manga_path),
            str(page_index),
            str(target_language)
        ]
        
        if image_hash:
            key_components.append(image_hash)
        
        key_string = "|".join(key_components)
        cache_key = hashlib.md5(key_string.encode('utf-8')).hexdigest()
        
        log.debug(f"生成实时翻译缓存键: {cache_key} (来源: {key_string})")
        return cache_key
    
    def get(self, key: str) -> Optional[RealtimeTranslationCacheData]:
        """获取缓存数据"""
        if not isinstance(key, str):
            log.warning(f"RealtimeTranslationCacheManager.get 接收到非字符串键: {key}")
            return None
        
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"""
            SELECT cache_data, access_count FROM {TABLE_NAME} WHERE cache_key = ?
            """, (key,))
            row = cursor.fetchone()
            
            if row:
                # 更新访问统计
                new_access_count = row["access_count"] + 1
                current_time = datetime.now().isoformat()
                cursor.execute(f"""
                UPDATE {TABLE_NAME} 
                SET last_accessed = ?, access_count = ? 
                WHERE cache_key = ?
                """, (current_time, new_access_count, key))
                conn.commit()
                
                # 解析缓存数据
                cache_data_json = row["cache_data"]
                cache_data_dict = json.loads(cache_data_json)
                cache_data = RealtimeTranslationCacheData.from_dict(cache_data_dict)
                
                log.debug(f"实时翻译缓存命中: {key}")
                return cache_data
            
            log.debug(f"实时翻译缓存未命中: {key}")
            return None
            
        except sqlite3.Error as e:
            log.error(f"从实时翻译缓存获取数据失败 (键: {key}): {e}")
            return None
        except json.JSONDecodeError as e:
            log.error(f"解析实时翻译缓存数据失败 (键: {key}): {e}")
            return None
    
    def set(self, key: str, data: RealtimeTranslationCacheData, **kwargs) -> None:
        """设置缓存数据"""
        if not isinstance(key, str):
            log.error(f"RealtimeTranslationCacheManager.set 接收到非字符串键: {key}")
            return
        
        if not isinstance(data, RealtimeTranslationCacheData):
            log.error(f"RealtimeTranslationCacheManager.set 接收到错误的数据类型: {type(data)}")
            return
        
        try:
            # 设置缓存元数据
            current_time = datetime.now().isoformat()
            data.created_at = current_time
            data.last_accessed = current_time
            data.access_count = 0
            
            # 序列化缓存数据
            cache_data_json = json.dumps(data.to_dict(), ensure_ascii=False)
            
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"""
            INSERT OR REPLACE INTO {TABLE_NAME} 
            (cache_key, manga_path, page_index, target_language, image_hash, 
             cache_data, created_at, last_accessed, access_count, cache_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                key, data.manga_path, data.page_index, data.target_language, 
                data.image_hash, cache_data_json, current_time, current_time, 
                0, data.cache_version
            ))
            conn.commit()
            
            log.info(f"实时翻译缓存已保存: {key}")
            
        except sqlite3.Error as e:
            log.error(f"设置实时翻译缓存数据失败 (键: {key}): {e}")
        except (TypeError, ValueError) as e:
            log.error(f"序列化实时翻译缓存数据失败 (键: {key}): {e}")
    
    def delete(self, key: str) -> None:
        """删除缓存数据"""
        if not isinstance(key, str):
            log.error(f"RealtimeTranslationCacheManager.delete 接收到非字符串键: {key}")
            return
        
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE cache_key = ?", (key,))
            conn.commit()
            
            if cursor.rowcount > 0:
                log.info(f"已删除实时翻译缓存: '{key}'")
            else:
                log.info(f"尝试删除不存在的实时翻译缓存键: {key}")
                
        except sqlite3.Error as e:
            log.error(f"删除实时翻译缓存数据失败 (键: {key}): {e}")
    
    def clear(self) -> None:
        """清空所有缓存"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {TABLE_NAME}")
            conn.commit()
            log.info(f"实时翻译缓存表 '{TABLE_NAME}' 已清空")
        except sqlite3.Error as e:
            log.error(f"清空实时翻译缓存失败: {e}")
    
    def close(self) -> None:
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def get_cache_size_bytes(self) -> int:
        """获取缓存大小"""
        try:
            if os.path.exists(self.db_path):
                size_bytes = os.path.getsize(self.db_path)
                log.debug(f"实时翻译缓存数据库大小: {size_bytes} 字节")
                return size_bytes
            else:
                log.debug("实时翻译缓存数据库文件不存在")
                return 0
        except OSError as e:
            log.error(f"获取实时翻译缓存大小失败: {e}")
            return 0

    def get_all_entries_for_display(self) -> List[Dict[str, Any]]:
        """获取所有缓存条目用于界面显示"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"""
            SELECT cache_key, manga_path, page_index, target_language,
                   image_hash, created_at, last_accessed, access_count, cache_version
            FROM {TABLE_NAME}
            ORDER BY last_accessed DESC
            """)
            rows = cursor.fetchall()

            results = []
            for row in rows:
                entry = dict(row)
                # 添加显示用的简化信息
                entry["manga_name"] = os.path.basename(entry["manga_path"])
                entry["page_display"] = f"第{entry['page_index'] + 1}页"
                entry["image_hash_short"] = entry["image_hash"][:8] + "..."
                results.append(entry)

            return results

        except sqlite3.Error as e:
            log.error(f"获取所有实时翻译缓存条目失败: {e}")
            return []

    def get_cache_by_manga(self, manga_path: str) -> List[RealtimeTranslationCacheData]:
        """获取指定漫画的所有缓存"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"""
            SELECT cache_data FROM {TABLE_NAME}
            WHERE manga_path = ?
            ORDER BY page_index
            """, (manga_path,))
            rows = cursor.fetchall()

            results = []
            for row in rows:
                cache_data_json = row["cache_data"]
                cache_data_dict = json.loads(cache_data_json)
                cache_data = RealtimeTranslationCacheData.from_dict(cache_data_dict)
                results.append(cache_data)

            return results

        except sqlite3.Error as e:
            log.error(f"获取漫画缓存失败 (漫画: {manga_path}): {e}")
            return []
        except json.JSONDecodeError as e:
            log.error(f"解析漫画缓存数据失败 (漫画: {manga_path}): {e}")
            return []

    def delete_by_manga(self, manga_path: str) -> int:
        """删除指定漫画的所有缓存"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE manga_path = ?", (manga_path,))
            conn.commit()

            deleted_count = cursor.rowcount
            log.info(f"已删除漫画 {manga_path} 的 {deleted_count} 个缓存条目")
            return deleted_count

        except sqlite3.Error as e:
            log.error(f"删除漫画缓存失败 (漫画: {manga_path}): {e}")
            return 0

    def cleanup_missing_files(self) -> int:
        """清理源文件已丢失的翻译缓存"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"SELECT cache_key, manga_path FROM {TABLE_NAME}")
            rows = cursor.fetchall()

            deleted_count = 0
            for row in rows:
                cache_key = row["cache_key"]
                manga_path = row["manga_path"]

                # 检查文件是否存在
                if not os.path.exists(manga_path):
                    cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE cache_key = ?", (cache_key,))
                    deleted_count += 1
                    log.debug(f"删除丢失文件的缓存: {manga_path}")

            conn.commit()
            log.info(f"清理完成，删除了 {deleted_count} 个丢失文件的缓存条目")
            return deleted_count

        except sqlite3.Error as e:
            log.error(f"清理丢失文件缓存失败: {e}")
            return 0

    def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            conn = self._connect()
            cursor = conn.cursor()

            # 总条目数
            cursor.execute(f"SELECT COUNT(*) as total FROM {TABLE_NAME}")
            total_entries = cursor.fetchone()["total"]

            # 按语言分组统计
            cursor.execute(f"""
            SELECT target_language, COUNT(*) as count
            FROM {TABLE_NAME}
            GROUP BY target_language
            """)
            language_stats = {row["target_language"]: row["count"] for row in cursor.fetchall()}

            # 最近访问统计
            cursor.execute(f"""
            SELECT COUNT(*) as recent_count
            FROM {TABLE_NAME}
            WHERE datetime(last_accessed) > datetime('now', '-7 days')
            """)
            recent_accessed = cursor.fetchone()["recent_count"]

            # 平均访问次数
            cursor.execute(f"SELECT AVG(access_count) as avg_access FROM {TABLE_NAME}")
            avg_access = cursor.fetchone()["avg_access"] or 0

            return {
                "total_entries": total_entries,
                "language_stats": language_stats,
                "recent_accessed": recent_accessed,
                "average_access_count": round(avg_access, 2),
                "cache_size_bytes": self.get_cache_size_bytes()
            }

        except sqlite3.Error as e:
            log.error(f"获取缓存统计信息失败: {e}")
            return {
                "total_entries": 0,
                "language_stats": {},
                "recent_accessed": 0,
                "average_access_count": 0,
                "cache_size_bytes": 0
            }
