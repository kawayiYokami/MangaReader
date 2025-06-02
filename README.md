# Manga Reader

一个现代化、功能丰富的漫画阅读器，旨在提供流畅且个性化的阅读体验。

## ✨ 功能特性

- **直观的用户界面**: 基于 `PySide6` 和 `qfluentwidgets` 构建，提供美观且响应迅速的界面。
- **灵活的阅读模式**: 支持单页、双页自适应显示，以及从左到右或从右到左的阅读顺序。
- **智能配置管理**: 通过 `QConfig` 系统，轻松管理阅读偏好、UI 设置和应用程序状态。
- **漫画管理**: 方便地浏览、搜索和管理本地漫画文件。
- **日志系统**: 集成日志功能，便于问题排查和应用监控。

## 🚀 快速开始

### 📦 安装

python 3.11

1. **克隆仓库**:
   ```bash
   git clone https://github.com/your-username/manga.git
   cd manga
   ```

2. **安装依赖**:
   建议使用 `pip` 安装项目依赖。请确保您的 Python 环境已安装 `pip`。
   ```bash
   pip install -r requirements.txt
   ```
   如果您遇到依赖问题，可以尝试重新生成 `requirements.txt` 文件：
   ```bash
   pip install pipreqs
   pipreqs --force --encoding=utf8 .
   pip install -r requirements.txt
   ```

### 🏃 运行

安装完所有依赖后，您可以通过以下命令启动应用程序：

```bash
python main.py
```

## 🛠️ 项目结构

```
manga/
├── core/                     # 核心业务逻辑和数据模型
│   ├── config.py             # 应用程序配置管理 (基于 QConfig)
│   ├── manga_cache.py        # 漫画数据缓存
│   ├── manga_manager.py      # 漫画文件管理和解析
│   ├── manga_model.py        # 漫画数据模型
│   └── translator.py         # 翻译相关功能
├── download/                 # 下载模块 (待实现或扩展)
├── main.py                   # 应用程序入口点
├── requirements.txt          # 项目依赖列表
├── ui/                       # 用户界面相关文件
│   └── new_interface/        # 新版 UI 模块
│       ├── control_panel.py  # 控制面板组件
│       ├── manga_browser.py  # 漫画浏览界面
│       ├── manga_list.py     # 漫画列表显示
│       ├── manga_viewer.py   # 漫画阅读器核心组件
│       └── tag_filter.py     # 标签过滤组件
├── utils/                    # 工具函数和辅助模块
│   ├── color_utils.py        # 颜色处理工具
│   └── manga_logger.py       # 自定义日志工具
└── views/                    # 视图接口定义
    ├── manga_browser_interface.py
    └── settings_interface.py
```

## ⚙️ 配置

应用程序的默认配置定义在 <mcfile name="config.py" path="core/config.py"></mcfile> 文件中。您可以在此文件中调整默认的阅读顺序、显示模式等设置。例如，默认设置为双页、从左到右阅读。

## 📜 许可证
本项目采用 [GNU General Public License v3.0](LICENSE) 授权。
