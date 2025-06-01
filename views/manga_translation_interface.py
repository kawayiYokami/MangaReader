# coding:utf-8
import os
import zipfile
import tempfile
import shutil
import re # For sanitizing temp path
from pathlib import Path
from typing import List, Any, Optional, Tuple

from PySide6.QtCore import Qt, Slot, QUrl, QThread
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QFileDialog, QTableWidget, 
                               QTableWidgetItem, QAbstractItemView, QHeaderView)
from qfluentwidgets import (ScrollArea, StrongBodyLabel, SubtitleLabel, setFont, PushButton, ToolButton, LineEdit,
                            ComboBox, ProgressBar, TextEdit, FluentIcon as FIF, InfoBar, InfoBarPosition, MessageBox)

# 项目内部导入
from core.batch_translation_worker import BatchTranslationWorker, TranslationTaskItem # Worker will need updates
from utils import manga_logger as log

class MangaTranslationInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("mangaTranslationInterface")
        self.setAcceptDrops(True)

        self.translation_thread: Optional[QThread] = None
        self.translation_worker: Optional[BatchTranslationWorker] = None

        # 设置默认输出目录和缓存目录
        self.default_output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.output')
        self.cache_dir = os.path.join(self.default_output_dir, 'cache')
        os.makedirs(self.default_output_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

        # 创建主布局
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 初始化控制面板和任务列表面板
        self._init_control_panel(self.default_output_dir)
        self._init_task_list_panel()

        # 添加到主布局
        self.main_layout.addWidget(self.control_panel_scroll)
        self.main_layout.addWidget(self.task_list_scroll)
        self.main_layout.setStretchFactor(self.control_panel_scroll, 2)
        self.main_layout.setStretchFactor(self.task_list_scroll, 3)

        # 设置样式
        self.control_panel_scroll.setFixedWidth(400)

    def _init_control_panel(self, default_output_dir: str):
        self.control_panel_scroll = ScrollArea(self)
        self.control_panel_scroll.setWidgetResizable(True)
        self.control_panel_scroll.setObjectName("controlPanelScroll")

        self.control_panel_widget = QWidget()
        self.control_panel_widget.setObjectName("controlPanelWidget")
        self.control_panel_layout = QVBoxLayout(self.control_panel_widget)
        self.control_panel_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.control_panel_layout.setContentsMargins(10, 10, 10, 10)
        self.control_panel_layout.setSpacing(18)

        file_import_title = SubtitleLabel("文件导入", self)
        setFont(file_import_title, 16)
        self.control_panel_layout.addWidget(file_import_title)

        self.drag_drop_area = StrongBodyLabel("将文件/文件夹拖拽至此\n或使用下方按钮添加", self)
        self.drag_drop_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drag_drop_area.setStyleSheet("border: 2px dashed #707070; padding: 20px; border-radius: 5px; background-color: transparent;")
        self.drag_drop_area.setMinimumHeight(100)
        self.drag_drop_area.setAcceptDrops(True)
        self.control_panel_layout.addWidget(self.drag_drop_area)

        self.add_files_button = PushButton("添加文件", self)
        self.add_files_button.setIcon(FIF.ADD_TO)
        self.add_files_button.clicked.connect(self._on_add_files_clicked)
        self.add_folder_button = PushButton("添加文件夹", self)
        self.add_folder_button.setIcon(FIF.FOLDER_ADD)
        self.add_folder_button.clicked.connect(self._on_add_folder_clicked)
        self.add_archive_button = PushButton("添加压缩包 (CBZ/CBR/ZIP)", self)
        self.add_archive_button.setIcon(FIF.DOCUMENT)
        self.add_archive_button.clicked.connect(self._on_add_archive_clicked)
        
        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.add_files_button)
        buttons_layout.addWidget(self.add_folder_button)
        self.control_panel_layout.addLayout(buttons_layout)
        self.control_panel_layout.addWidget(self.add_archive_button)

        translation_params_title = SubtitleLabel("翻译参数", self)
        setFont(translation_params_title, 16)
        self.control_panel_layout.addWidget(translation_params_title)

        source_lang_layout = QHBoxLayout()
        self.source_lang_label = StrongBodyLabel("源语言:", self)
        self.source_lang_combo = ComboBox(self)
        self.source_lang_combo.addItems(["自动检测", "日语 (ja)", "英语 (en)", "韩语 (ko)", "中文 (zh)"])
        self.source_lang_combo.setCurrentIndex(0)
        source_lang_layout.addWidget(self.source_lang_label)
        source_lang_layout.addWidget(self.source_lang_combo, 1)
        self.control_panel_layout.addLayout(source_lang_layout)

        target_lang_layout = QHBoxLayout()
        self.target_lang_label = StrongBodyLabel("目标语言:", self)
        self.target_lang_combo = ComboBox(self)
        self.target_lang_combo.addItems(["中文简体 (zh-CN)", "中文繁體 (zh-TW)", "英语 (en)"])
        self.target_lang_combo.setCurrentText("中文简体 (zh-CN)")
        target_lang_layout.addWidget(self.target_lang_label)
        target_lang_layout.addWidget(self.target_lang_combo, 1)
        self.control_panel_layout.addLayout(target_lang_layout)
        
        output_dir_layout = QHBoxLayout()
        self.output_dir_label = StrongBodyLabel("输出目录:", self)
        self.output_dir_edit = LineEdit(self)
        self.output_dir_edit.setPlaceholderText("选择或输入输出路径")
        self.output_dir_edit.setReadOnly(True)
        self.output_dir_edit.setText(default_output_dir)  # 设置默认输出目录
        self.select_output_dir_button = PushButton("选择目录", self)
        self.select_output_dir_button.setIcon(FIF.FOLDER)
        self.select_output_dir_button.clicked.connect(self._on_select_output_dir)

        output_dir_layout.addWidget(self.output_dir_label)
        output_dir_layout.addWidget(self.output_dir_edit, 1)
        output_dir_layout.addWidget(self.select_output_dir_button)
        self.control_panel_layout.addLayout(output_dir_layout)

        actions_title = SubtitleLabel("操作", self)
        setFont(actions_title, 16)
        self.control_panel_layout.addWidget(actions_title)
        self.start_translation_button = PushButton("开始翻译", self)
        self.start_translation_button.setObjectName("startTranslationButton")
        self.start_translation_button.setIcon(FIF.PLAY)
        self.start_translation_button.clicked.connect(self._on_start_translation_clicked)
        
        self.cancel_translation_button = PushButton("取消翻译", self)
        self.cancel_translation_button.setIcon(FIF.CANCEL)
        self.cancel_translation_button.clicked.connect(self._on_cancel_translation_clicked)
        self.cancel_translation_button.setEnabled(False)

        self.clear_task_list_button = PushButton("清空任务列表", self)
        self.clear_task_list_button.setIcon(FIF.DELETE)
        self.clear_task_list_button.clicked.connect(self._on_clear_task_list_clicked)
        
        self.control_panel_layout.addWidget(self.start_translation_button)
        self.control_panel_layout.addWidget(self.cancel_translation_button)
        self.control_panel_layout.addWidget(self.clear_task_list_button)


        status_title = SubtitleLabel("状态与日志", self)
        setFont(status_title, 16)
        self.control_panel_layout.addWidget(status_title)
        
        self.overall_progress_label = StrongBodyLabel("整体进度:", self)
        self.control_panel_layout.addWidget(self.overall_progress_label)
        self.overall_progress_bar = ProgressBar(self)
        self.overall_progress_bar.setValue(0)
        self.control_panel_layout.addWidget(self.overall_progress_bar)

        self.log_output_label = StrongBodyLabel("日志信息:", self)
        self.control_panel_layout.addWidget(self.log_output_label)
        self.log_output_text = TextEdit(self)
        self.log_output_text.setReadOnly(True)
        self.log_output_text.setPlaceholderText("操作日志将显示在此处...")
        self.log_output_text.setFixedHeight(150)
        self.control_panel_layout.addWidget(self.log_output_text)

        self.control_panel_layout.addStretch(1)
        self.control_panel_scroll.setWidget(self.control_panel_widget)

    def _init_task_list_panel(self):
        self.task_list_scroll = ScrollArea(self)
        self.task_list_scroll.setWidgetResizable(True)
        self.task_list_scroll.setObjectName("taskListScroll")
        self.task_list_scroll.setStyleSheet("ScrollArea { border: none; }")

        self.task_list_widget_container = QWidget()
        self.task_list_container_layout = QVBoxLayout(self.task_list_widget_container)
        self.task_list_container_layout.setContentsMargins(10, 10, 10, 10)
        self.task_list_container_layout.setSpacing(10)
        
        task_list_title = SubtitleLabel("翻译任务队列", self)
        setFont(task_list_title, 18)
        self.task_list_container_layout.addWidget(task_list_title)

        self.task_table = QTableWidget(self)
        self.task_table.setColumnCount(3) 
        self.task_table.setHorizontalHeaderLabels(["文件/任务", "状态", "详情/结果"])
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.task_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.task_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.task_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.task_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.task_table.setAcceptDrops(True)

        self.task_list_container_layout.addWidget(self.task_table)
        self.task_list_scroll.setWidget(self.task_list_widget_container)

    def dragEnterEvent(self, event: QDragEnterEvent):
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            all_local_files = all(url.isLocalFile() for url in mime_data.urls())
            if all_local_files:
                event.acceptProposedAction()
                return
        event.ignore()

    def dragLeaveEvent(self, event): pass

    def dropEvent(self, event: QDropEvent):
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            paths = [url.toLocalFile() for url in mime_data.urls() if url.isLocalFile()]
            if paths:
                self._add_tasks_from_paths(paths)
                event.acceptProposedAction()
                self._handle_log_message(f"通过拖拽添加了 {len(paths)} 个项目。")
                return
        event.ignore()

    def _add_tasks_from_paths(self, paths: list[str]):
        if not paths: return
        new_tasks_count = 0
        current_row_count = self.task_table.rowCount()
        existing_paths = set()
        for row in range(current_row_count):
            item = self.task_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole):
                existing_paths.add(item.data(Qt.ItemDataRole.UserRole))

        tasks_to_add_paths = []
        for path in paths:
            if path not in existing_paths:
                tasks_to_add_paths.append(path)
                existing_paths.add(path)

        if not tasks_to_add_paths:
            InfoBar.warning("任务已存在", "所有拖拽/选择的项目已在任务列表中。", duration=3000, parent=self, position=InfoBarPosition.TOP_RIGHT)
            return

        self.task_table.setRowCount(current_row_count + len(tasks_to_add_paths))
        for i, path_str in enumerate(tasks_to_add_paths):
            row = current_row_count + i
            p = Path(path_str)
            file_name = p.name
            task_display_name = file_name
            if p.is_dir(): task_display_name = f"[文件夹] {file_name}"
            elif p.suffix.lower() in ['.zip', '.cbz', '.cbr']: task_display_name = f"[压缩包] {file_name}"
            
            name_item = QTableWidgetItem(task_display_name)
            name_item.setData(Qt.ItemDataRole.UserRole, path_str)
            status_item = QTableWidgetItem("待处理")
            details_item = QTableWidgetItem("")
            self.task_table.setItem(row, 0, name_item)
            self.task_table.setItem(row, 1, status_item)
            self.task_table.setItem(row, 2, details_item)
            new_tasks_count += 1
        
        if new_tasks_count > 0:
            self._handle_log_message(f"添加了 {new_tasks_count} 个新任务到列表。")
            InfoBar.success("任务添加成功", f"已添加 {new_tasks_count} 个项目到任务列表。", duration=3000, parent=self, position=InfoBarPosition.TOP_RIGHT)

    @Slot()
    def _on_add_files_clicked(self):
        supported_image_formats = "*.jpg *.jpeg *.png *.webp *.bmp"
        files, _ = QFileDialog.getOpenFileNames(self, "选择一个或多个图片文件", "", f"图片文件 ({supported_image_formats});;所有文件 (*.*)")
        if files: self._add_tasks_from_paths(files)

    @Slot()
    def _on_add_folder_clicked(self):
        directory = QFileDialog.getExistingDirectory(self, "选择包含漫画图片的文件夹", "")
        if directory: self._add_tasks_from_paths([directory])

    @Slot()
    def _on_add_archive_clicked(self):
        supported_archive_formats = "*.cbz *.cbr *.zip"
        files, _ = QFileDialog.getOpenFileNames(self, "选择一个或多个漫画压缩包", "", f"漫画压缩包 ({supported_archive_formats});;所有文件 (*.*)")
        if files: self._add_tasks_from_paths(files)

    @Slot()
    def _on_select_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output_dir_edit.text() or ".")
        if directory:
            self.output_dir_edit.setText(directory)
            self._handle_log_message(f"输出目录已设置为: {directory}")

    @Slot()
    def _on_clear_task_list_clicked(self):
        if self.task_table.rowCount() == 0:
            InfoBar.info("提示", "任务列表已经为空。", duration=2000, parent=self, position=InfoBarPosition.TOP_RIGHT)
            return
        title = "确认清空任务列表"; content = "确定要移除任务列表中的所有项目吗？此操作不可撤销。"
        msg_box = MessageBox(title, content, self.window())
        if msg_box.exec():
            self.task_table.setRowCount(0)
            self._handle_log_message("任务列表已清空。")
            InfoBar.success("操作成功", "任务列表已成功清空。", duration=3000, parent=self, position=InfoBarPosition.TOP_RIGHT)

    @Slot()
    def _on_start_translation_clicked(self):
        if self.translation_thread and self.translation_thread.isRunning():
            InfoBar.warning("翻译进行中", "已有翻译任务在运行。", duration=3000, parent=self)
            return

        final_zip_output_dir_str = self.output_dir_edit.text()
        if not final_zip_output_dir_str:
            InfoBar.warning("设置输出目录", "请先选择翻译结果的输出目录。", duration=3000, parent=self)
            self.select_output_dir_button.setFocus()
            return
        
        final_zip_output_path = Path(final_zip_output_dir_str)
        if not final_zip_output_path.exists() or not final_zip_output_path.is_dir():
            InfoBar.error("输出目录无效", f"指定的输出目录不存在或不是有效文件夹: {final_zip_output_dir_str}", duration=4000, parent=self)
            return

        if self.task_table.rowCount() == 0:
            InfoBar.warning("任务列表为空", "请先添加任务。", duration=3000, parent=self)
            return

        all_input_image_paths_for_batch: List[Tuple[str, int]] = [] # (image_path_str, original_ui_row_index)
        first_item_name_for_zip = ""
        
        # --- 1. 收集所有需要处理的图片 ---
        for ui_row_index in range(self.task_table.rowCount()):
            name_item = self.task_table.item(ui_row_index, 0)
            original_path_str = name_item.data(Qt.ItemDataRole.UserRole)
            original_path = Path(original_path_str)

            if not first_item_name_for_zip:
                first_item_name_for_zip = original_path.stem

            image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.bmp']
            current_row_images = []

            if original_path.is_file():
                if original_path.suffix.lower() in image_extensions:
                    current_row_images.append(str(original_path))
                elif original_path.suffix.lower() in ['.zip', '.cbz', '.cbr']:
                    extraction_cache_dir = os.path.join(self.cache_dir, original_path.stem)
                    os.makedirs(extraction_cache_dir, exist_ok=True)
                    self._handle_log_message(f"正在解压 {original_path.name} 到 {extraction_cache_dir}")
                    try:
                        with zipfile.ZipFile(original_path, 'r') as zip_ref:
                            # 按顺序处理压缩包中的图片
                            archive_image_files = []
                            for member_name in sorted(zip_ref.namelist()):
                                member_path = Path(extraction_cache_dir) / member_name
                                if Path(member_name).suffix.lower() in image_extensions and not member_name.startswith('__MACOSX'):
                                    zip_ref.extract(member_name, path=extraction_cache_dir)
                                    archive_image_files.append(str(member_path))
                            current_row_images.extend(archive_image_files)
                        self._update_task_status_in_table(f"row{ui_row_index}", "解压完成", "")
                    except Exception as e_zip:
                        self._handle_log_message(f"解压 {original_path.name} 失败: {e_zip}")
                        self._update_task_status_in_table(f"row{ui_row_index}", "解压失败", str(e_zip))
                        continue
                else:
                    self._update_task_status_in_table(f"row{ui_row_index}", "格式不支持", "")
                    continue
            elif original_path.is_dir():
                folder_images = []
                for item_path in sorted(list(original_path.rglob('*'))):
                    if item_path.is_file() and item_path.suffix.lower() in image_extensions:
                        folder_images.append(str(item_path))
                if folder_images:
                    current_row_images.extend(folder_images)
                    self._update_task_status_in_table(f"row{ui_row_index}", "扫描完成", "")
                else:
                    self._update_task_status_in_table(f"row{ui_row_index}", "无图片", "")
                    continue
            
            for img_path in current_row_images:
                all_input_image_paths_for_batch.append((img_path, ui_row_index))

        if not all_input_image_paths_for_batch:
            InfoBar.warning("无有效图片", "未能从任务列表中找到任何有效的图片进行翻译。", duration=3000, parent=self)
            return

        # --- 2. 准备任务参数 ---
        safe_base_zip_name = re.sub(r'[^\w\-_.]', '_', first_item_name_for_zip) if first_item_name_for_zip else "manga_translation"
        base_zip_name = f"{safe_base_zip_name}_translated"

        # --- 3. 准备所有翻译任务 ---
        prepared_tasks: List[TranslationTaskItem] = []
        source_lang_text = self.source_lang_combo.currentText()
        source_lang = source_lang_text.split(" (")[0] if "(" in source_lang_text else source_lang_text
        target_lang_text = self.target_lang_combo.currentText()
        target_lang_code = target_lang_text.split(" (")[1][:-1] if "(" in target_lang_text else target_lang_text

        for img_overall_idx, (input_img_path_str, original_ui_row_idx) in enumerate(all_input_image_paths_for_batch):
            task_id = f"row{original_ui_row_idx}_img{img_overall_idx + 1}"
            output_filename = f"{img_overall_idx + 1:0{3}d}.png"
            task_output_path = str(os.path.join(self.cache_dir, 'translated', output_filename))
            os.makedirs(os.path.join(self.cache_dir, 'translated'), exist_ok=True)

            prepared_tasks.append(TranslationTaskItem(
                task_id=task_id,
                input_path=input_img_path_str,
                output_path=task_output_path,
                source_lang=source_lang,
                target_lang=target_lang_code
            ))
            self._update_task_status_in_table(f"row{original_ui_row_idx}", "准备中...", "")

        # --- 5. Start Translation ---
        title = "开始翻译任务"
        content = (f"即将开始翻译 {len(all_input_image_paths_for_batch)} 张图片。\n"
                   f"源语言: {source_lang_text}\n"
                   f"目标语言: {target_lang_text}\n"
                   f"输出为一个ZIP文件到: {final_zip_output_dir_str}\n"
                   f"ZIP文件名: {base_zip_name}.zip\n\n是否继续？")
        msg_box = MessageBox(title, content, self.window())
        
        if not msg_box.exec():
            self._handle_log_message("用户取消了翻译操作。")
            return

        # --- 6. Initialize Worker and Thread ---
        self.translation_worker = BatchTranslationWorker(
            tasks=prepared_tasks,
            final_zip_output_dir=final_zip_output_dir_str,
            base_zip_name=base_zip_name,
            default_source_lang=source_lang,
            default_target_lang=target_lang_code,
            translator_engine="智谱"
        )
        self.translation_thread = QThread(self)
        self.translation_worker.moveToThread(self.translation_thread)

        # --- 7. Connect Signals ---
        self.translation_worker.task_started.connect(self._handle_task_started)
        self.translation_worker.task_finished.connect(self._handle_task_finished)
        self.translation_worker.overall_progress.connect(self._handle_overall_progress)
        self.translation_worker.all_tasks_finished.connect(self._handle_all_tasks_finished_zip)
        self.translation_worker.log_message.connect(self._handle_log_message)
        
        self.translation_thread.started.connect(self.translation_worker.run)
        self.translation_thread.finished.connect(self.translation_thread.deleteLater)
        self.translation_worker.all_tasks_finished.connect(self.translation_worker.deleteLater)

        # --- 8. Start Translation ---
        self.translation_thread.start()

        # --- 9. Update UI State ---
        self.start_translation_button.setEnabled(False)
        self.cancel_translation_button.setEnabled(True)
        self.clear_task_list_button.setEnabled(False)
        self.overall_progress_bar.setValue(0)
        self._handle_log_message(f"开始批量翻译任务，共 {len(prepared_tasks)} 张图片。输出为ZIP: {base_zip_name}.zip")

    @Slot()
    def _on_cancel_translation_clicked(self):
        if self.translation_worker:
            self._handle_log_message("正在发送取消请求...")
            self.translation_worker.cancel()
            self.cancel_translation_button.setEnabled(False) 

    @Slot(object) # task_id (e.g., "row0_img1")
    def _handle_task_started(self, task_id: Any):
        self._update_task_status_in_table(task_id, "处理中...", "")

    @Slot(object, bool, str) # task_id, success, result_message (path to .png in temp or error)
    def _handle_task_finished(self, task_id: Any, success: bool, result_message: str):
        status = "翻译成功" if success else "翻译失败"
        # result_message for individual png is its path in temp dir, or error string
        # The UI table's "Details/Result" column for the main item might show aggregated info later
        # For now, just update status based on individual image progress
        self._update_task_status_in_table(task_id, status, Path(result_message).name if success else result_message)

    @Slot(int, str)
    def _handle_overall_progress(self, percentage: int, message: str):
        self.overall_progress_bar.setValue(percentage)
        # self.overall_progress_label.setText(f"整体进度: {message}") # Optional: update label too

    @Slot(str) # Slot now expects the final ZIP path or an error message
    def _handle_all_tasks_finished_zip(self, final_result_message: str):
        if final_result_message.lower().endswith(".zip") and Path(final_result_message).exists():
            self._handle_log_message(f"所有翻译任务已结束。输出ZIP: {final_result_message}")
            InfoBar.success("翻译完成", f"所有任务已处理完毕！结果已保存到: {final_result_message}", duration=5000, parent=self)
        else:
            self._handle_log_message(f"所有翻译任务已结束，但可能存在问题: {final_result_message}")
            InfoBar.error("翻译结束但有错误", f"任务处理完成，但ZIP包生成失败或有其他错误: {final_result_message}", duration=5000, parent=self)

        self.start_translation_button.setEnabled(True)
        self.cancel_translation_button.setEnabled(False)
        self.clear_task_list_button.setEnabled(True)
        
        if self.translation_thread and self.translation_thread.isRunning():
            self.translation_thread.quit()
            self.translation_thread.wait(3000)

        self.translation_thread = None
        self.translation_worker = None

    @Slot(str)
    def _handle_log_message(self, message: str):
        self.log_output_text.append(message)
        log.info(f"[UI_LOG] {message}") 

    def _update_task_status_in_table(self, task_id_or_row_id: Any, status: str, details: str = ""):
        main_task_row_index = -1
        
        task_id_str = str(task_id_or_row_id)
        is_sub_task_signal = "_img" in task_id_str # e.g. "row0_img1"

        if task_id_str.startswith("row"):
            try:
                main_task_id_part = task_id_str.split("_")[0] 
                main_task_row_index = int(main_task_id_part.replace("row", ""))
            except ValueError:
                self._handle_log_message(f"错误：无法从task_id '{task_id_str}'解析行号。")
                return

        if 0 <= main_task_row_index < self.task_table.rowCount():
            status_item = self.task_table.item(main_task_row_index, 1)
            if not status_item:
                status_item = QTableWidgetItem()
                self.task_table.setItem(main_task_row_index, 1, status_item)

            details_item = self.task_table.item(main_task_row_index, 2)
            if not details_item:
                details_item = QTableWidgetItem()
                self.task_table.setItem(main_task_row_index, 2, details_item)

            current_status_text = status_item.text()
            # Avoid overwriting a final state like "解压失败" or "格式不支持" with "处理中"
            # from a sub-task signal if the main task itself had an issue.
            final_states = ["解压失败", "格式不支持", "无图片", "翻译完成", "压缩完成"] # Add more as needed

            if is_sub_task_signal:
                if current_status_text not in final_states and not current_status_text.startswith("处理中 (部分)"):
                     status_item.setText("处理中 (部分)...")

                if status == "翻译失败": # For individual image failure
                    img_num = task_id_str.split("_img")[-1]
                    new_detail_msg = f"图片 {img_num} 失败: {details}"
                    current_details = details_item.text()
                    if new_detail_msg not in current_details:
                         details_item.setText(f"{current_details}; {new_detail_msg}" if current_details else new_detail_msg)
            else: # Signal for the main UI row (e.g., "解压完成", "准备中")
                if current_status_text not in final_states or status in final_states : # Allow updating to another final state
                    status_item.setText(status)
                    details_item.setText(details) # Main task details usually overwrite
        else:
            self._handle_log_message(f"收到未知或过时任务ID的状态更新: {task_id_str}, 状态: {status}")

    def closeEvent(self, event):
        if self.translation_thread and self.translation_thread.isRunning():
            if self.translation_worker:
                self.translation_worker.cancel()
            self.translation_thread.quit()
            if not self.translation_thread.wait(3000): 
                self._handle_log_message("警告：翻译线程未能及时关闭。")
        super().closeEvent(event)

    def _add_sample_tasks_to_table(self):
        pass # Intentionally empty

if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication
    from qfluentwidgets import FluentWindow, setTheme, Theme, FluentIcon

    app = QApplication(sys.argv)
    window = FluentWindow()
    translate_interface = MangaTranslationInterface()
    window.addSubInterface(translate_interface, FIF.EDIT, "漫画翻译") 
    window.navigationInterface.setCurrentItem(translate_interface.objectName())
    window.setWindowTitle("漫画翻译页面预览")
    window.resize(1300, 850)
    window.show()
    sys.exit(app.exec())