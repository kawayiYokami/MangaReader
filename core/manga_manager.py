import os
import json
from core.manga_model import MangaInfo, MangaLoader
from utils import manga_logger as log

class MangaManager:
    def __init__(self, manga_dir=''):
        log.info("初始化MangaManager")
        self.manga_dir = manga_dir
        self.manga_list = []
        self.tags = set()
        self.config_file = 'manga_config.json'
        self._load_config()
        log.info(f"MangaManager初始化完成，当前目录: {self.manga_dir}, 漫画数量: {len(self.manga_list)}")
    
    def set_manga_dir(self, dir_path):
        log.info(f"设置漫画目录: {dir_path}")
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            self.manga_dir = dir_path
            log.info(f"目录有效，开始扫描漫画文件")
            self.scan_manga_files()
        else:
            log.warning(f"目录无效或不存在: {dir_path}")
    
    def scan_manga_files(self):
        if not self.manga_dir:
            log.warning("未设置漫画目录，无法扫描文件")
            return
        
        self.manga_list.clear()
        self.tags.clear()
        
        try:
            # 使用 MangaLoader 的递归扫描方法
            manga_files = MangaLoader.find_manga_files(self.manga_dir)
            
            for file_path in manga_files:
                manga = MangaLoader.load_manga(file_path)
                if manga and manga.is_valid:
                    self.manga_list.append(manga)
                    self.tags.update(manga.tags)
                else:
                    log.warning(f"无法加载漫画: {file_path}")
            
            log.info(f"扫描完成，成功加载 {len(self.manga_list)} 本漫画，共 {len(self.tags)} 个标签")
        except Exception as e:
            log.error(f"扫描漫画文件时发生错误: {str(e)}")
    
    def filter_manga(self, tag_filters):
        if not tag_filters:
            return self.manga_list
        
        log.info(f"开始按标签过滤漫画，过滤标签: {tag_filters}")
        filtered_list = []
        for manga in self.manga_list:
            match = True
            for tag in tag_filters:
                if tag not in manga.tags:
                    match = False
                    break
            if match:
                filtered_list.append(manga)
        
        log.info(f"过滤完成，从 {len(self.manga_list)} 本漫画中筛选出 {len(filtered_list)} 本")
        return filtered_list
    
    def _load_config(self):
        log.info(f"尝试加载配置文件: {self.config_file}")
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.manga_dir = config.get('manga_dir', '')
                    log.info(f"从配置文件加载漫画目录: {self.manga_dir}")
                    if self.manga_dir:
                        if os.path.exists(self.manga_dir) and os.path.isdir(self.manga_dir):
                            log.info("开始扫描漫画文件")
                            self.scan_manga_files()
                        else:
                            log.warning(f"配置文件中的漫画目录不存在或无效: {self.manga_dir}")
            except Exception as e:
                log.error(f"加载配置文件时发生错误: {str(e)}")
        else:
            log.info("配置文件不存在，使用默认设置")
    
    def save_config(self):
        log.info(f"保存配置到文件: {self.config_file}")
        try:
            config = {
                'manga_dir': self.manga_dir
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            log.info("配置保存成功")
        except Exception as e:
            log.error(f"保存配置文件时发生错误: {str(e)}")
    
    def rename_manga_file(self, manga, new_name):
        """重命名漫画文件"""
        log.info(f"尝试重命名漫画: {manga.title} -> {new_name}")
        if not manga or not manga.file_path or not os.path.exists(manga.file_path):
            log.error("无效的漫画对象或文件不存在")
            return False
        
        try:
            # 获取文件目录和扩展名
            file_dir = os.path.dirname(manga.file_path)
            file_ext = os.path.splitext(manga.file_path)[1]
            
            # 构建新的文件路径
            new_file_path = os.path.join(file_dir, new_name + file_ext)
            
            # 检查新文件名是否已存在
            if os.path.exists(new_file_path):
                log.error(f"文件已存在，无法重命名: {new_file_path}")
                return False
            
            # 重命名文件
            os.rename(manga.file_path, new_file_path)
            
            # 更新漫画对象的属性
            old_title = manga.title
            manga.title = new_name + file_ext
            manga.file_path = new_file_path
            
            log.info(f"漫画重命名成功: {old_title} -> {manga.title}")
            return True
        except Exception as e:
            log.error(f"重命名漫画时发生错误: {str(e)}")
            return False