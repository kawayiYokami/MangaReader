from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHBoxLayout,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, QEasingCurve
from qfluentwidgets import (
    CardWidget,
    SearchLineEdit,
    ToolButton,
    PushButton,
    SmoothScrollArea,
    TableWidget,
)
from qfluentwidgets.common.icon import FluentIcon as FIF
from core.manga_manager import MangaManager  # 新增导入
from PyQt5.QtWidgets import QFileDialog


class MangaList(QWidget):  # 改为继承自QWidget
    """漫画列表组件"""

    def __init__(self, parent=None, manga_manager=None):  # 修改构造函数
        super().__init__(parent)
        self.parent = parent
        self.manga_manager = (
            manga_manager or MangaManager()
        )  # 使用传入的管理器或新建实例
        self.filtered_manga_list = []  # 添加过滤后的列表属性
        self.setup_ui()
        # 修改为连接filter_applied信号
        self.manga_manager.filter_applied.connect(self.update_table)

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)  # 移除外部边距

        # 搜索区域 - 移到卡片外部
        search_layout = QHBoxLayout()
        self.open_button = ToolButton(FIF.FOLDER, self)  # 使用文件夹图标
        self.open_button.clicked.connect(self.open_folder_dialog)
        self.search_input = SearchLineEdit()
        self.search_input.setPlaceholderText("搜索漫画...")
        self.search_input.textChanged.connect(self.on_search_text_changed)

        search_layout.addWidget(self.open_button)
        search_layout.addWidget(self.search_input)
        self.layout.addLayout(search_layout)

        # 卡片区域 - 只包含表格
        self.card = CardWidget()
        card_layout = QHBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)

        # 表格区域
        self.table = TableWidget(self.card)
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["标题"])

        # 设置表格大小策略，使其能够自适应卡片区域的大小变化
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.horizontalHeader().setStretchLastSection(True)

        # 简化示例数据
        manga_data = [
            ["等待打开"],
        ]

        self.table.setRowCount(len(manga_data))
        for i, (title,) in enumerate(manga_data):
            self.table.setItem(i, 0, QTableWidgetItem(title))

        # 设置表格属性
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.verticalHeader().hide()
        self.table.resizeColumnsToContents()

        # 连接表格选择信号
        self.table.itemSelectionChanged.connect(self.on_manga_selected)

        card_layout.addWidget(self.table)
        self.layout.addWidget(self.card)

        # 新增：初始化时如果有数据就立即显示
        if hasattr(self.manga_manager, "manga_list") and self.manga_manager.manga_list:
            self.update_table(self.manga_manager.manga_list)

    def open_folder_dialog(self):
        """打开文件夹对话框并加载漫画"""

        dir_path = QFileDialog.getExistingDirectory(
            self, "选择漫画目录", "", QFileDialog.ShowDirsOnly  # 默认路径
        )
        if dir_path:
            self.manga_manager.set_manga_dir(dir_path)  # 调用管理器更新目录

    def update_table(self, manga_list):
        """更新表格显示"""
        self.table.setRowCount(0)
        if manga_list:
            # 按标题排序
            sorted_list = sorted(
                manga_list,
                key=lambda m: next(
                    (
                        tag.split(":", 1)[1].lower()
                        for tag in m.tags
                        if tag.startswith("标题:")
                    ),
                    "",
                ),
            )
            self.filtered_manga_list = sorted_list  # 更新过滤后的列表
            self.table.setRowCount(len(sorted_list))
            for i, manga in enumerate(sorted_list):
                title = next(
                    (
                        tag.split(":", 1)[1]
                        for tag in manga.tags
                        if tag.startswith("标题:")
                    ),
                    "",
                )
                self.table.setItem(i, 0, QTableWidgetItem(title))

    def on_manga_selected(self):
        """处理漫画选择变更事件"""
        selected_items = self.table.selectedItems()
        if selected_items:
            selected_row = selected_items[0].row()
            # 从表格中获取当前显示的漫画标题
            selected_title = self.table.item(selected_row, 0).text()
            # 在过滤后的列表中查找匹配的漫画
            for manga in self.filtered_manga_list:
                manga_title = next(
                    (
                        tag.split(":", 1)[1]
                        for tag in manga.tags
                        if tag.startswith("标题:") and ":" in tag
                    )
                )
                if manga_title == selected_title:
                    self.manga_manager.set_current_manga(manga)
                    break

    def on_search_text_changed(self, text):
        """处理搜索文本变化事件"""
        if not text:  # 如果搜索框为空，显示所有漫画
            self.update_table(self.manga_manager.manga_list)
            return

        # 在所有标签中搜索匹配项
        search_text = text.lower()
        filtered_list = [
            manga
            for manga in self.filtered_manga_list
            if any(search_text in tag.lower() for tag in manga.tags)
        ]

        # 更新表格显示
        self.table.setRowCount(len(filtered_list))
        for i, manga in enumerate(filtered_list):
            title = next(
                (tag.split(":", 1)[1] for tag in manga.tags if tag.startswith("标题:")),
                "",
            )
            self.table.setItem(i, 0, QTableWidgetItem(title))
