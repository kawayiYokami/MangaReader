import os
import json
from PyQt5.QtCore import QObject, pyqtSignal
from core.manga_model import MangaInfo, MangaLoader
from utils import manga_logger as log

class MangaManager(QObject):
    # 数据状态信号
    data_loaded = pyqtSignal(list)      # 漫画数据加载完成
    data_loading = pyqtSignal()         # 开始加载数据
    data_load_failed = pyqtSignal(str)  # 加载失败(错误信息)
    tags_updated = pyqtSignal(set)      # 标签集合更新
    
    # 用户操作信号
    filter_applied = pyqtSignal(list)    # 应用过滤后的漫画列表
    filter_cleared = pyqtSignal()        # 清除过滤条件
    file_renamed = pyqtSignal(str, str)  # (旧路径, 新路径)
    file_opened = pyqtSignal(str)        # 文件打开通知
    dir_changed = pyqtSignal(str)        # 新增：目录变更信号(新目录路径)
    
    # 视图交互信号
    current_manga_changed = pyqtSignal(object)  # 当前选中漫画对象
    view_mode_changed = pyqtSignal(int)         # 视图模式变更
    page_changed = pyqtSignal(int)             # 页码变更信号

    def __init__(self, manga_dir=''):
        super().__init__()
        log.info("初始化MangaManager")
        self.manga_dir = manga_dir
        self.manga_list = []
        self.tags = set()
        self.config_file = 'manga_config.json'
        self.current_manga = None  # 当前选中的漫画
        self.current_page = 0      # 当前页码
        self._load_config()
        log.info(f"MangaManager初始化完成，当前目录: {self.manga_dir}, 漫画数量: {len(self.manga_list)}")
    
    def set_manga_dir(self, dir_path):
        log.info(f"设置漫画目录: {dir_path}")
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            self.manga_dir = dir_path
            self.save_config()
            log.info(f"目录有效，开始扫描漫画文件")
            self.scan_manga_files()
        else:
            log.warning(f"目录无效或不存在: {dir_path}")
    
    def scan_manga_files(self):
        if not self.manga_dir:
            log.warning("未设置漫画目录，无法扫描文件")
            return
        
        self.data_loading.emit()
        self.manga_list.clear()
        self.tags.clear()
        
        try:
            manga_files = MangaLoader.find_manga_files(self.manga_dir)
            
            for file_path in manga_files:
                manga = MangaLoader.load_manga(file_path)
                if manga and manga.is_valid:
                    self.manga_list.append(manga)
                    self.tags.update(manga.tags)
                else:
                    log.warning(f"无法加载漫画: {file_path}")
            
            log.info(f"扫描完成，成功加载 {len(self.manga_list)} 本漫画，共 {len(self.tags)} 个标签")
            # 漫画列表存储在self.manga_list中
            # 标签集合存储在self.tags中
            self.optimize_tags()
            self.analyze_and_merge_tags()
            self.data_loaded.emit(self.manga_list)
            self.tags_updated.emit(self.tags)
            self.filter_manga([])  # 新增：触发初始过滤，显示所有漫画
        except Exception as e:
            error_msg = f"扫描漫画文件时发生错误: {str(e)}"
            log.error(error_msg)
            self.data_load_failed.emit(error_msg)
            raise
    
    def change_page(self, page_number):
        """改变当前页码"""
        if self.current_manga is None:
            log.warning("未选择漫画，无法改变页码")
            return
            
        total_pages = len(self.current_manga.pages) if self.current_manga.pages else 0
        if 0 <= page_number < total_pages:
            self.current_page = page_number
            self.page_changed.emit(page_number)
        else:
            log.warning(f"页码超出范围: {page_number + 1}, 总页数: {total_pages}")
    
    def filter_manga(self, tag_filters):
        if not tag_filters:
            self.filter_cleared.emit()
            self.filter_applied.emit(self.manga_list)
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
        self.filter_applied.emit(filtered_list)
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
    
    def translate_titles(self):
        """
        翻译作品名和标题为中文
        """
        import zhconv
        
        log.info("开始翻译作品名和标题")
        
        for manga in self.manga_list:
            if manga.title:
                manga.title = zhconv.convert(manga.title, 'zh-hans')
            
        log.info("作品名和标题翻译完成")
        
    def optimize_tags(self):
        """
        优化加载回来的标签
        这个方法会在data_loaded信号发射前被调用
        功能：将标签中的繁体中文转换为简体中文
        """
        import zhconv
        
        log.info(f"开始优化标签，原始标签数量: {len(self.tags)}")
        log.debug(f"原始标签内容: {self.tags}")
        
        simplified_tags = set()
        for tag in self.tags:
            simplified_tag = zhconv.convert(tag, 'zh-hans')
            simplified_tags.add(simplified_tag)
            
        log.info(f"标签优化完成，转换后标签数量: {len(simplified_tags)}")
        log.debug(f"转换后标签内容: {simplified_tags}")
        
        self.tags = simplified_tags
        self.translate_titles()
        
    def analyze_and_merge_tags(self, similarity_threshold=0.9):
        """
        分析并合并相似的标签
        :param similarity_threshold: 相似度阈值(0-1之间)，默认0.8
        """
        from difflib import SequenceMatcher
        
        log.info(f"开始分析并合并相似标签，当前标签数量: {len(self.tags)}")
        
        tags_list = list(self.tags)
        merged_tags = set()
        
        while tags_list:
            current_tag = tags_list.pop(0)
            merged = False
            
            # 对特定前缀标签执行合并操作
            if current_tag.startswith(('作者', '作品', '汉化')):
                for merged_tag in merged_tags:
                    # 计算标签相似度
                    similarity = SequenceMatcher(None, current_tag, merged_tag).ratio()
                    if similarity >= similarity_threshold:
                        log.debug(f"合并相似标签: '{current_tag}' -> '{merged_tag}' (相似度: {similarity:.2f})")
                        merged = True
                        break
            
            # 所有标签都会被保留，非特定前缀标签直接添加
            if not merged:
                merged_tags.add(current_tag)
            
            if not merged:
                merged_tags.add(current_tag)
        
        log.info(f"标签合并完成，从 {len(self.tags)} 个标签合并为 {len(merged_tags)} 个")
        self.tags = merged_tags
        self.tags_updated.emit(self.tags)

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
        log.info(f"尝试重命名漫画: {manga.title} -> {new_name}")
        if not manga or not manga.file_path or not os.path.exists(manga.file_path):
            log.error("无效的漫画对象或文件不存在")
            return False
        
        try:
            file_dir = os.path.dirname(manga.file_path)
            file_ext = os.path.splitext(manga.file_path)[1]
            new_file_path = os.path.join(file_dir, new_name + file_ext)
            
            if os.path.exists(new_file_path):
                log.error(f"文件已存在，无法重命名: {new_file_path}")
                return False
            
            os.rename(manga.file_path, new_file_path)
            old_title = manga.title
            manga.title = new_name + file_ext
            manga.file_path = new_file_path
            
            log.info(f"漫画重命名成功: {old_title} -> {manga.title}")
            self.file_renamed.emit(manga.file_path, new_file_path)
            return True
        except Exception as e:
            log.error(f"重命名漫画时发生错误: {str(e)}")
            return False
    
    def set_current_manga(self, manga):
        """设置当前阅读的漫画"""
        if manga != self.current_manga:
            log.info(f"切换当前漫画: {manga.title if manga else 'None'}")
            self.current_manga = manga
            self.current_page = 0  # 重置页码
            self.current_manga_changed.emit(manga)  # 发送信号通知视图更新