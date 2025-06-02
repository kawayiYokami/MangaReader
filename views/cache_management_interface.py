# views/cache_management_interface.py
from PySide6.QtCore import Qt, Slot, QPoint
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, 
                               QTableWidgetItem, QAbstractItemView, QHeaderView, QLabel,
                               QMenu, QDialog, QPushButton as QtWidgetsPushButton,
                               QDialogButtonBox, QTextEdit, QMessageBox) 
from qfluentwidgets import (ScrollArea, SubtitleLabel, setFont, PushButton, ComboBox, BodyLabel,
                            LineEdit as FluentLineEdit, InfoBar, InfoBarPosition, TableWidget)

# 项目内部导入
from typing import Any, Dict, List, Optional 
from core.cache_factory import get_cache_factory_instance
from core.cache_interface import CacheInterface
from core.manga_cache import MangaListCacheManager
from core.ocr_cache_manager import OcrCacheManager
from core.translation_cache_manager import TranslationCacheManager
from utils import manga_logger as log 
from ui.new_interface.manga_list import ClearConfirmDialog
from core.harmonization_map_manager import get_harmonization_map_manager_instance

class HarmonizationMappingDialog(QDialog):
    """
    生成/编辑和谐映射对话框
    """
    def __init__(self, original_text: str = "", current_harmonized_text: str = "", 
                 is_editing_existing_entry: bool = False, parent=None):
        super().__init__(parent)
        
        title = "编辑和谐映射" if is_editing_existing_entry else "新增和谐映射"
        self.setWindowTitle(title)
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        self.original_label = BodyLabel("原文 (Original Text):", self)
        self.original_text_edit = QTextEdit(self)
        self.original_text_edit.setPlainText(original_text)
        self.original_text_edit.setReadOnly(False) # Always allow editing the field
        self.original_text_edit.setToolTip("需要被替换的文本。")

        self.harmonized_label = BodyLabel("替换为 (Replacement Text):", self)
        self.harmonized_text_edit = QTextEdit(self)
        self.harmonized_text_edit.setPlainText(current_harmonized_text)
        self.harmonized_text_edit.setPlaceholderText("输入替换后的文本（留空表示不替换或删除原文）")
        self.harmonized_text_edit.setToolTip("原文将被替换为此文本。")

        layout.addWidget(self.original_label)
        layout.addWidget(self.original_text_edit)
        layout.addWidget(self.harmonized_label)
        layout.addWidget(self.harmonized_text_edit)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.setLayout(layout)
        # Focus based on whether it's a new entry or editing an existing one
        if is_editing_existing_entry and original_text: # Editing existing
            self.harmonized_text_edit.setFocus() # Focus on replacement
            self.harmonized_text_edit.selectAll()
        else: # New entry
            self.original_text_edit.setFocus() # Focus on original text

    def get_texts(self) -> tuple[str, str]:
        return self.original_text_edit.toPlainText().strip(), self.harmonized_text_edit.toPlainText().strip()

