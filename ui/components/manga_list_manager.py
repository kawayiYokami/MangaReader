import os
from PyQt5.QtWidgets import (QTreeView, QMenu, QAction, QMessageBox, QInputDialog)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from utils import manga_logger as log

class MangaListManager:
    """负责漫画列表管理的组件"""
    
    def __init__(self, parent):
        self.parent = parent
        self.manga_manager = parent.manga_manager
        self.manga_list_view = None
        self.manga_model = None
    
    def setup_ui(self):
        # 漫画列表
        self.manga_list_view = QTreeView()
        self.manga_model = QStandardItemModel()
        self.manga_list_view.setModel(self.manga_model)
        self.manga_list_view.clicked.connect(self.on_manga_selected)
        
        # 设置右键菜单
        self.manga_list_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.manga_list_view.customContextMenuRequested.connect(self.show_manga_context_menu)
        
        return self.manga_list_view
    
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
            else:
                log.warning("选择的漫画数据为空")
        except Exception as e:
            log.error(f"选择漫画时发生错误: {str(e)}")
            QMessageBox.warning(self.parent, '错误', f'选择漫画时发生错误: {str(e)}')
            return
    
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
        rename_action.triggered.connect(lambda: self.rename_manga(manga))
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
        """重命名漫画文件"""
        log.info(f"尝试重命名漫画: {manga.title}")
        try:
            # 获取当前文件名（不含扩展名）
            current_name = os.path.splitext(manga.title)[0]
            
            # 弹出输入对话框
            new_name, ok = QInputDialog.getText(
                self.parent, '重命名漫画', '请输入新的文件名:', 
                text=current_name
            )
            
            if ok and new_name:
                # 调用MangaManager的重命名方法
                success = self.manga_manager.rename_manga_file(manga, new_name)
                if success:
                    # 更新列表显示
                    self.update_manga_list()
                    QMessageBox.information(self.parent, '成功', '漫画重命名成功')
                else:
                    QMessageBox.warning(self.parent, '错误', '漫画重命名失败')
        except Exception as e:
            log.error(f"重命名漫画时发生错误: {str(e)}")
            QMessageBox.warning(self.parent, '错误', f'重命名漫画时发生错误: {str(e)}')
    
    def toggle_page_direction(self):
        """切换页面显示方向"""
        self.parent.image_viewer.toggle_page_direction()
        if self.parent.current_manga:
            self.parent.image_viewer.show_current_page(
                self.parent.current_manga, 
                self.parent.navigation_controller.zoom_slider.value()
            )