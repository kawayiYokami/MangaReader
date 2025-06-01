# Qt相关导入
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QMessageBox

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
import os 
from fontTools.ttLib import TTFont # 用于读取字体名称

class TranslationSettingsCard(GroupHeaderCardWidget):
    """翻译相关设置卡片"""

    def __init__(self, manga_manager, parent=None):
        super().__init__(parent=parent)
        self.manga_manager = manga_manager
        self.available_fonts = {} # 用于存储字体文件名到字体信息的映射

        self.setTitle("翻译与文本设置") # 更新标题以包含字体设置
        self.setBorderRadius(8)

        # 翻译接口类型设置
        self.translator_combo = ComboBox(self)
        self.translator_combo.addItems(["Google", "智谱"]) 
        current_translator_type = config.translator_type.value
        if current_translator_type not in ["Google", "智谱"]:
            config.translator_type.value = "Google" 
            self.manga_manager.save_config()
        self.translator_combo.setCurrentText(config.translator_type.value)
        self.translator_combo.currentIndexChanged.connect(self._on_translator_changed)
        self.addGroup(
            FIF.LANGUAGE, 
            "翻译接口", 
            "选择使用的翻译服务提供商。", 
            self.translator_combo
        )

        # API密钥输入区域
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
        self.zhipu_model_combo.addItems([
            "glm-4-flash-250414", "glm-4-flash", "glm-4", "glm-3-turbo"
        ])
        self.zhipu_model_combo.setCurrentText(config.zhipu_model.value)
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
        
        self.api_key_layout.addWidget(self.zhipu_widget)
        self.api_key_layout.addWidget(self.google_widget)
        self._update_api_settings_visibility()
        self.addGroup(
            FIF.VPN, "API设置", "配置所选翻译服务的API参数。", self.api_key_widget
        )

        # 字体选择设置项
        self.font_combo = ComboBox(self)
        self.font_combo.setFixedWidth(300) # 调整宽度
        self._load_available_fonts() # 加载字体
        self.font_combo.currentIndexChanged.connect(self._on_font_name_changed)
        self.addGroup(
            FIF.FONT, 
            "文本替换字体",
            "选择用于翻译后文本替换的字体。",
            self.font_combo,
        )

        # 清空翻译缓存按钮
        self.clear_translation_cache_btn = PushButton("清空翻译缓存", self) # 重命名以区分
        self.clear_translation_cache_btn.clicked.connect(self._on_clear_translation_cache_clicked)
        self.addGroup(
            FIF.DELETE, "翻译缓存管理", "清空已缓存的翻译结果。", self.clear_translation_cache_btn
        )
        
    def _load_available_fonts(self):
        """加载可用字体到下拉框，并显示其中文名称"""
        self.font_combo.clear()
        self.available_fonts.clear()
        
        font_dir = "font" 
        if not (os.path.exists(font_dir) and os.path.isdir(font_dir)):
            print(f"警告: 找不到字体目录：{font_dir}")
            self.font_combo.addItem("默认字体 (未找到目录)", None)
            self.font_combo.setEnabled(False)
            return

        font_files = [(f, os.path.join(font_dir, f)) 
                     for f in os.listdir(font_dir) 
                     if f.lower().endswith(('.ttf', '.otf'))]
        
        if not font_files:
            print("警告: 字体目录中没有找到任何字体文件")
            self.font_combo.addItem("默认字体 (无可用)", None)
            self.font_combo.setEnabled(False)
            return

        for file_name, file_path in font_files:
            try:
                tt = TTFont(file_path, fontNumber=0) 
                name_records = tt['name'].names
                font_display_name = None
                
                for record in name_records:
                    if record.nameID in (4, 1) and record.platformID == 3 and record.platEncID == 1 and record.langID == 0x804: 
                        try:
                            font_display_name = record.string.decode('utf-16be')
                            break 
                        except Exception: pass
                
                if not font_display_name: 
                    for record in name_records:
                        if record.nameID in (4, 1) and record.platformID == 3 and record.platEncID == 1 and record.langID == 0x409: 
                            try:
                                font_display_name = record.string.decode('utf-16be')
                                break
                            except Exception: pass
                
                if not font_display_name: 
                     for record in name_records:
                        if record.nameID == 6:
                            try:
                                font_display_name = record.string.decode('utf-16be' if record.platformID == 3 else 'latin1') 
                                break
                            except: pass

                if not font_display_name: 
                    font_display_name = os.path.splitext(file_name)[0]
                
                display_text = f"{font_display_name} ({file_name})"
                self.font_combo.addItem(display_text, file_name) 
                self.available_fonts[file_name] = {'path': file_path, 'name': font_display_name}
                tt.close()
            except Exception as e:
                print(f"无法加载字体 {file_name}: {e}")
                self.font_combo.addItem(f"{file_name} (加载失败)", file_name)

        current_font_file_name = config.font_name.value
        index = self.font_combo.findData(current_font_file_name)
        if index >= 0:
            self.font_combo.setCurrentIndex(index)
        elif self.font_combo.count() > 0:
            self.font_combo.setCurrentIndex(0) 
            first_font_data = self.font_combo.itemData(0)
            if first_font_data:
                 config.font_name.value = first_font_data
                 self.manga_manager.save_config()

    def _on_translator_changed(self, index):
        new_translator_type = self.translator_combo.currentText()
        if config.translator_type.value != new_translator_type:
            config.translator_type.value = new_translator_type
            self.manga_manager.save_config()
        self._update_api_settings_visibility()
    
    def _update_api_settings_visibility(self):
        current_translator = config.translator_type.value
        self.zhipu_widget.setVisible(current_translator == "智谱")
        self.google_widget.setVisible(current_translator == "Google")
    
    def _on_zhipu_api_key_changed(self, text):
        config.zhipu_api_key.value = text
        self.manga_manager.save_config()
    
    def _on_zhipu_model_changed(self, index):
        config.zhipu_model.value = self.zhipu_model_combo.currentText()
        self.manga_manager.save_config()
    
    def _on_google_api_key_changed(self, text):
        config.google_api_key.value = text
        self.manga_manager.save_config()

    def _on_font_name_changed(self, index):
        selected_font_file_name = self.font_combo.itemData(index) 
        if selected_font_file_name and config.font_name.value != selected_font_file_name:
            config.font_name.value = selected_font_file_name
            self.manga_manager.save_config()

    def _on_clear_translation_cache_clicked(self): # 重命名槽函数
        if hasattr(self.manga_manager, "clear_translation_cache"):
            self.manga_manager.clear_translation_cache()
            InfoBar.success(
                title="成功", content="翻译缓存已清空", orient=Qt.Horizontal,
                isClosable=True, position=InfoBarPosition.TOP, duration=2000, parent=self
            )

