# core/manga_manager.py

import os
from PyQt5.QtCore import QObject, pyqtSignal # 这些在您的代码中已导入
from core.manga_model import MangaInfo, MangaLoader # 这些在您的代码中已导入
from core.config import config # 导入 config 对象
from utils import manga_logger as log # 这个在您的代码中已导入


class MangaManager(QObject):
    # 信号定义（保持不变）
    data_loaded = pyqtSignal(list)
    data_loading = pyqtSignal()
    data_load_failed = pyqtSignal(str)
    tags_updated = pyqtSignal(set)

    filter_applied = pyqtSignal(list)
    filter_cleared = pyqtSignal()
    file_renamed = pyqtSignal(str, str)
    file_opened = pyqtSignal(str)
    dir_changed = pyqtSignal(str)

    current_manga_changed = pyqtSignal(object)
    view_mode_changed = pyqtSignal(int)
    page_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        log.info("初始化MangaManager")

        self.manga_list = []
        self.tags = set()
        self.current_manga = None # 当前漫画对象，不直接持久化

        # 访问 config 值时使用 .value
        log.info(f"MangaManager初始化完成，当前目录: {config.manga_dir.value}, 漫画数量: {len(self.manga_list)}")

        # 访问 config 值时使用 .value，并检查目录是否存在且有效
        if config.manga_dir.value and os.path.exists(config.manga_dir.value) and os.path.isdir(config.manga_dir.value):
             self.scan_manga_files()
        # 访问 config 值时使用 .value
        elif config.manga_dir.value:
             log.warning(f"配置文件中的漫画目录不存在或无效: {config.manga_dir.value}")


    def set_manga_dir(self, dir_path):
        log.info(f"设置漫画目录: {dir_path}")
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            config.manga_dir.value = dir_path # 设置 config 值时使用 .value
            self.save_config()
            log.info(f"目录有效，开始扫描漫画文件")
            self.scan_manga_files()
            self.dir_changed.emit(config.manga_dir.value) # 发送信号时使用 .value
        else:
            log.warning(f"目录无效或不存在: {dir_path}")


    def scan_manga_files(self):
        # 访问 config 值时使用 .value
        if not config.manga_dir.value:
            log.warning("未设置漫画目录，无法扫描文件")
            return

        self.data_loading.emit()
        self.manga_list.clear()
        self.tags.clear()

        try:
            # 访问 config 值时使用 .value
            manga_files = MangaLoader.find_manga_files(config.manga_dir.value)

            for file_path in manga_files:
                manga = MangaLoader.load_manga(file_path)
                if manga and manga.is_valid:
                    self.manga_list.append(manga)
                else:
                    log.warning(f"无法加载漫画: {file_path}")

            log.info(f"扫描完成，成功加载 {len(self.manga_list)} 本漫画")

            # 根据 config 中的开关决定是否执行
            self.optimize_tags()
            self.analyze_and_merge_tags()
            self.translate_titles()

            for manga in self.manga_list:
                self.tags.update(manga.tags)

            log.info(f"标签收集完成，共收集 {len(self.tags)} 个标签")

            self.data_loaded.emit(self.manga_list)
            self.tags_updated.emit(self.tags)
            self.filter_manga([])

            # 恢复上次阅读状态
            # 访问 config 值时使用 .value
            if config.current_manga_path.value and os.path.exists(config.current_manga_path.value):
                 # 访问 config 值时使用 .value
                 found_manga = next((m for m in self.manga_list if m.file_path == config.current_manga_path.value), None)
                 if found_manga:
                     self.set_current_manga(found_manga)
                     # 访问 config 值时使用 .value
                     self.change_page(config.current_page.value)

        except Exception as e:
            error_msg = f"扫描漫画文件时发生错误: {str(e)}"
            log.error(error_msg)
            self.data_load_failed.emit(error_msg)


    def change_page(self, page_number):
        if self.current_manga is None:
            log.warning("未选择漫画，无法改变页码")
            return

        total_pages = len(self.current_manga.pages) if self.current_manga.pages else 0
        if 0 <= page_number < total_pages:
            config.current_page.value = page_number # 设置 config 值时使用 .value
            # self.current_page = page_number # 移除了 MangaManager 自身的页码属性
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

    def translate_titles(self):
        if not config.translate_title.value: # 访问 config 值时使用 .value
            return

        import zhconv

        log.info("开始翻译作品名和标题")
        for manga in self.manga_list:
            if manga.title:
                manga.title = zhconv.convert(manga.title, 'zh-hans')
        log.info("作品名和标题翻译完成")


    def optimize_tags(self):
        if not config.simplify_chinese.value: # 访问 config 值时使用 .value
             return

        import zhconv


        for manga in self.manga_list:
            simplified_tags = set()
            for tag in manga.tags:
                simplified_tag = zhconv.convert(tag, 'zh-hans')
                simplified_tags.add(simplified_tag)
            manga.tags = simplified_tags



    def analyze_and_merge_tags(self, similarity_threshold=0.9):
        if not config.merge_tags.value: # 访问 config 值时使用 .value
            return

        from difflib import SequenceMatcher

        for manga in self.manga_list:
             tags_list = list(manga.tags)
             merged_tags = set()
             while tags_list:
                 current_tag = tags_list.pop(0)
                 merged = False
                 if current_tag.startswith(('作者', '作品', '汉化')):
                     for merged_tag in merged_tags:
                         similarity = SequenceMatcher(None, current_tag, merged_tag).ratio()
                         if similarity >= similarity_threshold:
                             merged = True
                             break
                 if not merged:
                     merged_tags.add(current_tag)
             manga.tags = merged_tags


    def save_config(self):
        log.info(f"保存配置到文件: {config.file}")
        try:
            # 调用 config.save 方法保存所有 ConfigItem
            config.save()
            log.info("配置保存成功")
        except Exception as e:
            log.error(f"保存配置文件失败: {e}")


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
            manga.title = new_name
            manga.file_path = new_file_path

            log.info(f"漫画重命名成功: {old_title} -> {manga.title}")
            self.file_renamed.emit(manga.file_path, new_file_path)

            if self.current_manga == manga:
                config.current_manga_path.value = new_file_path # 设置 config 值时使用 .value
                self.save_config()

            return True
        except Exception as e:
            log.error(f"重命名漫画时发生错误: {str(e)}")
            return False


    def set_current_manga(self, manga):
        if manga != self.current_manga:
            log.info(f"切换当前漫画: {manga.title if manga else 'None'}")
            self.current_manga = manga
            config.current_manga_path.value = manga.file_path if manga else '' # 设置 config 值时使用 .value
            # 调用 change_page，change_page 会负责更新 config.current_page
            self.change_page(0)
            self.current_manga_changed.emit(manga)

    def set_current_manga_by_path(self, file_path):
         found_manga = next((m for m in self.manga_list if m.file_path == file_path), None)
         if found_manga:
             self.set_current_manga(found_manga)
             # 访问 config 值时使用 .value
             self.change_page(config.current_page.value)