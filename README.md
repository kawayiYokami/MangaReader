# Manga Translator

现代化漫画翻译工具，集成OCR识别、多引擎翻译和文本替换功能。

## ✨ 核心功能
- **OCR文本识别**：精准识别漫画中的多语言文本
- **多引擎翻译**：支持Google翻译/智谱AI/本地模型
- **批量处理**：自动翻译整个漫画章节
- **字体保持**：智能处理文本布局保持原始美学
- **缓存系统**：显著提升重复处理效率

## 🚀 快速开始

### 安装

python 版本是3.11.12


运行 update_ocr_font.bat
或者手动克隆项目https://github.com/jingsongliujing/OnnxOCR.git到目录下

```bash
cd manga
pip install uv
uv venv
uv pip install -r requirements.txt
update_ocr_font.bat
```

### 配置
1. 编辑 `config/config.json` 配置翻译服务：
```json
{
  "translation_services": {
    "zhipu_ai": {
      "api_key": "YOUR_ZHIPU_API_KEY"
    }
  }
}
```

### 运行
```bash
python main.py
```

### 使用流程
1. 选择漫画文件或文件夹
2. 设置翻译参数（语言/引擎）
3. 执行翻译（单页或批量）
4. 查看/保存结果

## 📄 许可证
[MIT License](LICENSE)