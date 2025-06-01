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
from PySide6.QtGui import QPixmap, QFont, QImage

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
    from ui.ocr_translation.translation_settings_window import TranslationSettingsWindow


class OCRTestWindow(QMainWindow):
    """OCR测试窗口"""
    
    def __init__(self):
        super().__init__()
        # 图像处理相关
        self.image_translator = None
        self.current_image_path = None
        self.cached_image_data = None
        self.original_pixmap = None
        self.current_results = []
        self.current_translations = {}
        self._color_cache = {}  # 用于存储文本组的颜色
        
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
    
    def init_translator(self):
        """初始化翻译器"""
        try:
            # 获取翻译器类型和配置
            translator_type = config.translator_type.value
            translator_kwargs = {}

            # 根据不同的翻译器类型，准备相应的参数
            if translator_type == "智谱":
                api_key = config.zhipu_api_key.value
                model = config.zhipu_model.value
                if not api_key:
                    log.warning("智谱API密钥未配置，翻译功能将不可用")
                    return
                translator_kwargs.update({"api_key": api_key, "model": model})
            
            elif translator_type == "Google":
                api_key = config.google_api_key.value
                if api_key:  # Google API密钥是可选的
                    translator_kwargs["api_key"] = api_key
            
            else:
                log.warning(f"未知的翻译器类型: {translator_type}，使用Google翻译作为默认选项")
                translator_type = "Google"
            
            # 创建图片翻译器实例
            self.image_translator = ImageTranslator(
                translator_type=translator_type,
                **translator_kwargs
            )
            
            # 更新状态标签
            self.status_label.setText(f"翻译引擎: {translator_type}")
            
        except Exception as e:
            log.error(f"初始化翻译器失败: {e}")
            self.status_label.setText("翻译引擎: 初始化失败")
            self.image_translator = None
    
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
                return                # 启用OCR和漫画替换按钮
            if self.image_translator:
                self.ocr_button.setEnabled(True)
                self.manga_replace_button.setEnabled(True)
            
            # 清空之前的结果
            self.text_result.clear()
            self.translation_result.clear()
            self.details_result.clear()
            self.translate_button.setEnabled(False)
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
        if self.cached_image_data is None or not self.image_translator:
            QMessageBox.warning(self, "警告", "请先选择图片并等待翻译器准备就绪")
            return
        
        try:
            # 更新UI状态
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.ocr_button.setEnabled(False)
            self.statusBar().showMessage("正在进行OCR识别...")
            
            # 使用ImageTranslator执行OCR
            self.current_results = self.image_translator.get_ocr_results(self.cached_image_data)
            
            # 过滤纯数字和符号文本
            self.current_results = self.image_translator.ocr_manager.filter_numeric_and_symbols(self.current_results)
            
            # 对OCR结果进行结构性文本合并
            if self.current_results:
                self.current_results = self.image_translator.ocr_manager.get_structured_text(self.current_results)
            
            if self.current_results:
                # 显示主要文本结果
                full_text = "\n".join([r['text'] for r in self.current_results])
                self.text_result.setText(full_text)
                
                # 显示详细OCR信息
                details = []
                for i, result in enumerate(self.current_results, 1):
                    # 获取第一个OCR结果的边界框作为示例
                    bbox = result['ocr_results'][0].bbox if result['ocr_results'] else []
                    bbox_str = "\n    ".join([f"点{j+1}: ({x}, {y})" 
                                            for j, (x, y) in enumerate(bbox)])
                    
                    # 收集所有OCR结果的置信度
                    confidences = [ocr.confidence for ocr in result['ocr_results']]
                    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                    
                    details.append(
                        f"\n文本组 {i}: '{result['text']}'\n"
                        f"  平均置信度: {avg_confidence:.2f}\n"
                        f"  类型: {result['direction'] if 'direction' in result else '未知'}\n"
                        f"  包含 {len(result['ocr_results'])} 个OCR结果\n"
                        f"  示例文本框坐标:\n    {bbox_str}"
                    )
                
                self.details_result.setText("\n".join(details))
                
                # 在图像上绘制OCR框并显示
                self._draw_ocr_boxes(self.current_results)
                
                # 启用后续操作按钮
                self.translate_button.setEnabled(True)
            else:
                self.text_result.setText("未识别到任何文本。")
                self.details_result.setText("未识别到任何文本。")
            
            # 恢复UI状态
            self.progress_bar.setVisible(False)
            self.ocr_button.setEnabled(True)
            self.statusBar().showMessage(
                f"OCR识别完成，共识别到 {len(self.current_results or [])} 个文本区域"
            )
            
        except Exception as e:
            error_msg = f"OCR识别失败: {str(e)}"
            self.progress_bar.setVisible(False)
            self.ocr_button.setEnabled(True)
            QMessageBox.critical(self, "OCR错误", error_msg)
            self.statusBar().showMessage("OCR识别失败")
            log.error(error_msg)
    
    def start_translation(self):
        """开始翻译OCR结果"""
        if not self.current_results or not self.image_translator:
            QMessageBox.warning(self, "警告", "请先进行OCR识别")
            return
            
        try:
            # 更新UI状态
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.translate_button.setEnabled(False)
            self.statusBar().showMessage("正在翻译识别结果...")

            # 使用ImageTranslator批量翻译文本
            success_count = 0
            translated_texts = []
            total = len(self.current_results)
            
            # 处理结构化文本列表
            for i, result in enumerate(self.current_results, 1):
                try:
                    # 从结构化文本中获取完整文本
                    original_text = result['text']  # 结构化文本中的完整文本
                    # 翻译单个文本
                    translated = self.image_translator.translate_text(original_text)
                    translated_texts.append(f"{i}. {original_text} -> {translated}")
                    success_count += 1
                except Exception as e:
                    log.error(f"翻译失败 [{i}/{total}]: {original_text} - {str(e)}")
                    translated_texts.append(f"{i}. {original_text} -> [翻译失败]")

            # 显示翻译结果
            self.translation_result.setText("\n".join(translated_texts))
            
            # 更新UI状态
            self.manga_replace_button.setEnabled(success_count > 0)
            self.progress_bar.setVisible(False)
            self.translate_button.setEnabled(True)
            
            # 更新状态栏信息
            status_msg = (
                f"翻译完成，成功率: {success_count}/{total} "
                f"({(success_count/total*100):.1f}%)"
            )
            self.statusBar().showMessage(status_msg)
            log.info(status_msg)
            
        except Exception as e:
            error_msg = f"翻译过程发生错误: {str(e)}"
            self.progress_bar.setVisible(False)
            self.translate_button.setEnabled(True)
            QMessageBox.critical(self, "翻译错误", error_msg)
            self.statusBar().showMessage("翻译失败")
            log.error(error_msg)
    
    def start_manga_replacement(self):
        """开始漫画文本替换"""
        if not self.image_translator or self.cached_image_data is None:
            QMessageBox.warning(self, "警告", "请先选择图片")
            return
            
        try:
            # 更新UI状态
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.manga_replace_button.setEnabled(False)
            self.statusBar().showMessage("正在执行漫画文本替换...")
            
            # 准备OCR选项，如果有现成的OCR结果就复用
            ocr_options = None
            if self.current_results:
                ocr_options = {
                    "results": self.current_results,
                    "reuse_results": True  # 标记复用OCR结果
                }
            
            # 使用ImageTranslator执行替换
            replaced_image = self.image_translator.translate_image(
                self.cached_image_data,
                target_language="zh",
                ocr_options=ocr_options
            )
            
            if replaced_image is not None:
                # 显示替换后的图像
                self._display_result_image(replaced_image)
                
                # 如果有原始图像路径，保存结果
                if self.current_image_path:
                    base_name = os.path.basename(self.current_image_path)
                    name, ext = os.path.splitext(base_name)
                    output_dir = os.path.join(os.path.dirname(self.current_image_path), "output")
                    os.makedirs(output_dir, exist_ok=True)
                    
                    # 生成输出路径
                    output_path = os.path.join(output_dir, f"{name}_replaced{ext}")
                    if cv2.imwrite(output_path, replaced_image):
                        msg = f"替换后的图片已保存至: {output_path}"
                        log.info(msg)
                        self.statusBar().showMessage(msg)
                    else:
                        raise RuntimeError("保存替换后的图片失败")
            else:
                raise RuntimeError("图像处理失败，未能生成替换结果")
                
            # 恢复UI状态
            self.progress_bar.setVisible(False)
            self.manga_replace_button.setEnabled(True)
            
        except Exception as e:
            error_msg = f"漫画文本替换失败: {str(e)}"
            self.progress_bar.setVisible(False)
            self.manga_replace_button.setEnabled(True)
            QMessageBox.critical(self, "替换错误", error_msg)
            self.statusBar().showMessage("漫画文本替换失败")
            log.error(error_msg)
    
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

    def _draw_ocr_boxes(self, ocr_results):
        """在图像上绘制OCR文本框，并为每个文本区域添加半透明彩色背景，保持文本居中对齐"""
        if self.cached_image_data is None or not ocr_results:
            return

        # 创建图像副本以进行绘制
        result_image = self.cached_image_data.copy()
        
        # 生成不同的颜色用于不同的文本区域
        colors = self._generate_distinct_colors(len(ocr_results))
        
        # 为每个文本区域绘制半透明背景和边框
        for i, result in enumerate(ocr_results):
            color = colors[i]  # 当前文本区域的颜色
            
            # 从结果中获取所有OCR结果的边界框点
            all_points = []
            for ocr_result in result['ocr_results']:
                all_points.extend(ocr_result.bbox)
            
            if all_points:
                # 转换为numpy数组以便计算
                points = np.array(all_points).reshape(-1, 2)
                
                # 计算包含所有点的最小矩形
                x_min = int(np.min(points[:, 0]))
                y_min = int(np.min(points[:, 1]))
                x_max = int(np.max(points[:, 0]))
                y_max = int(np.max(points[:, 1]))

                # 计算文本区域的宽度和高度
                width = x_max - x_min
                height = y_max - y_min

                # 对于每个子文本框，计算其在文本区域内的相对位置
                for ocr_result in result['ocr_results']:
                    points = np.array(ocr_result.bbox).reshape(-1, 2)
                    sub_x_min = int(np.min(points[:, 0]))
                    sub_x_max = int(np.max(points[:, 0]))
                    sub_width = sub_x_max - sub_x_min

                    # 计算子文本框的水平中心点
                    sub_center_x = (sub_x_min + sub_x_max) // 2
                    # 计算整个文本区域的水平中心点
                    center_x = (x_min + x_max) // 2
                    # 计算需要的水平偏移量
                    offset_x = center_x - sub_center_x

                    # 如果是竖排文本（direction为'vertical'），特殊处理
                    if result.get('direction') == 'vertical':
                        # 对于竖排文本，我们保持垂直对齐
                        points[:, 0] += offset_x
                
                # 创建一个与原图相同大小的透明遮罩
                overlay = result_image.copy()
                
                # 绘制半透明背景矩形
                cv2.rectangle(overlay, (x_min, y_min), (x_max, y_max), color, -1)
                
                # 应用透明度（alpha为0.3表示30%不透明度）
                alpha = 0.3
                cv2.addWeighted(overlay, alpha, result_image, 1 - alpha, 0, result_image)
                
                # 绘制实线边框
                cv2.rectangle(result_image, (x_min, y_min), (x_max, y_max), color, 2)

        # 显示处理后的图像
        self._display_result_image(result_image)
    
    def open_translation_settings(self):
        """打开翻译设置窗口"""
        dialog = TranslationSettingsWindow(self)
        if dialog.exec() == QDialog.Accepted:
            # 如果用户更改了设置并点击确定，重新初始化翻译器
            self.init_translator()
            if self.image_translator:
                self.status_label.setText(f"翻译引擎: {config.translator_type.value}")
            else:
                self.status_label.setText("翻译引擎: 未就绪")
    
    def _generate_distinct_colors(self, n):
        """生成n个有区分度的颜色"""
        if n in self._color_cache:
            return self._color_cache[n]
        
        import colorsys
        colors = []
        for i in range(n):
            # 使用HSV色彩空间来生成均匀分布的颜色
            hue = i / n
            sat = 0.7  # 适中的饱和度
            val = 0.95  # 较高的亮度
            # 转换到RGB色彩空间
            rgb = colorsys.hsv_to_rgb(hue, sat, val)
            # 转换为BGR并缩放到0-255 范围
            bgr = (int(rgb[2] * 255), int(rgb[1] * 255), int(rgb[0] * 255))
            colors.append(bgr)
        
        self._color_cache[n] = colors
        return colors


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
