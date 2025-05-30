#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
翻译设置窗口
提供图形界面来配置翻译相关设置
"""

import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, 
    QGroupBox, QMessageBox, QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core.config import config


class TranslationSettingsWindow(QDialog):
    """翻译设置窗口"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("翻译设置")
        self.setFixedSize(500, 600)
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
        self.translator_combo.addItems(["Google", "智谱", "DeepL", "百度", "MyMemory"])
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
        
        # DeepL设置
        self.deepl_group = QGroupBox("DeepL翻译设置")
        deepl_layout = QFormLayout(self.deepl_group)
        
        self.deepl_api_key_edit = QLineEdit()
        self.deepl_api_key_edit.setEchoMode(QLineEdit.Password)
        self.deepl_api_key_edit.setPlaceholderText("请输入DeepL API密钥")
        deepl_layout.addRow("API密钥:", self.deepl_api_key_edit)
        
        layout.addWidget(self.deepl_group)
        
        # 百度设置
        self.baidu_group = QGroupBox("百度翻译设置")
        baidu_layout = QFormLayout(self.baidu_group)
        
        self.baidu_app_id_edit = QLineEdit()
        self.baidu_app_id_edit.setPlaceholderText("请输入百度翻译APP ID")
        baidu_layout.addRow("APP ID:", self.baidu_app_id_edit)
        
        self.baidu_app_key_edit = QLineEdit()
        self.baidu_app_key_edit.setEchoMode(QLineEdit.Password)
        self.baidu_app_key_edit.setPlaceholderText("请输入百度翻译APP Key")
        baidu_layout.addRow("APP Key:", self.baidu_app_key_edit)
        
        layout.addWidget(self.baidu_group)
        
        # MyMemory设置
        self.mymemory_group = QGroupBox("MyMemory翻译设置")
        mymemory_layout = QFormLayout(self.mymemory_group)
        
        self.mymemory_email_edit = QLineEdit()
        self.mymemory_email_edit.setPlaceholderText("可选，提供邮箱可增加免费额度")
        mymemory_layout.addRow("邮箱:", self.mymemory_email_edit)
        
        layout.addWidget(self.mymemory_group)
        
        # 说明文本
        info_text = QTextEdit()
        info_text.setMaximumHeight(100)
        info_text.setReadOnly(True)
        info_text.setText(
            "说明：\n"
            "• 智谱AI：需要API密钥，推荐使用GLM-4-Flash-250414模型\n"
            "• Google：免费版本有限制，付费版本需要API密钥\n"
            "• DeepL：需要API密钥，翻译质量较高\n"
            "• 百度：需要APP ID和APP Key\n"
            "• MyMemory：免费使用，提供邮箱可增加额度"
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
        
        # 其他设置
        self.google_api_key_edit.setText(config.google_api_key.value)
        self.deepl_api_key_edit.setText(config.deepl_api_key.value)
        self.baidu_app_id_edit.setText(config.baidu_app_id.value)
        self.baidu_app_key_edit.setText(config.baidu_app_key.value)
        self.mymemory_email_edit.setText(config.mymemory_email.value)
    
    def on_translator_changed(self, translator_type):
        """翻译器类型改变时的处理"""
        # 隐藏所有设置组
        self.zhipu_group.setVisible(False)
        self.google_group.setVisible(False)
        self.deepl_group.setVisible(False)
        self.baidu_group.setVisible(False)
        self.mymemory_group.setVisible(False)
        
        # 显示对应的设置组
        if translator_type == "智谱":
            self.zhipu_group.setVisible(True)
        elif translator_type == "Google":
            self.google_group.setVisible(True)
        elif translator_type == "DeepL":
            self.deepl_group.setVisible(True)
        elif translator_type == "百度":
            self.baidu_group.setVisible(True)
        elif translator_type == "MyMemory":
            self.mymemory_group.setVisible(True)
    
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
            elif translator_type == "DeepL":
                api_key = self.deepl_api_key_edit.text().strip()
                if not api_key:
                    QMessageBox.warning(self, "警告", "请输入DeepL API密钥")
                    return
                translator = TranslatorFactory.create_translator(
                    translator_type="DeepL",
                    api_key=api_key
                )
            elif translator_type == "百度":
                app_id = self.baidu_app_id_edit.text().strip()
                app_key = self.baidu_app_key_edit.text().strip()
                if not app_id or not app_key:
                    QMessageBox.warning(self, "警告", "请输入百度翻译APP ID和APP Key")
                    return
                translator = TranslatorFactory.create_translator(
                    translator_type="百度",
                    app_id=app_id,
                    app_key=app_key
                )
            else:  # MyMemory
                email = self.mymemory_email_edit.text().strip()
                translator = TranslatorFactory.create_translator(
                    translator_type="MyMemory",
                    email=email if email else None
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
            
            # 保存其他设置
            config.google_api_key.value = self.google_api_key_edit.text().strip()
            config.deepl_api_key.value = self.deepl_api_key_edit.text().strip()
            config.baidu_app_id.value = self.baidu_app_id_edit.text().strip()
            config.baidu_app_key.value = self.baidu_app_key_edit.text().strip()
            config.mymemory_email.value = self.mymemory_email_edit.text().strip()
            
            QMessageBox.information(self, "成功", "设置已保存！")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "保存错误", f"保存设置时发生错误：\n{str(e)}")


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = TranslationSettingsWindow()
    window.show()
    sys.exit(app.exec())