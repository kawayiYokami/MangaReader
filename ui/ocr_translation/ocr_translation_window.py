#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OCR测试窗口
提供图形界面来测试OCR功能
"""

import os
import sys
import cv2 # 新增导入cv2
import numpy as np
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QWidget, QFileDialog,
    QProgressBar, QSplitter, QScrollArea, QMessageBox, QDialog
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QFont, QImage

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from core.ocr_manager import OCRManager, OCRResult
from core.translator import TranslatorFactory
from core.manga_text_replacer import MangaTextReplacer, create_manga_translation_dict
from core.config import config
from utils import manga_logger as log
from qfluentwidgets import (
    CardWidget,
    PushButton,
    InfoBar,
    InfoBarPosition,
    BodyLabel,
    ImageLabel,
    SmoothScrollArea,
)
# 尝试相对导入，如果失败则使用绝对导入
try:
    from .translation_settings_window import TranslationSettingsWindow
except ImportError:
    from ui.ocr_translation.translation_settings_window import TranslationSettingsWindow


class OCRTestWindow(QMainWindow):
    """OCR测试窗口"""
    
    def __init__(self):
        super().__init__()
        self.ocr_manager = None
        self.translator = None
        
        self.manga_text_replacer = None
        self.current_image_path = None
        self.cached_image_data = None # 新增：缓存图片数据
        self.original_pixmap = None # 初始化原始图片数据
        self.bbox_scale_factor = 1.0  # 新增：文本框缩放比例，默认为1.0
        self.current_results = []
        self.current_translations = {}  # 存储当前的翻译结果
        self.init_ui()
        self.init_ui()
        self.init_ocr()
        self.init_translator()
        
        self.init_manga_text_replacer()
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("OCR测试工具")
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QHBoxLayout(central_widget)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # 左侧：图像显示区域
        left_widget = self.create_image_area()
        splitter.addWidget(left_widget)
        
        # 右侧：控制和结果区域
        right_widget = self.create_control_area()
        splitter.addWidget(right_widget)
        
        # 设置分割器比例
        splitter.setSizes([600, 600])
        
        # 状态栏
        self.statusBar().showMessage("准备就绪")
    
    def create_image_area(self):
        """创建图像显示区域"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 图像显示标签
        self.image_label = ImageLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #aaa;
                background-color: #f5f5f5;
                min-height: 400px;
            }
        """)
        self.image_label.setText("点击「打开图片」按钮选择图像")
        # self.image_label.setScaledContents(True)  # 禁用内容缩放，手动控制缩放以保持宽高比
        self.image_label.setMinimumSize(400, 300)  # 设置最小尺寸
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.image_label)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumSize(600, 400)  # 设置滚动区域最小尺寸
        
        layout.addWidget(scroll_area)
        
        return widget
    
    def create_control_area(self):
        """创建控制和结果区域"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 控制按钮区域
        button_layout = QHBoxLayout()
        
        self.open_button = QPushButton("📁 打开图片")
        self.open_button.setMinimumHeight(40)
        self.open_button.clicked.connect(self.open_image)
        
        self.ocr_button = QPushButton("🔍 开始OCR")
        self.ocr_button.setMinimumHeight(40)
        self.ocr_button.setEnabled(False)
        self.ocr_button.clicked.connect(self.start_ocr)
        
        self.translate_button = QPushButton("🌐 翻译")
        self.translate_button.setMinimumHeight(40)
        self.translate_button.setEnabled(False)
        self.translate_button.clicked.connect(self.start_translation)
        
        self.save_button = QPushButton("💾 保存结果")
        self.save_button.setMinimumHeight(40)
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_results)
        
        
        
        self.manga_replace_button = QPushButton("📚 漫画替换")
        self.manga_replace_button.setMinimumHeight(40)
        self.manga_replace_button.setEnabled(False)
        self.manga_replace_button.clicked.connect(self.start_manga_replacement)
        
        self.settings_button = QPushButton("⚙️ 翻译设置")
        self.settings_button.setMinimumHeight(40)
        self.settings_button.clicked.connect(self.open_translation_settings)
        
        # 创建两行按钮布局
        button_layout1 = QHBoxLayout()
        button_layout1.addWidget(self.open_button)
        button_layout1.addWidget(self.ocr_button)
        button_layout1.addWidget(self.translate_button)
        button_layout1.addWidget(self.settings_button)
        
        button_layout2 = QHBoxLayout()
        button_layout2.addWidget(self.manga_replace_button)
        button_layout2.addWidget(self.save_button)
        
        layout.addLayout(button_layout1)
        layout.addLayout(button_layout2)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel("OCR引擎状态: 正在初始化...")
        self.status_label.setStyleSheet("color: #666; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        # 结果显示区域
        results_label = QLabel("识别结果:")
        results_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(results_label)
        
        # 文本结果
        self.text_result = QTextEdit()
        self.text_result.setPlaceholderText("OCR识别的文本将显示在这里...")
        self.text_result.setMinimumHeight(200)
        layout.addWidget(self.text_result)
        
        # 翻译结果
        translation_label = QLabel("翻译结果:")
        translation_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(translation_label)
        
        self.translation_result = QTextEdit()
        self.translation_result.setPlaceholderText("翻译结果将显示在这里...")
        self.translation_result.setMinimumHeight(150)
        layout.addWidget(self.translation_result)
        
        # 详细结果
        details_label = QLabel("详细信息:")
        details_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(details_label)
        
        self.details_result = QTextEdit()
        self.details_result.setPlaceholderText("详细的OCR结果信息将显示在这里...")
        self.details_result.setMinimumHeight(120)
        layout.addWidget(self.details_result)
        
        return widget
    
    def init_ocr(self):
        """初始化OCR管理器"""
        try:
            self.ocr_manager = OCRManager()
            
            # 连接信号
            self.ocr_manager.model_loaded.connect(self.on_model_loaded)
            self.ocr_manager.model_load_error.connect(self.on_model_load_error)
            self.ocr_manager.ocr_started.connect(self.on_ocr_started)
            self.ocr_manager.ocr_finished.connect(self.on_ocr_finished)
            self.ocr_manager.ocr_error.connect(self.on_ocr_error)
            self.ocr_manager.ocr_progress.connect(self.on_ocr_progress)
            
            # 加载模型
            self.ocr_manager.load_model()
            
        except Exception as e:
            self.status_label.setText(f"OCR引擎初始化失败: {str(e)}")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
    
    def init_translator(self):
        """初始化翻译器"""
        try:
            # 从配置中获取翻译器设置
            translator_type = config.translator_type.value
            
            if translator_type == "智谱":
                api_key = config.zhipu_api_key.value
                model = config.zhipu_model.value
                
                if not api_key:
                    log.warning("智谱API密钥未配置，翻译功能将不可用")
                    return
                
                self.translator = TranslatorFactory.create_translator(
                    translator_type="智谱",
                    api_key=api_key,
                    model=model
                )
                log.info(f"翻译器初始化成功: {translator_type} ({model})")
            else:
                # 使用其他翻译器
                if translator_type == "Google":
                    api_key = config.google_api_key.value
                    self.translator = TranslatorFactory.create_translator(
                        translator_type="Google",
                        api_key=api_key if api_key else None
                    )
                elif translator_type == "DeepL":
                    api_key = config.deepl_api_key.value
                    if not api_key:
                        log.warning("DeepL API密钥未配置，翻译功能将不可用")
                        return
                    self.translator = TranslatorFactory.create_translator(
                        translator_type="DeepL",
                        api_key=api_key
                    )
                elif translator_type == "百度":
                    app_id = config.baidu_app_id.value
                    app_key = config.baidu_app_key.value
                    if not app_id or not app_key:
                        log.warning("百度翻译APP ID或APP Key未配置，翻译功能将不可用")
                        return
                    self.translator = TranslatorFactory.create_translator(
                        translator_type="百度",
                        app_id=app_id,
                        app_key=app_key
                    )
                elif translator_type == "MyMemory":
                    email = config.mymemory_email.value
                    self.translator = TranslatorFactory.create_translator(
                        translator_type="MyMemory",
                        email=email if email else None
                    )
                else:
                    # 默认使用Google翻译
                    self.translator = TranslatorFactory.create_translator("Google")
                
                log.info(f"翻译器初始化成功: {translator_type}")
                
        except Exception as e:
            log.error(f"翻译器初始化失败: {str(e)}")
            self.translator = None
    
    
            
    
    def init_manga_text_replacer(self):
        """初始化漫画文本替换器"""
        try:
            self.manga_text_replacer = MangaTextReplacer()
            log.info("漫画文本替换器初始化成功")
        except Exception as e:
            log.error(f"漫画文本替换器初始化失败: {str(e)}")
            self.manga_text_replacer = None
    
    def open_image(self):
        """打开图片文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片文件",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.tiff);;所有文件 (*)"
        )
        
        if file_path:
            self.load_image(file_path)
    
    def load_image(self, file_path):
        """加载并显示图片"""
        try:
            # 加载图片
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "错误", "无法加载图片文件")
                return
            
            # 缓存原始 pixmap，以便在窗口大小改变时重新缩放
            self.original_pixmap = pixmap
            self._update_image_display()
            self.image_label.setText("")
            
            # 保存路径
            self.current_image_path = file_path
            
            # 读取图片数据并缓存
            self.cached_image_data = cv2.imread(file_path)
            if self.cached_image_data is None:
                QMessageBox.warning(self, "错误", "无法读取图片数据进行OCR")
                self.current_image_path = None
                self.cached_image_data = None
                return
            
            # 启用OCR按钮
            if self.ocr_manager and self.ocr_manager.is_ready():
                self.ocr_button.setEnabled(True)
            
            # 清空之前的结果
            self.text_result.clear()
            self.translation_result.clear()
            self.details_result.clear()
            self.save_button.setEnabled(False)
            self.translate_button.setEnabled(False)
            self.manga_replace_button.setEnabled(False)
            self.current_translations = {}
            
            self.statusBar().showMessage(f"已加载图片: {os.path.basename(file_path)}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载图片时发生错误: {str(e)}")
            
    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        # 延迟更新图像显示，确保标签尺寸已更新
        QTimer.singleShot(0, self._update_image_display)

    def _update_image_display(self):
        """根据当前标签大小更新图像显示"""
        try:
            if self.original_pixmap and not self.original_pixmap.isNull():
                # 获取图像标签的当前可用尺寸
                label_size = self.image_label.size()
                
                # 只有当标签有有效尺寸时才进行缩放
                if label_size.width() > 0 and label_size.height() > 0:
                    # 缩放图片以适应标签的尺寸，保持宽高比
                    scaled_pixmap = self.original_pixmap.scaled(
                        label_size,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    self.image_label.setPixmap(scaled_pixmap)
                    print(f"🔄 图像更新: 标签尺寸 {label_size.width()}x{label_size.height()}, "
                          f"缩放后 {scaled_pixmap.width()}x{scaled_pixmap.height()}")
                else:
                    print(f"⚠️ 图像更新: 标签尺寸无效 ({label_size.width()}x{label_size.height()}), 暂不缩放。")
        except Exception as e:
            print(f"❌ _update_image_display 发生错误: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def start_ocr(self):
        """开始OCR识别"""
        if self.cached_image_data is None or not self.ocr_manager or not self.ocr_manager.is_ready():
            QMessageBox.warning(self, "警告", "请先选择图片并等待OCR引擎准备就绪")
            return
        
        # 开始识别，使用缓存的图片数据
        self.ocr_manager.recognize_image_data(self.cached_image_data)
    
    def start_translation(self):
        """开始翻译OCR结果（使用结构化文本）"""
        if not self.current_results:
            QMessageBox.warning(self, "警告", "请先进行OCR识别")
            return
        
        if not self.translator:
            QMessageBox.warning(self, "警告", "翻译器未初始化，请检查翻译设置")
            return
        
        try:
            # 显示进度
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.translate_button.setEnabled(False)
            self.statusBar().showMessage("正在翻译...")
            
            # 获取结构化文本（合并后的文本框）
            structured_texts = self.ocr_manager.get_structured_text(self.current_results)
            
            # 在详细信息区域显示结构化文本信息
            details_info = []
            for i, item in enumerate(structured_texts, 1):
                details_info.append(f"结构化文本块 #{i}:")
                details_info.append(f"  - 文本内容: {item['text']}")
                details_info.append(f"  - 方向: {item.get('direction', 'auto')}")
                details_info.append(f"  - 包含OCR结果数: {len(item['ocr_results'])}")
                details_info.append("")
            self.details_result.setText("\n".join(details_info))
            
            # 翻译每个结构化文本块
            display_translated_texts = [] # 用于显示在UI上的翻译结果
            pure_translated_texts = []    # 存储纯粹的翻译结果，用于创建翻译字典
            
            for item in structured_texts:
                full_text = item['text']
                if not full_text.strip():
                    # 跳过空文本
                    continue
                
                translated = ""
                try:
                    # 翻译完整文本块
                    translated = self.translator.translate(full_text, target_lang="zh")
                    
                    # 将翻译结果应用到所有相关的OCRResult对象
                    for ocr_result in item['ocr_results']:
                        ocr_result.translated_text = translated
                    
                    display_translated_texts.append(translated)  # 只显示译文
                    pure_translated_texts.append(translated)
                except Exception as e:
                    log.error(f"翻译文本块失败: {full_text}, 错误: {e}")
                    # 翻译失败时使用原文
                    for ocr_result in item['ocr_results']:
                        ocr_result.translated_text = full_text
                    display_translated_texts.append("[翻译失败]")  # 只显示翻译失败的标记
                    pure_translated_texts.append(full_text) # 翻译失败时，纯翻译结果使用原文
            
            # 显示翻译结果
            self.translation_result.setText("\n".join(display_translated_texts))
            
            # 创建翻译字典用于漫画文本替换
            # 使用结构化文本和纯翻译列表
            self.current_translations = create_manga_translation_dict(
                structured_texts,
                pure_translated_texts
            )
            
            # 启用漫画文本替换按钮
            if self.manga_text_replacer and self.current_translations:
                self.manga_replace_button.setEnabled(True)
            
            # 隐藏进度条
            self.progress_bar.setVisible(False)
            self.translate_button.setEnabled(True)
            self.statusBar().showMessage("翻译完成")
        except Exception as e:
            self.progress_bar.setVisible(False)
            self.translate_button.setEnabled(True)
            error_msg = f"翻译失败: {str(e)}"
            self.translation_result.setText(error_msg)
            QMessageBox.critical(self, "翻译错误", error_msg)
            self.statusBar().showMessage("翻译失败")
    
    
    
    def start_manga_replacement(self):
        """开始漫画文本替换"""
        if not self.current_results:
            QMessageBox.warning(self, "警告", "请先进行OCR识别")
            return
        
        if not self.current_translations:
            QMessageBox.warning(self, "警告", "请先进行翻译")
            return
        
        if not self.manga_text_replacer:
            QMessageBox.warning(self, "警告", "漫画文本替换器未初始化")
            return
        
        if self.cached_image_data is None:
            QMessageBox.warning(self, "警告", "没有可用的图像数据")
            return
        
        try:
            # 显示进度
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.manga_replace_button.setEnabled(False)
            self.statusBar().showMessage("正在进行漫画文本替换...")
            
            # 获取结构化文本
            structured_texts = self.ocr_manager.get_structured_text(self.current_results)
            
            # 使用新的API直接传入结构化文本进行替换
            replaced_image_data = self.manga_text_replacer.process_manga_image(
                self.cached_image_data.copy(),
                structured_texts,
                self.current_translations,
                target_language="zh",
                inpaint_background=True
            )
            
            if replaced_image_data is not None:
                # 在替换后的图像上绘制边界框以显示替换位置
                debug_image = replaced_image_data.copy()
                # 遍历结构化文本块，绘制边界框
                for text_block in structured_texts:
                    # 收集所有OCR结果的边界点
                    bbox_points = []
                    for ocr_result in text_block['ocr_results']:
                        bbox_points.extend(ocr_result.bbox)
                    
                    if bbox_points:
                        # 计算边界框
                        points = np.array(bbox_points)
                        x_min = min(p[0] for p in bbox_points)
                        y_min = min(p[1] for p in bbox_points)
                        x_max = max(p[0] for p in bbox_points)
                        y_max = max(p[1] for p in bbox_points)
                        
                        rect_points = np.array([
                            [x_min, y_min],
                            [x_max, y_min],
                            [x_max, y_max],
                            [x_min, y_max]
                        ], dtype=np.int32)
                        
                        cv2.polylines(debug_image, [rect_points], isClosed=True, color=(0, 255, 0), thickness=2)
                
                self._display_result_image(debug_image)  # 显示带边界框的替换结果
                self.statusBar().showMessage("漫画文本替换完成")
                self.save_button.setEnabled(True)
                self._save_manga_replaced_image(replaced_image_data)  # 保存不带边界框的原始替换结果
            else:
                QMessageBox.warning(self, "警告", "漫画文本替换失败，请检查日志")
                self.statusBar().showMessage("漫画文本替换失败")
            
            # 隐藏进度条
            self.progress_bar.setVisible(False)
            self.manga_replace_button.setEnabled(True)
        except Exception as e:
            self.progress_bar.setVisible(False)
            self.manga_replace_button.setEnabled(True)
            error_msg = f"漫画文本替换失败: {str(e)}"
            QMessageBox.critical(self, "漫画替换错误", error_msg)
            self.statusBar().showMessage("漫画文本替换失败")

    def _save_manga_replaced_image(self, image_data):
        """保存漫画替换后的图片"""
        if image_data is None:
            return
        
        if self.current_image_path:
            base_name = os.path.basename(self.current_image_path)
            name, ext = os.path.splitext(base_name)
            output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{name}_replaced{ext}")
            
            try:
                cv2.imwrite(output_path, image_data)
                log.info(f"漫画替换后的图片已保存: {output_path}")
            except Exception as e:
                log.error(f"保存漫画替换后的图片失败: {e}")
        else:
            log.warning("没有当前图片路径，无法保存替换后的图片。")

    def _display_result_image(self, image_data):
        """显示处理结果图像"""
        try:
            if image_data is not None:
                height, width, channel = image_data.shape
                bytes_per_line = 3 * width
                q_image = QImage(image_data.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
                pixmap = QPixmap.fromImage(q_image)
                self.original_pixmap = pixmap # 更新原始pixmap为处理后的图像
                self._update_image_display() # 重新显示图像
            else:
                log.warning("没有图像数据可显示。")
        except Exception as e:
            log.error(f"显示结果图像时发生错误: {str(e)}")
            QMessageBox.critical(self, "显示错误", f"显示结果图像时发生错误: {str(e)}")

    def open_translation_settings(self):
        """打开翻译设置窗口"""
        settings_window = TranslationSettingsWindow(self)
        if settings_window.exec() == QDialog.Accepted:
            # 如果设置被保存，重新初始化翻译器
            self.init_translator()
            # 重新检查翻译按钮状态
            self.translate_button.setEnabled(self.translator is not None and len(self.current_results) > 0)
            log.info("翻译设置已更新，翻译器已重新初始化。")

    def save_results(self):
        """保存OCR和翻译结果到文件"""
        if not self.current_results:
            QMessageBox.warning(self, "警告", "没有OCR结果可保存")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存结果",
            "ocr_translation_results.txt",
            "文本文件 (*.txt);;所有文件 (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("--- OCR 识别结果 ---\n")
                    for i, result in enumerate(self.current_results):
                        f.write(f"文本 {i+1}: {result.text}\n")
                        f.write(f"  置信度: {result.confidence:.2f}\n")
                        f.write(f"  边界框: {result.bbox}\n")
                        if result.translated_text:
                            f.write(f"  翻译: {result.translated_text}\n")
                        f.write("\n")
                    
                    f.write("\n--- 结构化文本和翻译结果 ---\n")
                    f.write(self.translation_result.toPlainText())
                    f.write("\n\n--- 详细OCR信息 ---\n")
                    f.write(self.details_result.toPlainText())
                
                QMessageBox.information(self, "保存成功", f"结果已保存到: {file_path}")
                self.statusBar().showMessage(f"结果已保存到: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "保存错误", f"保存文件时发生错误: {str(e)}")
                self.statusBar().showMessage("保存失败")

    def on_model_loaded(self):
        """OCR模型加载完成回调"""
        self.status_label.setText("OCR引擎状态: 已加载模型")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        # 如果已经加载了图片，启用OCR按钮
        if self.current_image_path:
            self.ocr_button.setEnabled(True)
        log.info("OCR模型加载完成。")

    def on_model_load_error(self, error_msg):
        """OCR模型加载错误回调"""
        self.status_label.setText(f"OCR引擎状态: 模型加载失败 ({error_msg})")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.ocr_button.setEnabled(False)
        log.error(f"OCR模型加载失败: {error_msg}")

    def on_ocr_started(self):
        """OCR识别开始回调"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0) # 设置为不确定模式
        self.ocr_button.setEnabled(False)
        self.translate_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.manga_replace_button.setEnabled(False)
        self.text_result.clear()
        self.translation_result.clear()
        self.details_result.clear()
        self.statusBar().showMessage("正在进行OCR识别...")
        log.info("OCR识别开始。")

    def on_ocr_finished(self, results):
        """OCR识别完成回调"""
        self.progress_bar.setVisible(False)
        self.ocr_button.setEnabled(True)
        self.statusBar().showMessage("OCR识别完成")
        log.info(f"OCR识别完成，识别到 {len(results)} 个文本区域。")
        
        self.current_results = results
        
        # 显示纯文本结果
        if results:
            # 使用OCRManager的get_text_only方法获取合并后的文本
            full_text = self.ocr_manager.get_text_only(results)
            self.text_result.setText(full_text)
            self.save_button.setEnabled(True)
            
            # 启用翻译按钮
            if self.translator:
                self.translate_button.setEnabled(True)
            
            # 获取结构化文本
            structured_texts = self.ocr_manager.get_structured_text(results)

            # 显示详细结果
            details = []
            
            # 先显示结构化文本信息
            details.append("=== 结构化文本信息 ===")
            for i, item in enumerate(structured_texts, 1):
                bbox_points = []
                for ocr_result in item['ocr_results']:
                    bbox_points.extend(ocr_result.bbox)
                x_min = min(p[0] for p in bbox_points)
                y_min = min(p[1] for p in bbox_points)
                x_max = max(p[0] for p in bbox_points)
                y_max = max(p[1] for p in bbox_points)
                
                details.append(f"\n结构化文本块 #{i}:")
                details.append(f"  - 文本内容: {item['text']}")
                details.append(f"  - 方向: {item.get('direction', 'auto')}")
                details.append(f"  - 包含OCR结果数: {len(item['ocr_results'])}")
                details.append(f"  - 文本框范围: ({x_min}, {y_min}) -> ({x_max}, {y_max})")

            # 再显示原始OCR结果信息
            details.append("\n=== 原始OCR结果 ===")
            for i, r in enumerate(results):
                # 格式化文本框坐标为更易读的形式
                bbox_str = "\n    ".join([f"点{j+1}: ({x}, {y})" for j, (x, y) in enumerate(r.bbox)])
                details.append(f"\n文本 {i+1}: '{r.text}'\n"
                             f"  置信度: {r.confidence:.2f}\n"
                             f"  方向: {r.direction}\n"
                             f"  列: {r.column}\n"
                             f"  行: {r.row}\n"
                             f"  合并数: {r.merged_count}\n"
                             f"  文本框坐标:\n    {bbox_str}")
            
            # 设置详细信息文本
            self.details_result.setText("\n".join(details))
            
            # 绘制文本框到图像上并显示
            self._draw_ocr_boxes(results)
        else:
            self.text_result.setText("未识别到任何文本。")
            self.details_result.setText("未识别到任何文本。")
            self.save_button.setEnabled(False)
            self.translate_button.setEnabled(False)
            self.manga_replace_button.setEnabled(False)
            self.image_label.setPixmap(self.original_pixmap.scaled(
                self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)) # 恢复原始图片显示
            
    def on_ocr_error(self, error_msg):
        """OCR识别错误回调"""
        self.progress_bar.setVisible(False)
        self.ocr_button.setEnabled(True)
        self.translate_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.manga_replace_button.setEnabled(False)
        self.statusBar().showMessage("OCR识别失败")
        QMessageBox.critical(self, "OCR错误", error_msg)
        log.error(f"OCR识别错误: {error_msg}")

    def on_ocr_progress(self, progress_msg):
        """OCR进度回调"""
        self.statusBar().showMessage(progress_msg)

    def _draw_ocr_boxes(self, ocr_results):
        """在图像上绘制OCR文本框"""
        if self.cached_image_data is None or not ocr_results:
            return

        # 复制原始图像数据，避免修改原图
        display_image = self.cached_image_data.copy()
        
        # 获取结构化文本
        structured_texts = self.ocr_manager.get_structured_text(ocr_results)

        # 为每个结构化文本块绘制边界框
        for item in structured_texts:
            # 收集该文本块中所有OCR结果的边界点
            all_points = []
            for ocr_result in item['ocr_results']:
                all_points.extend(ocr_result.bbox)
            
            if not all_points:
                continue
                
            # 计算文本块的边界框
            x_min = min(p[0] for p in all_points)
            y_min = min(p[1] for p in all_points)
            x_max = max(p[0] for p in all_points)
            y_max = max(p[1] for p in all_points)
            
            # 创建矩形边界框的四个顶点
            rect_points = np.array([
                [x_min, y_min],  # 左上
                [x_max, y_min],  # 右上
                [x_max, y_max],  # 右下
                [x_min, y_max]   # 左下
            ], dtype=np.int32)
            
            # 直接绘制矩形边界框
            cv2.polylines(display_image, [rect_points], isClosed=True, color=(0, 255, 0), thickness=2)

        # 将OpenCV图像转换为QPixmap显示
        h, w, ch = display_image.shape
        bytes_per_line = ch * w
        q_image = QImage(display_image.data, w, h, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
        pixmap = QPixmap.fromImage(q_image)
        
        # 更新显示，让QLabel自动处理缩放
        self.image_label.setPixmap(pixmap.scaled(
            self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))


def run_as_standalone():
    """作为独立程序运行OCR测试窗口"""
    import os
    import sys
    
    # 添加项目根目录到路径
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    sys.path.insert(0, project_root)
    
    app = QApplication(sys.argv)
    window = OCRTestWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    run_as_standalone()
