# core/db/repositories/manga_repository.py
import sqlite3
import json
from typing import List

from core.manga.manga_model import MangaInfo
from core.db.database_manager import db_manager
import logging

class MangaRepository:
    def __init__(self):
        self.db_manager = db_manager

    def add_or_update_manga(self, manga: MangaInfo):
        """添加或更新一本漫画到数据库，包括其标签"""
        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        try:
            manga_sql = """
            INSERT INTO mangas (
                file_path, title, last_modified, total_pages, file_size, file_type, 
                is_valid, pages, page_dimensions, dimension_variance, is_likely_manga
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                title = excluded.title,
                last_modified = excluded.last_modified,
                total_pages = excluded.total_pages,
                file_size = excluded.file_size,
                file_type = excluded.file_type,
                is_valid = excluded.is_valid,
                pages = excluded.pages,
                page_dimensions = excluded.page_dimensions,
                dimension_variance = excluded.dimension_variance,
                is_likely_manga = excluded.is_likely_manga;
            """
            manga_values = (
                manga.file_path, manga.title, manga.last_modified, manga.total_pages,
                manga.file_size, manga.file_type, manga.is_valid,
                json.dumps(manga.pages), json.dumps(manga.page_dimensions),
                manga.dimension_variance, manga.is_likely_manga
            )
            cursor.execute(manga_sql, manga_values)

            # --- 处理标签 ---
            tag_ids = []
            if manga.tags:
                cursor.executemany("INSERT OR IGNORE INTO tags (name) VALUES (?)", [(tag,) for tag in manga.tags])
                placeholders = ','.join('?' for _ in manga.tags)
                cursor.execute(f"SELECT id FROM tags WHERE name IN ({placeholders})", list(manga.tags))
                tag_ids = [row['id'] for row in cursor.fetchall()]

            cursor.execute("DELETE FROM manga_tags WHERE manga_path = ?", (manga.file_path,))
            if tag_ids:
                cursor.executemany(
                    "INSERT INTO manga_tags (manga_path, tag_id) VALUES (?, ?)",
                    [(manga.file_path, tag_id) for tag_id in tag_ids]
                )
            
            conn.commit()
            logging.debug(f"成功添加/更新漫画到数据库: {manga.title}")

        except sqlite3.Error as e:
            logging.error(f"添加/更新漫画 '{manga.file_path}' 时发生数据库错误: {e}", exc_info=True)
            conn.rollback()

    def get_mangas(self, order_by="last_modified DESC", search_query: str = None) -> List[MangaInfo]:
        """从数据库获取漫画列表，支持排序和搜索"""
        conn = self.db_manager._get_connection()
        cursor = conn.cursor()
        
        sql = """
        SELECT
            m.*,
            GROUP_CONCAT(t.name) as tag_names
        FROM
            mangas m
        LEFT JOIN
            manga_tags mt ON m.file_path = mt.manga_path
        LEFT JOIN
            tags t ON mt.tag_id = t.id
        """
        
        params = []
        if search_query:
            sql += " WHERE m.title LIKE ?"
            params.append(f"%{search_query}%")
            
        sql += " GROUP BY m.file_path"
        
        if order_by:
            allowed_orders = ["last_modified DESC", "last_modified ASC", "title ASC", "title DESC"]
            if order_by in allowed_orders:
                sql += f" ORDER BY {order_by}"

        manga_list = []
        try:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            for row in rows:
                manga_data = dict(row)
                
                manga_data['pages'] = json.loads(manga_data['pages']) if manga_data['pages'] else []
                manga_data['page_dimensions'] = json.loads(manga_data['page_dimensions']) if manga_data['page_dimensions'] else []
                
                tags = set(manga_data['tag_names'].split(',')) if manga_data['tag_names'] else set()
                manga_data['tags'] = tags
                del manga_data['tag_names']
                
                manga_list.append(MangaInfo(**manga_data))
                
        except sqlite3.Error as e:
            logging.error(f"从数据库获取漫画列表时出错: {e}", exc_info=True)

        return manga_list
        
    def clear_all_manga_data(self):
        """清空所有漫画相关的数据表"""
        conn = self.db_manager._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM manga_tags")
            cursor.execute("DELETE FROM tags")
            cursor.execute("DELETE FROM mangas")
            conn.commit()
            logging.info("已成功清空 mangas, tags, 和 manga_tags 表。")
        except sqlite3.Error as e:
            logging.error(f"清空漫画数据时发生错误: {e}")
            conn.rollback()

# 创建一个单例实例
manga_repository = MangaRepository()