class ThemeSettinsCard(GroupHeaderCardWidget):
    def __init__(self, manga_manager, parent=None):
        super().__init__(parent=parent)
        self.manga_manager = manga_manager
        self.setTitle("外观与材质设置")
        self.setBorderRadius(8)
        self.theme_combo = ComboBox(self)
        self.theme_combo.addItems(["浅色", "深色", "跟随系统"])
        self.log_level_combo = ComboBox(self)
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level_combo.setCurrentText(config.log_level.value)
        self.log_level_combo.currentIndexChanged.connect(self._on_log_level_changed)
        self.addGroup(
            FIF.INFO, "日志等级", "设置应用程序的日志输出等级。", self.log_level_combo
        )
        current_theme_enum = config.themeMode.value
        if current_theme_enum == Theme.LIGHT: self.theme_combo.setCurrentText("浅色")
        elif current_theme_enum == Theme.DARK: self.theme_combo.setCurrentText("深色")
        else: self.theme_combo.setCurrentText("跟随系统")
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        self.addGroup(
            FIF.BRUSH, "应用主题", "选择应用程序的主题样式。", self.theme_combo
        )

    def _on_theme_changed(self, index):
        selected_text = self.theme_combo.currentText()
        if selected_text == "浅色": new_theme_enum = Theme.LIGHT
        elif selected_text == "深色": new_theme_enum = Theme.DARK
        else: new_theme_enum = Theme.AUTO
        setTheme(new_theme_enum)
        config.themeMode.value = new_theme_enum
        config.save()
        
    def _on_log_level_changed(self, index):
        selected_level = self.log_level_combo.currentText()
        config.log_level.value = selected_level
        self.manga_manager.save_config()
        from utils.manga_logger import MangaLogger
        MangaLogger.get_instance().set_level(selected_level)

