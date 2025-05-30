# 图片翻译模块使用指南

## 概述

`ImageTranslator` 是一个独立的图片翻译处理模块，整合了OCR识别、文本翻译和漫画文本替换功能。它可以接受一张图片，返回翻译后被替换进去的图片，方便其他功能调用。

## 主要功能

- **OCR文字识别**: 使用ONNX PaddleOCR引擎识别图片中的文字
- **多语言翻译**: 支持智谱、Google、DeepL、百度、MyMemory等翻译服务
- **智能文本替换**: 自动检测文本方向，智能布局替换文字
- **批量处理**: 支持批量翻译多张图片
- **简单易用**: 提供简洁的API接口

## 安装依赖

确保已安装以下依赖：

```bash
pip install opencv-python
pip install pillow
pip install numpy
pip install deep-translator
pip install requests
```

## 快速开始

### 基础使用

```python
from core.image_translator import create_image_translator

# 创建翻译器（使用Google翻译，无需API密钥）
translator = create_image_translator("Google")

# 翻译单张图片
result_path = translator.translate_image_simple(
    image_path="input.jpg",
    output_dir="output",
    target_language="zh"
)

print(f"翻译完成: {result_path}")
```

### 高级使用

```python
import cv2
from core.image_translator import ImageTranslator

# 使用智谱翻译器
translator = ImageTranslator(
    translator_type="智谱",
    api_key="your_api_key",
    model="glm-4-flash"
)

# 读取图片数据
image_data = cv2.imread("input.jpg")

# 直接传入图片数据进行翻译
result_image = translator.translate_image(
    image_input=image_data,
    target_language="zh",
    output_path="output/result.jpg",
    save_original=True
)
```

## API 参考

### ImageTranslator 类

#### 初始化

```python
ImageTranslator(translator_type="Google", **translator_kwargs)
```

**参数:**
- `translator_type`: 翻译器类型 ("智谱", "Google", "DeepL", "百度", "MyMemory")
- `**translator_kwargs`: 翻译器相关参数
  - 智谱: `api_key`, `model`
  - Google: `api_key` (可选)
  - DeepL: `api_key`
  - 百度: `app_id`, `app_key`
  - MyMemory: `email` (可选)

#### 主要方法

##### translate_image()

```python
translate_image(image_input, target_language="zh", output_path=None, save_original=False, ocr_options=None)
```

翻译图片中的文字。

**参数:**
- `image_input`: 输入图片路径或图片数据(numpy数组)
- `target_language`: 目标语言代码 ("zh", "en", "ja", "ko"等)
- `output_path`: 输出图片路径(可选)
- `save_original`: 是否保存原图副本
- `ocr_options`: OCR选项

**返回:** 翻译后的图片数据(numpy数组)

##### translate_image_simple()

```python
translate_image_simple(image_path, output_dir="output", target_language="zh")
```

简化的图片翻译接口。

**参数:**
- `image_path`: 输入图片路径
- `output_dir`: 输出目录
- `target_language`: 目标语言

**返回:** 输出图片路径

##### batch_translate_images()

```python
batch_translate_images(input_dir, output_dir="output", target_language="zh", image_extensions=None)
```

批量翻译图片。

**参数:**
- `input_dir`: 输入目录
- `output_dir`: 输出目录
- `target_language`: 目标语言
- `image_extensions`: 支持的图片扩展名列表

**返回:** 输出文件路径列表

##### get_ocr_results()

```python
get_ocr_results(image_input)
```

仅执行OCR识别，返回识别结果。

**参数:**
- `image_input`: 输入图片路径或图片数据

**返回:** OCR识别结果列表

##### translate_text()

```python
translate_text(text, target_language="zh")
```

翻译单个文本。

**参数:**
- `text`: 要翻译的文本
- `target_language`: 目标语言

**返回:** 翻译结果

### 便捷函数

#### create_image_translator()

```python
create_image_translator(translator_type="Google", **kwargs)
```

创建图片翻译器的便捷函数。

## 支持的翻译器

### 1. Google翻译 (推荐)
- **类型**: "Google"
- **优点**: 免费，无需API密钥，支持多种语言
- **缺点**: 可能受网络限制

```python
translator = create_image_translator("Google")
```

### 2. 智谱AI
- **类型**: "智谱"
- **优点**: 中文翻译质量高，支持多种模型
- **缺点**: 需要API密钥

```python
translator = create_image_translator(
    "智谱",
    api_key="your_api_key",
    model="glm-4-flash"
)
```

### 3. DeepL
- **类型**: "DeepL"
- **优点**: 翻译质量高
- **缺点**: 需要API密钥，有使用限制

```python
translator = create_image_translator(
    "DeepL",
    api_key="your_api_key"
)
```

### 4. 百度翻译
- **类型**: "百度"
- **优点**: 中文支持好
- **缺点**: 需要APP ID和密钥

