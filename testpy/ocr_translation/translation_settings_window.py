#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
翻译设置窗口
提供图形界面来配置翻译相关设置
"""

import sys
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, 
    QGroupBox, QMessageBox, QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PIL import ImageFont
from fontTools.ttLib import TTFont

from core.config import config


class TranslationSettingsWindow(QDialog):
    """翻译设置窗口"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("翻译设置")
        self.setFixedSize(500, 400)  # 减少窗口高度，因为选项更少了
        self.setModal(True)
        
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("翻译设置")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 翻译器选择
        translator_group = QGroupBox("翻译器选择")
        translator_layout = QFormLayout(translator_group)
        
        self.translator_combo = QComboBox()
        self.translator_combo.addItems(["Google", "智谱"])
        self.translator_combo.currentTextChanged.connect(self.on_translator_changed)
        translator_layout.addRow("翻译器类型:", self.translator_combo)
        
        layout.addWidget(translator_group)

        
        # 智谱AI设置
        self.zhipu_group = QGroupBox("智谱AI设置")
        zhipu_layout = QFormLayout(self.zhipu_group)
        
        self.zhipu_api_key_edit = QLineEdit()
        self.zhipu_api_key_edit.setEchoMode(QLineEdit.Password)
        self.zhipu_api_key_edit.setPlaceholderText("请输入智谱AI API密钥")
        zhipu_layout.addRow("API密钥:", self.zhipu_api_key_edit)
        
        self.zhipu_model_combo = QComboBox()
        self.zhipu_model_combo.addItems([
            "glm-4-flash-250414",
            "glm-4-flash", 
            "glm-4", 
            "glm-3-turbo"
        ])
        zhipu_layout.addRow("模型:", self.zhipu_model_combo)
        
        layout.addWidget(self.zhipu_group)
        
        # Google设置
        self.google_group = QGroupBox("Google翻译设置")
        google_layout = QFormLayout(self.google_group)
        
        self.google_api_key_edit = QLineEdit()
        self.google_api_key_edit.setEchoMode(QLineEdit.Password)
        self.google_api_key_edit.setPlaceholderText("可选，留空使用免费版本")
        google_layout.addRow("API密钥:", self.google_api_key_edit)
        
        layout.addWidget(self.google_group)
        
        # 字体设置
        self.font_group = QGroupBox("文字替换设置")
        font_layout = QFormLayout(self.font_group)
        
        self.font_combo = QComboBox()
        self.load_available_fonts()  # 加载字体
        font_layout.addRow("替换字体:", self.font_combo)
        
        layout.addWidget(self.font_group)
        
        # 说明文本
        info_text = QTextEdit()
        info_text.setMaximumHeight(80)
        info_text.setReadOnly(True)
        info_text.setText(
            "说明：\n"
            "• 智谱AI：需要API密钥，推荐使用GLM-4-Flash-250414模型\n"
            "• Google：免费版本有限制，付费版本需要API密钥"
        )
        layout.addWidget(info_text)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.test_button = QPushButton("测试连接")
        self.test_button.clicked.connect(self.test_connection)
        button_layout.addWidget(self.test_button)
        
        button_layout.addStretch()
        
        self.save_button = QPushButton("保存")
        self.save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_button)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # 初始状态
        self.on_translator_changed(self.translator_combo.currentText())

    def load_settings(self):
        """加载当前设置"""
        # 翻译器类型
        translator_type = config.translator_type.value
        index = self.translator_combo.findText(translator_type)
        if index >= 0:
            self.translator_combo.setCurrentIndex(index)
        
        # 智谱AI设置
        self.zhipu_api_key_edit.setText(config.zhipu_api_key.value)
        zhipu_model = config.zhipu_model.value
        model_index = self.zhipu_model_combo.findText(zhipu_model)
        if model_index >= 0:
            self.zhipu_model_combo.setCurrentIndex(model_index)
        
        # Google设置
        self.google_api_key_edit.setText(config.google_api_key.value)


    def on_translator_changed(self, translator_type):
        """翻译器类型改变时的处理"""
        # 隐藏所有设置组
        self.zhipu_group.setVisible(False)
        self.google_group.setVisible(False)
        self.nllb_group.setVisible(False)
        
        # 显示对应的设置组
        if translator_type == "智谱":
            self.zhipu_group.setVisible(True)
        elif translator_type == "Google":
            self.google_group.setVisible(True)

    def test_connection(self):
        """测试翻译器连接"""
        try:
            from core.translator import TranslatorFactory
            
            translator_type = self.translator_combo.currentText()
            
            if translator_type == "智谱":
                api_key = self.zhipu_api_key_edit.text().strip()
                model = self.zhipu_model_combo.currentText()
                
                if not api_key:
                    QMessageBox.warning(self, "警告", "请输入智谱AI API密钥")
                    return
                
                translator = TranslatorFactory.create_translator(
                    translator_type="智谱",
                    api_key=api_key,
                    model=model
                )
            elif translator_type == "Google":
                api_key = self.google_api_key_edit.text().strip()
                translator = TranslatorFactory.create_translator(
                    translator_type="Google",
                    api_key=api_key if api_key else None
                )
            
            # 测试翻译
            test_text = "Hello, World!"
            result = translator.translate(test_text, target_lang="zh")
            
            if result and result != f"[Translation Failed: {test_text}]":
                QMessageBox.information(
                    self, 
                    "测试成功", 
                    f"翻译器连接成功！\n\n测试翻译：\n原文：{test_text}\n译文：{result}"
                )
            else:
                QMessageBox.warning(self, "测试失败", "翻译器连接失败，请检查设置")
                
        except Exception as e:
            QMessageBox.critical(self, "测试错误", f"测试过程中发生错误：\n{str(e)}")

    def save_settings(self):
        """保存设置"""
        try:
            # 保存翻译器类型
            config.translator_type.value = self.translator_combo.currentText()
            
            # 保存智谱AI设置
            config.zhipu_api_key.value = self.zhipu_api_key_edit.text().strip()
            config.zhipu_model.value = self.zhipu_model_combo.currentText()
            
            # 保存Google设置
            config.google_api_key.value = self.google_api_key_edit.text().strip()
            
            
            # 保存字体设置
            font_file_name = self.font_combo.currentData()
            if font_file_name:
                config.font_name.value = font_file_name
            
            QMessageBox.information(self, "成功", "设置已保存！")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "保存错误", f"保存设置时发生错误：\n{str(e)}")

    def load_available_fonts(self):
        """加载可用字体到下拉框"""
        try:
            # 获取font目录中的所有字体文件
            font_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'font')
            if not os.path.exists(font_dir):
                QMessageBox.warning(self, "警告", f"找不到字体目录：{font_dir}")
                return

            # 加载字体文件
            font_files = [(f, os.path.join(font_dir, f)) 
                         for f in os.listdir(font_dir) 
                         if f.lower().endswith(('.ttf', '.otf'))]
            
            if not font_files:
                QMessageBox.warning(self, "警告", "字体目录中没有找到任何字体文件")
                return
            
            self.font_combo.clear()
            self.available_fonts = {}  # 用于存储字体文件名到字体信息的映射
            
            # 加载每个字体文件并读取其属性
            for file_name, file_path in font_files:
                try:
                    # 使用fontTools读取字体
                    tt = TTFont(file_path)
                    # 尝试获取中文名称
                    name_records = tt['name'].names
                    font_name = None
                    
                    # 优先查找简体中文名称
                    for record in name_records:
                        if record.platformID == 3 and record.langID in (2052, 1033):  # Windows 简体中文或英文
                            try:
                                if record.nameID in (4, 6, 1, 16):  # 完整名称、PostScript名称、字体家族名称或首选家族名称
                                    font_name = record.string.decode('utf-16be')
                                    if record.langID == 2052:  # 如果找到中文名称就立即使用
                                        break
                            except:
                                continue
                    
                    # 如果没有找到任何名称，使用文件名
                    if not font_name:
                        font_name = os.path.splitext(file_name)[0]
                    
                    display_text = f"{font_name} ({file_name})"
                    self.font_combo.addItem(display_text, file_name)
                    self.available_fonts[file_name] = {
                        'path': file_path,
                        'name': font_name
                    }
                    
                    tt.close()
                except Exception as e:
                    print(f"无法加载字体 {file_name}: {e}")
            
            # 设置当前选中的字体
            current_font = config.font_name.value
            index = self.font_combo.findData(current_font)
            if index >= 0:
                self.font_combo.setCurrentIndex(index)
            elif self.font_combo.count() > 0:
                # 如果找不到已配置的字体，默认选择第一个
                self.font_combo.setCurrentIndex(0)
        
        except Exception as e:
            QMessageBox.warning(self, "字体加载错误", f"无法加载可用字体：\n{str(e)}")


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = TranslationSettingsWindow()
    window.show()
    sys.exit(app.exec())