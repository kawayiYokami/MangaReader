"""
统一缓存键生成器

提供统一的缓存键生成方法，确保不同实例间缓存键的一致性。
遵循架构设计原则，所有缓存键生成都通过此模块统一管理。
"""

import hashlib
from typing import Optional
from pathlib import Path


class CacheKeyGenerator:
    """统一缓存键生成器"""
    
    @staticmethod
    def generate_translation_key(manga_path: str, page_index: int, translator_id: str, target_language: str = "zh") -> str:
        """
        生成翻译缓存键
        
        Args:
            manga_path: 漫画文件路径
            page_index: 页面索引
            translator_id: 翻译引擎ID（如：zhipu-glm4, google等）
            target_language: 目标语言
            
        Returns:
            统一格式的翻译缓存键
        """
        # 标准化路径，确保跨平台一致性
        normalized_path = str(Path(manga_path).resolve()).replace('\\', '/')
        return f"translation:{normalized_path}:{page_index}:{target_language}:{translator_id}"
    
    @staticmethod
    def generate_original_key(manga_path: str, page_index: int) -> str:
        """
        生成原图缓存键
        
        Args:
            manga_path: 漫画文件路径
            page_index: 页面索引
            
        Returns:
            统一格式的原图缓存键
        """
        # 标准化路径，确保跨平台一致性
        normalized_path = str(Path(manga_path).resolve()).replace('\\', '/')
        return f"original:{normalized_path}:{page_index}"
    
    @staticmethod
    def generate_session_key(session_id: str, manga_path: str) -> str:
        """
        生成会话缓存键
        
        Args:
            session_id: 会话ID
            manga_path: 漫画文件路径
            
        Returns:
            统一格式的会话缓存键
        """
        normalized_path = str(Path(manga_path).resolve()).replace('\\', '/')
        return f"session:{session_id}:{normalized_path}"
    
    @staticmethod
    def generate_hash_key(content: str) -> str:
        """
        生成内容哈希键（用于去重）
        
        Args:
            content: 要哈希的内容
            
        Returns:
            SHA256哈希值
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    @staticmethod
    def parse_translation_key(cache_key: str) -> Optional[dict]:
        """
        解析翻译缓存键

        Args:
            cache_key: 缓存键

        Returns:
            解析后的字典或None
        """
        try:
            parts = cache_key.split(':')
            if len(parts) >= 5 and parts[0] == 'translation':
                # 重新组合路径部分（可能包含冒号）
                manga_path = ':'.join(parts[1:-3])  # 除了最后3个部分
                page_index = int(parts[-3])
                target_language = parts[-2]
                translator_id = parts[-1]

                return {
                    'type': 'translation',
                    'manga_path': manga_path,
                    'page_index': page_index,
                    'target_language': target_language,
                    'translator_id': translator_id
                }
        except (ValueError, IndexError):
            pass
        return None
    
    @staticmethod
    def parse_original_key(cache_key: str) -> Optional[dict]:
        """
        解析原图缓存键

        Args:
            cache_key: 缓存键

        Returns:
            解析后的字典或None
        """
        try:
            parts = cache_key.split(':')
            if len(parts) >= 3 and parts[0] == 'original':
                # 重新组合路径部分（可能包含冒号）
                manga_path = ':'.join(parts[1:-1])  # 除了第一个和最后一个部分
                page_index = int(parts[-1])

                return {
                    'type': 'original',
                    'manga_path': manga_path,
                    'page_index': page_index
                }
        except (ValueError, IndexError):
            pass
        return None


# 全局实例
_cache_key_generator = CacheKeyGenerator()

def get_cache_key_generator() -> CacheKeyGenerator:
    """获取全局缓存键生成器实例"""
    return _cache_key_generator
