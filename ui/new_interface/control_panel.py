from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    TransparentPushButton,
    Slider,
    FluentIcon as FIF,
    TransparentToolButton,
    isDarkTheme,
    PillPushButton,
    InfoBar,
    InfoBarPosition,
    SwitchButton,
)
from core.manga_manager import MangaManager
from PyQt5.QtGui import QColor
from core.config import config, DisplayMode, ReadingOrder
from PyQt5.QtCore import QTimer


class ControlPanel(CardWidget):
    """控制面板组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.manga_manager = None
        self.auto_timer = None
        self.auto_flip_interval = 3000  # 默认3秒自动翻页间隔
        # 尝试从父组件获取manga_manager
        if hasattr(parent, "manga_manager"):
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

        # 添加页码标签
        self.page_label = BodyLabel("0/0")
        self.page_label.setFixedWidth(80)
        self.page_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.page_label)

        # 添加Switch开关
        self.switch_button = SwitchButton()
        self.switch_button.checkedChanged.connect(self.on_switch_changed)
        self.layout.addWidget(self.switch_button)

        # 根据阅读方向更新滑动条方向
        if hasattr(self.parent, "reading_order"):
            self.update_slider_direction(self.parent.reading_order)

        # 添加右侧弹性空间
        self.layout.addStretch(1)

        # 初始状态下禁用控制按钮，直到选择了漫画
        self.set_opacity()

    def set_opacity(self, alpha=250):
        """设置控制面板透明度
        :param alpha: 透明度值(0-255)
        """
        # 根据当前主题设置基础颜色
        if isDarkTheme():
            bg_color = "rgba(32, 32, 32"
        else:
            bg_color = "rgba(243, 243, 243"

        # 应用新透明度
        self.setStyleSheet(
            f"""
            ControlPanel {{
                background: {bg_color}, {alpha});
                border-radius: 8px;
            }}
        """
        )

    def on_prev_page(self):
        """上一页按钮点击事件"""
        if hasattr(self.parent, "prev_page"):
            if self.auto_timer and self.auto_timer.isActive():
                self.stop_auto_flip()
                self.start_auto_flip()
            self.parent.prev_page()

    def on_next_page(self):
        """下一页按钮点击事件"""
        if hasattr(self.parent, "next_page"):
            if self.auto_timer and self.auto_timer.isActive():
                self.stop_auto_flip()
                self.start_auto_flip()
            self.parent.next_page()

    def on_manga_changed(self, manga):
        """当前漫画变更时的处理函数"""
        self.update_page_label()

        # 启用或禁用控制按钮
        enabled = manga is not None

        # 更新标签按钮
        self.update_tag_buttons()

    def update_page_label(self):
        """更新滑动条范围和页码显示"""
        if (
            self.manga_manager
            and hasattr(self.manga_manager, "current_manga")
            and self.manga_manager.current_manga
        ):
            total_pages = self.manga_manager.current_manga.total_pages
            self.page_slider.setMaximum(total_pages - 1)

            # 根据阅读方向设置滑动条值
            if (
                hasattr(self.parent, "reading_order")
                and self.parent.reading_order == ReadingOrder.RIGHT_TO_LEFT.value
            ):
                current_page = total_pages - 1 - config.current_page.value
                self.page_slider.setValue(current_page)
            else:
                current_page = config.current_page.value
                self.page_slider.setValue(current_page)

            # 更新页码标签
            if hasattr(self, "page_label"):
                self.page_label.setText(f"{current_page + 1}/{total_pages}")

            # 同时更新滑动条方向
            if hasattr(self.parent, "reading_order"):
                self.update_slider_direction(self.parent.reading_order)

    def on_slider_changed(self, value):
        """滑动条值改变事件"""
        if (
            self.manga_manager
            and hasattr(self.manga_manager, "current_manga")
            and self.manga_manager.current_manga
        ):
            # 根据阅读方向调整页面值
            if (
                hasattr(self.parent, "reading_order")
                and self.parent.reading_order == ReadingOrder.RIGHT_TO_LEFT.value
            ):
                total_pages = self.manga_manager.current_manga.total_pages
                value = total_pages - 1 - value
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
            if tag.startswith("标题:"):
                continue
            button = PillPushButton()
            button.setText(tag.split(":", 1)[1] if ":" in tag else tag)
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked, t=tag: self.on_tag_clicked(t, checked)
            )
            # 添加双击事件
            button.mouseDoubleClickEvent = (
                lambda event, t=tag: self.on_tag_double_clicked(t, event)
            )
            self.tag_layout.addWidget(button)
            self.tag_buttons.append(button)

    def on_tag_double_clicked(self, tag, event):
        """标签双击事件处理"""
        import pyperclip

        # 复制标签内容到剪贴板
        pyperclip.copy(tag.split(":", 1)[1] if ":" in tag else tag)
        # 显示简洁的居中提示信息
        InfoBar.success(
            title="",  # 空标题
            content="已复制",  # 简洁提示
            isClosable=True,
            position=InfoBarPosition.BOTTOM,  # 窗口正中间
            duration=1500,  # 缩短显示时间
            parent=self.parent,
        )

    def on_tag_clicked(self, tag, checked):
        """标签按钮点击事件"""
        if hasattr(self.parent, "tag_filter") and self.parent.tag_filter:
            self.parent.tag_filter.set_tag_state(tag, checked)

        # 清空所有其他按钮的选中状态
        for button in self.tag_buttons:
            if button.text() != tag.split(":", 1)[1] if ":" in tag else tag:
                button.setChecked(False)

        if self.manga_manager:
            # 根据按钮状态传递当前标签作为过滤器
            tag_filters = [tag] if checked else []
            self.manga_manager.filter_manga(tag_filters)

    def update_slider_direction(self, reading_order):
        """根据阅读方向更新滑动条方向"""
        if reading_order == ReadingOrder.RIGHT_TO_LEFT.value:
            self.page_slider.setInvertedAppearance(True)
            self.page_slider.setInvertedControls(True)
        else:
            self.page_slider.setInvertedAppearance(False)
            self.page_slider.setInvertedControls(False)

    def on_switch_changed(self, is_checked):
        """Switch开关状态改变事件"""
        if is_checked:
            self.start_auto_flip()
        else:
            self.stop_auto_flip()

    def start_auto_flip(self):
        """启动自动翻页定时器"""
        if not self.auto_timer:

            self.auto_timer = QTimer()
            self.auto_timer.timeout.connect(self.auto_flip_page)
            # 从config读取PageInterval值作为间隔时间(毫秒)
            interval = config.page_interval.value * 1000
            print(f"[DEBUG] 启动自动翻页定时器，间隔时间: {interval}ms")
            print(f"[DEBUG] 当前配置值 page_interval: {config.page_interval.value}秒")
            self.auto_timer.start(interval)

    def stop_auto_flip(self):
        """停止自动翻页定时器"""
        if self.auto_timer:
            print("[DEBUG] 停止自动翻页定时器")
            self.auto_timer.stop()
            self.auto_timer = None

    def auto_flip_page(self):
        """自动翻页逻辑"""
        print("[DEBUG] 执行自动翻页动作")
        if hasattr(self.parent, "next_page"):
            self.parent.next_page()
        else:
            print("[DEBUG] 父组件没有next_page方法，停止定时器")
            self.stop_auto_flip()
