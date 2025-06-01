# core/ocr_cache_manager.py
import sqlite3
import json
import os
from typing import Any, List, Optional, Tuple

from core.cache_interface import CacheInterface
from core.data_models import OCRResult # Corrected import path
from utils import manga_logger as log

CACHE_DIR = "app/config"
DB_NAME = "ocr_cache.db"
DB_PATH = os.path.join(CACHE_DIR, DB_NAME)

class OcrCacheManager(CacheInterface):
    """
    OCR 结果缓存管理器，使用 SQLite 数据库。
    """
    TABLE_NAME = "ocr_cache"

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_cache_dir_exists()
        self.conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _ensure_cache_dir_exists(self):
        """确保缓存目录存在"""
        if not os.path.exists(CACHE_DIR):
            try:
                os.makedirs(CACHE_DIR)
                log.info(f"创建缓存目录: {CACHE_DIR}")
            except OSError as e:
                log.error(f"创建缓存目录 {CACHE_DIR} 失败: {e}")
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
            # Attempt a simple query to check if the connection is live
            self.conn.execute("SELECT 1").fetchone()
            return False
        except sqlite3.ProgrammingError: # Connection closed or cursor used on closed connection
            return True
        except sqlite3.OperationalError: # Potentially, connection is still open but unusable
            return True


    def _init_db(self):
        """初始化数据库和表"""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                cache_key TEXT PRIMARY KEY,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                last_modified REAL NOT NULL,
                page_num INTEGER NOT NULL,
                ocr_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.commit()
        except sqlite3.Error as e:
            log.error(f"初始化数据库表 {self.TABLE_NAME} 失败: {e}")
            # Do not close connection here, _connect will handle re-connection if needed
            # self.close() # Avoid closing if it's already problematic

    def generate_key(self, file_path: str, page_num: int, original_archive_path: Optional[str] = None) -> str:
        """
        根据文件路径和页码生成唯一的缓存键。
        如果提供了 original_archive_path，则基于原始压缩包信息生成键。
        键的组成: "原始（或文件）名::文件大小::最后修改时间::页码"
        """
        path_to_use_for_metadata = original_archive_path if original_archive_path else file_path
        
        try:
            # 使用 path_to_use_for_metadata 的 basename 作为键的一部分。
            # 对于压缩包，这是压缩包的文件名。对于独立文件，这是该图片的文件名。
            # page_num 确保了压缩包内不同图片的唯一性。
            key_base_name = os.path.basename(path_to_use_for_metadata)
            file_size = os.path.getsize(path_to_use_for_metadata)
            last_modified = os.path.getmtime(path_to_use_for_metadata)
            
            key = f"{key_base_name}::{file_size}::{last_modified}::{page_num}"
            
            log_context = f"原始存档='{original_archive_path}', " if original_archive_path else ""
            log_path_info = f"实际使用路径='{path_to_use_for_metadata}' (用于元数据)"
            if not original_archive_path and file_path != path_to_use_for_metadata: # Should not happen if logic is correct
                 log_path_info += f", 图片文件='{file_path}'"
            elif not original_archive_path:
                 log_path_info = f"图片文件='{file_path}'"


            log.debug(f"生成OCR缓存键: {log_context}{log_path_info}, 大小={file_size}, 修改时间={last_modified}, 页码={page_num} -> 键='{key}'")
            return key
        except OSError as e:
            log.error(f"生成缓存键失败 (元数据路径: {path_to_use_for_metadata}, 原始存档: {original_archive_path if original_archive_path else 'N/A'}, 实际图片路径: {file_path}): {e}")
            raise

    def _get_file_metadata(self, file_path: str) -> Tuple[str, int, float]:
        """Helper to get file metadata, raises OSError if file not found/accessible"""
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        last_modified = os.path.getmtime(file_path)
        return file_name, file_size, last_modified

    def get(self, key: str) -> Optional[List[OCRResult]]:
        """
        根据键获取缓存数据 (OCRResult 列表)。
        """
        log.debug(f"尝试从OCR缓存获取数据，键: '{key}'")
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"SELECT ocr_data FROM {self.TABLE_NAME} WHERE cache_key = ?", (key,))
            row = cursor.fetchone()
            if row:
                log.debug(f"OCR缓存命中，键: '{key}'")
                ocr_data_json = row["ocr_data"]
                ocr_data_list = json.loads(ocr_data_json)
                # Assuming OCRResult can be reconstructed from a dict
                return [OCRResult(**data_dict) for data_dict in ocr_data_list]
            else:
                log.debug(f"OCR缓存未命中，键: '{key}'")
                return None
        except sqlite3.Error as e:
            log.error(f"从缓存获取数据失败 (键: {key}): {e}")
            return None
        except json.JSONDecodeError as e:
            log.error(f"解析缓存的 OCR 数据失败 (键: {key}): {e}")
            # Optionally delete corrupted cache entry
            # self.delete(key)
            return None
        except Exception as e: # Catch other potential errors during OCRResult reconstruction
            log.error(f"重建 OCRResult 对象失败 (键: {key}): {e}")
            return None


    def set(self, key: str, data: List[OCRResult], **kwargs) -> None:
        """
        根据键设置缓存数据 (OCRResult 列表)。
        kwargs can include file_path and page_num if key is not self-generated.
        For this manager, key is expected to be generated by self.generate_key,
        so file_path and page_num are passed to extract metadata for DB columns.
        """
        input_image_path = kwargs.get("file_path") # Actual image path (e.g. temp path from archive, or direct image path)
        page_num = kwargs.get("page_num")
        original_archive_path = kwargs.get("original_archive_path") # Path to original archive, if applicable

        # Determine which path to use for storing metadata in the DB, consistent with generate_key
        path_for_db_metadata = original_archive_path if original_archive_path else input_image_path

        if not path_for_db_metadata or page_num is None:
            log.error(f"设置缓存失败: 'file_path' (或 'original_archive_path' 如果适用) 和 'page_num' 必须在 kwargs 中提供 (键: {key})")
            # Fallback attempt (less robust, ideally kwargs should always be complete)
            try:
                parts = key.split("::")
                if len(parts) == 4 and page_num is None:
                     page_num = int(parts[3])
                # We still might not have path_for_db_metadata if input_image_path was also missing.
                if not path_for_db_metadata or page_num is None:
                    # If original_archive_path was None, and input_image_path was None, we can't proceed.
                    # If original_archive_path was provided but page_num is still None, also an issue.
                    raise ValueError("无法确定元数据路径或页码。")
            except (IndexError, ValueError) as e_parse:
                 log.error(f"无法从键 '{key}' 解析元数据或元数据不完整: {e_parse}")
                 return

        try:
            # Get metadata from the path that was used for key generation
            db_file_name, db_file_size, db_last_modified = self._get_file_metadata(path_for_db_metadata)
            log_context = f"原始存档='{original_archive_path}', " if original_archive_path else ""
            log.debug(f"设置OCR缓存数据: 键='{key}', {log_context}元数据源路径='{path_for_db_metadata}', 实际图片='{input_image_path}', 页码={page_num}")
        except OSError as e:
            log.error(f"设置缓存失败，无法获取文件元数据 (元数据路径: {path_for_db_metadata}, 实际图片: {input_image_path}): {e}")
            return

        try:
            ocr_data_list = [result.to_dict() for result in data]
            ocr_data_json = json.dumps(ocr_data_list)

            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"""
            INSERT OR REPLACE INTO {self.TABLE_NAME}
            (cache_key, file_name, file_size, last_modified, page_num, ocr_data)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (key, db_file_name, db_file_size, db_last_modified, page_num, ocr_data_json))
            conn.commit()
        except sqlite3.Error as e:
            log.error(f"设置缓存数据失败 (键: {key}): {e}")
        except TypeError as e: # Error during to_dict() or json.dumps
            log.error(f"序列化 OCR 数据失败 (键: {key}): {e}")
        except OSError as e: # Should be caught by _get_file_metadata, but as a safeguard
            log.error(f"设置缓存时文件操作失败 (文件: {file_path}): {e}")


    def delete(self, key: str) -> None:
        """
        删除指定键的缓存。
        """
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {self.TABLE_NAME} WHERE cache_key = ?", (key,))
            conn.commit()
        except sqlite3.Error as e:
            log.error(f"删除缓存数据失败 (键: {key}): {e}")

    def clear(self) -> None:
        """
        清空所有 OCR 缓存。
        """
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {self.TABLE_NAME}")
            conn.commit()
            log.info("OCR 缓存已清空")
        except sqlite3.Error as e:
            log.error(f"清空 OCR 缓存失败: {e}")

    def close(self) -> None:
        """
        关闭数据库连接。
        """
        if self.conn:
            try:
                self.conn.close()
                self.conn = None
                log.info("OCR 缓存数据库连接已关闭")
            except sqlite3.Error as e:
                log.error(f"关闭数据库连接失败: {e}")

    def __del__(self):
        self.close()

# Example Usage (for testing purposes, not part of the class)
if __name__ == '__main__':
    # This example assumes ocr_manager.py and utils/manga_logger.py are accessible
    # and a dummy OCRResult class or the actual one is available.
    
    # Dummy OCRResult for testing if actual is not available here
    class OCRResult:
        def __init__(self, text, bbox, confidence, **kwargs):
            self.text = text
            self.bbox = bbox
            self.confidence = confidence
            self.kwargs = kwargs
        def to_dict(self):
            return {'text': self.text, 'bbox': self.bbox, 'confidence': self.confidence, **self.kwargs}
        def __repr__(self):
            return f"OCRResult(text='{self.text}')"

    # Ensure app/config directory exists for the test
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    # Create a dummy file for testing generate_key
    dummy_file_path = os.path.join(CACHE_DIR, "test_manga.cbz")
    if not os.path.exists(dummy_file_path):
        with open(dummy_file_path, "w") as f:
            f.write("dummy content")

    cache_manager = OcrCacheManager()

    # Test generate_key
    try:
        key1 = cache_manager.generate_key(dummy_file_path, 0)
        print(f"Generated key 1: {key1}")
        key2 = cache_manager.generate_key(dummy_file_path, 1)
        print(f"Generated key 2: {key2}")
    except Exception as e:
        print(f"Error generating key: {e}")
        # Clean up dummy file if key generation failed due to it
        if os.path.exists(dummy_file_path):
            os.remove(dummy_file_path)
        raise

    # Test set
    mock_ocr_results_p0 = [
        OCRResult("Hello", [[0,0],[10,10]], 0.9),
        OCRResult("World", [[20,20],[30,30]], 0.8)
    ]
    mock_ocr_results_p1 = [
        OCRResult("Test", [[0,0],[10,10]], 0.95),
    ]
    
    print(f"\nSetting cache for key1 with file_path='{dummy_file_path}', page_num=0")
    cache_manager.set(key1, mock_ocr_results_p0, file_path=dummy_file_path, page_num=0)
    
    print(f"\nSetting cache for key2 with file_path='{dummy_file_path}', page_num=1")
    cache_manager.set(key2, mock_ocr_results_p1, file_path=dummy_file_path, page_num=1)

    # Test get
    retrieved_p0 = cache_manager.get(key1)
    print(f"\nRetrieved for key1: {retrieved_p0}")
    assert retrieved_p0 is not None and len(retrieved_p0) == 2
    assert retrieved_p0[0].text == "Hello"

    retrieved_p1 = cache_manager.get(key2)
    print(f"Retrieved for key2: {retrieved_p1}")
    assert retrieved_p1 is not None and len(retrieved_p1) == 1
    assert retrieved_p1[0].text == "Test"
    
    retrieved_non_existent = cache_manager.get("non_existent_key")
    print(f"Retrieved for non_existent_key: {retrieved_non_existent}")
    assert retrieved_non_existent is None

    # Test delete
    cache_manager.delete(key1)
    retrieved_after_delete = cache_manager.get(key1)
    print(f"\nRetrieved for key1 after delete: {retrieved_after_delete}")
    assert retrieved_after_delete is None

    # Test clear
    cache_manager.clear()
    retrieved_after_clear = cache_manager.get(key2)
    print(f"\nRetrieved for key2 after clear: {retrieved_after_clear}")
    assert retrieved_after_clear is None
    
    # Clean up
    cache_manager.close()
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    if os.path.exists(dummy_file_path):
        os.remove(dummy_file_path)
    print("\nTest finished and cleaned up.")