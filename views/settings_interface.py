# PyQt5相关导入
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout

# qfluentwidgets组件导入
from qfluentwidgets import (
    SpinBox, SwitchButton, ComboBox, ScrollArea, GroupHeaderCardWidget, CardWidget,
    SettingCardGroup, SwitchSettingCard, ComboBoxSettingCard, CustomColorSettingCard,
    OptionsSettingCard, PushSettingCard, FolderListSettingCard, HyperlinkCard,
    PrimaryPushSettingCard, ExpandLayout, RangeSettingCard, FluentIcon as FIF
)
from qfluentwidgets import setTheme, setThemeColor, isDarkTheme, Theme

# 项目核心模块导入
from core.manga_manager import MangaManager
from core.config import config, ReadingOrder, DisplayMode

class ThemeSettinsCard(GroupHeaderCardWidget):

    def __init__(self, manga_manager, parent=None):
        super().__init__(parent=parent)
        self.manga_manager = manga_manager

        self.setTitle("外观与材质设置")
        self.setBorderRadius(8)

        # --- 应用主题设置项 (使用 config.themeMode) ---
        self.theme_combo = ComboBox(self)
        self.theme_combo.addItems(["浅色", "深色", "跟随系统"])

        # 从 config.themeMode 加载初始值 (.value 是 Theme 枚举成员)
        current_theme_enum = config.themeMode.value
        # 将 Theme 枚举成员映射到 ComboBox 的文本
        if current_theme_enum == Theme.LIGHT:
            self.theme_combo.setCurrentText("浅色")
        elif current_theme_enum == Theme.DARK:
            self.theme_combo.setCurrentText("深色")
        else: # 对应 Theme.AUTO
            self.theme_combo.setCurrentText("跟随系统")

        # 连接信号到槽函数
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        self.addGroup(FIF.BRUSH, "应用主题", "选择应用程序的主题样式。", self.theme_combo)
        
        # TODO: 添加其他可能的个性化或材质设置项

    # --- 槽函数：更新 config 并保存 ---

    def _on_theme_changed(self, index):
        # 获取选中的文本
        selected_text = self.theme_combo.currentText()
        # 将文本映射回 Theme 枚举成员
        if selected_text == "浅色":
            new_theme_enum = Theme.LIGHT
        elif selected_text == "深色":
            new_theme_enum = Theme.DARK
        else: # "跟随系统"
            new_theme_enum = Theme.AUTO
        setTheme(new_theme_enum)
        config.save()

    def _on_radius_changed(self, index):
        config.radius.value = index # 直接保存索引作为整数值
        self.manga_manager.save_config()
        # TODO: 如果需要，立即应用圆角

    def _on_theme_color_changed(self, color): # 假设 color 参数是 QColor 对象
        # 将颜色转换为 Hex ARGB 字符串保存
        config.theme_color.value = color.name(QColor.HexArgb)
        self.manga_manager.save_config()
        # TODO: 如果需要，立即应用主题色 (可能需要调用库的 setCustomColor 函数)
        # from qfluentwidgets import setCustomColor
        # setCustomColor(config.theme_color.value)


