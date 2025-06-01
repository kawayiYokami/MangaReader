#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试文件：漫画批量翻译GUI
用于测试压缩包中的漫画批量翻译功能
"""

import os
import sys
import zipfile
import tempfile
from pathlib import Path
from typing import List, Optional
from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                            QWidget, QFileDialog, QProgressBar, QLabel)
from PySide6.QtCore import Qt, QThread, Signal

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.image_translator import create_image_translator
from utils import manga_logger as log


class TranslationWorker(QThread):
    """翻译工作线程"""
    progress = Signal(int, str)  # 进度信号：(进度值, 状态信息)
    finished = Signal(str)       # 完成信号：输出文件路径
    error = Signal(str)          # 错误信号：错误信息

    def __init__(self, zip_path: str, target_language: str = "zh"):
        super().__init__()
        self.zip_path = zip_path
        self.target_language = target_language
        self.temp_dir = None
        self.translator = None

    def run(self):
        try:
            # 1. 创建临时目录
            self.temp_dir = tempfile.mkdtemp(prefix="manga_translate_")
            extract_dir = os.path.join(self.temp_dir, "input")
            output_dir = os.path.join(self.temp_dir, "output")
            os.makedirs(extract_dir, exist_ok=True)
            os.makedirs(output_dir, exist_ok=True)

            # 2. 解压文件
            self.progress.emit(0, "正在解压文件...")
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            # 3. 获取所有图片文件（不区分大小写）
            image_extensions = ['.jpg', '.jpeg', '.png', '.webp']
            image_files = []
            for file_path in Path(extract_dir).rglob('*'):
                if file_path.suffix.lower() in image_extensions:
                    image_files.append(file_path)
            
            # 删除重复项（如果有）
            image_files = list(set(image_files))
            
            if not image_files:
                self.error.emit("压缩包中未找到图片文件")
                return

            # 4. 初始化翻译器
            self.progress.emit(10, "初始化翻译器...")
            self.translator = create_image_translator("智谱")  # 或使用其他翻译器

            # 5. 准备翻译
            total_files = len(image_files)
            self.progress.emit(15, f"找到 {total_files} 个图片文件，开始翻译...")

            # 准备输入和输出路径
            input_paths = [str(f) for f in image_files]
            output_paths = []
            for f in image_files:
                rel_path = f.relative_to(extract_dir)
                out_path = os.path.join(output_dir, str(rel_path))
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                output_paths.append(out_path)

            # 6. 批量翻译
            try:
                self.translator.batch_translate_images_optimized(
                    input_paths,
                    output_paths=output_paths,
                    target_language=self.target_language
                )
            except Exception as e:
                self.error.emit(f"翻译过程出错: {e}")
                return

            # 7. 创建新的压缩包
            self.progress.emit(90, "正在打包翻译结果...")
            output_zip_path = self._create_output_zip(output_dir)

            # 完成
            self.progress.emit(100, "翻译完成！")
            self.finished.emit(output_zip_path)

        except Exception as e:
            self.error.emit(f"处理过程出错: {e}")
        finally:
            # 清理临时文件
            if self.temp_dir and os.path.exists(self.temp_dir):
                import shutil
                try:
                    shutil.rmtree(self.temp_dir)
                except Exception as e:
                    log.error(f"清理临时文件失败: {e}")

    def _create_output_zip(self, output_dir: str) -> str:
        """创建输出压缩包"""
        zip_name = os.path.splitext(os.path.basename(self.zip_path))[0]
        output_zip_path = os.path.join(
            os.path.dirname(self.zip_path),
            f"{zip_name}_translated.zip"
        )

        with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(output_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, output_dir)
                    zipf.write(file_path, arcname)

        return output_zip_path


class MangaTranslatorWindow(QMainWindow):
    """漫画翻译器主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("漫画翻译器")
        self.setMinimumSize(400, 200)
        
        # 初始化UI
        self._init_ui()
        
        self.worker = None

    def _init_ui(self):
        """初始化UI界面"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QVBoxLayout(central_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 添加控件
        self.status_label = QLabel("请选择要翻译的漫画压缩包")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.select_button = QPushButton("选择文件")
        self.select_button.clicked.connect(self._on_select_file)
        layout.addWidget(self.select_button)

    def _on_select_file(self):
        """选择文件按钮点击事件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择漫画压缩包",
            "",
            "ZIP Files (*.zip)"
        )
        
        if not file_path:
            return
            
        self._start_translation(file_path)

    def _start_translation(self, zip_path: str):
        """开始翻译过程"""
        # 禁用按钮
        self.select_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 创建并启动工作线程
        self.worker = TranslationWorker(zip_path)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, value: int, message: str):
        """进度更新处理"""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)

    def _on_finished(self, output_path: str):
        """翻译完成处理"""
        self.status_label.setText(f"翻译完成！输出文件：{output_path}")
        self.select_button.setEnabled(True)
        self.progress_bar.setVisible(False)

    def _on_error(self, error_message: str):
        """错误处理"""
        self.status_label.setText(f"错误：{error_message}")
        self.select_button.setEnabled(True)
        self.progress_bar.setVisible(False)


def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = MangaTranslatorWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
