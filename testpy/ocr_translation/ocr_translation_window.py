#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OCR测试窗口
提供图形界面来测试OCR功能
"""

import os
import sys
import cv2
import numpy as np
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QWidget, QFileDialog,
    QProgressBar, QSplitter, QScrollArea, QMessageBox, QDialog
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QFont, QImage, QPainter, QColor, QPen

from typing import Optional, List, Dict
# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from core.ocr_manager import OCRResult
from core.image_translator import ImageTranslator, create_image_translator
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
    from testpy.ocr_translation.translation_settings_window import TranslationSettingsWindow

class OCRTestWindow(QMainWindow):
    """OCR测试窗口"""
    
    def __init__(self):
        super().__init__()
        # 图像处理相关
        self.image_translator: Optional[ImageTranslator] = None
        self.current_image_path: Optional[str] = None
        self.cached_image_data: Optional[np.ndarray] = None
        self.original_pixmap: Optional[QPixmap] = None
        self.current_ocr_results: List[OCRResult] = [] # 存储原始OCR结果
        self.current_structured_results: List[OCRResult] = [] # 存储结构化OCR结果
        self.current_translations: Dict[str, str] = {}
        self._color_cache: Dict[int, QColor] = {}  # 用于存储文本组的颜色
        
        # 初始化组件
        self.init_ui()
        self.init_translator()

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
        self.image_label.setMinimumSize(400, 300)
        
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.image_label)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumSize(600, 400)
        
        layout.addWidget(scroll_area)
        
        return widget
    
    def create_control_area(self):
        """创建控制和结果区域"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        button_layout1 = QHBoxLayout()
        self.open_button = QPushButton("📁 打开图片")
        self.open_button.setMinimumHeight(40)
        self.open_button.clicked.connect(self.open_image)
        button_layout1.addWidget(self.open_button)

        self.ocr_button = QPushButton("🔍 开始OCR")
        self.ocr_button.setMinimumHeight(40)
        self.ocr_button.setEnabled(False)
        self.ocr_button.clicked.connect(self.start_ocr)
        button_layout1.addWidget(self.ocr_button)

        self.translate_button = QPushButton("🌐 翻译")
        self.translate_button.setMinimumHeight(40)
        self.translate_button.setEnabled(False)
        self.translate_button.clicked.connect(self.start_translation)
        button_layout1.addWidget(self.translate_button)
        
        self.settings_button = QPushButton("⚙️ 翻译设置")
        self.settings_button.setMinimumHeight(40)
        self.settings_button.clicked.connect(self.open_translation_settings)
        button_layout1.addWidget(self.settings_button)
        
        button_layout2 = QHBoxLayout()
        self.manga_replace_button = QPushButton("📚 漫画替换")
        self.manga_replace_button.setMinimumHeight(40)
        self.manga_replace_button.setEnabled(False)
        self.manga_replace_button.clicked.connect(self.start_manga_replacement)
        button_layout2.addWidget(self.manga_replace_button)
        
        layout.addLayout(button_layout1)
        layout.addLayout(button_layout2)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("OCR引擎状态: 正在初始化...")
        self.status_label.setStyleSheet("color: #666; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        results_label = QLabel("识别结果:")
        results_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(results_label)
        
        self.text_result = QTextEdit()
        self.text_result.setPlaceholderText("OCR识别的文本将显示在这里...")
        self.text_result.setMinimumHeight(200)
        layout.addWidget(self.text_result)
        
        translation_label = QLabel("翻译结果:")
        translation_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(translation_label)
        
        self.translation_result = QTextEdit()
        self.translation_result.setPlaceholderText("翻译结果将显示在这里...")
        self.translation_result.setMinimumHeight(150)
        layout.addWidget(self.translation_result)
        
        details_label = QLabel("详细信息 (结构化结果):")
        details_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(details_label)
        
        self.details_result = QTextEdit()
        self.details_result.setPlaceholderText("详细的结构化OCR结果信息将显示在这里...")
        self.details_result.setMinimumHeight(120)
        layout.addWidget(self.details_result)
        
        return widget
    
    def init_translator(self):
        """初始化翻译器"""
        try:
            translator_type = config.translator_type.value
            translator_kwargs = {}

            if translator_type == "智谱":
                api_key = config.zhipu_api_key.value
                model = config.zhipu_model.value
                if not api_key:
                    log.warning("智谱API密钥未配置，翻译功能将不可用")
                    self.status_label.setText("翻译引擎: 智谱 (API Key未配置)")
                    return
                translator_kwargs.update({"api_key": api_key, "model": model})
            
            elif translator_type == "Google":
                api_key = config.google_api_key.value
                if api_key:
                    translator_kwargs["api_key"] = api_key
            
            
                nllb_source_lang_code = config.nllb_source_lang.value
                translator_kwargs.update({
                    "nllb_model_name": nllb_model_name,
                    "nllb_source_lang_code": nllb_source_lang_code
                })
            
            else:
                log.warning(f"未知的翻译器类型: {translator_type}，使用Google翻译作为默认选项")
                translator_type = "Google" # Fallback
            
            self.image_translator = create_image_translator(
                translator_type=translator_type,
                **translator_kwargs
            )
            
            self.status_label.setText(f"翻译引擎: {translator_type} (就绪)")
            
        except Exception as e:
            log.error(f"初始化翻译器失败: {e}")
            self.status_label.setText(f"翻译引擎: 初始化失败 - {e}")
            self.image_translator = None
    
    def open_image(self):
        """打开图片文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片文件", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.tiff);;所有文件 (*)"
        )
        if file_path:
            self.load_image(file_path)
    
    def load_image(self, file_path):
        """加载并显示图片"""
        try:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "错误", "无法加载图片文件")
                return
            
            self.original_pixmap = pixmap
            self._update_image_display() # Initial display
            self.image_label.setText("")
            
            self.current_image_path = file_path
            
            # 使用 OpenCV 读取图像数据，支持中文路径
            img_array = np.fromfile(file_path, dtype=np.uint8)
            self.cached_image_data = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            if self.cached_image_data is None:
                QMessageBox.warning(self, "错误", "无法使用OpenCV读取图片数据进行OCR")
                self.current_image_path = None
                self.cached_image_data = None
                self.ocr_button.setEnabled(False)
                self.manga_replace_button.setEnabled(False)
                return

            if self.image_translator and self.image_translator.is_ready():
                self.ocr_button.setEnabled(True)
                self.manga_replace_button.setEnabled(True)
            else:
                self.ocr_button.setEnabled(False)
                self.manga_replace_button.setEnabled(False)
                log.warning("ImageTranslator 未就绪，OCR和替换按钮禁用。")

            self.text_result.clear()
            self.translation_result.clear()
            self.details_result.clear()
            self.translate_button.setEnabled(False)
            self.current_ocr_results = []
            self.current_structured_results = []
            self.current_translations = {}
            
            self.statusBar().showMessage(f"已加载图片: {os.path.basename(file_path)}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载图片时发生错误: {str(e)}")
            log.error(f"加载图片失败: {e}", exc_info=True)
            
    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        QTimer.singleShot(0, self._update_image_display)

    def _update_image_display(self, pixmap_to_display: Optional[QPixmap] = None):
        """根据当前标签大小更新图像显示"""
        try:
            display_pixmap = pixmap_to_display if pixmap_to_display else self.original_pixmap
            if display_pixmap and not display_pixmap.isNull():
                label_size = self.image_label.size()
                if label_size.width() > 0 and label_size.height() > 0:
                    scaled_pixmap = display_pixmap.scaled(
                        label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    self.image_label.setPixmap(scaled_pixmap)
                # else:
                #     log.debug(f"标签尺寸无效 ({label_size.width()}x{label_size.height()}), 暂不缩放。")
        except Exception as e:
            log.error(f"_update_image_display 发生错误: {str(e)}", exc_info=True)
    
    def start_ocr(self):
        """开始OCR识别"""
        if self.cached_image_data is None or not self.image_translator or not self.image_translator.ocr_manager:
            QMessageBox.warning(self, "警告", "请先选择图片并等待翻译器和OCR管理器准备就绪")
            return
        
        try:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0) # Indeterminate
            self.ocr_button.setEnabled(False)
            self.translate_button.setEnabled(False)
            self.manga_replace_button.setEnabled(False)
            self.statusBar().showMessage("正在进行OCR识别...")
            
            # 1. 获取原始OCR结果
            self.current_ocr_results = self.image_translator.get_ocr_results(
                self.cached_image_data,
                file_path_for_cache=self.current_image_path,
                page_num_for_cache=0 
            )
            
            # 2. 过滤
            filtered_results = self.image_translator.ocr_manager.filter_numeric_and_symbols(self.current_ocr_results)
            filtered_results = self.image_translator.ocr_manager.filter_by_confidence(filtered_results, config.ocr_confidence_threshold.value)

            # 3. 获取结构化文本 (List[OCRResult])
            self.current_structured_results = self.image_translator.ocr_manager.get_structured_text(filtered_results)
            
            if self.current_structured_results:
                # 显示主要文本结果 (来自结构化结果)
                full_text = "\n".join([res.text for res in self.current_structured_results])
                self.text_result.setText(full_text)
                
                # 显示详细OCR信息 (来自结构化结果)
                details = []
                for i, result in enumerate(self.current_structured_results, 1): # result is OCRResult
                    bbox_str = "\n    ".join([f"点{j+1}: ({x}, {y})" for j, (x, y) in enumerate(result.bbox)])
                    
                    details.append(
                        f"\n结构化文本块 {i}: '{result.text}'\n"
                        f"  置信度: {result.confidence:.2f}\n"
                        f"  方向: {result.direction if result.direction else '未知'}\n"
                        f"  合并数量: {result.merged_count}\n" # 显示原始组成部分的数量
                        f"  文本框坐标 (BBox):\n    {bbox_str}"
                    )
                self.details_result.setText("\n".join(details))
                
                self._draw_ocr_boxes_from_structured(self.current_structured_results)
                
                self.translate_button.setEnabled(True)
                self.manga_replace_button.setEnabled(True) # 即使没有翻译也可以尝试替换
            else:
                self.text_result.setText("未识别到任何有效文本。")
                self.details_result.setText("未识别到任何有效文本。")
                self._update_image_display() # 显示原图
            
            self.statusBar().showMessage(
                f"OCR识别完成，共识别到 {len(self.current_structured_results or [])} 个结构化文本区域"
            )
            
        except Exception as e:
            error_msg = f"OCR识别失败: {str(e)}"
            QMessageBox.critical(self, "OCR错误", error_msg)
            self.statusBar().showMessage("OCR识别失败")
            log.error(error_msg, exc_info=True)
        finally:
            self.progress_bar.setVisible(False)
            self.ocr_button.setEnabled(True)
    
    def start_translation(self):
        """开始翻译OCR结果"""
        if not self.current_structured_results or not self.image_translator:
            QMessageBox.warning(self, "警告", "请先进行OCR识别并获得结构化结果")
            return
            
        try:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.translate_button.setEnabled(False)
            self.statusBar().showMessage("正在翻译识别结果...")

            texts_to_translate = [res.text for res in self.current_structured_results if res.text.strip()]
            if not texts_to_translate:
                QMessageBox.information(self, "提示", "没有需要翻译的文本。")
                self.translation_result.clear()
                return

            translated_map = {}
            # 批量翻译（如果翻译器支持）或逐个翻译
            if hasattr(self.image_translator.translator, 'translate_batch') and callable(getattr(self.image_translator.translator, 'translate_batch')):
                try:
                    log.info(f"使用批量翻译接口翻译 {len(texts_to_translate)} 条文本...")
                    translated_list = self.image_translator.translator.translate_batch(texts_to_translate, target_lang="zh")
                    translated_map = dict(zip(texts_to_translate, translated_list))
                except Exception as batch_e:
                    log.warning(f"批量翻译失败 ({batch_e})，尝试逐条翻译...")
                    # Fallback to individual translation
                    for i, text in enumerate(texts_to_translate):
                        try:
                            translated_map[text] = self.image_translator.translate_text(text, target_language="zh")
                        except Exception as e_single:
                            log.error(f"单条翻译失败: {text} - {e_single}")
                            translated_map[text] = f"[翻译失败: {text}]"
            else:
                for i, text in enumerate(texts_to_translate):
                    try:
                        translated_map[text] = self.image_translator.translate_text(text, target_language="zh")
                    except Exception as e_single:
                        log.error(f"单条翻译失败: {text} - {e_single}")
                        translated_map[text] = f"[翻译失败: {text}]"
            
            self.current_translations = translated_map # 存储所有翻译，包括失败的

            # 更新 current_structured_results 中的 translated_text
            for res in self.current_structured_results:
                res.translated_text = self.current_translations.get(res.text, res.text) # 如果翻译失败，使用原文

            display_texts = []
            success_count = 0
            for i, res in enumerate(self.current_structured_results, 1):
                original = res.text
                translated = res.translated_text
                if not translated.startswith("[翻译失败"):
                    success_count +=1
                display_texts.append(f"{i}. {original} -> {translated}")

            self.translation_result.setText("\n".join(display_texts))
            
            total = len(self.current_structured_results)
            status_msg = f"翻译完成，成功率: {success_count}/{total} ({(success_count/total*100 if total > 0 else 0):.1f}%)"
            self.statusBar().showMessage(status_msg)
            log.info(status_msg)
            
        except Exception as e:
            error_msg = f"翻译过程发生错误: {str(e)}"
            QMessageBox.critical(self, "翻译错误", error_msg)
            self.statusBar().showMessage("翻译失败")
            log.error(error_msg, exc_info=True)
        finally:
            self.progress_bar.setVisible(False)
            self.translate_button.setEnabled(True)
            # manga_replace_button 应该在OCR后就启用，翻译是可选的
            if self.current_structured_results:
                 self.manga_replace_button.setEnabled(True)
    
    def start_manga_replacement(self):
        """开始漫画文本替换"""
        if not self.image_translator or self.cached_image_data is None:
            QMessageBox.warning(self, "警告", "请先选择图片并确保翻译器就绪")
            return
        
        if not self.current_structured_results:
            QMessageBox.information(self, "提示", "没有OCR结果可供替换。请先执行OCR。")
            # 尝试执行一次OCR
            self.start_ocr()
            if not self.current_structured_results: # 如果OCR后仍然没有结果
                return


        try:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.manga_replace_button.setEnabled(False)
            self.statusBar().showMessage("正在执行漫画文本替换...")
            
            # 使用 self.current_structured_results (List[OCRResult])
            # 和 self.current_translations (Dict[str, str])
            # ImageTranslator.translate_image 内部会调用 MangaTextReplacer
            # 它需要 List[OCRResult] 和 Dict[str, str]
            
            # 为了让 translate_image 复用已有的OCR和翻译结果，构造 ocr_options
            ocr_options_for_replacement = {
                "results": self.current_structured_results, # 这是 List[OCRResult]
                "reuse_results": True 
            }
            
            # translate_image 内部会处理翻译，但我们已经有翻译了
            # MangaTextReplacer.process_manga_image 会使用传入的 structured_texts 和 translations
            # 所以我们直接调用 translate_image，它会把这些传递下去

            replaced_image_data = self.image_translator.translate_image(
                self.cached_image_data, # 原始图像数据
                target_language="zh", # 目标语言
                ocr_options=ocr_options_for_replacement, # 传递结构化结果以复用
                # file_path_for_cache, page_num_for_cache 等在 translate_image 内部处理
                file_path_for_cache=self.current_image_path,
                page_num_for_cache=0
            )
            
            if replaced_image_data is not None:
                self._display_result_image(replaced_image_data)
                self.statusBar().showMessage("漫画文本替换完成")
                InfoBar.success("成功", "漫画文本替换完成！", parent=self, position=InfoBarPosition.TOP, duration=3000)
            else:
                QMessageBox.warning(self, "替换失败", "漫画文本替换未能生成图像。")
                self.statusBar().showMessage("漫画文本替换失败")
                self._update_image_display() # 显示原图
            
        except Exception as e:
            error_msg = f"漫画文本替换失败: {str(e)}"
            QMessageBox.critical(self, "替换错误", error_msg)
            self.statusBar().showMessage("漫画文本替换失败")
            log.error(error_msg, exc_info=True)
            self._update_image_display() # 显示原图
        finally:
            self.progress_bar.setVisible(False)
            self.manga_replace_button.setEnabled(True)
    
    def _display_result_image(self, image_data: np.ndarray):
        """显示处理结果图像"""
        try:
            if image_data is None or image_data.size == 0:
                log.warning("尝试显示的图像数据为空。")
                return

            height, width, channel = image_data.shape
            bytes_per_line = 3 * width
            q_image = QImage(image_data.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
            
            pixmap = QPixmap.fromImage(q_image)
            if pixmap.isNull():
                log.error("从QImage创建QPixmap失败。")
                return
            
            # 更新 original_pixmap 为结果图像，以便缩放
            self.original_pixmap = pixmap 
            self._update_image_display(pixmap_to_display=pixmap)

        except Exception as e:
            log.error(f"显示结果图像时出错: {e}", exc_info=True)
            QMessageBox.warning(self, "显示错误", f"无法显示结果图像: {e}")

    def _draw_ocr_boxes_from_structured(self, structured_results: List[OCRResult]):
        """在图片上绘制结构化OCR结果的边界框"""
        if self.original_pixmap is None or self.original_pixmap.isNull():
            return

        # 创建一个可编辑的副本
        temp_pixmap = self.original_pixmap.copy()
        painter = QPainter(temp_pixmap)
        
        # 坐标已经是相对于 original_pixmap 的，无需在此处进行额外的缩放/偏移计算。
        # _update_image_display 会负责将带有绘制框的 temp_pixmap 整体缩放到标签大小。

        for i, result in enumerate(structured_results): # result is OCRResult
            color = self._generate_distinct_colors(i)
            pen = QPen(color, 2) # 画笔宽度为2
            painter.setPen(pen)
            
            # result.bbox 是 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            # 这些是相对于原始图像的坐标
            points = result.bbox
            if len(points) == 4:
                # 直接使用原始坐标在 temp_pixmap (original_pixmap的副本) 上绘制
                for k in range(4):
                    p1_coords = points[k]
                    p2_coords = points[(k + 1) % 4]
                    painter.drawLine(int(p1_coords[0]), int(p1_coords[1]), 
                                     int(p2_coords[0]), int(p2_coords[1]))
                
                # 可选：在框旁边绘制文本编号 (使用原始坐标)
                # text_x = int(points[0][0])
                # text_y = int(points[0][1]) - 5 # 向上偏移一点
                # current_font = painter.font()
                # # 可以考虑设置一个固定的、较小的字体大小，或者根据图像的某种比例来调整
                # # 例如，如果图像很大，一个绝对大小为10的字体可能太小
                # # current_font.setPointSize(10) # 示例：固定大小
                # painter.setFont(current_font)
                # painter.drawText(text_x, text_y, str(i + 1))

        painter.end()
        self._update_image_display(pixmap_to_display=temp_pixmap)


    def open_translation_settings(self):
        """打开翻译设置对话框"""
        # 确保 image_translator 已初始化
        if not self.image_translator:
            self.init_translator() # 尝试重新初始化
            if not self.image_translator:
                QMessageBox.warning(self, "错误", "翻译器未能初始化，无法打开设置。")
                return

        settings_dialog = TranslationSettingsWindow(parent=self)
        if settings_dialog.exec(): # exec() 是模态对话框
            log.info("翻译设置已更新，重新初始化翻译器...")
            self.init_translator() # 设置更改后重新初始化翻译器
            # 可能需要根据新的翻译器状态更新UI，例如按钮的启用状态
            if self.image_translator and self.image_translator.is_ready() and self.cached_image_data is not None:
                self.ocr_button.setEnabled(True)
                self.manga_replace_button.setEnabled(True)
                if self.current_structured_results:
                    self.translate_button.setEnabled(True)
            else:
                self.ocr_button.setEnabled(False)
                self.translate_button.setEnabled(False)
                self.manga_replace_button.setEnabled(False)


    def _generate_distinct_colors(self, index: int) -> QColor:
        """生成易于区分的颜色"""
        if index in self._color_cache:
            return self._color_cache[index]

        # 使用HSV颜色空间生成颜色，饱和度和亮度固定，只改变色调
        hue = (index * (360 / 10)) % 360  # 例如每10个索引循环一次色调
        color = QColor.fromHsv(hue, 200, 220) # 鲜艳的颜色
        self._color_cache[index] = color
        return color

def run_as_standalone():
    """作为独立应用运行"""
    # 初始化日志记录器 # 这行将被移除
    # log.init_logger(config.log_level.value, config.log_file.value) # 这行将被移除
    log.info("OCR测试工具启动...")

    app = QApplication(sys.argv)
    window = OCRTestWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    run_as_standalone()
