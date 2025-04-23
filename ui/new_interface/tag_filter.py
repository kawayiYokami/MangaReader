from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QButtonGroup, QSizePolicy
from PyQt5.QtCore import Qt, QEasingCurve
from qfluentwidgets import (
    CardWidget,
    PushButton,
    FlowLayout,
    SmoothScrollArea,
    SegmentedWidget,
    PillPushButton,
)

# 删除错误的导入
# from qfluentwidgets import StyleSheet
from core.manga_manager import MangaManager  # 新增导入


class TagFilter(CardWidget):
    def __init__(self, parent=None, manga_manager=None):  # 修改构造函数
        super().__init__(parent)
        self.parent = parent
        self.manga_manager = manga_manager or MangaManager()  # 初始化管理器
        self.setBorderRadius(8)

        # 初始化标签相关属性
        self.tag_buttons = []
        self.current_tags = set()
        self.current_type = ""

        self.setup_ui()

        # 连接标签更新信号
        if self.manga_manager:
            self.manga_manager.tags_updated.connect(self.update_tags)

        # 添加这行样式表
        self.setAttribute(Qt.WA_StyledBackground)  # 确保样式应用到整个组件
        self.setStyleSheet(
            """
            TagFilter {
                background: transparent;
                border: none;
            }
            /* 原有样式表保持不变 */
        """
        )

    def setup_ui(self):
        self.layout = QVBoxLayout(self)

        # 标签类型选择 - 使用SegmentedWidget
        self.type_selector = SegmentedWidget(self)
        self.type_selector.setFixedHeight(30)
        tag_types = ["作者", "作品", "平台", "汉化", "会场"]
        for tag_type in tag_types:
            self.type_selector.addItem(tag_type, tag_type)

        # 修正：使用正确的信号连接方式
        self.type_selector.currentItemChanged.connect(self.on_type_changed)

        self.layout.addWidget(self.type_selector, alignment=Qt.AlignTop)

        # 创建滚动区域（按照官方示例方式）
        # 创建滚动区域并设置样式
        self.scroll_area = SmoothScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setViewportMargins(0, 5, 0, 5)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(
            """
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """
        )

        # 容器Widget设置
        self.scroll_widget = QWidget()
        self.scroll_widget.setStyleSheet("background: transparent;")
        self.scroll_widget.setMinimumWidth(200)  # 设置最小宽度
        self.tag_layout = FlowLayout(self.scroll_widget, isTight=True)

        # 设置布局属性
        self.tag_layout.setContentsMargins(8, 8, 8, 8)
        self.tag_layout.setVerticalSpacing(8)
        self.tag_layout.setHorizontalSpacing(8)

        # 确保FlowLayout能感知容器宽度变化
        self.scroll_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 创建标签按钮组
        self.tag_button_group = QButtonGroup(self)
        self.tag_button_group.setExclusive(False)
        self.tag_button_group.buttonClicked.connect(self.on_tag_clicked)

        # 设置滚动区域
        self.scroll_area.setWidget(self.scroll_widget)
        self.layout.addWidget(self.scroll_area)

        # 确保UI初始化完成后更新标签
        if self.manga_manager and self.manga_manager.tags:
            self.update_tags(self.manga_manager.tags)
            # 在添加完所有标签类型后，设置默认选中"作者"
            self.type_selector.setCurrentItem("作者")

    def clear_tags(self):
        """清空所有标签按钮"""
        for button in self.tag_buttons:
            self.tag_layout.removeWidget(button)
            button.deleteLater()
        self.tag_buttons.clear()
        self.tag_button_group.buttons().clear()

    def update_tags(self, tags):
        """根据新标签集合更新标签栏"""
        self.current_tags = tags
        self.filter_tags_by_type(self.current_type)

    def filter_tags_by_type(self, tag_type):
        """根据标签类型过滤并显示标签"""
        self.clear_tags()
        self.current_type = tag_type

        if not tag_type or not self.manga_manager:
            return

        # 使用MangaManager获取过滤后的标签
        filtered_tags = {
            tag for tag in self.manga_manager.tags if tag.startswith(f"{tag_type}:")
        }

        self.refresh_tag_buttons(filtered_tags)  # 调用单独的刷新方法

    def refresh_tag_buttons(self, tags):
        """刷新标签按钮显示"""
        for tag in tags:
            tag_name = tag.split(":", 1)[1] if ":" in tag else tag
            button = PillPushButton(tag_name)
            button.setCheckable(True)
            button.setProperty("full_tag", tag)
            self.tag_layout.addWidget(button)
            self.tag_button_group.addButton(button)
            self.tag_buttons.append(button)

    def on_type_changed(self, index):
        """标签类型选择变化时的处理"""
        tag_type = self.type_selector.items[index].text()
        self.filter_tags_by_type(tag_type)

    def on_tag_clicked(self, button):
        """标签点击事件处理"""
        tag = button.property("full_tag")

        if tag and self.manga_manager:
            # 清空同分类下的所有标签按钮选中状态
            current_type = tag.split(":")[0] if ":" in tag else ""
            for btn in self.tag_buttons:
                btn_tag = btn.property("full_tag")
                if btn_tag and btn_tag.startswith(current_type + ":") and btn != button:
                    btn.setChecked(False)

            if button.isChecked():
                self.manga_manager.filter_manga([tag])
            else:
                self.manga_manager.filter_manga([])