class MangaSettinsCard(GroupHeaderCardWidget):
    def __init__(self, manga_manager, parent=None): 
        super().__init__(parent=parent)
        self.manga_manager = manga_manager 
        self.setTitle("漫画功能设置")
        self.setBorderRadius(8)

        self.reading_order_combo = ComboBox(self)
        self.reading_order_combo.addItems(["从右到左", "从左到右"])
        self.reading_order_combo.setFixedWidth(200)
        self.reading_order_combo.setCurrentText(config.reading_order.value)
        self.reading_order_combo.currentIndexChanged.connect(self._on_reading_order_changed)
        self.addGroup(
            icon=FIF.VIEW, title="阅读方向", content="设置漫画页面的阅读方向。", widget=self.reading_order_combo
        )

        self.display_mode_combo = ComboBox(self)
        self.display_mode_combo.addItems(["单页显示", "双页显示", "自适应"])
        self.display_mode_combo.setFixedWidth(200)
        self.display_mode_combo.setCurrentText(config.display_mode.value)
        self.display_mode_combo.currentIndexChanged.connect(self._on_display_mode_changed)
        self.addGroup(
            icon=FIF.LAYOUT, title="显示模式", content="选择漫画内容的显示方式。", widget=self.display_mode_combo
        )

        self.page_interval_spinbox = SpinBox(self)
        self.page_interval_spinbox.setRange(1, 300)
        self.page_interval_spinbox.setValue(config.page_interval.value)
        self.page_interval_spinbox.valueChanged.connect(self._on_page_interval_changed)
        self.addGroup(
            icon=FIF.SCROLL, title="翻页间隔 (秒)", content="自动翻页的时间间隔 (1-300s)。", widget=self.page_interval_spinbox
        )

        self.translate_switch = SwitchButton(self)
        self.translate_switch.setChecked(config.translate_title.value)
        self.translate_switch.checkedChanged.connect(self._on_translate_changed)
        self.addGroup(
            icon=FIF.LANGUAGE, title="漫画阅读器，自动翻译总开关", content="特别说明，仍需要在阅读的时候单独打开这个漫画的翻译开关才会自动翻译。", widget=self.translate_switch
        )

        self.simplify_switch = SwitchButton(self)
        self.simplify_switch.setChecked(config.simplify_chinese.value)
        self.simplify_switch.checkedChanged.connect(self._on_simplify_changed)
        self.addGroup(
            icon=FIF.FONT, title="简体化", content="将繁体中文内容转换为简体中文。", widget=self.simplify_switch
        )

        self.merge_tags_switch = SwitchButton(self)
        self.merge_tags_switch.setChecked(config.merge_tags.value)
        self.merge_tags_switch.checkedChanged.connect(self._on_merge_tags_changed)
        self.addGroup(
            icon=FIF.TAG, title="合并相似标签", content="自动合并相似名称的标签。", widget=self.merge_tags_switch
        )

        # 新增：清空漫画缓存按钮
        self.clear_manga_cache_btn = PushButton("清空漫画缓存", self)
        self.clear_manga_cache_btn.clicked.connect(self._on_clear_manga_cache_clicked)
        self.addGroup(
            FIF.BROOM, # 或者 FIF.DELETE
            "漫画缓存管理", 
            "清空已缓存的漫画数据（例如封面、预读页面等）。", 
            self.clear_manga_cache_btn
        )

    def _on_reading_order_changed(self, index):
        config.reading_order.value = self.reading_order_combo.currentText()
        self.manga_manager.save_config()

    def _on_display_mode_changed(self, index):
        config.display_mode.value = self.display_mode_combo.currentText()
        self.manga_manager.save_config()

    def _on_page_interval_changed(self, value):
        config.page_interval.value = value
        self.manga_manager.save_config()

    def _on_translate_changed(self, checked):
        config.translate_title.value = checked
        self.manga_manager.save_config()

    def _on_simplify_changed(self, checked):
        config.simplify_chinese.value = checked
        self.manga_manager.save_config()

    def _on_merge_tags_changed(self, checked):
        config.merge_tags.value = checked
        self.manga_manager.save_config()

    def _on_clear_manga_cache_clicked(self):
        """清空漫画缓存按钮点击事件 (功能暂不实现)"""
        print("清空漫画缓存按钮被点击 (功能暂未实现)")
        # 实际实现时，可以调用 manga_manager 中的方法
        # if hasattr(self.manga_manager, "clear_manga_cache"):
        #     self.manga_manager.clear_manga_cache()
        #     InfoBar.success(
        #         title="成功", content="漫画缓存已清空", orient=Qt.Horizontal,
        #         isClosable=True, position=InfoBarPosition.TOP, duration=2000, parent=self
        #     )
        # else:
        InfoBar.info(
            title="提示", content="清空漫画缓存功能暂未实现。", orient=Qt.Horizontal,
            isClosable=True, position=InfoBarPosition.TOP, duration=3000, parent=self
        )

class SettingsInterface(ScrollArea):
    def __init__(self, parent=None, manga_manager=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.manga_manager = manga_manager or MangaManager(self) 
        self.setup_ui()

    def setup_ui(self):
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.vBoxLayout = QVBoxLayout(self.view)
        self.vBoxLayout.setSpacing(32)
        self.vBoxLayout.setContentsMargins(20, 32, 20, 20)
        self.vBoxLayout.setAlignment(Qt.AlignTop)

        self.theme_settings_card = ThemeSettinsCard(self.manga_manager, self.view)
        self.vBoxLayout.addWidget(self.theme_settings_card)

        self.manga_settings_card = MangaSettinsCard(self.manga_manager, self.view)
        self.vBoxLayout.addWidget(self.manga_settings_card)

        self.translation_settings_card = TranslationSettingsCard(self.manga_manager, self.view)
        self.vBoxLayout.addWidget(self.translation_settings_card)

        self.vBoxLayout.addStretch(1)