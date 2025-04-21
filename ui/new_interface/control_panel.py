from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from PyQt5.QtCore import Qt
from qfluentwidgets import CardWidget, TransparentPushButton, Slider, FluentIcon, TransparentToolButton, isDarkTheme, PillPushButton
from core.manga_manager import MangaManager

class ControlPanel(CardWidget):
    """控制面板组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.manga_manager = None
        # 尝试从父组件获取manga_manager
        if hasattr(parent, 'manga_manager'):
            self.manga_manager = parent.manga_manager
        else:
            self.manga_manager = MangaManager()
            
        # 连接信号
        if self.manga_manager:
            self.manga_manager.current_manga_changed.connect(self.on_manga_changed)
            self.manga_manager.page_changed.connect(self.update_page_label)
            
        self.setFixedHeight(50)  # 设置固定高度
        self.setup_ui()
        
    def setup_ui(self):
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 0, 10, 0)
        
        # 标签按钮区域
        self.tag_container = QWidget()
        self.tag_layout = QHBoxLayout(self.tag_container)
        self.tag_layout.setContentsMargins(0, 0, 0, 0)
        self.tag_layout.setSpacing(5)
        self.tag_buttons = []
        
        # 添加标签容器
        self.layout.addWidget(self.tag_container)
        
        # 页面滑动条
        self.page_slider = Slider(Qt.Horizontal)
        self.page_slider.setFixedWidth(200)
        self.page_slider.setSingleStep(1)
        self.page_slider.valueChanged.connect(self.on_slider_changed)
        self.layout.addWidget(self.page_slider)
        
        # 阅读方向按钮
        self.direction_button = TransparentToolButton()
        self.direction_button.setCheckable(True)
        self.direction_button.clicked.connect(self.toggle_direction)
        self.direction_button.setIcon(FluentIcon.RIGHT_ARROW)
        self.layout.addWidget(self.direction_button)
        
        # 添加右侧弹性空间
        self.layout.addStretch(1)
        
        # 初始状态下禁用控制按钮，直到选择了漫画
        self.direction_button.setEnabled(False)
        self.set_opacity(250)

    def set_opacity(self, alpha):
        """设置控制面板透明度
        :param alpha: 透明度值(0-255)
        """
        # 根据当前主题设置基础颜色
        if isDarkTheme():
            bg_color = "rgba(32, 32, 32"
        else:
            bg_color = "rgba(243, 243, 243"
            
        # 应用新透明度
        self.setStyleSheet(f"""
            ControlPanel {{
                background: {bg_color}, {alpha});
                border-radius: 8px;
            }}
        """)

    def toggle_direction(self):
        """切换阅读方向（从左到右/从右到左）"""
        if hasattr(self.parent, 'toggle_reading_order'):
            current_order = self.parent.toggle_reading_order()
            self.direction_button.setChecked(current_order == 'right_to_left')
            self.direction_button.setIcon(FluentIcon.RIGHT_ARROW if current_order == 'right_to_left' else FluentIcon.LEFT_ARROW)
            
        # 更新显示
        if hasattr(self.parent, 'update_display'):
            self.parent.update_display()
    
    def on_prev_page(self):
        """上一页按钮点击事件"""
        if hasattr(self.parent, 'prev_page'):
            self.parent.prev_page()
    
    def on_next_page(self):
        """下一页按钮点击事件"""
        if hasattr(self.parent, 'next_page'):
            self.parent.next_page()
    
    def on_manga_changed(self, manga):
        """当前漫画变更时的处理函数"""
        self.update_page_label()
        
        # 启用或禁用控制按钮
        enabled = manga is not None
        self.direction_button.setEnabled(enabled)
        
        # 更新标签按钮
        self.update_tag_buttons()
    
    def update_page_label(self):
        """更新滑动条范围"""
        if self.manga_manager and hasattr(self.manga_manager, 'current_manga') and self.manga_manager.current_manga:
            total_pages = self.manga_manager.current_manga.total_pages
            self.page_slider.setMaximum(total_pages - 1)
            self.page_slider.setValue(self.manga_manager.current_page)
            
    def on_slider_changed(self, value):
        """滑动条值改变事件"""
        if self.manga_manager and hasattr(self.manga_manager, 'current_manga') and self.manga_manager.current_manga:
            self.manga_manager.change_page(value)
            
    def update_tag_buttons(self):
        """更新标签按钮"""
        # 清除现有按钮
        for button in self.tag_buttons:
            button.deleteLater()
        self.tag_buttons.clear()
        
        if not self.manga_manager or not self.manga_manager.current_manga:
            return
            
        # 为当前漫画的每个标签创建按钮
        for tag in self.manga_manager.current_manga.tags:
            # 跳过以'标题:'开头的标签
            if tag.startswith('标题:'):
                continue
            button = PillPushButton()
            button.setText(tag.split(':', 1)[1] if ':' in tag else tag)
            button.setCheckable(True)
            button.clicked.connect(lambda checked, t=tag: self.on_tag_clicked(t, checked))
            self.tag_layout.addWidget(button)
            self.tag_buttons.append(button)
            
    def on_tag_clicked(self, tag, checked):
        """标签按钮点击事件"""
        if hasattr(self.parent, 'tag_filter') and self.parent.tag_filter:
            self.parent.tag_filter.set_tag_state(tag, checked)
        
        # 清空所有其他按钮的选中状态
        for button in self.tag_buttons:
            if button.text() != tag.split(':', 1)[1] if ':' in tag else tag:
                button.setChecked(False)
                
        if self.manga_manager:
            # 根据按钮状态传递当前标签作为过滤器
            tag_filters = [tag] if checked else []
            self.manga_manager.filter_manga(tag_filters)