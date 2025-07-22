# Manga Manager & Reader - 漫画管理器与阅读器

[![Python-Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/) [![Vue-Version](https://img.shields.io/badge/vue-3.x-brightgreen.svg)](https://vuejs.org/) [![License](https://img.shields.io/badge/license-GPL--3.0-brightgreen.svg)](LICENSE)

一款专为漫画收藏爱好者设计的本地管理器与阅读器。它能自动扫描、解析和组织您的漫画收藏，通过强大的元数据和标签系统提供极致的浏览体验。

## ✨ 核心功能

### 📚 智能漫画库管理
- **自动化元数据解析**: 无需手动整理！仅通过文件名，即可自动解析出 `作者`, `作品系列`, `汉化组`, `会场` 等信息，并生成分类标签。
- **强大的标签系统**:
  - **分类标签**: 所有标签按 `作者`, `作品`, `汉化` 等类别清晰展示。
  - **快速过滤**: 只需点击标签，即可在海量收藏中快速筛选出您想看的内容。
- **批量图像压缩**: 支持将处理后的图片保存为 `WEBP` 格式，有效减小存储体积。
- **前后端分离架构**: 基于 FastAPI 和 Vue 3，提供现代化的、可独立部署的 Web UI。
- **持久化缓存**: 为漫画封面、图片和元数据建立缓存，实现秒速加载和浏览。

### 📖 沉浸式阅读体验
- **灵活的阅读模式**: 支持从右到左、从左到右的阅读顺序，以及单页、双页显示模式。
- **AI 辅助翻译**:
    - 在阅读器中一键开启，将漫画原文以“剧本”形式展示在侧边栏。
    - 支持接入多种大语言模型（LLM）服务，可在设置中灵活配置。
- **现代化UI**: 界面基于 Element Plus，支持亮色、暗色及自动（跟随系统）三种主题。
- **跨设备同步**: （需部署在可访问的网络）通过Web服务，可在不同设备上继续阅读。

### ⚙️ 系统设置
- **AI 服务配置**: 提供对外部 AI 翻译服务的可视化配置管理。
- **缓存管理**: 可查看和清理漫画列表缓存。

## 🛠️ 技术栈

- **后端**: `Python 3.11+`, `FastAPI`, `Uvicorn`
- **前端**: `Vue 3`, `Vite`, `TypeScript`, `Pinia`, `Element Plus`
- **数据库/缓存**: `LMDB` 用于持久化缓存

## 🏗️ 项目结构

```
.
├── core/                # 核心业务逻辑 (Python)
│   ├── manga/           # 漫画管理、解析、元数据
│   ├── ai_translator/   # AI翻译模块，包含智能体和配置管理
│   └── ...
│
├── vue/                 # 前端应用 (Vue 3)
│   ├── src/             # 源代码
│   │   ├── components/  # 组件
│   │   ├── pages/       # 页面视图
│   │   ├── store/       # Pinia状态管理
│   │   └── router/      # 路由
│   └── package.json     # 前端依赖与脚本
│
├── web/                 # 后端API服务 (FastAPI)
│   ├── api/             # API路由模块
│   ├── websocket/       # WebSocket处理
│   └── api_server.py    # FastAPI应用入口
│
├── utils/               # 通用工具模块
├── pyproject.toml       # Python项目配置与依赖
└── README.md            # 就是你正在看的文件
```

## 🚀 快速开始

### 🚀 快速使用 (桌面应用模式)

对于大多数用户，最简单的启动方式是直接运行桌面应用。
在确保已安装 `uv` 并完成后端依赖安装后，您无需启动单独的后端 API 或前端开发服务器。

1.  **安装 `uv` (如果尚未安装)**:
    ```bash
    pip install uv
    ```
2.  **克隆项目仓库并进入目录**:
    ```bash
    git clone https://github.com/kawayiYokami/MangaReader.git
    cd MangaReader
    ```
3.  **安装后端依赖**:
    ```bash
    uv venv
    # Windows: .\.venv\Scripts\activate
    # macOS/Linux: source .venv/bin/activate
    uv pip install .
    ```
4.  **直接启动桌面应用**:
    ```bash
    python run_desktop_app.py
    ```
    - 这将自动启动内部后端服务并显示桌面界面。

### 环境要求

*   **Python**: `>=3.11,<3.14`
*   **Node.js**: `>=22.0.0` (仅开发前端或手动构建前端时需要)
*   **uv**: (推荐的Python包管理器)
*   **npm** 或 **pnpm** 或 **yarn**: (Node.js包管理器，仅开发前端或手动构建前端时需要)

### 安装步骤

1.  **克隆项目仓库**:
    ```bash
    git clone https://github.com/kawayiYokami/MangaReader.git
    cd MangaReader
    ```

2.  **安装后端依赖**:
    ```bash
    # 安装 uv (如果尚未安装)
    pip install uv
    
    # 创建并激活虚拟环境
    uv venv
    # Windows: .\.venv\Scripts\activate
    # macOS/Linux: source .venv/bin/activate
    
    # 安装Python依赖
    uv pip install .
    ```

3.  **安装前端依赖 (仅用于前端开发或手动构建)**:
    ```bash
    # 进入vue目录
    cd vue
    
    # 安装Node.js依赖
    npm install
    ```
    - **注意**: 如果您只是想运行桌面应用或纯Web服务端，且 `vue/dist` 目录已存在，则无需执行此步骤。本项目通常会直接提供已 `build` 好的 `vue/dist` 文件。

## 🚀 运行程序

本项目支持多种运行模式，以适应开发、测试和生产环境的需求。

### 1. 开发模式 (前后端分离)

此模式下，后端 API 服务和前端开发服务器独立运行，方便开发调试。

**a. 启动后端 API 服务**

在项目 **根目录** 下运行：

```bash
python run_api_server.py [--host <host>] [--port <port>] [--reload]
# 示例: python run_api_server.py --host 127.0.0.1 --port 8100 --reload
```
- `run_api_server.py`: 启动纯 FastAPI 后端，监听指定地址和端口（默认 `http://127.0.0.1:8100`）。`--reload` 参数用于开发时的代码热重载。
- **注意**: 后端 API 默认端口为 `8100`。

**b. 启动前端开发服务器 (仅用于前端开发)**

打开一个新的终端，进入 `vue` 目录，然后运行：

```bash
cd vue
npm run dev
```
- `npm run dev`: 启动 Vue 前端开发服务器 (基于 Vite)，通常监听在 `http://localhost:5173`。
- 启动后，请在浏览器中访问 Vite 提示的地址。
- **重要**: 此步骤仅在您需要进行前端开发时才需要。

### 2. 桌面应用模式

此模式将后端 API 和前端 UI 集成到一个桌面应用中，通过 PyWebView 提供类似原生应用的体验。

**a. 开发模式下的桌面应用 (用于前端开发调试)**

此模式用于在开发前端时，通过桌面环境调试与系统交互的功能（如文件选择、拖放）。

在项目 **根目录** 下运行：

```bash
python run_pywebview_dev.py
```
- `run_pywebview_dev.py`: 启动一个 PyWebView 窗口，并加载 `http://localhost:5173` (前端开发服务器地址)。
- **重要**: 运行此脚本前，请确保 `run_api_server.py` 和 `npm run dev` 都已在后台启动。

**b. 生产模式下的桌面应用 (最终发布版本)**

此模式用于打包和发布最终的桌面应用程序，也是推荐的最终用户使用方式。它会内置后端服务并加载预构建的前端文件。

在项目 **根目录** 下运行：

```bash
python run_desktop_app.py
```
- `run_desktop_app.py`: 启动内部 FastAPI 后端服务，并使用 PyWebView 加载 `vue/dist` 目录下的静态前端文件。
- **注意**: `vue/dist` 目录通常包含已构建好的前端静态资源。**项目会直接上传 `build` 好的 `vue/dist`，通常无需您手动执行 `npm run build`。** 如果 `vue/dist` 不存在或需要更新，您可以在 `vue` 目录下运行 `npm run build` 来生成。

### 3. 纯 Web 服务器模式 (用于局域网/公网部署)

此模式是一个独立的 Web 应用部署方案，将后端 API 和预构建的前端静态文件整合在一个 FastAPI 服务器中。

在项目 **根目录** 下运行：

```bash
python run_web_server.py [--host <host>] [--port <port>]
# 示例: python run_web_server.py --host 0.0.0.0 --port 8100
```
- `run_web_server.py`: 启动 FastAPI 后端，并将 `vue/dist` 目录挂载为静态文件服务。它会监听所有网络接口 (`0.0.0.0`)，允许局域网或公网访问。
- **注意**: 前端文件将从 `vue/dist` 目录提供。**项目会直接上传 `build` 好的 `vue/dist`，通常无需您手动执行 `npm run build`。**
- 访问地址通常为 `http://<你的IP地址>:<port>`。

## 📋 使用流程

1.  **启动应用**: 根据您的需求选择上述任一运行模式启动程序。
2.  **设置漫画目录**: **在桌面应用界面中**，进入 `设置` 页面，输入漫画根文件夹的 **绝对路径** 并保存。
3.  **自动扫描**: 程序会自动扫描目录下的所有漫画文件和文件夹，并解析元数据。
4.  **浏览与筛选**: 在主页，使用顶部的搜索框或点击下方的分类标签来筛选您的漫画。
5.  **阅读**: 点击任意漫画封面即可进入阅读界面。

## 🙏 致谢
本项目的发展离不开众多优秀的开源库和社区的支持。