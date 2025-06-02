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
from core.translators.nllb_translator import NLLBTranslator


class TranslationSettingsCard(GroupHeaderCardWidget):
    """翻译相关设置卡片"""

    def __init__(self, manga_manager, parent=None):
        super().__init__(parent=parent)
        self.manga_manager = manga_manager
        self.available_fonts = {}

        self.setTitle("翻译与文本设置")
        self.setBorderRadius(8)

        self.translator_combo = ComboBox(self)
        self.translator_combo.addItems(["Google", "智谱", "NLLB"])
        current_translator_type = config.translator_type.value
        if current_translator_type not in ["Google", "智谱", "NLLB"]:
            config.translator_type.value = "Google" # Default to Google if invalid
            # self.manga_manager.save_config() # Save will be called at the end of init
        self.translator_combo.setCurrentText(config.translator_type.value)

        self.addGroup(
            FIF.LANGUAGE,
            "翻译接口",
            "选择使用的翻译服务提供商。",
            self.translator_combo
        )

        self.api_key_widget = QWidget(self)
        self.api_key_layout = QVBoxLayout(self.api_key_widget)
        self.api_key_layout.setContentsMargins(0, 0, 0, 0)
        self.api_key_layout.setSpacing(8)
        
        self.zhipu_widget = QWidget(self.api_key_widget)
        self.zhipu_layout = QGridLayout(self.zhipu_widget)
        self.zhipu_layout.setContentsMargins(0, 0, 0, 0)
        self.zhipu_layout.setSpacing(8)
        self.zhipu_api_key_edit = LineEdit(self.zhipu_widget)
        self.zhipu_api_key_edit.setPlaceholderText("请输入智谱AI API密钥")
        self.zhipu_api_key_edit.setEchoMode(LineEdit.Password)
        self.zhipu_model_combo = ComboBox(self.zhipu_widget)
        self.zhipu_model_combo.addItems([
            "glm-4-flash-250414", "glm-4-flash", "glm-4", "glm-3-turbo"
        ])
        self.zhipu_layout.addWidget(BodyLabel("API密钥:"), 0, 0)
        self.zhipu_layout.addWidget(self.zhipu_api_key_edit, 0, 1)
        self.zhipu_layout.addWidget(BodyLabel("模型:"), 1, 0)
        self.zhipu_layout.addWidget(self.zhipu_model_combo, 1, 1)
        
        self.google_widget = QWidget(self.api_key_widget)
        self.google_layout = QGridLayout(self.google_widget)
        self.google_layout.setContentsMargins(0, 0, 0, 0)
        self.google_api_key_edit = LineEdit(self.google_widget)
        self.google_api_key_edit.setPlaceholderText("请输入Google API密钥 (可选)")
        self.google_api_key_edit.setEchoMode(LineEdit.Password)
        self.google_layout.addWidget(BodyLabel("API密钥 (可选):"), 0, 0)
        self.google_layout.addWidget(self.google_api_key_edit, 0, 1)

        self.nllb_widget = QWidget(self.api_key_widget)
        self.nllb_layout = QGridLayout(self.nllb_widget)
        self.nllb_layout.setContentsMargins(0,0,0,0)
        self.nllb_layout.setSpacing(8)

        self.nllb_model_name_edit = LineEdit(self.nllb_widget)
        self.nllb_model_name_edit.setPlaceholderText(f"默认为 {NLLBTranslator.DEFAULT_MODEL_NAME}")

        # 将 NLLB 源语言从 LineEdit 改为 ComboBox
        self.nllb_source_lang_combo = ComboBox(self.nllb_widget)
        # NLLB 支持的常见源语言
        common_nllb_sources = [
            ("日语", "jpn_Jpan"),
            ("英语", "eng_Latn"),
            ("简体中文", "zho_Hans"),
            ("韩语", "kor_Hang"),
        ]
        for display_name, code in common_nllb_sources:
            # 使用QComboBox的setItemData方法
            self.nllb_source_lang_combo.addItem(display_name)
            index = self.nllb_source_lang_combo.count() - 1
            self.nllb_source_lang_combo.setItemData(index, code)
            # 验证数据是否正确设置
            stored_data = self.nllb_source_lang_combo.itemData(index)
        # 默认选择日语作为源语言，或从配置加载
        default_src_lang_code = config.nllb_source_lang.value or NLLBTranslator.DEFAULT_SOURCE_LANG_CODE
        default_src_index = self.nllb_source_lang_combo.findData(default_src_lang_code)
        if default_src_index != -1:
            self.nllb_source_lang_combo.setCurrentIndex(default_src_index)
        elif self.nllb_source_lang_combo.count() > 0:
             self.nllb_source_lang_combo.setCurrentIndex(0) # Fallback to first item


        self.nllb_target_lang_combo = ComboBox(self.nllb_widget)
        common_nllb_targets = [
            ("简体中文", "zho_Hans"),
            ("繁体中文", "zho_Hant"),
            ("英文", "eng_Latn"),
            ("日文", "jpn_Jpan"),
            ("韩文", "kor_Hang"),
        ]
        for display_name, code in common_nllb_targets:
            # 使用QComboBox的setItemData方法
            self.nllb_target_lang_combo.addItem(display_name)
            index = self.nllb_target_lang_combo.count() - 1
            self.nllb_target_lang_combo.setItemData(index, code)
            # 验证数据是否正确设置
            stored_data = self.nllb_target_lang_combo.itemData(index)

        self.nllb_layout.addWidget(BodyLabel("模型名称:"), 0, 0)
        self.nllb_layout.addWidget(self.nllb_model_name_edit, 0, 1)
        self.nllb_layout.addWidget(BodyLabel("源语言 (Tokenizer):"), 1, 0)
        self.nllb_layout.addWidget(self.nllb_source_lang_combo, 1, 1) # 使用 ComboBox
        self.nllb_layout.addWidget(BodyLabel("目标语言:"), 2, 0)
        self.nllb_layout.addWidget(self.nllb_target_lang_combo, 2, 1)

        self.api_key_layout.addWidget(self.zhipu_widget)
        self.api_key_layout.addWidget(self.google_widget)
        self.api_key_layout.addWidget(self.nllb_widget)

        self.addGroup(
            FIF.SETTING, "服务特定设置", "配置所选翻译服务的特定参数。", self.api_key_widget
        )

        self.font_combo = ComboBox(self)
        self.font_combo.setFixedWidth(300)
        self._load_available_fonts()
        
        self.addGroup(
            FIF.FONT,
            "文本替换字体",
            "选择用于翻译后文本替换的字体。",
            self.font_combo,
        )

        self.clear_translation_cache_btn = PushButton("清空翻译缓存", self)
        self.addGroup(
            FIF.DELETE, "翻译缓存管理", "清空已缓存的翻译结果。", self.clear_translation_cache_btn
        )
        
        self._connect_signals()
        self._load_settings_from_config()
        self._update_api_settings_visibility()


    def _connect_signals(self):
        self.translator_combo.currentIndexChanged.connect(self._on_translator_changed)
        
        self.zhipu_api_key_edit.textChanged.connect(self._on_zhipu_api_key_changed)
        self.zhipu_model_combo.currentIndexChanged.connect(self._on_zhipu_model_changed)
        self.google_api_key_edit.textChanged.connect(self._on_google_api_key_changed)
        
        self.nllb_model_name_edit.textChanged.connect(self._on_nllb_model_name_changed)
        self.nllb_source_lang_combo.currentIndexChanged.connect(self._on_nllb_source_lang_changed) # 连接新的 ComboBox
        self.nllb_target_lang_combo.currentIndexChanged.connect(self._on_nllb_target_lang_changed)
        
        self.font_combo.currentIndexChanged.connect(self._on_font_name_changed)
        self.clear_translation_cache_btn.clicked.connect(self._on_clear_translation_cache_clicked)

    def _load_settings_from_config(self):
        self.translator_combo.setCurrentText(config.translator_type.value)

        self.zhipu_api_key_edit.setText(config.zhipu_api_key.value)
        self.zhipu_model_combo.setCurrentText(config.zhipu_model.value)
        self.google_api_key_edit.setText(config.google_api_key.value)

        self.nllb_model_name_edit.setText(config.nllb_model_name.value or NLLBTranslator.DEFAULT_MODEL_NAME)
        
        # 加载 NLLB 源语言下拉框
        nllb_source_code_from_config = config.nllb_source_lang.value or NLLBTranslator.DEFAULT_SOURCE_LANG_CODE
        source_index = self.nllb_source_lang_combo.findData(nllb_source_code_from_config)
        if source_index != -1:
            self.nllb_source_lang_combo.setCurrentIndex(source_index)
        elif self.nllb_source_lang_combo.count() > 0: # 如果配置值无效，选择第一个作为默认
            self.nllb_source_lang_combo.setCurrentIndex(0)
            # 更新配置为当前选中的默认值
            # config.nllb_source_lang.value = self.nllb_source_lang_combo.currentData() # 避免在加载时保存

        # 加载 NLLB 目标语言下拉框
        nllb_target_code_from_config = config.nllb_target_lang.value or NLLBTranslator.NLLB_LANG_CODE_MAP.get("zh")
        target_index = self.nllb_target_lang_combo.findData(nllb_target_code_from_config)
        if target_index != -1:
            self.nllb_target_lang_combo.setCurrentIndex(target_index)
        elif self.nllb_target_lang_combo.count() > 0:
            self.nllb_target_lang_combo.setCurrentIndex(0)
            # config.nllb_target_lang.value = self.nllb_target_lang_combo.currentData() # 避免在加载时保存

    def _load_available_fonts(self):
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

    def _on_translator_changed(self, index):
        new_translator_type = self.translator_combo.currentText()
        if config.translator_type.value != new_translator_type:
            config.translator_type.value = new_translator_type
            self.manga_manager.save_config()
        self._update_api_settings_visibility()
        self._load_settings_from_config() 
    
    def _update_api_settings_visibility(self):
        current_translator = config.translator_type.value
        self.zhipu_widget.setVisible(current_translator == "智谱")
        self.google_widget.setVisible(current_translator == "Google")
        self.nllb_widget.setVisible(current_translator == "NLLB")
    
    def _on_zhipu_api_key_changed(self, text):
        config.zhipu_api_key.value = text
        self.manga_manager.save_config()
    
    def _on_zhipu_model_changed(self, index):
        config.zhipu_model.value = self.zhipu_model_combo.currentText()
        self.manga_manager.save_config()
    
    def _on_google_api_key_changed(self, text):
        config.google_api_key.value = text
        self.manga_manager.save_config()

    def _on_nllb_model_name_changed(self, text):
        config.nllb_model_name.value = text or NLLBTranslator.DEFAULT_MODEL_NAME
        self.manga_manager.save_config()

    def _on_nllb_source_lang_changed(self, index): 
        if index < 0:
            print(f"警告：无效的源语言索引值 {index}")
            return
            
        selected_source_code = self.nllb_source_lang_combo.itemData(index)
        selected_text = self.nllb_source_lang_combo.itemText(index)
        print(f"选中源语言索引 {index}:")
        print(f"- 显示文本: {selected_text}")
        print(f"- 数据值: {selected_source_code}")
        print(f"- ComboBox总项目数: {self.nllb_source_lang_combo.count()}")
        
        if selected_source_code:
            config.nllb_source_lang.value = selected_source_code
            print(f"设置 NLLB 源语言为: {selected_source_code}")
            self.manga_manager.save_config()  # 使用manga_manager来保存配置
        else:
            print(f"警告：索引 {index} 的源语言项目没有关联的数据值")

    def _on_nllb_target_lang_changed(self, index):
        if index < 0:
            print(f"警告：无效的索引值 {index}")
            return
            
        selected_target_code = self.nllb_target_lang_combo.itemData(index)
        selected_text = self.nllb_target_lang_combo.itemText(index)
        print(f"选中索引 {index}:")
        print(f"- 显示文本: {selected_text}")
        print(f"- 数据值: {selected_target_code}")
        print(f"- ComboBox总项目数: {self.nllb_target_lang_combo.count()}")
        
        if selected_target_code:
            config.nllb_target_lang.value = selected_target_code
            print(f"设置 NLLB 目标语言为: {selected_target_code}")
            self.manga_manager.save_config()  # 使用manga_manager来保存配置
        else:
            print(f"警告：索引 {index} 的项目没有关联的数据值")

    def _on_font_name_changed(self, index):
        selected_font_file_name = self.font_combo.itemData(index)
        if selected_font_file_name and config.font_name.value != selected_font_file_name:
            config.font_name.value = selected_font_file_name
            self.manga_manager.save_config()

    def _on_clear_translation_cache_clicked(self):
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

        self.clear_manga_cache_btn = PushButton("清空漫画缓存", self)
        self.clear_manga_cache_btn.clicked.connect(self._on_clear_manga_cache_clicked)
        self.addGroup(
            FIF.BROOM, 
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
        print("清空漫画缓存按钮被点击 (功能暂未实现)")
        InfoBar.info(
            title="提示", content="清空漫画缓存功能暂未实现。", orient=Qt.Horizontal,
            isClosable=True, position=InfoBarPosition.TOP, duration=3000, parent=self
        )

class SettingsInterface(ScrollArea):
    def __init__(self, parent=None, manga_manager=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.manga_manager = manga_manager or MangaManager(self)
        # --- CRITICAL CHANGE: Make SettingsInterface (ScrollArea) and its viewport transparent ---
        self.setStyleSheet("background: transparent;")
        self.viewport().setStyleSheet("background: transparent;")
        # ------------------------------------------------------------------------------------
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