class MangaSettinsCard(GroupHeaderCardWidget):

    def __init__(self, manga_manager, parent=None): # 接收 manga_manager 参数
        super().__init__(parent=parent)
        self.manga_manager = manga_manager # 存储 manga_manager 实例

        self.setTitle("漫画功能设置")
        self.setBorderRadius(8)

        # 阅读方向设置项
        self.reading_order_combo = ComboBox(self)
        self.reading_order_combo.addItems(["从右到左", "从左到右"])
        self.reading_order_combo.setFixedWidth(200)
        # 从 config 加载初始值并设置控件状态
        self.reading_order_combo.setCurrentText(config.reading_order.value)
        # 连接信号到槽函数
        self.reading_order_combo.currentIndexChanged.connect(self._on_reading_order_changed)

        self.addGroup(
            icon=FIF.VIEW,
            title="阅读方向",
            content="设置漫画页面的阅读方向，例如日漫通常为从右到左。",
            widget=self.reading_order_combo
        )

        # 显示模式设置项
        self.display_mode_combo = ComboBox(self)
        self.display_mode_combo.addItems(["单页显示", "双页显示", "自适应"])
        self.display_mode_combo.setFixedWidth(200)
        # 从 config 加载初始值并设置控件状态
        self.display_mode_combo.setCurrentText(config.display_mode.value)
        # 连接信号到槽函数
        self.display_mode_combo.currentIndexChanged.connect(self._on_display_mode_changed)

        self.addGroup(
            icon=FIF.LAYOUT,
            title="显示模式",
            content="选择是单页、双页显示漫画内容，或自适应屏幕。",
            widget=self.display_mode_combo
        )

        # 翻页间隔设置项
        self.page_interval_spinbox = SpinBox(self)
        self.page_interval_spinbox.setRange(1, 300)
        # 从 config 加载初始值并设置控件状态
        self.page_interval_spinbox.setValue(config.page_interval.value)
        # 连接信号到槽函数
        self.page_interval_spinbox.valueChanged.connect(self._on_page_interval_changed)

        self.addGroup(
            icon=FIF.SCROLL,
            title="翻页间隔 (秒)",
            content="设置自动翻页的时间间隔，单位为秒 (1-300)。",
            widget=self.page_interval_spinbox
        )

        # 翻译标题和作品开关
        self.translate_switch = SwitchButton(self)
        # 从 config 加载初始值并设置控件状态
        self.translate_switch.setChecked(config.translate_title.value)
        # 连接信号到槽函数
        self.translate_switch.checkedChanged.connect(self._on_translate_changed)
        self.addGroup(
            icon=FIF.LANGUAGE,
            title="翻译标题和作品",
            content="自动将漫画的标题和作品信息翻译成当前语言。",
            widget=self.translate_switch
        )

        # 简体化开关
        self.simplify_switch = SwitchButton(self)
        # 从 config 加载初始值并设置控件状态
        self.simplify_switch.setChecked(config.simplify_chinese.value)
        # 连接信号到槽函数
        self.simplify_switch.checkedChanged.connect(self._on_simplify_changed)
        self.addGroup(
            icon=FIF.FONT,
            title="简体化",
            content="将繁体中文内容转换为简体中文。",
            widget=self.simplify_switch
        )

        # 合并相似标签开关
        self.merge_tags_switch = SwitchButton(self)
        # 从 config 加载初始值并设置控件状态
        self.merge_tags_switch.setChecked(config.merge_tags.value)
        # 连接信号到槽函数
        self.merge_tags_switch.checkedChanged.connect(self._on_merge_tags_changed)
        self.addGroup(
            icon=FIF.TAG,
            title="合并相似标签",
            content="自动合并具有相似名称的标签，以减少冗余。",
            widget=self.merge_tags_switch
        )

    # --- 槽函数：更新 config 并保存 ---

    def _on_reading_order_changed(self, index):
        config.reading_order.value = self.reading_order_combo.currentText()
        self.manga_manager.save_config()
        # TODO: 如果需要，通知 MangaManager 应用新的阅读方向

    def _on_display_mode_changed(self, index):
        config.display_mode.value = self.display_mode_combo.currentText()
        self.manga_manager.save_config()
        # TODO: 如果需要，通知 MangaManager 应用新的显示模式

    def _on_page_interval_changed(self, value):
        config.page_interval.value = value
        self.manga_manager.save_config()
        # TODO: 如果需要，通知相关的自动翻页计时器更新间隔

    def _on_translate_changed(self, checked):
        config.translate_title.value = checked
        self.manga_manager.save_config()
        # TODO: 如果此设置影响已加载的数据，可能需要触发重新处理或重新加载

    def _on_simplify_changed(self, checked):
        config.simplify_chinese.value = checked
        self.manga_manager.save_config()
        # TODO: 如果此设置影响已加载的数据，可能需要触发重新处理或重新加载

    def _on_merge_tags_changed(self, checked):
        config.merge_tags.value = checked
        self.manga_manager.save_config()
        # TODO: 如果此设置影响已加载的数据，可能需要触发重新处理或重新加载




class SettingsInterface(ScrollArea):
    """设置界面"""
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.manga_manager = MangaManager(self) # 实例化 MangaManager
        self.setup_ui()

    def setup_ui(self):
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.vBoxLayout = QVBoxLayout(self.view)
        self.vBoxLayout.setSpacing(6)
        self.vBoxLayout.setContentsMargins(20, 32, 20, 20)
        self.vBoxLayout.setAlignment(Qt.AlignTop)

        # 实例化 MangaSettinsCard 并传递 manga_manager 实例
        self.manga_settings_card = MangaSettinsCard(self.manga_manager, self.view)
        self.vBoxLayout.addWidget(self.manga_settings_card)

        # 实例化 ThemeSettinsCard 并传递 manga_manager 实例
        self.theme_settings_card = ThemeSettinsCard(self.manga_manager, self.view)
        self.vBoxLayout.addWidget(self.theme_settings_card)

        self.enableTransparentBackground()

        
