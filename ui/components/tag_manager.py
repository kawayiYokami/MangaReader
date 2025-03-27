from PyQt5.QtWidgets import (QButtonGroup, QRadioButton, QScrollArea, 
                             QFrame, QPushButton, QHBoxLayout)
from PyQt5.QtCore import Qt
from ui.layouts.flow_layout import FlowLayout
from utils import manga_logger as log
from styles.light_style import Win11LightStyle
from styles.dark_style import Win11DarkStyle
from styles.style import Win11Style

class TagManager:
    """负责标签管理和过滤的组件"""
    
    def __init__(self, parent):
        self.parent = parent
        self.manga_manager = parent.manga_manager
        self.tag_buttons = {}
        self.tag_frame = None
        self.tag_layout = None
        self.tag_type_group = QButtonGroup(parent)
        self.tag_type_group.buttonClicked.connect(self.update_tag_buttons)
        self.filter_button_group = QButtonGroup(parent)
        self.filter_button_group.setExclusive(False)  # 设置为非互斥（多选）模式
    
    def setup_ui(self, parent_layout):
        # 创建标签类型布局
        tag_type_layout = QHBoxLayout()
        self.create_tag_type_buttons(tag_type_layout)
        parent_layout.addLayout(tag_type_layout)
        
        # 标签过滤按钮区域（使用QScrollArea包装）
        tag_scroll_area = QScrollArea()
        tag_scroll_area.setWidgetResizable(True)
        tag_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tag_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tag_scroll_area = tag_scroll_area  # 保存为实例变量

        self.tag_frame = QFrame()
        # 使用FlowLayout来实现标签的流式布局
        self.tag_layout = FlowLayout(self.tag_frame)
        self.tag_layout.setSpacing(5)
        tag_scroll_area.setWidget(self.tag_frame)
    
        return tag_scroll_area
    
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
    
    def on_tag_button_clicked(self):
        # 获取发送信号的按钮
        button = self.parent.sender()
        
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
            self.parent.manga_list_manager.update_manga_list()
    
    def filter_and_update_manga_list(self, tag):
        log.info(f"选择标签: {tag}")
        filtered_manga = self.manga_manager.filter_manga([tag])
        self.parent.manga_list_manager.update_manga_list(filtered_manga)