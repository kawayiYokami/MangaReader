# OCR管理器 (OCRManager)

## 概述

OCRManager 是一个专门为漫画项目设计的OCR（光学字符识别）核心类，集成了高性能的 OnnxOCR 引擎，提供完整的图像文字识别功能。

## 主要特性

### 🔍 高精度识别
- 基于 PaddleOCR 的 ONNX 模型
- 支持中文、英文、日文等多语言识别
- 识别精度高，速度快

### ⚡ 异步处理
- 支持异步和同步两种识别模式
- 不阻塞主线程，适合GUI应用
- 提供完整的信号系统

### 🎯 灵活配置
- 可配置文本检测、识别、角度分类
- 支持GPU加速（需要相应运行时）
- 丰富的参数选项

### 📊 结果处理
- 置信度过滤
- 文本提取和合并
- 坐标信息获取
- 结果可视化

## 快速开始

### 1. 基本使用示例

```python
from core.ocr_manager import OCRManager
import time

# 创建OCR管理器
ocr_manager = OCRManager()

# 加载模型
ocr_manager.load_model()

# 等待模型加载完成
while not ocr_manager.is_ready():
    time.sleep(0.1)

# 同步识别
results = ocr_manager.recognize_image_sync("image.jpg")

# 显示结果
for result in results:
    print(f"文本: {result.text}")
    print(f"置信度: {result.confidence}")
    print(f"坐标: {result.bbox}")
```

### 2. 异步使用示例

```python
from PySide6.QtWidgets import QApplication
from core.ocr_manager import OCRManager

app = QApplication([])
ocr_manager = OCRManager()

# 连接信号
ocr_manager.ocr_finished.connect(lambda results: print(f"识别完成: {len(results)}个结果"))

# 加载模型并识别
ocr_manager.load_model()
ocr_manager.recognize_image("image.jpg")

app.exec()
```

## 核心类说明

### OCRResult 类
```python
class OCRResult:
    def __init__(self, text: str, bbox: List[List[int]], confidence: float):
        self.text = text          # 识别的文本
        self.bbox = bbox          # 文本框坐标
        self.confidence = confidence  # 置信度
```

### OCRManager 类

#### 主要方法

- `load_model(options=None)` - 加载OCR模型
- `recognize_image(image_path, options=None)` - 异步识别图像
- `recognize_image_sync(image_path, options=None)` - 同步识别图像
- `get_text_only(results)` - 提取纯文本
- `filter_by_confidence(results, min_confidence)` - 置信度过滤
- `save_ocr_result_image(image, results, output_path)` - 保存标注图像

#### 信号

- `model_loaded` - 模型加载完成
- `model_load_error(str)` - 模型加载错误
- `ocr_started` - OCR开始
- `ocr_finished(list)` - OCR完成
- `ocr_error(str)` - OCR错误
- `ocr_progress(str)` - OCR进度

## 测试和演示

### 运行测试
```bash
python test_ocr_manager.py
```

### 运行演示
```bash
python demo_ocr.py
```

## 依赖要求

核心依赖：
- `PySide6` - Qt界面框架
- `opencv-python` - 图像处理
- `numpy` - 数值计算
- `onnxruntime` - ONNX运行时

OnnxOCR依赖：
- `shapely` - 几何计算
- `pyclipper` - 多边形裁剪
- `scikit-image` - 图像处理
- `imgaug` - 图像增强

## 项目集成

### 在MangaManager中使用

```python
class MangaManager(QObject):
    def __init__(self):
        super().__init__()
        # 添加OCR管理器
        self.ocr_manager = OCRManager(self)
        self.ocr_manager.model_loaded.connect(self.on_ocr_ready)
        self.ocr_manager.load_model()
    
    def recognize_current_page(self):
        """识别当前页面文字"""
        if self.current_manga and self.ocr_manager.is_ready():
            current_page = self.current_manga.pages[self.current_page_index]
            self.ocr_manager.recognize_image(current_page)
```

### 在界面中使用

```python
def on_ocr_button_clicked(self):
    """OCR按钮点击事件"""
    self.manga_manager.recognize_current_page()

def on_ocr_finished(self, results):
    """OCR完成回调"""
    text = self.manga_manager.ocr_manager.get_text_only(results)
    self.text_display.setText(text)
```

## 性能优化

1. **模型预加载**: 应用启动时预先加载模型
2. **图像预处理**: 适当的图像预处理可提高识别精度
3. **批量处理**: 使用队列进行批量识别
4. **结果缓存**: 缓存识别结果避免重复计算

## 文件结构

```
core/
├── ocr_manager.py          # OCR管理器核心类
├── __init__.py            # 模块导出
└── ...

docs/
└── ocr_usage_guide.md     # 详细使用指南

test_ocr_manager.py        # 完整测试脚本
demo_ocr.py               # 简单演示脚本
README_OCR.md             # 本文件
```

## 注意事项

1. OCRManager 需要在Qt应用环境中运行
2. 首次使用需要等待模型加载完成
3. 大图像识别可能需要较长时间
4. GPU加速需要安装 `onnxruntime-gpu`

## 示例输出

```
🚀 OCR管理器演示开始...
📦 正在加载OCR模型...
✅ OCR模型加载完成！

🖼️ 正在识别图像: OnnxOCR/onnxocr/test_images/1.jpg
⏱️ 识别耗时: 0.12秒
📝 识别到 2 个文本区域:
  1. '土地整治与土壤修复研究中心' (置信度: 0.989)
  2. '华南农业大学—东园' (置信度: 0.892)

📄 合并文本:
土地整治与土壤修复研究中心
华南农业大学—东园
🎯 高置信度结果: 2/2

🎉 OCR演示完成！
```

## 更多信息

详细的使用指南请参考：[docs/ocr_usage_guide.md](docs/ocr_usage_guide.md)