class CacheManagementInterface(QWidget):
    """
    缓存管理界面
    """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("cacheManagementInterface")
        self.harmonization_manager = get_harmonization_map_manager_instance() 

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self._init_control_panel()
        self._init_display_area()

        self.main_layout.addWidget(self.control_panel_scroll)
        self.main_layout.addWidget(self.display_area_scroll)
        self.main_layout.setStretchFactor(self.control_panel_scroll, 1) 
        self.main_layout.setStretchFactor(self.display_area_scroll, 3) 

        self.control_panel_scroll.setFixedWidth(300) 
        self._load_cache_data(self.cache_type_combo.currentText())

    def _init_control_panel(self):
        self.control_panel_scroll = ScrollArea(self)
        # --- CRITICAL CHANGE: Make control_panel_scroll and its viewport transparent ---
        self.control_panel_scroll.setStyleSheet("background: transparent;")
        self.control_panel_scroll.viewport().setStyleSheet("background: transparent;")
        # -----------------------------------------------------------------------------
        self.control_panel_scroll.setWidgetResizable(True)
        self.control_panel_scroll.setObjectName("controlPanelScroll")

        self.control_panel_widget = QWidget()
        self.control_panel_widget.setObjectName("controlPanelWidget")
        self.control_panel_layout = QVBoxLayout(self.control_panel_widget)
        self.control_panel_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.control_panel_layout.setContentsMargins(10, 10, 10, 10)
        self.control_panel_layout.setSpacing(15)

        title = SubtitleLabel("缓存管理", self)
        setFont(title, 18)
        self.control_panel_layout.addWidget(title)

        self.cache_type_label = BodyLabel("选择缓存类型:", self)
        self.cache_type_combo = ComboBox(self)
        self.cache_type_combo.addItems(["漫画列表", "OCR", "翻译", "和谐映射"]) 
        self.cache_type_combo.currentIndexChanged.connect(self._on_cache_type_changed) 

        self.control_panel_layout.addWidget(self.cache_type_label)
        self.control_panel_layout.addWidget(self.cache_type_combo)

        self.refresh_button = PushButton("刷新视图", self)
        self.refresh_button.clicked.connect(lambda: self._load_cache_data(self.cache_type_combo.currentText())) 

        self.clear_cache_button = PushButton("清空缓存", self)
        self.clear_cache_button.clicked.connect(self._on_clear_cache) 

        self.control_panel_layout.addWidget(self.refresh_button)
        self.control_panel_layout.addWidget(self.clear_cache_button)

        self.optimization_title = SubtitleLabel("优化操作", self)
        setFont(self.optimization_title, 16)
        self.control_panel_layout.addWidget(self.optimization_title)

        self.optimize_manga_button = PushButton("移除不存在目录条目", self)
        self.optimize_ocr_button = PushButton("移除不存在/已修改文件条目", self)
        self.optimize_translation_button = PushButton("移除旧条目", self) 

        self.control_panel_layout.addWidget(self.optimize_manga_button)
        self.control_panel_layout.addWidget(self.optimize_ocr_button)
        self.control_panel_layout.addWidget(self.optimize_translation_button)

        self.control_panel_layout.addStretch(1)
        self.control_panel_scroll.setWidget(self.control_panel_widget)

    def _init_display_area(self):
        self.display_area_scroll = ScrollArea(self)
        # --- CRITICAL CHANGE: Make display_area_scroll and its viewport transparent ---
        self.display_area_scroll.setStyleSheet("background: transparent;")
        self.display_area_scroll.viewport().setStyleSheet("background: transparent;")
        # ----------------------------------------------------------------------------
        self.display_area_scroll.setWidgetResizable(True)
        self.display_area_scroll.setObjectName("displayAreaScroll")

        self.display_area_widget_container = QWidget()
        self.display_area_container_layout = QVBoxLayout(self.display_area_widget_container)
        self.display_area_container_layout.setContentsMargins(10, 40, 10, 10)
        self.display_area_container_layout.setSpacing(10)

        self.filter_search_layout = QHBoxLayout()
        self.search_label = BodyLabel("搜索:", self)
        self.search_line_edit = FluentLineEdit(self) 
        self.search_line_edit.setPlaceholderText("输入搜索关键词")

        self.filter_label = BodyLabel("筛选:", self)
        self.filter_combo = ComboBox(self)
        self.filter_combo.addItem("所有") 

        self.apply_filter_search_button = PushButton("应用", self)
        self.reset_filter_button = PushButton("重置", self)

        self.filter_search_layout.addWidget(self.search_label)
        self.filter_search_layout.addWidget(self.search_line_edit, 1)
        self.filter_search_layout.addWidget(self.filter_label)
        self.filter_search_layout.addWidget(self.filter_combo)
        self.filter_search_layout.addWidget(self.apply_filter_search_button)
        self.filter_search_layout.addWidget(self.reset_filter_button)

        self.display_area_container_layout.addLayout(self.filter_search_layout)

        self.cache_table = TableWidget(self) 
        self.cache_table.setSortingEnabled(True)
        self.cache_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cache_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cache_table.verticalHeader().setVisible(False) 
        self.cache_table.horizontalHeader().setStretchLastSection(True) 

        self.cache_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.cache_table.customContextMenuRequested.connect(self._show_table_context_menu)

        self.display_area_container_layout.addWidget(self.cache_table)
        self.display_area_scroll.setWidget(self.display_area_widget_container)

    @Slot(QPoint)
    def _show_table_context_menu(self, pos: QPoint):
        current_cache_type_name = self.cache_type_combo.currentText()
        menu = QMenu(self)
        selected_items = self.cache_table.selectedItems()
        selected_row = -1
        if selected_items:
            item = selected_items[0] 
            selected_row = self.cache_table.row(item)

        if current_cache_type_name == "和谐映射":
            add_action = menu.addAction("新增映射")
            add_action.triggered.connect(self._add_harmonization_mapping_slot)

            if selected_row >= 0: 
                edit_action = menu.addAction("编辑选中映射")
                edit_action.triggered.connect(lambda checked=False, row=selected_row: self._edit_harmonization_mapping_slot(row))
                
                delete_action = menu.addAction("删除选中映射")
                delete_action.triggered.connect(lambda checked=False, row=selected_row: self._delete_harmonization_mapping_slot(row))
        
        elif current_cache_type_name == "翻译" and selected_row >= 0:
            original_text_item = self.cache_table.item(selected_row, 1) 
            is_sensitive_item = self.cache_table.item(selected_row, 3)  
            if is_sensitive_item and original_text_item and is_sensitive_item.text() == "是":
                harmonize_action = menu.addAction("从翻译生成和谐映射")
                harmonize_action.triggered.connect(lambda checked=False, text=original_text_item.text(): self._handle_harmonization_mapping_from_translation(text))
            
        if menu.actions():
            menu.exec(self.cache_table.viewport().mapToGlobal(pos))

    def _handle_delete_selected_entry(self, row_index: int):
        current_cache_type_name = self.cache_type_combo.currentText()
        cache_type_slug = self._map_cache_type_name_to_slug(current_cache_type_name)
        log.info(f"请求删除 '{current_cache_type_name}' 缓存中第 {row_index + 1} 行的条目 (generic handler)。")

        if cache_type_slug == "harmonization_map":
            log.warning("_handle_delete_selected_entry called for Harmonization Map, redirecting to specific handler.")
            self._delete_harmonization_mapping_slot(row_index)
            return
        try:
            factory = get_cache_factory_instance()
            manager = factory.get_manager(cache_type_slug)
            identifier_item = self.cache_table.item(row_index, 0) 
            if identifier_item:
                identifier = identifier_item.text()
                log.info(f"模拟删除条目 (generic): {identifier} from {current_cache_type_name}")
                InfoBar.success("模拟删除", f"条目 '{identifier[:30]}...' 已从缓存中移除（模拟）。", duration=3000, parent=self)
                self._load_cache_data(current_cache_type_name) 
            else:
                InfoBar.warning("删除失败", "无法确定要删除的条目 (generic)。", duration=3000, parent=self)
        except Exception as e:
            InfoBar.error("删除失败", f"删除缓存条目时发生错误 (generic): {e}", duration=5000, parent=self)

    def _handle_harmonization_mapping_from_translation(self, original_text: str):
        log.info(f"请求从翻译条目为原文生成和谐映射: '{original_text[:50]}...'")
        existing_harmonized_text = self.harmonization_manager.get_mapping(original_text)
        dialog = HarmonizationMappingDialog(
            original_text=original_text, 
            current_harmonized_text=(existing_harmonized_text or ""),
            is_editing_existing_entry=True, # Treat as editing, but original field in dialog is based on this
            parent=self
        )
        # In this specific flow, original_text from translation is fixed.
        # The dialog's original_text_edit will show it but should ideally be read-only.
        # Let's ensure HarmonizationMappingDialog handles this if is_editing_existing_entry is true
        # and original_text is provided.
        # For now, the dialog makes it editable. If user changes it, it will be a new mapping.
        # This might be acceptable. Or, a more specialized dialog for this flow.
        # Given current HarmonizationMappingDialog, original_text field will be editable.

        if dialog.exec():
            new_original_from_dialog, new_harmonized = dialog.get_texts() 
            
            # If user changed the original_text in dialog (which they can now)
            # we should use that new_original_from_dialog.
            # If original_text (from translation) must be preserved, dialog needs adjustment or this logic.
            # For now, assume user's input in dialog is king.
            final_original_text = new_original_from_dialog 

            if not final_original_text:
                 InfoBar.warning("操作中止", "原文不能为空。", duration=3000, parent=self)
                 return

            if self.harmonization_manager.add_or_update_mapping(final_original_text, new_harmonized):
                InfoBar.success("操作成功", "和谐映射已保存。", duration=3000, parent=self)
                if self.cache_type_combo.currentText() == "和谐映射":
                    self._load_cache_data("和谐映射")
            else:
                InfoBar.error("保存失败", "保存和谐映射时发生错误。", duration=5000, parent=self)
        else:
            log.info("用户取消了从翻译生成和谐映射操作。")

    @Slot(int)
    def _on_cache_type_changed(self, index: int):
        selected_type = self.cache_type_combo.itemText(index)
        self._load_cache_data(selected_type)

    def _load_cache_data(self, cache_type_name: str, search_term: str = "", filter_criteria: Any = None):
        log.info(f"加载 {cache_type_name} 缓存数据...")
        self.cache_table.clearContents()
        self.cache_table.setRowCount(0)
        self.cache_table.setColumnCount(0) 
        
        cache_type_slug = self._map_cache_type_name_to_slug(cache_type_name)
        data_loaded_count = 0

        try:
            if cache_type_slug == "harmonization_map":
                log.info("加载和谐映射数据...")
                mappings = self.harmonization_manager.get_all_mappings()
                headers = ["原始文本", "替换为"]
                self.cache_table.setColumnCount(len(headers))
                self.cache_table.setHorizontalHeaderLabels(headers)
                self.cache_table.setRowCount(len(mappings))
                for row_idx, (original, harmonized) in enumerate(mappings.items()):
                    self.cache_table.setItem(row_idx, 0, QTableWidgetItem(original))
                    self.cache_table.setItem(row_idx, 1, QTableWidgetItem(harmonized))
                data_loaded_count = len(mappings)
                log.info(f"成功加载和谐映射数据，共 {data_loaded_count} 条。")
            
            elif cache_type_slug in ["manga_list", "ocr", "translation"]:
                factory = get_cache_factory_instance()
                manager = factory.get_manager(cache_type_slug)
                data_for_display = [] 
                if isinstance(manager, MangaListCacheManager):
                    cached_directories = manager.get_all_entries_for_display()
                    all_manga_entries: List[Dict[str, Any]] = []
                    for dir_entry in cached_directories:
                        directory_path = dir_entry.get("directory_path")
                        if directory_path:
                            manga_list_in_dir = manager.get(directory_path)
                            if manga_list_in_dir:
                                all_manga_entries.extend(manga_list_in_dir)
                    headers = ["文件路径", "标题", "标签", "总页数", "是否有效", "最后修改时间", "是否已翻译"]
                    data_for_display = all_manga_entries
                    self.cache_table.setColumnCount(len(headers))
                    self.cache_table.setHorizontalHeaderLabels(headers)
                    self.cache_table.setRowCount(len(data_for_display))
                    for row_idx, entry in enumerate(data_for_display):
                        self.cache_table.setItem(row_idx, 0, QTableWidgetItem(str(entry.get("file_path", ""))))
                        self.cache_table.setItem(row_idx, 1, QTableWidgetItem(str(entry.get("title", ""))))
                        self.cache_table.setItem(row_idx, 2, QTableWidgetItem(", ".join(map(str, entry.get("tags", [])))))
                        self.cache_table.setItem(row_idx, 3, QTableWidgetItem(str(entry.get("total_pages", ""))))
                        self.cache_table.setItem(row_idx, 4, QTableWidgetItem(str(entry.get("is_valid", ""))))
                        self.cache_table.setItem(row_idx, 5, QTableWidgetItem(str(entry.get("last_modified", ""))))
                        self.cache_table.setItem(row_idx, 6, QTableWidgetItem(str(entry.get("is_translated", ""))))

                elif isinstance(manager, OcrCacheManager):
                    headers = ["缓存键", "文件名", "页码", "最后修改时间"]
                    data_for_display = manager.get_all_entries_for_display()
                    self.cache_table.setColumnCount(len(headers))
                    self.cache_table.setHorizontalHeaderLabels(headers)
                    self.cache_table.setRowCount(len(data_for_display))
                    for row_idx, entry in enumerate(data_for_display):
                        self.cache_table.setItem(row_idx, 0, QTableWidgetItem(entry.get("cache_key", "")))
                        self.cache_table.setItem(row_idx, 1, QTableWidgetItem(entry.get("file_name", "")))
                        self.cache_table.setItem(row_idx, 2, QTableWidgetItem(str(entry.get("page_num", ""))))
                        self.cache_table.setItem(row_idx, 3, QTableWidgetItem(str(entry.get("last_modified", ""))))

                elif isinstance(manager, TranslationCacheManager):
                    headers = ["缓存键", "原文样本", "译文样本", "是否和谐", "最后更新时间"] 
                    data_for_display = manager.get_all_entries_for_display() 
                    self.cache_table.setColumnCount(len(headers))
                    self.cache_table.setHorizontalHeaderLabels(headers)
                    self.cache_table.setRowCount(len(data_for_display))
                    for row_idx, entry in enumerate(data_for_display):
                        self.cache_table.setItem(row_idx, 0, QTableWidgetItem(entry.get("cache_key", "")))
                        self.cache_table.setItem(row_idx, 1, QTableWidgetItem(entry.get("original_text_sample", "")))
                        translated_text_sample = entry.get("translated_text", "")
                        if isinstance(translated_text_sample, str) and len(translated_text_sample) > 50:
                            translated_text_sample = translated_text_sample[:50] + "..."
                        self.cache_table.setItem(row_idx, 2, QTableWidgetItem(str(translated_text_sample)))
                        is_sensitive = entry.get("is_sensitive", False) 
                        self.cache_table.setItem(row_idx, 3, QTableWidgetItem("是" if is_sensitive else "否"))
                        self.cache_table.setItem(row_idx, 4, QTableWidgetItem(str(entry.get("last_updated", ""))))
                else:
                    log.warning(f"工厂分支中遇到未知管理器类型: {type(manager)} for slug {cache_type_slug}")
                    InfoBar.warning("加载失败", f"内部错误: 不支持的管理器 {cache_type_name}", duration=3000, parent=self)
                    return
                data_loaded_count = len(data_for_display)
                log.info(f"成功加载 {cache_type_name} 缓存数据，共 {data_loaded_count} 条。")
            else:
                if cache_type_slug: 
                    log.warning(f"尝试加载未处理的有效缓存类型 slug: {cache_type_slug} (来自名称: {cache_type_name})")
                    InfoBar.warning("加载失败", f"暂不支持的缓存类型: {cache_type_name}", duration=3000, parent=self)
                return

            self.cache_table.resizeColumnsToContents()
        except Exception as e:
            log.error(f"加载 {cache_type_name} 缓存数据失败: {e}", exc_info=True)
            InfoBar.error("加载失败", f"加载缓存数据时发生错误: {e}", duration=5000, parent=self)

    @Slot()
    def _on_clear_cache(self):
        selected_type_name = self.cache_type_combo.currentText()
        cache_type_slug = self._map_cache_type_name_to_slug(selected_type_name)

        if cache_type_slug == "harmonization_map":
            reply = QMessageBox.question(self, "确认清空", 
                                         f"确定要清空所有和谐映射吗？此操作不可撤销。",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                if self.harmonization_manager.clear_all_mappings():
                    InfoBar.success("清空成功", "所有和谐映射已清空。", duration=3000, parent=self)
                    self._load_cache_data(selected_type_name)
                else:
                    InfoBar.error("清空失败", "清空和谐映射时发生错误。", duration=5000, parent=self)
            return

        message_box = ClearConfirmDialog(self, cache_type_name=selected_type_name)
        if message_box.exec():
            try:
                factory = get_cache_factory_instance()
                manager = factory.get_manager(cache_type_slug)
                manager.clear()
                InfoBar.success("清空成功", f"{selected_type_name} 缓存已清空。", duration=3000, parent=self)
                self._load_cache_data(selected_type_name)
            except Exception as e:
                InfoBar.error("清空失败", f"清空缓存时发生错误: {e}", duration=5000, parent=self)

    def _map_cache_type_name_to_slug(self, name: str) -> str:
        if name == "漫画列表":
            return "manga_list"
        elif name == "OCR":
            return "ocr"
        elif name == "翻译":
            return "translation"
        elif name == "和谐映射":
            return "harmonization_map"
        else:
            log.warning(f"未知的缓存类型名称: {name}，无法映射到 slug。")
            return ""

    def _add_harmonization_mapping_slot(self):
        self._open_mapping_dialog_and_save()

    def _edit_harmonization_mapping_slot(self, row: int):
        try:
            original_item = self.cache_table.item(row, 0)
            harmonized_item = self.cache_table.item(row, 1)
            if original_item and harmonized_item:
                original = original_item.text()
                harmonized = harmonized_item.text()
                self._open_mapping_dialog_and_save(original_to_edit=original, current_harmonized=harmonized)
            else:
                InfoBar.warning("操作失败", "无法读取选中行的数据进行编辑。", duration=3000, parent=self)
        except Exception as e:
            log.error(f"编辑和谐映射槽函数错误 (行 {row}): {e}", exc_info=True)
            InfoBar.error("错误", "编辑操作准备时发生内部错误。", duration=3000, parent=self)

    def _delete_harmonization_mapping_slot(self, row: int):
        try:
            original_item = self.cache_table.item(row, 0)
            if not original_item:
                InfoBar.warning("操作失败", "无法读取选中行的数据进行删除。", duration=3000, parent=self)
                return
            original_text_to_delete = original_item.text()
            
            reply = QMessageBox.question(self, "确认删除", 
                                         f"确定要删除映射:\n\n原文: {original_text_to_delete}\n\n此操作不可撤销。",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                if self.harmonization_manager.delete_mapping(original_text_to_delete):
                    InfoBar.success("删除成功", f"映射 '{original_text_to_delete[:30]}...' 已删除。", duration=3000, parent=self)
                    self._load_cache_data(self.cache_type_combo.currentText())
                else:
                    InfoBar.error("删除失败", "删除映射时发生错误。", duration=3000, parent=self)
        except Exception as e:
            log.error(f"删除和谐映射槽函数错误 (行 {row}): {e}", exc_info=True)
            InfoBar.error("错误", "删除操作时发生内部错误。", duration=3000, parent=self)

    def _open_mapping_dialog_and_save(self, original_to_edit: Optional[str] = None, 
                                    current_harmonized: Optional[str] = None):
        is_editing_existing_entry = original_to_edit is not None 
        
        dialog_original_text = original_to_edit if is_editing_existing_entry else ""
        
        dialog = HarmonizationMappingDialog(
            original_text=dialog_original_text, 
            current_harmonized_text=(current_harmonized or ""), 
            is_editing_existing_entry=is_editing_existing_entry, 
            parent=self
        )

        if dialog.exec():
            new_original, new_harmonized = dialog.get_texts()

            if not new_original:
                InfoBar.warning("操作中止", "原文不能为空。", duration=3000, parent=self)
                return
            
            action_description = "保存"
            success_message = "映射已保存。"

            if is_editing_existing_entry: 
                action_description = "更新"
                success_message = "映射已更新。"
                if original_to_edit != new_original: # Check if original key changed
                    log.info(f"和谐映射的原文在编辑时已更改。旧原文: '{original_to_edit}', 新原文: '{new_original}'. 将删除旧条目。")
                    delete_success = self.harmonization_manager.delete_mapping(original_to_edit)
                    if not delete_success:
                        log.error(f"尝试更新映射时，删除旧原文 '{original_to_edit}' 失败。")
                        InfoBar.error("更新失败", f"无法删除旧的原文映射 '{original_to_edit[:30]}...'。", duration=4000, parent=self)
                        return 
            
            if self.harmonization_manager.add_or_update_mapping(new_original, new_harmonized):
                log.info(f"和谐映射已{action_description}: 原文='{new_original}', 和谐后='{new_harmonized}'")
                InfoBar.success(f"{action_description}成功", success_message, duration=3000, parent=self)
                self._load_cache_data(self.cache_type_combo.currentText())
            else:
                log.error(f"和谐映射{action_description}失败: 原文='{new_original}', 和谐后='{new_harmonized}'")
                InfoBar.error(f"{action_description}失败", f"{action_description}映射时发生错误。", duration=5000, parent=self)
        else:
            log.info("用户取消了和谐映射编辑/新增操作。")
