# core/manga_manager.py

import os
from PySide6.QtCore import QObject, Signal  # 导入 PySide6 的信号
from core.manga.manga_model import MangaInfo, MangaLoader
from core.config import config
from utils import manga_logger as log
from core.translation.translator import TranslatorFactory
from core.core_cache.cache_factory import get_cache_factory_instance # Added
from core.core_cache.cache_interface import CacheInterface # Added


class MangaManager(QObject):
    # 信号定义
    data_loaded = Signal(list)
    data_loading = Signal()
    data_load_failed = Signal(str)
    tags_updated = Signal(set)

    filter_applied = Signal(list)
    filter_cleared = Signal()
    file_renamed = Signal(str, str)
    file_opened = Signal(str)
    dir_changed = Signal(str)

    current_manga_changed = Signal(object)
    view_mode_changed = Signal(int)
    page_changed = Signal(int)
    manga_list_updated = Signal(list)
    tags_cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        import inspect
        caller_frame = inspect.currentframe().f_back
        caller_info = inspect.getframeinfo(caller_frame)
        log.info(f"MangaManager初始化 - 调用者: {caller_info.filename}:{caller_info.lineno} 函数: {caller_info.function}")
        if self.parent: # Check if parent exists
             log.info(f"父类类型: {self.parent.__class__}")
        else:
            log.info("MangaManager 没有父对象")


        self.manga_list_cache_manager: CacheInterface = get_cache_factory_instance().get_manager("manga_list")
        self.translation_cache_manager: CacheInterface = get_cache_factory_instance().get_manager("translation")
        # self.ocr_cache_manager: CacheInterface = get_cache_factory_instance().get_manager("ocr") # If needed directly

        self.manga_list = []
        self.tags = set()
        self.current_manga = None

        # 初始化时直接从缓存加载漫画库
        self.load_library_from_cache()

        log.info(
            f"MangaManager初始化完成，从缓存加载了 {len(self.manga_list)} 本漫画"
        )
            
    def save_config(self):
        """保存配置到文件"""
        try:
            config.save()
            log.info("配置已保存")
        except Exception as e:
            log.error(f"保存配置时发生错误: {str(e)}")
            
    def create_translator(self):
        """根据配置创建翻译器实例"""
        try:
            translator_type = config.translator_type.value
            log.info(f"创建翻译器: {translator_type}")
            
            if translator_type == "智谱":
                return TranslatorFactory.create_translator(
                    translator_type=translator_type,
                    api_key=config.zhipu_api_key.value,
                    model=config.zhipu_model.value
                )
            elif translator_type == "Google":
                return TranslatorFactory.create_translator(
                    translator_type=translator_type,
                    api_key=config.google_api_key.value
                )
            else:
                log.warning(f"未知的翻译器类型: {translator_type}，使用Google翻译作为默认选项")
                return TranslatorFactory.create_translator("Google")
        except Exception as e:
            log.error(f"创建翻译器时发生错误: {str(e)}，使用Google翻译作为备选")
            return TranslatorFactory.create_translator("Google")
            
    def clear_translation_cache(self):
        """清空翻译缓存"""
        try:
            self.translation_cache_manager.clear()
            log.info("翻译缓存已通过 TranslationCacheManager 清空")
            # 移除旧的兼容代码，因为它直接操作文件，与新管理器冲突
        except Exception as e:
            log.error(f"通过 TranslationCacheManager 清空翻译缓存时发生错误: {str(e)}")
            
    def clear_manga_cache(self):
        """清空漫画扫描缓存"""
        try:
            self.manga_list_cache_manager.clear()
            log.info("漫画扫描缓存已通过 MangaListCacheManager 清空")
        except Exception as e:
            log.error(f"通过 MangaListCacheManager 清空漫画扫描缓存时发生错误: {str(e)}")

    def clear_all_data(self):
        """清空所有加载的漫画数据和缓存"""
        log.info("开始清空所有漫画数据和缓存")
        self.manga_list.clear()
        self.tags.clear()
        self.current_manga = None
        
        # 清空配置中的当前漫画路径
        config.current_manga_path.value = ""
        config.current_page.value = 0
        self.save_config()

        # 清空缓存
        self.clear_manga_cache()
        self.clear_translation_cache()

        # 发送信号通知UI更新
        self.filter_applied.emit([])
        self.tags_cleared.emit() # 发送标签清空信号
        log.info("所有漫画数据和缓存已清空")

    def add_manga_from_path(self, path: str):
        """从指定路径（文件或文件夹）扫描并添加漫画到主库中。"""
        if not os.path.exists(path):
            log.error(f"路径不存在，无法添加: {path}")
            return
        
        self.data_loading.emit()
        log.info(f"开始从路径添加漫画: {path}")
        
        try:
            newly_scanned_mangas = []
            if os.path.isdir(path):
                manga_files = MangaLoader.find_manga_files(path)
                for file_path in manga_files:
                    manga = MangaLoader.load_manga(file_path, analyze_dimensions=config.enable_dimension_analysis.value)
                    if manga and manga.is_valid:
                        newly_scanned_mangas.append(manga)
            elif os.path.isfile(path):
                 manga = MangaLoader.load_manga(path, analyze_dimensions=config.enable_dimension_analysis.value)
                 if manga and manga.is_valid:
                    newly_scanned_mangas.append(manga)
            
            if not newly_scanned_mangas:
                log.warning(f"路径 {path} 中未找到有效漫画。")
                self.data_loaded.emit(self.manga_list) # 仍然发送信号，以便UI可以停止加载状态
                return

            # 使用字典来合并新旧漫画，确保唯一性并处理更新
            merged_mangas = {m.file_path: m for m in self.manga_list}
            added_count = 0
            updated_count = 0

            for new_manga in newly_scanned_mangas:
                if new_manga.file_path in merged_mangas:
                    updated_count += 1
                else:
                    added_count += 1
                # 无论新增还是更新，都将新对象放入字典
                merged_mangas[new_manga.file_path] = new_manga
            
            # 循环结束后，从字典的值重建最终列表
            self.manga_list = list(merged_mangas.values())

            log.info(f"添加完成: 新增 {added_count} 本, 更新 {updated_count} 本。漫画库总数: {len(self.manga_list)}")

            # 更新标签和缓存
            self._update_tags_and_cache()
            
        except Exception as e:
            error_msg = f"从路径 {path} 添加漫画时发生错误: {e}"
            log.error(error_msg, exc_info=True)
            self.data_load_failed.emit(error_msg)

    def load_library_from_cache(self):
        """从缓存加载主漫画库。"""
        self.data_loading.emit()
        try:
            cache_key = self.manga_list_cache_manager.generate_key()
            cached_data = self.manga_list_cache_manager.get(cache_key)

            if not cached_data:
                log.info("漫画库缓存为空，无需加载。")
                self.manga_list = []
                self.tags = set()
                self.data_loaded.emit(self.manga_list)
                return

            log.info(f"从缓存加载漫画列表，共 {len(cached_data)} 条记录")
            self.manga_list.clear()
            
            for manga_data in cached_data:
                file_path = manga_data.get("file_path")
                # 检查文件是否存在，如果不存在则不加载，下次添加时会自动处理
                if file_path and os.path.exists(file_path):
                    manga = MangaInfo(
                        file_path,
                        last_modified=manga_data.get("last_modified", 0)
                    )
                    manga.title = manga_data.get("title", os.path.basename(file_path))
                    manga.tags = set(manga_data.get("tags", []))
                    manga.total_pages = manga_data.get("total_pages", 0)
                    manga.is_valid = manga_data.get("is_valid", True) # 缓存中的通常是有效的
                    manga.last_modified = manga_data.get("last_modified", 0)
                    self.manga_list.append(manga)
                else:
                    log.warning(f"缓存中的漫画文件不存在，已跳过: {file_path}")

            log.info(f"成功从缓存加载 {len(self.manga_list)} 本有效漫画。")
            self._update_tags_and_cache(save_to_cache=False) # 只更新标签，不重复写入缓存

        except Exception as e:
            error_msg = f"从缓存加载漫画库时发生错误: {e}"
            log.error(error_msg, exc_info=True)
            self.data_load_failed.emit(error_msg)

    def _update_tags_and_cache(self, save_to_cache=True):
        """辅助函数，用于更新标签和保存缓存。"""
        # 重新收集所有漫画的标签
        self.tags.clear()
        for manga in self.manga_list:
            self.tags.update(manga.tags)
        log.info(f"标签收集完成，共收集 {len(self.tags)} 个标签")

        if save_to_cache:
            cache_key = self.manga_list_cache_manager.generate_key()
            self.manga_list_cache_manager.set(cache_key, self.manga_list)
            log.info(f"主漫画库已更新到缓存中，共 {len(self.manga_list)} 本。")

        # 发送信号通知UI更新
        self.data_loaded.emit(self.manga_list)
        self.tags_updated.emit(self.tags)
        self.filter_manga([]) # 应用空过滤器以显示所有

    def change_page(self, page_number):
        if self.current_manga is None:
            log.warning("未选择漫画，无法改变页码")
            return

        total_pages = len(self.current_manga.pages) if self.current_manga.pages else 0
        if 0 <= page_number < total_pages:
            config.current_page.value = page_number  # 设置 config 值时使用 .value
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

        log.info(
            f"过滤完成，从 {len(self.manga_list)} 本漫画中筛选出 {len(filtered_list)} 本"
        )
        self.filter_applied.emit(filtered_list)
        return filtered_list

    def translate_titles(self):
        if not config.translate_title.value:  # 访问 config 值时使用 .value
            return

        import zhconv

        log.info("开始翻译作品名和标题")
        for manga in self.manga_list:
            if manga.title:
                manga.title = zhconv.convert(manga.title, "zh-hans")
        log.info("作品名和标题翻译完成")

    def analyze_manga_dimensions(self, force_reanalyze: bool = False):
        """
        为需要的ZIP漫画进行尺寸分析（只分析ZIP文件，文件夹漫画不需要分析）

        Args:
            force_reanalyze: 是否强制重新分析（即使已有分析结果）
        """
        from core.manga.manga_model import MangaLoader
        import os

        # 筛选需要分析的ZIP漫画（排除文件夹）
        need_analysis = []
        for manga in self.manga_list:
            # 只分析ZIP文件，跳过文件夹
            if os.path.isdir(manga.file_path):
                continue
            if force_reanalyze or manga.dimension_variance is None:
                need_analysis.append(manga)

        # DEBUG: 检查漫画列表中的方差数据
        zip_count = 0
        analyzed_count = 0
        for manga in self.manga_list[:10]:  # 只检查前10个
            if not os.path.isdir(manga.file_path):
                zip_count += 1
                if manga.dimension_variance is not None:
                    analyzed_count += 1
                log.debug(f"DEBUG ZIP漫画: {os.path.basename(manga.file_path)}, 方差={manga.dimension_variance}, 类型={type(manga.dimension_variance)}")

        log.info(f"DEBUG 统计: 前10个中有{zip_count}个ZIP文件，其中{analyzed_count}个已分析")

        if not need_analysis:
            log.info("所有ZIP漫画都已有尺寸分析数据，无需重新分析")
            return 0

        total_zip_count = len([m for m in self.manga_list if not os.path.isdir(m.file_path)])
        log.info(f"开始为 {len(need_analysis)} 本ZIP漫画进行尺寸分析（总共 {total_zip_count} 本ZIP漫画）")

        analyzed_count = 0
        failed_count = 0

        for i, manga in enumerate(need_analysis):
            try:
                log.info(f"正在分析 ({i+1}/{len(need_analysis)}): {manga.title}")

                # 调用MangaLoader的尺寸分析方法
                MangaLoader._analyze_manga_dimensions(manga)
                analyzed_count += 1

                log.debug(f"完成尺寸分析: {manga.file_path}, "
                         f"方差分数={manga.dimension_variance:.3f}, "
                         f"可能是漫画={manga.is_likely_manga}")

            except Exception as e:
                log.error(f"尺寸分析失败 {manga.file_path}: {e}")
                failed_count += 1
                # 设置默认值，避免重复分析
                manga.dimension_variance = 0.0
                manga.is_likely_manga = True

        log.info(f"尺寸分析完成: 成功分析 {analyzed_count} 本，失败 {failed_count} 本")

        # 更新缓存（保存分析结果）
        if analyzed_count > 0:
            try:
                from core.config import config
                cache_key = self.manga_list_cache_manager.generate_key(config.manga_dir.value)
                self.manga_list_cache_manager.set(cache_key, self.manga_list)
                log.info("已保存尺寸分析结果到缓存")
            except Exception as e:
                log.warning(f"保存尺寸分析结果到缓存失败: {e}")

        return analyzed_count

    def optimize_tags(self):
        if not config.simplify_chinese.value:  # 访问 config 值时使用 .value
            return

        import zhconv

        for manga in self.manga_list:
            simplified_tags = set()
            for tag in manga.tags:
                simplified_tag = zhconv.convert(tag, "zh-hans")
                simplified_tags.add(simplified_tag)
            manga.tags = simplified_tags

    def analyze_and_merge_tags(self, similarity_threshold=0.9):
        if not config.merge_tags.value:  # 访问 config 值时使用 .value
            return

        from difflib import SequenceMatcher

        for manga in self.manga_list:
            tags_list = list(manga.tags)
            merged_tags = set()
            while tags_list:
                current_tag = tags_list.pop(0)
                merged = False
                if current_tag.startswith(("作者", "作品", "汉化")):
                    for merged_tag in merged_tags:
                        similarity = SequenceMatcher(
                            None, current_tag, merged_tag
                        ).ratio()
                        if similarity >= similarity_threshold:
                            merged = True
                            break
                if not merged:
                    merged_tags.add(current_tag)
            manga.tags = merged_tags

    def save_config(self):
        log.info(f"保存配置到文件: {config.config_file}")
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
                config.current_manga_path.value = (
                    new_file_path  # 设置 config 值时使用 .value
                )
                self.save_config()

            return True
        except Exception as e:
            log.error(f"重命名漫画时发生错误: {str(e)}")
            return False

    def set_current_manga(self, manga):
        if manga != self.current_manga:
            log.info(f"切换当前漫画: {manga.title if manga else 'None'}")
            
            # 检查漫画文件是否存在，如果不存在则更新漫画列表
            if manga and not os.path.exists(manga.file_path):
                log.warning(f"漫画文件不存在: {manga.file_path}，将从列表中移除")
                self.manga_list = [m for m in self.manga_list if m.file_path != manga.file_path]
                # 更新缓存
                cache_key_update = self.manga_list_cache_manager.generate_key(config.manga_dir.value)
                self.manga_list_cache_manager.set(cache_key_update, self.manga_list)
                self.current_manga = None
                config.current_manga_path.value = ""
                self.current_manga_changed.emit(None)
                return
            
            # 检查漫画文件是否被修改，如果被修改则重新加载
            if manga:
                # is_manga_modified is now part of MangaListCacheManager
                if self.manga_list_cache_manager.is_manga_modified(manga.file_path):
                    log.info(f"漫画文件已修改，重新加载: {manga.file_path}")
                    updated_manga = MangaLoader.load_manga(manga.file_path)
                    if updated_manga and updated_manga.is_valid:
                        # 更新列表中的漫画对象
                        for i, m_loop in enumerate(self.manga_list): # Renamed m to m_loop to avoid conflict
                            if m_loop.file_path == manga.file_path:
                                self.manga_list[i] = updated_manga
                                manga = updated_manga # Update the manga variable being processed
                                break
                        # 更新缓存
                        cache_key_update_modified = self.manga_list_cache_manager.generate_key(config.manga_dir.value)
                        self.manga_list_cache_manager.set(cache_key_update_modified, self.manga_list)
            
            self.current_manga = manga
            config.current_manga_path.value = (
                manga.file_path if manga else ""
            )  # 设置 config 值时使用 .value
            # 调用 change_page，change_page 会负责更新 config.current_page
            self.change_page(0)
            self.current_manga_changed.emit(manga)

    def set_current_manga_by_path(self, file_path):
        found_manga = next(
            (m for m in self.manga_list if m.file_path == file_path), None
        )
        if found_manga:
            self.set_current_manga(found_manga)
            # 访问 config 值时使用 .value
            self.change_page(config.current_page.value)

    def clear_manga_cache(self):
        """清空漫画列表缓存"""
        try:
            # 使用新的单一key模型
            cache_key = self.manga_list_cache_manager.generate_key()
            self.manga_list_cache_manager.delete(cache_key)
            log.info("主漫画库缓存已清空")
        except Exception as e:
            log.error(f"清空漫画列表缓存失败: {e}")
            raise
