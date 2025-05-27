# PyQt5相关导入
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout

# qfluentwidgets组件导入
from qfluentwidgets import (
    BodyLabel,
    SpinBox,
    SwitchButton,
    ComboBox,
    ScrollArea,
    GroupHeaderCardWidget,
    CardWidget,
    SettingCardGroup,
    SwitchSettingCard,
    ComboBoxSettingCard,
    CustomColorSettingCard,
    OptionsSettingCard,
    PushSettingCard,
    FolderListSettingCard,
    HyperlinkCard,
    PrimaryPushSettingCard,
    ExpandLayout,
    RangeSettingCard,
    LineEdit,
    PushButton,
    FluentIcon as FIF,
    InfoBar,
    InfoBarPosition,
)
from qfluentwidgets import setTheme, setThemeColor, isDarkTheme, Theme

# 项目核心模块导入
from core.manga_manager import MangaManager
from core.config import config, ReadingOrder, DisplayMode




class TranslationSettingsCard(GroupHeaderCardWidget):
    """翻译相关设置卡片"""

    def __init__(self, manga_manager, parent=None):
        super().__init__(parent=parent)
        self.manga_manager = manga_manager

        self.setTitle("翻译设置")
        self.setBorderRadius(8)

        # 翻译接口类型设置
        self.translator_combo = ComboBox(self)
        self.translator_combo.addItems(["Google", "智谱", "DeepL", "百度", "MyMemory"])
        # 从配置中加载初始值
        self.translator_combo.setCurrentText(config.translator_type.value)
        # 连接信号到槽函数
        self.translator_combo.currentIndexChanged.connect(self._on_translator_changed)
        self.addGroup(
            FIF.LANGUAGE, 
            "翻译接口", 
            "选择使用的翻译服务提供商。", 
            self.translator_combo
        )

        # 创建API密钥输入区域
        self.api_key_widget = QWidget(self)
        self.api_key_layout = QVBoxLayout(self.api_key_widget)
        self.api_key_layout.setContentsMargins(0, 0, 0, 0)
        self.api_key_layout.setSpacing(8)
        
        # 智谱AI设置
        self.zhipu_widget = QWidget(self.api_key_widget)
        self.zhipu_layout = QGridLayout(self.zhipu_widget)
        self.zhipu_layout.setContentsMargins(0, 0, 0, 0)
        self.zhipu_layout.setSpacing(8)
        
        self.zhipu_api_key_edit = LineEdit(self.zhipu_widget)
        self.zhipu_api_key_edit.setPlaceholderText("请输入智谱AI API密钥")
        self.zhipu_api_key_edit.setEchoMode(LineEdit.Password)
        self.zhipu_api_key_edit.setText(config.zhipu_api_key.value)
        self.zhipu_api_key_edit.textChanged.connect(self._on_zhipu_api_key_changed)
        
        self.zhipu_model_combo = ComboBox(self.zhipu_widget)
        self.zhipu_model_combo.addItems(["glm-4-plus", "glm-4-air-250414", "glm-4-airx", "glm-4-long", "glm-4-flashx", "glm-4-flash-250414"])
        self.zhipu_model_combo.setCurrentText("glm-4-flash-250414" if config.zhipu_model.value == "glm-4-flash" else config.zhipu_model.value)
        self.zhipu_model_combo.currentIndexChanged.connect(self._on_zhipu_model_changed)
        
        self.zhipu_layout.addWidget(BodyLabel("API密钥:"), 0, 0)
        self.zhipu_layout.addWidget(self.zhipu_api_key_edit, 0, 1)
        self.zhipu_layout.addWidget(BodyLabel("模型:"), 1, 0)
        self.zhipu_layout.addWidget(self.zhipu_model_combo, 1, 1)
        
        # Google设置
        self.google_widget = QWidget(self.api_key_widget)
        self.google_layout = QGridLayout(self.google_widget)
        self.google_layout.setContentsMargins(0, 0, 0, 0)
        
        self.google_api_key_edit = LineEdit(self.google_widget)
        self.google_api_key_edit.setPlaceholderText("请输入Google API密钥 (可选)")
        self.google_api_key_edit.setEchoMode(LineEdit.Password)
        self.google_api_key_edit.setText(config.google_api_key.value)
        self.google_api_key_edit.textChanged.connect(self._on_google_api_key_changed)
        
        self.google_layout.addWidget(BodyLabel("API密钥 (可选):"), 0, 0)
        self.google_layout.addWidget(self.google_api_key_edit, 0, 1)
        
        # DeepL设置
        self.deepl_widget = QWidget(self.api_key_widget)
        self.deepl_layout = QGridLayout(self.deepl_widget)
        self.deepl_layout.setContentsMargins(0, 0, 0, 0)
        
        self.deepl_api_key_edit = LineEdit(self.deepl_widget)
        self.deepl_api_key_edit.setPlaceholderText("请输入DeepL API密钥")
        self.deepl_api_key_edit.setEchoMode(LineEdit.Password)
        self.deepl_api_key_edit.setText(config.deepl_api_key.value)
        self.deepl_api_key_edit.textChanged.connect(self._on_deepl_api_key_changed)
        
        self.deepl_layout.addWidget(BodyLabel("API密钥:"), 0, 0)
        self.deepl_layout.addWidget(self.deepl_api_key_edit, 0, 1)
        
        # 百度设置
        self.baidu_widget = QWidget(self.api_key_widget)
        self.baidu_layout = QGridLayout(self.baidu_widget)
        self.baidu_layout.setContentsMargins(0, 0, 0, 0)
        self.baidu_layout.setSpacing(8)
        
        self.baidu_app_id_edit = LineEdit(self.baidu_widget)
        self.baidu_app_id_edit.setPlaceholderText("请输入百度翻译APP ID")
        self.baidu_app_id_edit.setText(config.baidu_app_id.value)
        self.baidu_app_id_edit.textChanged.connect(self._on_baidu_app_id_changed)
        
        self.baidu_app_key_edit = LineEdit(self.baidu_widget)
        self.baidu_app_key_edit.setPlaceholderText("请输入百度翻译APP Key")
        self.baidu_app_key_edit.setEchoMode(LineEdit.Password)
        self.baidu_app_key_edit.setText(config.baidu_app_key.value)
        self.baidu_app_key_edit.textChanged.connect(self._on_baidu_app_key_changed)
        
        self.baidu_layout.addWidget(BodyLabel("APP ID:"), 0, 0)
        self.baidu_layout.addWidget(self.baidu_app_id_edit, 0, 1)
        self.baidu_layout.addWidget(BodyLabel("APP Key:"), 1, 0)
        self.baidu_layout.addWidget(self.baidu_app_key_edit, 1, 1)
        
        # MyMemory设置
        self.mymemory_widget = QWidget(self.api_key_widget)
        self.mymemory_layout = QGridLayout(self.mymemory_widget)
        self.mymemory_layout.setContentsMargins(0, 0, 0, 0)
        
        self.mymemory_email_edit = LineEdit(self.mymemory_widget)
        self.mymemory_email_edit.setPlaceholderText("请输入邮箱 (可选，提供可增加免费额度)")
        self.mymemory_email_edit.setText(config.mymemory_email.value)
        self.mymemory_email_edit.textChanged.connect(self._on_mymemory_email_changed)
        
        self.mymemory_layout.addWidget(BodyLabel("邮箱 (可选):"), 0, 0)
        self.mymemory_layout.addWidget(self.mymemory_email_edit, 0, 1)
        
        # 将所有翻译器设置添加到布局中
        self.api_key_layout.addWidget(self.zhipu_widget)
        self.api_key_layout.addWidget(self.google_widget)
        self.api_key_layout.addWidget(self.deepl_widget)
        self.api_key_layout.addWidget(self.baidu_widget)
        self.api_key_layout.addWidget(self.mymemory_widget)
        
        # 根据当前选择的翻译器显示对应的设置
        self._update_api_settings_visibility()
        
        self.addGroup(
            FIF.VPN, 
            "API设置", 
            "配置所选翻译服务的API参数。", 
            self.api_key_widget
        )

        # 清空翻译缓存按钮
        self.clear_cache_btn = PushButton("清空翻译缓存", self)
        self.clear_cache_btn.clicked.connect(self._on_clear_cache_clicked)
        self.addGroup(
            FIF.DELETE, 
            "缓存管理", 
            "清空已缓存的翻译结果。", 
            self.clear_cache_btn
        )
        
    def _on_translator_changed(self, index):
        """翻译接口类型变更处理函数"""
        # 更新配置
        config.translator_type.value = self.translator_combo.currentText()
        self.manga_manager.save_config()
        
        # 更新API设置显示
        self._update_api_settings_visibility()
    
    def _update_api_settings_visibility(self):
        """根据当前选择的翻译接口更新API设置显示"""
        current_translator = config.translator_type.value
        
        # 隐藏所有设置
        self.zhipu_widget.setVisible(False)
        self.google_widget.setVisible(False)
        self.deepl_widget.setVisible(False)
        self.baidu_widget.setVisible(False)
        self.mymemory_widget.setVisible(False)
        
        # 显示当前选择的翻译器设置
        if current_translator == "智谱":
            self.zhipu_widget.setVisible(True)
        elif current_translator == "Google":
            self.google_widget.setVisible(True)
        elif current_translator == "DeepL":
            self.deepl_widget.setVisible(True)
        elif current_translator == "百度":
            self.baidu_widget.setVisible(True)
        elif current_translator == "MyMemory":
            self.mymemory_widget.setVisible(True)
    
    def _on_zhipu_api_key_changed(self, text):
        """智谱API密钥变更处理函数"""
        config.zhipu_api_key.value = text
        self.manga_manager.save_config()
    
    def _on_zhipu_model_changed(self, index):
        """智谱模型变更处理函数"""
        config.zhipu_model.value = self.zhipu_model_combo.currentText()
        self.manga_manager.save_config()
    
    def _on_google_api_key_changed(self, text):
        """Google API密钥变更处理函数"""
        config.google_api_key.value = text
        self.manga_manager.save_config()
    
    def _on_deepl_api_key_changed(self, text):
        """DeepL API密钥变更处理函数"""
        config.deepl_api_key.value = text
        self.manga_manager.save_config()
    
    def _on_baidu_app_id_changed(self, text):
        """百度APP ID变更处理函数"""
        config.baidu_app_id.value = text
        self.manga_manager.save_config()
    
    def _on_baidu_app_key_changed(self, text):
        """百度APP Key变更处理函数"""
        config.baidu_app_key.value = text
        self.manga_manager.save_config()
    
    def _on_mymemory_email_changed(self, text):
        """MyMemory邮箱变更处理函数"""
        config.mymemory_email.value = text
        self.manga_manager.save_config()
    
    def _on_clear_cache_clicked(self):
        """清空翻译缓存按钮点击事件"""
        # 这里实现清空翻译缓存的逻辑
        # 可以调用manga_manager中的方法来清空缓存
        if hasattr(self.manga_manager, "clear_translation_cache"):
            self.manga_manager.clear_translation_cache()
            # 可以添加一个提示，表示缓存已清空
            InfoBar.success(
                title="成功",
                content="翻译缓存已清空",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
class ThemeSettinsCard(GroupHeaderCardWidget):

    def __init__(self, manga_manager, parent=None):
        super().__init__(parent=parent)
        self.manga_manager = manga_manager

        self.setTitle("外观与材质设置")
        self.setBorderRadius(8)

        # --- 应用主题设置项 (使用 config.themeMode) ---
        self.theme_combo = ComboBox(self)
        self.theme_combo.addItems(["浅色", "深色", "跟随系统"])

        # 日志等级设置
        self.log_level_combo = ComboBox(self)
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        # 从配置中加载初始值
        self.log_level_combo.setCurrentText(config.log_level.value)
        # 连接信号到槽函数
        self.log_level_combo.currentIndexChanged.connect(self._on_log_level_changed)
        self.addGroup(
            FIF.INFO, 
            "日志等级", 
            "设置应用程序的日志输出等级。", 
            self.log_level_combo
        )

        # 从 config.themeMode 加载初始值 (.value 是 Theme 枚举成员)
        current_theme_enum = config.themeMode.value
        # 将 Theme 枚举成员映射到 ComboBox 的文本
        if current_theme_enum == Theme.LIGHT:
            self.theme_combo.setCurrentText("浅色")
        elif current_theme_enum == Theme.DARK:
            self.theme_combo.setCurrentText("深色")
        else:  # 对应 Theme.AUTO
            self.theme_combo.setCurrentText("跟随系统")

        # 连接信号到槽函数
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        self.addGroup(
            FIF.BRUSH, "应用主题", "选择应用程序的主题样式。", self.theme_combo
        )

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
        else:  # "跟随系统"
            new_theme_enum = Theme.AUTO
        setTheme(new_theme_enum)
        config.save()
        
    def _on_log_level_changed(self, index):
        # 获取选中的日志等级
        selected_level = self.log_level_combo.currentText()
        # 更新配置
        config.log_level.value = selected_level
        self.manga_manager.save_config()
        # 应用新的日志等级
        from utils.manga_logger import MangaLogger
        MangaLogger.get_instance().set_level(selected_level)

    def _on_radius_changed(self, index):
        config.radius.value = index  # 直接保存索引作为整数值
        self.manga_manager.save_config()
        # TODO: 如果需要，立即应用圆角

    def _on_theme_color_changed(self, color):  # 假设 color 参数是 QColor 对象
        # 将颜色转换为 Hex ARGB 字符串保存
        config.theme_color.value = color.name(QColor.HexArgb)
        self.manga_manager.save_config()
        # TODO: 如果需要，立即应用主题色 (可能需要调用库的 setCustomColor 函数)
        # from qfluentwidgets import setCustomColor
        # setCustomColor(config.theme_color.value)


class MangaSettinsCard(GroupHeaderCardWidget):

    def __init__(self, manga_manager, parent=None):  # 接收 manga_manager 参数
        super().__init__(parent=parent)
        self.manga_manager = manga_manager  # 存储 manga_manager 实例

        self.setTitle("漫画功能设置")
        self.setBorderRadius(8)

        # 阅读方向设置项
        self.reading_order_combo = ComboBox(self)
        self.reading_order_combo.addItems(["从右到左", "从左到右"])
        self.reading_order_combo.setFixedWidth(200)
        # 从 config 加载初始值并设置控件状态
        self.reading_order_combo.setCurrentText(config.reading_order.value)
        # 连接信号到槽函数
        self.reading_order_combo.currentIndexChanged.connect(
            self._on_reading_order_changed
        )

        self.addGroup(
            icon=FIF.VIEW,
            title="阅读方向",
            content="设置漫画页面的阅读方向，例如日漫通常为从右到左。",
            widget=self.reading_order_combo,
        )

        # 显示模式设置项
        self.display_mode_combo = ComboBox(self)
        self.display_mode_combo.addItems(["单页显示", "双页显示", "自适应"])
        self.display_mode_combo.setFixedWidth(200)
        # 从 config 加载初始值并设置控件状态
        self.display_mode_combo.setCurrentText(config.display_mode.value)
        # 连接信号到槽函数
        self.display_mode_combo.currentIndexChanged.connect(
            self._on_display_mode_changed
        )

        self.addGroup(
            icon=FIF.LAYOUT,
            title="显示模式",
            content="选择是单页、双页显示漫画内容，或自适应屏幕。",
            widget=self.display_mode_combo,
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
            widget=self.page_interval_spinbox,
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
            widget=self.translate_switch,
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
            widget=self.simplify_switch,
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
            widget=self.merge_tags_switch,
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

    def __init__(self, parent=None, manga_manager=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.manga_manager = manga_manager or MangaManager(self)  # 使用传入的manager或新建实例
        self.setup_ui()

    def setup_ui(self):
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.vBoxLayout = QVBoxLayout(self.view)
        self.vBoxLayout.setSpacing(32)
        self.vBoxLayout.setContentsMargins(20, 32, 20, 20)
        self.vBoxLayout.setAlignment(Qt.AlignTop)

        # 实例化 ThemeSettinsCard 并传递 manga_manager 实例
        self.theme_settings_card = ThemeSettinsCard(self.manga_manager, self.view)
        self.vBoxLayout.addWidget(self.theme_settings_card)

        # 实例化 MangaSettinsCard 并传递 manga_manager 实例
        self.manga_settings_card = MangaSettinsCard(self.manga_manager, self.view)
        self.vBoxLayout.addWidget(self.manga_settings_card)

        # 实例化 TranslationSettingsCard 并传递 manga_manager 实例
        self.translation_settings_card = TranslationSettingsCard(self.manga_manager, self.view)
        self.vBoxLayout.addWidget(self.translation_settings_card)

        self.enableTransparentBackground()
