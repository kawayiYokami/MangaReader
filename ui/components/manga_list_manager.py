import os
from PyQt5.QtWidgets import (QTreeView, QMenu, QAction, QMessageBox, QInputDialog,
                             QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QApplication,
                             QToolTip, QButtonGroup) # Import QButtonGroup
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from utils import manga_logger as log
from ui.layouts.flow_layout import FlowLayout # 确保 FlowLayout 已经被导入

class MangaListManager(QWidget):
    """负责漫画列表管理的组件"""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.manga_manager = parent.manga_manager
        self.manga_list_view = None
        self.manga_model = None
        self.current_style = parent.current_style
        self.tag_display_area = None
        self.tag_display_layout = None
        self.tag_button_group = QButtonGroup(self) # Initialize QButtonGroup

    def setup_ui(self):
        # 创建主垂直布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 创建用于显示标签按钮的区域
        self.tag_display_area = QWidget()
        self.tag_display_layout = FlowLayout(self.tag_display_area)
        self.tag_display_layout.setSpacing(5)
        main_layout.addWidget(self.tag_display_area)

        # 漫画列表
        self.manga_list_view = QTreeView()
        self.manga_model = QStandardItemModel()
        self.manga_list_view.setModel(self.manga_model)
        self.manga_list_view.clicked.connect(self.on_manga_selected)
        self.manga_list_view.doubleClicked.connect(self.on_manga_double_clicked) # 连接双击信号

        # 隐藏 TreeView 的头部
        self.manga_list_view.header().setVisible(False)

        main_layout.addWidget(self.manga_list_view)

        return self

    def update_manga_list(self, manga_list=None):
        log.info("开始更新漫画列表")
        self.manga_model.clear()

        # 如果没有提供漫画列表，则显示所有漫画
        if manga_list is None:
            manga_list = self.manga_manager.manga_list

        # 添加漫画到列表
        for manga in manga_list:
            # 从标签中获取作者和标题
            author = next((tag.split(':', 1)[1] for tag in manga.tags if tag.startswith('作者:')), '')
            title = next((tag.split(':', 1)[1] for tag in manga.tags if tag.startswith('标题:')), '')

            # 格式化显示
            display_name = f"[{author}] {title}"
            item = QStandardItem(display_name)
            item.setData(manga, Qt.UserRole + 1)
            self.manga_model.appendRow(item)

        log.info(f"漫画列表更新完成，共 {len(manga_list)} 项")

    def on_manga_selected(self, index):
        log.info(f"选择漫画，索引: {index.row()}")
        try:
            manga = self.manga_model.data(index, Qt.UserRole + 1)
            if manga:
                self.parent.current_manga = manga
                self.parent.current_manga.current_page = 0
                self.parent.navigation_controller.update_navigation_buttons()
                self.parent.image_viewer.show_current_page(
                    self.parent.current_manga,
                    self.parent.navigation_controller.zoom_slider.value()
                )

                # 清空之前的标签按钮
                for i in reversed(range(self.tag_display_layout.count())):
                    widget = self.tag_display_layout.itemAt(i).widget()
                    if widget is not None:
                        widget.deleteLater()

                # 显示当前选中漫画的标签按钮（只显示冒号后面的部分）
                for tag in manga.tags:
                    tag_text = tag.split(":", 1)[1] if ":" in tag else tag
                    tag_button = QPushButton(tag_text)
                    tag_button.setCheckable(True) # Make the button checkable
                    tag_button.setProperty("full_tag", tag) # Store the full tag
                    tag_button.clicked.connect(self.on_manga_tag_clicked)
                    self.tag_display_layout.addWidget(tag_button)
                    self.tag_button_group.addButton(tag_button) # Add button to the group

            else:
                log.warning("选择的漫画数据为空")
        except Exception as e:
            log.error(f"选择漫画时发生错误: {str(e)}")
            QMessageBox.warning(self.parent, '错误', f'选择漫画时发生错误: {str(e)}')
            return

    def on_manga_double_clicked(self, index):
        """双击漫画列表项时触发，用于重命名"""
        log.info(f"双击漫画，索引: {index.row()}")
        try:
            manga = self.manga_model.data(index, Qt.UserRole + 1)
            if manga:
                current_name = os.path.splitext(manga.title)[0]
                
                # 创建自定义样式的输入对话框
                dialog = QInputDialog(self.parent)
                dialog.setWindowTitle('重命名漫画')
                dialog.setLabelText('请输入新的文件名:')
                dialog.setTextValue(current_name)
                dialog.setStyleSheet("""
                    QInputDialog {
                        background-color: #2b2b2b;
                        font-size: 14px;
                    }
                    QLabel {
                        color: #ffffff;
                        padding: 8px 0;
                    }
                    QLineEdit {
                        background-color: #3c3f41;
                        color: #ffffff;
                        border: 1px solid #555555;
                        padding: 5px;
                        min-width: 300px;
                    }
                    QPushButton {
                        background-color: #4a4a4a;
                        color: #ffffff;
                        border: none;
                        padding: 5px 15px;
                        min-width: 80px;
                    }
                    QPushButton:hover {
                        background-color: #5a5a5a;
                    }
                """)
                
                # 设置对话框按钮文本
                dialog.setOkButtonText("确定")
                dialog.setCancelButtonText("取消")
                
                if dialog.exec_():
                    new_name = dialog.textValue()
                    if new_name:
                        old_file_path = manga.file_path
                        old_base_name = os.path.basename(old_file_path)
                        new_file_path = self.manga_manager.rename_manga_file_with_dialog(manga, new_name)
                        if new_file_path:
                            new_base_name = os.path.basename(new_file_path)
                            # 更新模型中的显示
                            author = next((tag.split(':', 1)[1] for tag in manga.tags if tag.startswith('作者:')), '')
                            display_name = f"[{author}] {os.path.splitext(new_base_name)[0]}"
                            item = self.manga_model.itemFromIndex(index)
                            item.setText(display_name)
                            # 更新 MangaInfo 对象中的 title 和 file_path
                            manga.title = new_base_name
                            manga.file_path = new_file_path
                            QMessageBox.information(self.parent, '成功', f'已将 "{old_base_name}" 重命名为 "{new_base_name}"')
                        else:
                            QMessageBox.warning(self.parent, '错误', '重命名失败。')
            else:
                log.warning("双击的漫画数据为空")
        except Exception as e:
            log.error(f"双击重命名漫画时发生错误: {str(e)}")
            QMessageBox.warning(self.parent, '错误', f'重命名漫画时发生错误: {str(e)}')

    def on_manga_tag_clicked(self):
        """处理漫画标签按钮的点击事件"""
        button = self.parent.sender()
        if button:
            full_tag = button.property("full_tag")
            if full_tag:
                # 复制标签值到剪切板
                tag_value = full_tag.split(":", 1)[1] if ":" in full_tag else full_tag
                clipboard = QApplication.clipboard()
                clipboard.setText(tag_value)
                log.info(f"标签 '{tag_value}' 已复制到剪切板")

                # 显示复制成功的提示
                QToolTip.showText(button.mapToGlobal(button.rect().topRight()), "已复制", button)

                # 激活上方标签栏里的同款标签
                self.filter_by_tag(full_tag)

    def show_manga_context_menu(self, position):
        log.info("显示漫画列表右键菜单")
        index = self.manga_list_view.indexAt(position)
        if not index.isValid():
            log.debug("无效的索引位置，不显示右键菜单")
            return

        # 获取选中的漫画
        manga = self.manga_model.data(index, Qt.UserRole + 1)
        if not manga:
            log.warning("无法获取漫画数据，不显示右键菜单")
            return

        # 创建右键菜单
        context_menu = QMenu(self.parent)

        # 添加基本菜单项
        open_folder_action = QAction("打开所在文件夹", self.parent)
        open_folder_action.triggered.connect(lambda: self.open_manga_folder(manga))
        context_menu.addAction(open_folder_action)

        rename_action = QAction("重命名", self.parent)
        rename_action.triggered.connect(lambda: self.on_manga_double_clicked(index)) # 右键菜单也触发相同的重命名逻辑
        context_menu.addAction(rename_action)

        # 添加分隔线和显示方向选项
        context_menu.addSeparator()

        # 添加显示方向切换选项
        direction_action = QAction("下一页显示在左边" if self.parent.image_viewer.next_page_on_right else "下一页显示在右边", self.parent)
        direction_action.triggered.connect(self.toggle_page_direction)
        context_menu.addAction(direction_action)

        # 添加过滤子菜单
        filter_menu = QMenu("过滤", context_menu)

        # 获取漫画的所有有效标签（排除标题标签）
        valid_tags = sorted([tag for tag in manga.tags if not tag.startswith('标题:')])

        # 为每个标签创建过滤动作
        for tag in valid_tags:
            filter_action = QAction(tag, self.parent)
            # 修改这里，使用普通函数而不是 lambda
            filter_action.triggered.connect(self.create_filter_handler(tag))
            filter_menu.addAction(filter_action)

        context_menu.addMenu(filter_menu)

        # 显示菜单
        context_menu.exec_(self.manga_list_view.mapToGlobal(position))

    def create_filter_handler(self, tag):
        """创建过滤处理函数"""
        def handler():
            self.filter_by_tag(tag)
        return handler

    def filter_by_tag(self, tag):
        """根据选中的标签进行过滤"""
        log.info(f"根据标签进行过滤: {tag}")

        # 获取标签类型（冒号前的部分）
        tag_type = tag.split(':', 1)[0]

        # 找到并选中对应的标签类型按钮
        for button in self.parent.tag_manager.tag_type_group.buttons():
            if button.text() == tag_type:
                button.setChecked(True)
                # 更新标签按钮
                self.parent.tag_manager.update_tag_buttons()
                break

        # 找到并选中对应的标签按钮
        if tag in self.parent.tag_manager.tag_buttons:
            self.parent.tag_manager.tag_buttons[tag].setChecked(True)
            # 触发标签按钮的点击事件
            self.parent.tag_manager.filter_and_update_manga_list(tag)

    def open_manga_folder(self, manga):
        log.info(f"打开漫画所在文件夹并选中文件: {manga.title}")
        try:
            # 确保路径是绝对路径并规范化
            file_path = os.path.abspath(manga.file_path)
            # 使用双引号包裹路径，以处理路径中可能包含的空格
            command = f'explorer /select,"{file_path}"'
            log.debug(f"执行命令: {command}")
            os.system(command)
        except Exception as e:
            log.error(f"打开文件夹时发生错误: {str(e)}")
            QMessageBox.warning(self.parent, '错误', f'无法打开文件夹: {str(e)}')

    def rename_manga(self, manga):
        """重命名漫画文件 (这个方法现在不再直接被双击调用)"""
        pass

    def toggle_page_direction(self):
        """切换页面显示方向"""
        self.parent.image_viewer.toggle_page_direction()
        if self.parent.current_manga:
            self.parent.image_viewer.show_current_page(
                self.parent.current_manga,
                self.parent.navigation_controller.zoom_slider.value()
            )