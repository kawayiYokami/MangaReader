import os
import json
from utils import manga_logger as log

# 缓存文件路径
CACHE_DIR = "app/config"
CACHE_FILE = os.path.join(CACHE_DIR, "manga_scan_cache.json")

class MangaCache:
    """漫画扫描结果缓存管理类"""
    
    def __init__(self):
        """初始化缓存管理器"""
        self.cache = {}
        # 确保缓存目录存在
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
            log.info(f"创建缓存目录: {CACHE_DIR}")
        self._load_cache()
    
    def _load_cache(self):
        """从文件加载缓存"""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                log.info(f"从 {CACHE_FILE} 加载缓存成功")
            except (IOError, json.JSONDecodeError) as e:
                log.error(f"加载缓存文件 {CACHE_FILE} 时出错: {e}，将使用空缓存")
                self.cache = {}
        else:
            log.info(f"缓存文件 {CACHE_FILE} 不存在，将使用空缓存")
            self.cache = {}
    
    def save_cache(self):
        """将缓存保存到文件"""
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=4)
            log.info(f"缓存已保存到 {CACHE_FILE}")
        except IOError as e:
            log.error(f"保存缓存文件 {CACHE_FILE} 时出错: {e}")
    
    def get_manga_list(self, directory):
        """获取指定目录的漫画列表缓存
        
        Args:
            directory (str): 漫画目录路径
            
        Returns:
            dict: 包含漫画信息的字典，如果没有缓存则返回None
        """
        if directory in self.cache:
            return self.cache[directory]
        return None
    
    def update_manga_list(self, directory, manga_list):
        """更新指定目录的漫画列表缓存
        
        Args:
            directory (str): 漫画目录路径
            manga_list (list): 漫画信息列表，每个元素是一个字典，包含漫画的基本信息
        """
        # 将漫画列表转换为可序列化的格式
        serializable_list = []
        for manga in manga_list:
            if hasattr(manga, "file_path") and hasattr(manga, "last_modified"):
                manga_info = {
                    "file_path": manga.file_path,
                    "title": manga.title,
                    "tags": list(manga.tags),
                    "total_pages": manga.total_pages,
                    "is_valid": manga.is_valid,
                    "last_modified": manga.last_modified,
                    "pages": manga.pages
                }
                serializable_list.append(manga_info)
        
        self.cache[directory] = serializable_list
        self.save_cache()
        log.info(f"已更新目录 {directory} 的漫画列表缓存，共 {len(serializable_list)} 本漫画")
    
    def is_manga_modified(self, file_path):
        """检查漫画文件是否被修改
        
        Args:
            file_path (str): 漫画文件路径
            
        Returns:
            bool: 如果文件被修改或不存在于缓存中，返回True；否则返回False
        """
        if not os.path.exists(file_path):
            return True  # 文件不存在，视为已修改
        
        current_mtime = os.path.getmtime(file_path)
        
        # 在所有缓存的目录中查找该文件
        for directory, manga_list in self.cache.items():
            for manga in manga_list:
                if manga["file_path"] == file_path:
                    # 比较最后修改时间
                    return current_mtime > manga["last_modified"]
        
        return True  # 缓存中没有找到，视为已修改
    
    def clear_cache(self):
        """清空所有缓存"""
        self.cache = {}
        if os.path.exists(CACHE_FILE):
            try:
                os.remove(CACHE_FILE)
                log.info(f"缓存文件 {CACHE_FILE} 已删除")
            except Exception as e:
                log.error(f"删除缓存文件 {CACHE_FILE} 时出错: {e}")

# 创建全局缓存实例
manga_cache = MangaCache()