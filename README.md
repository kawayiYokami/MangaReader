# Manga Manager & Reader

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/vue-3.x-brightgreen.svg)](https://vuejs.org/)
[![License](https://img.shields.io/badge/license-GPL--3.0-brightgreen.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/kawayiYokami/MangaReader)](https://github.com/kawayiYokami/MangaReader/releases/latest)

本地漫画管理与阅读器，自动扫描、解析和组织漫画收藏。

## ✨ 主要功能

- **智能解析**: 自动从文件名提取作者、系列、汉化组等元数据
- **标签系统**: 分类标签 + 快速过滤
- **批量压缩**: WebP 格式图像压缩
- **阅读模式**: 单页/双页、左右阅读方向
- **AI翻译**: 集成 LLM 翻译服务
- **现代UI**: Element Plus，支持亮/暗色主题

## 📥 下载

[📦 最新版本](https://github.com/kawayiYokami/MangaReader/releases/latest) - Windows 免安装，解压即用

## 🚀 快速开始（开发者）

### 要求
- Python 3.11+
- Node.js 22+ (仅开发前端时)

### 安装运行

```bash
# 克隆仓库
git clone https://github.com/kawayiYokami/MangaReader.git
cd MangaReader

# 安装依赖
pip install uv
uv sync

# 桌面模式
python scripts/run_desktop_app.py

# Web服务模式
python scripts/run_web_server.py --host 0.0.0.0 --port 8100
```

## 📝 使用说明

1. 启动应用
2. 在设置页面配置漫画目录路径
3. 自动扫描并解析元数据
4. 通过标签筛选或搜索漫画
5. 点击封面进入阅读

## 🛠️ 技术栈

**后端**: Python 3.11, FastAPI, Uvicorn
**前端**: Vue 3, Vite, TypeScript, Pinia, Element Plus
**缓存**: LMDB

## 📄 许可证

GPL-3.0 License