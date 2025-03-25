import os
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTreeView, QLabel, QPushButton, QFileDialog,
                             QScrollArea, QFrame, QMessageBox, QSplitter,
                             QMenu, QAction, QButtonGroup, QRadioButton,
                             QSizePolicy, QSlider)  # 添加 QSlider
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QImage, QStandardItemModel, QStandardItem
from core.manga_manager import MangaManager
from core.manga_model import MangaLoader
from ui.layouts.flow_layout import FlowLayout
from utils import manga_logger as log
from PyQt5.QtWidgets import QInputDialog
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtCore import QTimer
from styles.style import Win11Style
from styles.light_style import Win11LightStyle
from styles.dark_style import Win11DarkStyle

from ui.components.image_label import ImageLabel

class MangaViewer(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("漫画查看器")
        self.manga_manager = MangaManager()
        self.current_manga = None
        self.next_page_on_right = True  # 添加：控制下一页显示位置
        self.is_single_page_mode = False  # 添加单双页模式控制
        self.current_style = 'default'  # 添加：当前主题样式
        
        # 确保按钮组正确初始化
        self.tag_button_group = QButtonGroup(self)
        self.tag_button_group.setExclusive(True)  # 设置为互斥（单选）模式
        
        self.setup_ui()
        Win11Style.apply_style(self)
        log.info("MangaViewer初始化完成")

    def setup_ui(self):
        log.info("开始设置UI界面")
        self.setWindowTitle('漫画查看器')
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        
        # 创建水平分割器
        h_splitter = QSplitter(Qt.Horizontal)
        
        # 左侧面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 修改选择目录部分的布局
        dir_layout = QHBoxLayout()
        self.select_dir_btn = QPushButton('📂')  # 使用文件夹图标
        self.select_dir_btn.setMaximumWidth(30)  # 设置按钮宽度
        self.select_dir_btn.clicked.connect(self.select_directory)
        
        # 添加搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('搜索漫画...')
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)  # 设置为单次触发
        self.search_timer.timeout.connect(self.perform_search)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        
        dir_layout.addWidget(self.select_dir_btn)
        dir_layout.addWidget(self.search_input)
        left_layout.addLayout(dir_layout)
        
        # 创建标签分类按钮组
        self.tag_type_group = QButtonGroup(self)
        self.tag_type_group.buttonClicked.connect(self.update_tag_buttons)
        
        # 创建标签类型布局并添加到左侧面板
        tag_type_layout = QHBoxLayout()
        self.create_tag_type_buttons(tag_type_layout)
        left_layout.addLayout(tag_type_layout)
        
        # 创建垂直分割器
        v_splitter = QSplitter(Qt.Vertical)
        
        # 标签过滤按钮区域（使用QScrollArea包装）
        tag_scroll_area = QScrollArea()
        tag_scroll_area.setWidgetResizable(True)
        tag_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tag_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.tag_buttons = {}
        self.tag_frame = QFrame()
        # 使用QFlowLayout来实现标签的流式布局
        self.tag_layout = FlowLayout(self.tag_frame)
        self.tag_layout.setSpacing(5)
        tag_scroll_area.setWidget(self.tag_frame)
        
        # 添加新的按钮组
        self.filter_button_group = QButtonGroup(self)
        self.filter_button_group.setExclusive(False)  # 设置为非互斥（多选）模式
        
        # 漫画列表（确保在filter_buttons之前初始化）
        self.manga_list_view = QTreeView()
        self.manga_model = QStandardItemModel()
        self.manga_list_view.setModel(self.manga_model)
        self.manga_list_view.clicked.connect(self.on_manga_selected)
        
        # 设置右键菜单
        self.manga_list_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.manga_list_view.customContextMenuRequested.connect(self.show_manga_context_menu)
        
        # 将组件添加到垂直分割器
        v_splitter.addWidget(tag_scroll_area)
        v_splitter.addWidget(self.manga_list_view)
        
        # 设置垂直分割器初始大小
        v_splitter.setSizes([200, 400])
        left_layout.addWidget(v_splitter)
        
        # 右侧面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 图片查看区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.image_label = ImageLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        scroll_area.setWidget(self.image_label)
        right_layout.addWidget(scroll_area)
        
        # 导航按钮布局
        nav_layout = QHBoxLayout()
        nav_layout.addStretch()
        
        # 创建导航按钮组
        nav_button_widget = QWidget()
        nav_button_layout = QHBoxLayout(nav_button_widget)
        nav_button_layout.setContentsMargins(0, 0, 0, 0)
        nav_button_layout.setSpacing(5)
        
        # 添加页面滑动条
        self.page_slider = QSlider(Qt.Horizontal)
        self.page_slider.setMinimum(0)
        self.page_slider.setMaximum(0)
        self.page_slider.valueChanged.connect(self.on_slider_value_changed)
        self.page_slider.setFixedWidth(200)
        
        # 使用自定义的 PageSlider
        from ui.components.page_slider import PageSlider
        self.page_slider = PageSlider()
        self.page_slider.valueChanged.connect(self.on_slider_value_changed)
        
        # 使用自定义的 ZoomSlider
        from ui.components.zoom_slider import ZoomSlider
        self.zoom_slider = ZoomSlider()
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        
        self.prev_btn = QPushButton('←')
        self.prev_btn.setFixedWidth(30)
        self.prev_btn.clicked.connect(self.prev_page)
        
        self.single_page_btn = QPushButton('双页')
        self.single_page_btn.setFixedWidth(50)
        self.single_page_btn.setCheckable(True)
        self.single_page_btn.clicked.connect(self.toggle_page_mode)
        
        self.next_btn = QPushButton('→')
        self.next_btn.setFixedWidth(30)
        self.next_btn.clicked.connect(self.next_page)
        
        nav_button_layout.addWidget(self.page_slider)
        nav_button_layout.addWidget(self.prev_btn)
        nav_button_layout.addWidget(self.single_page_btn)
        nav_button_layout.addWidget(self.next_btn)
        nav_button_layout.addWidget(self.zoom_slider)
        
        # 添加风格切换按钮
        self.style_btn = QPushButton('默认')
        self.style_btn.setFixedWidth(50)
        self.style_btn.clicked.connect(self.toggle_style)
        nav_button_layout.addWidget(self.style_btn)
        
        nav_layout.addWidget(nav_button_widget)
        nav_layout.addStretch()
        
        right_layout.addLayout(nav_layout)
        
        # 将左右面板添加到水平分割器
        h_splitter.addWidget(left_panel)
        h_splitter.addWidget(right_panel)
        
        # 设置水平分割器初始大小比例
        h_splitter.setSizes([300, 900])
        
        # 设置拉伸因子，使右侧面板获得所有额外空间
        h_splitter.setStretchFactor(0, 0)  # 左侧面板不拉伸
        h_splitter.setStretchFactor(1, 1)  # 右侧面板获得所有额外空间
        
        # 设置左侧面板最小宽度
        left_panel.setMinimumWidth(300)  # 防止左侧面板被完全收缩
        
        layout.addWidget(h_splitter)
        
        self.update_navigation_buttons()
        
        # 确保图像显示控件可以接收键盘焦点
        self.image_label.setFocusPolicy(Qt.StrongFocus)
        # 启用鼠标追踪
        self.image_label.setMouseTracking(True)
    
    def select_directory(self):
        log.info("打开选择漫画目录对话框")
        dir_path = QFileDialog.getExistingDirectory(self, '选择漫画目录')
        if dir_path:
            log.info(f"用户选择了目录: {dir_path}")
            self.manga_manager.set_manga_dir(dir_path)
            self.update_tag_buttons()
            self.update_manga_list()
        else:
            log.info("用户取消了目录选择")
    
    def update_tag_buttons(self):
        log.info("开始更新标签按钮")
        # 清除现有标签按钮
        for btn in self.tag_buttons.values():
            btn.deleteLater()
        self.tag_buttons.clear()
        
        # 获取当前选中的标签类型按钮
        selected_button = self.tag_type_group.checkedButton()
        if selected_button is None:
            log.warning("没有选中的标签类型")
            return
            
        selected_type = selected_button.text()
        prefix = f"{selected_type}:"
        
        # 过滤出允许显示的标签
        filtered_tags = [tag for tag in sorted(self.manga_manager.tags) 
                        if tag.startswith(prefix)]
        
        # 创建标签按钮，只显示冒号后的内容
        for tag in filtered_tags:
            tag_text = tag.split(':', 1)[1]  # 只取冒号后的部分
            btn = QPushButton(tag_text)
            btn.setCheckable(True)
            self.tag_layout.addWidget(btn)
            self.tag_buttons[tag] = btn  # 注意：这里仍然使用完整tag作为键
            btn.clicked.connect(self.on_tag_button_clicked)
        
        log.info(f"标签按钮更新完成，显示了 {len(filtered_tags)} 个标签")
    
    def filter_and_update_manga_list(self, tag):
        log.info(f"选择标签: {tag}")
        filtered_manga = self.manga_manager.filter_manga([tag])
        self.update_manga_list(filtered_manga)
    
    def on_tag_button_clicked(self):
        # 获取发送信号的按钮
        button = self.sender()
        
        # 如果点击的是当前选中的按钮，取消选中并显示所有漫画
        if button.isChecked():
            # 取消其他按钮的选中状态
            for btn in self.tag_buttons.values():
                if btn != button:
                    btn.setChecked(False)
            
            # 获取完整的标签（标签类型:标签值）
            selected_type = self.tag_type_group.checkedButton().text()
            full_tag = f"{selected_type}:{button.text()}"
            
            # 调用新的方法进行过滤和更新
            self.filter_and_update_manga_list(full_tag)
        else:
            # 显示所有漫画
            log.info("取消选择标签，显示所有漫画")
            self.update_manga_list()
    
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
                self.current_manga = manga
                self.current_manga.current_page = 0
                self.show_current_page()
            else:
                log.warning("选择的漫画数据为空")
        except Exception as e:
            log.error(f"选择漫画时发生错误: {str(e)}")
            QMessageBox.warning(self, '错误', f'选择漫画时发生错误: {str(e)}')
            return
    
    def show_current_page(self):
        if not self.current_manga:
            return
        
        try:
            # 加载当前页面
            current_image = MangaLoader.get_page_image(self.current_manga, self.current_manga.current_page)
            if not current_image:
                self.image_label.setText("无法加载图像")
                self.update_navigation_buttons()
                return

            # 获取下一页图像（如果是双页模式且存在下一页）
            next_image = None
            if not self.is_single_page_mode and self.current_manga.current_page < self.current_manga.total_pages - 1:
                next_image = MangaLoader.get_page_image(self.current_manga, self.current_manga.current_page + 1)

            try:
                # 处理当前页面
                if current_image.mode != 'RGB':
                    current_image = current_image.convert('RGB')
                
                # 如果是双页模式且有下一页，处理下一页图像
                if next_image and not self.is_single_page_mode:
                    if next_image.mode != 'RGB':
                        next_image = next_image.convert('RGB')
                    
                    # 创建合并图像
                    total_width = current_image.width + (next_image.width if next_image else 0)
                    max_height = max(current_image.height, next_image.height if next_image else 0)
                    
                    # 创建新的RGB图像
                    from PIL import Image
                    combined_image = Image.new('RGB', (total_width, max_height))
                    
                    # 根据显示方向粘贴图像
                    if self.next_page_on_right:
                        combined_image.paste(current_image, (0, 0))
                        combined_image.paste(next_image, (current_image.width, 0))
                    else:
                        combined_image.paste(next_image, (0, 0))
                        combined_image.paste(current_image, (next_image.width, 0))
                else:
                    # 单页模式，直接使用当前页面
                    combined_image = current_image
                
                # 转换为QImage
                img_data = combined_image.tobytes()
                qim = QImage(img_data, combined_image.width, combined_image.height, 
                           combined_image.width * 3, QImage.Format_RGB888)
                
                if qim.isNull():
                    log.error("QImage创建失败")
                    self.image_label.setText("图像转换失败")
                    self.update_navigation_buttons()
                    return
                
                # 创建QPixmap并缩放
                pixmap = QPixmap.fromImage(qim)
                if pixmap.isNull():
                    log.error("QPixmap创建失败")
                    self.image_label.setText("图像转换失败：无法创建QPixmap")
                    self.update_navigation_buttons()
                    return
                
                # 获取 QScrollArea
                scroll_area = None
                parent = self.image_label.parent()
                while parent:
                    if isinstance(parent, QScrollArea):
                        scroll_area = parent
                        break
                    parent = parent.parent()
                
                if scroll_area:
                    viewport_size = scroll_area.viewport().size()
                    scale_w = viewport_size.width() / pixmap.width()
                    scale_h = viewport_size.height() / pixmap.height()
                    scale = min(scale_w, scale_h)
                    
                    # 应用用户缩放比例
                    zoom_factor = self.zoom_slider.value() / 100.0
                    scale *= zoom_factor
                    
                    new_width = int(pixmap.width() * scale)
                    new_height = int(pixmap.height() * scale)
                    
                    scaled_pixmap = pixmap.scaled(new_width, new_height, 
                                                Qt.KeepAspectRatio, 
                                                Qt.SmoothTransformation)
                    
                    self.image_label.setPixmap(scaled_pixmap)
                    self.image_label.setFixedSize(new_width, new_height)
                else:
                    self.image_label.setPixmap(pixmap)
                
                self.update_navigation_buttons()
                
            except Exception as e:
                log.error(f"处理图像时发生错误: {str(e)}")
                self.image_label.setText(f"图像处理错误: {str(e)}")
                self.update_navigation_buttons()
                
        except Exception as e:
            log.error(f"显示页面时发生错误: {str(e)}")
            self.image_label.setText(f"显示错误: {str(e)}")
            self.update_navigation_buttons()
    
    def change_page(self, direction):
        """统一处理页面变化
        Args:
            direction: 1 表示向后，-1 表示向前
        """
        if not self.current_manga:
            return
            
        step = 1 if self.is_single_page_mode else 2
        current_page = self.current_manga.current_page
        total_pages = self.current_manga.total_pages
        
        if direction > 0:  # 向后翻页
            if current_page < total_pages - step:
                self.current_manga.current_page += step
                self.show_current_page()
        else:  # 向前翻页
            if current_page >= step:
                self.current_manga.current_page -= step
                self.show_current_page()

    def prev_page(self):
        self.change_page(-1)
    
    def next_page(self):
        self.change_page(1)

    def show_previous_page(self):
        self.change_page(-1)

    def show_next_page(self):
        self.change_page(1)
    
    def on_slider_value_changed(self):
        """处理滑动条值变化"""
        if self.current_manga and not self.is_updating_slider:
            self.current_manga.current_page = self.page_slider.value()
            self.show_current_page()

    def on_zoom_changed(self):
        """处理缩放值变化"""
        if self.current_manga:
            self.show_current_page()

    def show_current_page(self):
        if not self.current_manga:
            return
        
        try:
            # 加载当前页面
            current_image = MangaLoader.get_page_image(self.current_manga, self.current_manga.current_page)
            if not current_image:
                self.image_label.setText("无法加载图像")
                self.update_navigation_buttons()
                return

            # 获取下一页图像（如果是双页模式且存在下一页）
            next_image = None
            if not self.is_single_page_mode and self.current_manga.current_page < self.current_manga.total_pages - 1:
                next_image = MangaLoader.get_page_image(self.current_manga, self.current_manga.current_page + 1)

            try:
                # 处理当前页面
                if current_image.mode != 'RGB':
                    current_image = current_image.convert('RGB')
                
                # 如果是双页模式且有下一页，处理下一页图像
                if next_image and not self.is_single_page_mode:
                    if next_image.mode != 'RGB':
                        next_image = next_image.convert('RGB')
                    
                    # 创建合并图像
                    total_width = current_image.width + (next_image.width if next_image else 0)
                    max_height = max(current_image.height, next_image.height if next_image else 0)
                    
                    # 创建新的RGB图像
                    from PIL import Image
                    combined_image = Image.new('RGB', (total_width, max_height))
                    
                    # 根据显示方向粘贴图像
                    if self.next_page_on_right:
                        combined_image.paste(current_image, (0, 0))
                        combined_image.paste(next_image, (current_image.width, 0))
                    else:
                        combined_image.paste(next_image, (0, 0))
                        combined_image.paste(current_image, (next_image.width, 0))
                else:
                    # 单页模式，直接使用当前页面
                    combined_image = current_image
                
                # 转换为QImage
                img_data = combined_image.tobytes()
                qim = QImage(img_data, combined_image.width, combined_image.height, 
                           combined_image.width * 3, QImage.Format_RGB888)
                
                if qim.isNull():
                    log.error("QImage创建失败")
                    self.image_label.setText("图像转换失败")
                    self.update_navigation_buttons()
                    return
                
                # 创建QPixmap并缩放
                pixmap = QPixmap.fromImage(qim)
                if pixmap.isNull():
                    log.error("QPixmap创建失败")
                    self.image_label.setText("图像转换失败：无法创建QPixmap")
                    self.update_navigation_buttons()
                    return
                
                # 获取 QScrollArea
                scroll_area = None
                parent = self.image_label.parent()
                while parent:
                    if isinstance(parent, QScrollArea):
                        scroll_area = parent
                        break
                    parent = parent.parent()
                
                if scroll_area:
                    viewport_size = scroll_area.viewport().size()
                    scale_w = viewport_size.width() / pixmap.width()
                    scale_h = viewport_size.height() / pixmap.height()
                    scale = min(scale_w, scale_h)
                    
                    # 应用用户缩放比例
                    zoom_factor = self.zoom_slider.value() / 100.0
                    scale *= zoom_factor
                    
                    new_width = int(pixmap.width() * scale)
                    new_height = int(pixmap.height() * scale)
                    
                    scaled_pixmap = pixmap.scaled(new_width, new_height, 
                                                Qt.KeepAspectRatio, 
                                                Qt.SmoothTransformation)
                    
                    self.image_label.setPixmap(scaled_pixmap)
                    self.image_label.setFixedSize(new_width, new_height)
                else:
                    self.image_label.setPixmap(pixmap)
                
                self.update_navigation_buttons()
                
            except Exception as e:
                log.error(f"处理图像时发生错误: {str(e)}")
                self.image_label.setText(f"图像处理错误: {str(e)}")
                self.update_navigation_buttons()
                
        except Exception as e:
            log.error(f"显示页面时发生错误: {str(e)}")
            self.image_label.setText(f"显示错误: {str(e)}")
            self.update_navigation_buttons()
    
    def change_page(self, direction):
        """统一处理页面变化
        Args:
            direction: 1 表示向后，-1 表示向前
        """
        if not self.current_manga:
            return
            
        step = 1 if self.is_single_page_mode else 2
        current_page = self.current_manga.current_page
        total_pages = self.current_manga.total_pages
        
        if direction > 0:  # 向后翻页
            if current_page < total_pages - step:
                self.current_manga.current_page += step
                self.show_current_page()
        else:  # 向前翻页
            if current_page >= step:
                self.current_manga.current_page -= step
                self.show_current_page()

    def prev_page(self):
        self.change_page(-1)
    
    def next_page(self):
        self.change_page(1)

    def show_previous_page(self):
        self.change_page(-1)

    def show_next_page(self):
        self.change_page(1)
    
    def on_slider_value_changed(self):
        """处理滑动条值变化"""
        if self.current_manga and not self.is_updating_slider:
            self.current_manga.current_page = self.page_slider.value()
            self.show_current_page()

    def update_navigation_buttons(self):
        has_manga = self.current_manga is not None
        if has_manga:
            prev_enabled = self.current_manga.current_page > 0
            next_enabled = self.current_manga.current_page < self.current_manga.total_pages - 1
            self.prev_btn.setEnabled(prev_enabled)
            self.next_btn.setEnabled(next_enabled)
            
            # 更新滑动条
            self.is_updating_slider = True  # 设置标志，防止触发 valueChanged 信号
            self.page_slider.setMaximum(self.current_manga.total_pages - 1)
            self.page_slider.setValue(self.current_manga.current_page)
            self.is_updating_slider = False
        else:
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            self.page_slider.setMaximum(0)
            self.page_slider.setValue(0)
    
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
        context_menu = QMenu(self)
        
        # 添加基本菜单项
        open_folder_action = QAction("打开所在文件夹", self)
        open_folder_action.triggered.connect(lambda: self.open_manga_folder(manga))
        context_menu.addAction(open_folder_action)
        
        rename_action = QAction("重命名", self)
        rename_action.triggered.connect(lambda: self.rename_manga(manga))
        context_menu.addAction(rename_action)
        
        # 添加分隔线和显示方向选项
        context_menu.addSeparator()
        
        # 添加显示方向切换选项
        direction_action = QAction("下一页显示在左边" if self.next_page_on_right else "下一页显示在右边", self)
        direction_action.triggered.connect(self.toggle_page_direction)
        context_menu.addAction(direction_action)
        
        # 添加过滤子菜单
        filter_menu = QMenu("过滤", context_menu)
        
        # 获取漫画的所有有效标签（排除标题标签）
        valid_tags = sorted([tag for tag in manga.tags if not tag.startswith('标题:')])
        
        # 为每个标签创建过滤动作
        for tag in valid_tags:
            filter_action = QAction(tag, self)
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
        for button in self.tag_type_group.buttons():
            if button.text() == tag_type:
                button.setChecked(True)
                # 更新标签按钮
                self.update_tag_buttons()
                break
        
        # 找到并选中对应的标签按钮
        if tag in self.tag_buttons:
            self.tag_buttons[tag].setChecked(True)
            # 触发标签按钮的点击事件
            self.filter_and_update_manga_list(tag)
    
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
            QMessageBox.warning(self, '错误', f'无法打开文件夹: {str(e)}')
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 如果当前有显示的图片，重新加载并显示
        if self.current_manga:
            self.show_current_page()
    
    def convert_image_to_pixmap(self, image):
        """将 PIL Image 转换为 QPixmap"""
        try:
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            img_data = image.tobytes()
            qim = QImage(img_data, image.width, image.height, image.width * 3, QImage.Format_RGB888)
            
            if qim.isNull():
                return None
                
            return QPixmap.fromImage(qim)
        except Exception as e:
            log.error(f"转换图像时发生错误: {str(e)}")
            return None
    
    def closeEvent(self, event):
        log.info("程序关闭，保存配置")
        self.manga_manager.save_config()
        log.info("配置保存完成，程序退出")
        super().closeEvent(event)

    def show_previous_page(self):
        print("Calling prev_page")  # 调试输出
        self.prev_page()

    def show_next_page(self):
        print("Calling next_page")  # 调试输出
        self.next_page()

    def show_manga_info(self):
        if self.current_manga:
            log.info("\n=== 漫画信息 ===")
            # 从标签中获取标题和作者
            title = next((tag.split(':', 1)[1] for tag in self.current_manga.tags if tag.startswith('标题:')), '')
            author = next((tag.split(':', 1)[1] for tag in self.current_manga.tags if tag.startswith('作者:')), '')
            
            log.info(f"标题: {title}")
            log.info(f"作者: {author}")
            log.info(f"标签: {sorted(self.current_manga.tags)}")
            log.info("===============")

    def create_tag_type_buttons(self, layout):
        """动态创建标签类型按钮"""
        # 获取所有标签
        all_tags = set()
        for manga in self.manga_manager.manga_list:
            all_tags.update(manga.tags)
        
        # 提取标签类型（冒号前的部分），排除标题标签
        tag_types = set()
        for tag in all_tags:
            if ':' in tag:
                tag_type = tag.split(':', 1)[0]
                if tag_type != '标题':  # 排除标题标签
                    tag_types.add(tag_type)
        
        # 按优先级排序标签类型（最多8个）
        priority_types = ['会场', '作者', '作品', '平台', '组', '汉化', '其他']
        sorted_types = sorted(tag_types, key=lambda x: (
            priority_types.index(x) if x in priority_types else len(priority_types)
        ))[:8]
        
        # 创建按钮
        for i, tag_type in enumerate(sorted_types):
            btn = QRadioButton(tag_type)
            if i == 0:  # 默认选中第一个
                btn.setChecked(True)
            self.tag_type_group.addButton(btn)
            layout.addWidget(btn)

    def filter_manga(self, tag_filters):
        if not tag_filters:
            return self.manga_manager.manga_list
        
        filtered_list = []
        for manga in self.manga_manager.manga_list:
            match = True
            for tag in tag_filters:
                if tag not in manga.tags:
                    match = False
                    break
            if match:
                filtered_list.append(manga)
        return filtered_list

    def on_search_text_changed(self):
        """当搜索框文本改变时触发"""
        # 重置定时器
        self.search_timer.stop()
        # 1秒后执行搜索
        self.search_timer.start(100)
    
    def perform_search(self):
        """执行搜索"""
        search_text = self.search_input.text().lower()
        log.info(f"执行搜索: {search_text}")
        
        if not search_text:
            # 如果搜索框为空，显示所有漫画
            self.update_manga_list()
            return
        
        # 搜索文件名
        filtered_manga = [
            manga for manga in self.manga_manager.manga_list
            if search_text in os.path.basename(manga.file_path).lower()
        ]
        
        # 更新显示
        self.update_manga_list(filtered_manga)

    def toggle_page_direction(self):
        """切换页面显示方向"""
        self.next_page_on_right = not self.next_page_on_right
        self.show_current_page()  # 刷新显示

    def toggle_page_mode(self):
        """切换单页/双页显示模式"""
        self.is_single_page_mode = self.single_page_btn.isChecked()
        self.single_page_btn.setText('单页' if self.is_single_page_mode else '双页')
        if self.current_manga:
            self.show_current_page()
    
    def toggle_style(self):
        """切换界面风格"""
        styles = {'default': ('light', '亮色'), 'light': ('dark', '暗色'), 'dark': ('default', '默认')}
        next_style, btn_text = styles[self.current_style]
        self.current_style = next_style
        self.style_btn.setText(btn_text)
        
        if next_style == 'default':
            Win11Style.apply_style(self)
        elif next_style == 'light':
            Win11LightStyle.apply_style(self)
        else:
            Win11DarkStyle.apply_style(self)