```python
translator = create_image_translator(
    "百度",
    app_id="your_app_id",
    app_key="your_app_key"
)
```

### 5. MyMemory
- **类型**: "MyMemory"
- **优点**: 免费
- **缺点**: 翻译质量一般，有使用限制

```python
translator = create_image_translator(
    "MyMemory",
    email="your_email@example.com"  # 可选
)
```

## 支持的语言代码

- `zh`: 中文
- `en`: 英文
- `ja`: 日文
- `ko`: 韩文
- `fr`: 法文
- `de`: 德文
- `es`: 西班牙文
- `ru`: 俄文

## 使用示例

### 示例1: 基础图片翻译

```python
from core.image_translator import create_image_translator

# 创建翻译器
translator = create_image_translator("Google")

# 翻译图片
result_path = translator.translate_image_simple(
    image_path="manga_page.jpg",
    output_dir="translated",
    target_language="zh"
)

print(f"翻译完成: {result_path}")
```

### 示例2: 批量翻译

```python
from core.image_translator import create_image_translator

# 创建翻译器
translator = create_image_translator("Google")

# 批量翻译
output_paths = translator.batch_translate_images(
    input_dir="manga_pages",
    output_dir="translated_pages",
    target_language="zh"
)

print(f"批量翻译完成，处理了 {len(output_paths)} 个文件")
```

### 示例3: 仅OCR识别

```python
from core.image_translator import create_image_translator

translator = create_image_translator("Google")

# 仅执行OCR识别
ocr_results = translator.get_ocr_results("image.jpg")

for i, result in enumerate(ocr_results, 1):
    print(f"{i}. 文本: '{result.text}'")
    print(f"   置信度: {result.confidence:.2f}")
```

### 示例4: 自定义OCR选项

```python
from core.image_translator import create_image_translator

translator = create_image_translator("Google")

# 自定义OCR选项
ocr_options = {
    'det': True,    # 启用文本检测
    'rec': True,    # 启用文本识别
    'cls': True     # 启用角度分类
}

result_image = translator.translate_image(
    image_input="image.jpg",
    target_language="zh",
    output_path="result.jpg",
    ocr_options=ocr_options
)
```

## 注意事项

1. **首次使用**: 首次运行时会下载OCR模型，可能需要一些时间
2. **图片格式**: 支持常见的图片格式 (jpg, png, bmp, tiff等)
3. **文字方向**: 自动检测文字方向，支持水平和垂直文本
4. **翻译质量**: 翻译质量取决于所选的翻译服务
5. **网络连接**: 大部分翻译服务需要网络连接
6. **API限制**: 使用付费翻译服务时注意API调用限制

## 错误处理

模块提供了完善的错误处理机制：

```python
from core.image_translator import create_image_translator

try:
    translator = create_image_translator("Google")
    result_path = translator.translate_image_simple("image.jpg")
    print(f"成功: {result_path}")
except FileNotFoundError as e:
    print(f"文件不存在: {e}")
except RuntimeError as e:
    print(f"运行时错误: {e}")
except Exception as e:
    print(f"其他错误: {e}")
```

## 性能优化

1. **缓存机制**: 翻译结果会自动缓存，避免重复翻译
2. **批量处理**: 使用批量翻译功能提高效率
3. **模型复用**: OCR模型只加载一次，可重复使用
4. **内存管理**: 及时释放大图片的内存

## 扩展功能

### 集成到其他项目

```python
# 在其他模块中使用
from core.image_translator import ImageTranslator

class MyImageProcessor:
    def __init__(self):
        self.translator = ImageTranslator("Google")
    
    def process_image(self, image_path):
        # 执行图片翻译
        result = self.translator.translate_image_simple(image_path)
        return result
```

### 自定义翻译器

可以通过继承基类来实现自定义翻译器，然后集成到ImageTranslator中。

## 故障排除

### 常见问题

1. **OCR模型加载失败**
   - 检查网络连接
   - 确保有足够的磁盘空间
   - 检查OnnxOCR目录是否完整

2. **翻译失败**
   - 检查API密钥是否正确
   - 确认网络连接正常
   - 检查翻译服务是否可用

3. **图片无法读取**
   - 确认图片文件存在
   - 检查图片格式是否支持
   - 确认文件权限

4. **内存不足**
   - 处理大图片时可能出现内存问题
   - 建议先压缩图片或分批处理

### 日志调试

模块使用了完善的日志系统，可以通过查看日志来诊断问题：

```python
from utils import manga_logger as log

# 设置日志级别
log.setLevel(log.DEBUG)

# 然后运行翻译代码，查看详细日志
```

## 更新日志

- **v1.0.0**: 初始版本，支持基础图片翻译功能
- 整合OCR识别、翻译和文本替换
- 支持多种翻译服务
- 提供批量处理功能

## 贡献

欢迎提交问题和改进建议！

## 许可证

本项目遵循项目主许可证。
