# Manga Translator

现代化漫画翻译工具，集成 OCR 识别、多引擎翻译和文本替换功能，提供高效的漫画本地化解决方案。

## ✨ 功能特性

-   **OCR 文本识别**：精准识别漫画中的文本区域，支持多语言字符集。
-   **多引擎翻译**：
    -   默认集成 **Google 翻译**。
    -   支持用户配置 **智谱 AI API Key** 以获得更高质量的翻译。
    -   支持通过 **本地模型接口** 调用用户自行部署的翻译模型。
-   **批量处理**：全自动批量翻译整个漫画章节或指定图片范围。
-   **字体保持与文本替换**：内置精选字体库，智能算法处理气泡内文本布局，力求保持原始漫画美学。
-   **用户界面**：基于 PySide6 和 qfluentwidgets 构建的现代化、直观操作界面。
-   **缓存系统**：对漫画列表、OCR识别结果、翻译结果进行缓存，显著提高重复处理效率，并支持可视化管理。
-   **和谐化词管理**：允许用户自定义原文与和谐后文本的映射规则，自动应用于翻译预处理阶段。

## 🛠️ 技术栈

-   **主要语言**: Python 3.9+
-   **GUI框架**: PySide6, qfluentwidgets
-   **包管理/虚拟环境**: uv
-   **OCR技术**: OnnxOCR (通过子模块集成，提供移动版和可选的完整版模型支持)
-   **图像处理**: Pillow
-   **核心依赖库**: （可根据 `requirements.txt` ([`requirements.txt`](requirements.txt)) 补充其他关键库，如 `transformers` 如果本地模型接口需要）

## 📂 项目结构

```mermaid
graph TD
    A[manga/] --> B(main.py);
    A --> C(pyproject.toml);
    A --> D(README.md);
    A --> E(update_ocr_font.bat);
    A --> F(uv.toml);
    A --> G(requirements.txt);
    A --> H[core/];
    A --> I[font/];
    A --> J[OnnxOCR/ (子模块)];
    A --> K[ui/];
    A --> L[utils/];
    A --> M[views/];
    A --> N[cache/];
    A --> O[config/];
    A --> P[models/];
    A --> Q[testpy/];

    subgraph core [core/ - 核心逻辑]
        H1(batch_translation_worker.py);
        H2(cache_factory.py);
        H3(config.py);
        H4(harmonization_map_manager.py);
        H5(image_translator.py);
        H6(manga_cache.py);
        H7(manga_manager.py);
        H8(manga_model.py);
        H9(manga_text_replacer.py);
        H10(ocr_cache_manager.py);
        H11(ocr_manager.py);
        H12(translation_cache_manager.py);
        H13(translator.py);
    end

    subgraph ui [ui/ - 用户界面]
        K_new[new_interface/ - 主应用界面];
        K_new --> K_panel(control_panel.py);
        K_new --> K_browser(manga_browser.py);
        K_new --> K_list(manga_list.py);
        K_new --> K_viewer(manga_viewer.py);
    end
    
    subgraph views [views/ - 视图接口]
        M_cache(cache_management_interface.py);
        M_browser(manga_browser_interface.py);
        M_trans(manga_translation_interface.py);
        M_set(settings_interface.py);
    end

    subgraph testpy [testpy/ - 测试与调试工具]
        Q_ocr[ocr_translation/];
        Q_ocr --> Q_ocr_win(ocr_translation_window.py); % 独立翻译功能调试与高级设置窗口
    end

    subgraph cache [cache/ - 缓存数据]
        N_harm(harmonization_map.json);
        N_dang(dangerous_words.db);
        N_ocr_db(ocr_cache.db);
        N_trans_db(translation_cache.db);
        N_manga_db(manga_list_cache.db);
    end

    subgraph config [config/ - 应用配置]
        O_conf(config.json); % 主要用户配置文件
    end
    
    subgraph font [font/ - 字体库]
    end
    
    subgraph models [models/ - (可选)本地模型存放]
    end
    
    subgraph OnnxOCR [OnnxOCR/ - OCR引擎子模块]
    end
    
    subgraph utils [utils/ - 工具模块]
    end
```
-   **`main.py` ([`main.py`](main.py))**: 应用入口。
-   **`core/` ([`core`](core))**: 包含所有核心业务逻辑，如图像处理、OCR、翻译、缓存管理、文本替换等。
-   **`ui/new_interface/` ([`ui/new_interface`](ui/new_interface))**: 基于 PySide6 和 qfluentwidgets 构建的主用户界面。
-   **`views/` ([`views`](views))**: 定义了各个功能模块的界面接口。
-   **`testpy/ocr_translation/` ([`testpy/ocr_translation`](testpy/ocr_translation))**: 提供一个独立的翻译功能调试与高级参数设置窗口。
-   **`cache/` ([`cache`](cache))**: 存放各类缓存数据，如和谐化词典、OCR及翻译结果等。
-   **`config/` ([`config`](config))**: 包含用户可配置的 `config.json` ([`config/config.json`](config/config.json)) 文件。
-   **`font/` ([`font`](font))**: 存储用于文本替换的字体文件。
-   **`OnnxOCR/` ([`OnnxOCR`](OnnxOCR))**: OCR引擎的子模块。
-   **`models/` ([`models`](models))**: （可选）用于存放本地翻译模型等。
-   **`utils/` ([`utils`](utils))**: 通用工具模块，如日志记录。

## 🚀 快速开始

### 📦 安装

1.  **克隆仓库**:
    强烈建议使用 `--recurse-submodules` 参数以确保 OCR 引擎子模块 (OnnxOCR) 被正确克隆（其自带移动版OCR模型）。
    ```bash
    git clone --recurse-submodules https://github.com/your-username/manga.git
    cd manga
    ```
    *(请将 `your-username/manga.git` 替换为实际的仓库地址)*

2.  **安装依赖**:
    本项目使用 `uv` 进行包管理和虚拟环境管理。
    ```bash
    pip install uv
    uv venv  # 创建或激活虚拟环境，例如: .venv
    # source .venv/bin/activate  (Linux/macOS)
    # .venv\Scripts\activate (Windows)
    uv pip install -r requirements.txt
    ```

3.  **初始化 OCR**:
    运行 `update_ocr_font.bat` ([`update_ocr_font.bat`](update_ocr_font.bat)) 脚本。此脚本主要用于确保 OnnxOCR 子项目的正确设置。
    ```bash
    update_ocr_font.bat
    ```
    > **可选**: OnnxOCR 项目本身提供了完整版OCR模型的下载方式（通常在其官方项目文档中可以找到，例如通过网盘链接）。如果您需要更高的OCR识别精度，可以查阅 OnnxOCR 的文档 ([https://github.com/jingsongliujing/OnnxOCR](https://github.com/jingsongliujing/OnnxOCR)) 并考虑替换其自带的移动版模型。本翻译工具默认使用随 OnnxOCR 子项目提供的移动版模型。

### ⚙️ 配置

关键配置主要通过 `config/config.json` ([`config/config.json`](config/config.json)) 文件进行。首次运行或文件不存在时，程序可能会尝试创建一个默认的配置文件。

1.  **翻译引擎配置**:
    *   **Google 翻译**: 默认启用，通常无需额外配置。
    *   **智谱 AI**:
        *   在 `config/config.json` ([`config/config.json`](config/config.json)) 文件中找到或添加类似如下的配置节：
            ```json
            {
              "translation_services": {
                "zhipu_ai": {
                  "api_key": "YOUR_ZHIPU_API_KEY"
                }
                // ... 其他翻译服务配置
              }
              // ... 其他配置
            }
            ```
        *   将 `"YOUR_ZHIPU_API_KEY"` 替换为您自己的智谱 AI API Key。
        *   在应用内的翻译设置中选择“智谱 AI”作为翻译引擎。
    *   **本地模型接口**:
        *   如果您部署了本地翻译服务（如基于 NLLB、MarianMT 等模型的API），可以在 `config/config.json` ([`config/config.json`](config/config.json)) 中配置其端点和必要的参数。例如：
            ```json
            {
              "translation_services": {
                "local_model": {
                  "api_url": "http://localhost:5000/translate", // 您的本地API端点
                  "model_name": "nllb-custom" // （可选）如果您的API需要模型名参数
                }
              }
            }
            ```
        *   具体参数取决于您的本地API实现。
        *   在应用内的翻译设置中选择“本地模型”作为翻译引擎。

2.  **其他配置**:
    `config/config.json` ([`config/config.json`](config/config.json)) 中可能还包含其他可配置项，如默认语言、缓存路径、OCR参数等。请参考该文件内的注释或程序的相关设置界面。

### 🏃 运行

启动应用程序：
```bash
python main.py
```

### 📖 使用指南

1.  **启动应用**后，通过主界面浏览并选择您想要翻译的漫画文件或包含漫画图片的文件夹。
2.  **配置翻译任务**:
    *   在主界面或相关的设置区域（例如，通过主菜单访问的“翻译设置”或“OCR设置”；或者，如果 `testpy/ocr_translation/ocr_translation_window.py` ([`testpy/ocr_translation/ocr_translation_window.py`](testpy/ocr_translation/ocr_translation_window.py)) 仍作为调试/高级设置入口，则通过它）进行以下配置：
        *   选择**源语言**和**目标语言**。
        *   选择要使用的**翻译引擎**（Google、智谱 AI、本地模型）。
        *   （可选）调整 OCR 文本检测参数，如置信度阈值、区域合并等。
3.  **执行翻译**:
    *   **单页/选择翻译**: 在漫画查看器中选择特定页面或文本框进行翻译。
    *   **批量翻译**: 设置好参数后，启动批量翻译任务处理整个漫画或选定范围。
4.  **缓存管理**:
    *   通过主菜单或设置界面访问“缓存管理” ([`views/cache_management_interface.py`](views/cache_management_interface.py))。
    *   可以查看、清理或管理 OCR 缓存、翻译缓存和漫画列表缓存。
5.  **和谐化词管理**:
    *   通常通过编辑 `cache/harmonization_map.json` ([`cache/harmonization_map.json`](cache/harmonization_map.json)) 文件来添加或修改原文与和谐后文本的映射规则。格式为 `{"原文": "和谐后文本", ...}`。
    *   部分版本可能提供UI界面进行管理。

#### 简易工作流程

```mermaid
flowchart TD
    A[选择漫画图片/章节] --> B{配置翻译参数};
    B -- 源/目标语言 --> B;
    B -- 选择翻译引擎 --> B;
    B -- (可选)OCR参数 --> B;
    B --> C[启动翻译];
    C --> D[OCR文本识别];
    D --> E[文本和谐化处理 (若启用)];
    E --> F[翻译文本];
    F --> G[文本替换回图片];
    G --> H[查看/保存结果];
```

## 🤝 贡献指南

欢迎各种形式的贡献！请遵循以下流程：

1.  如果您发现 bug 或有功能建议，请先搜索现有的 Issues，如果找不到相关的，请创建一个新的 Issue 来描述问题或建议。
2.  如果您希望贡献代码，请先 Fork 本仓库。
3.  基于 `main` 分支创建一个新的特性分支 (例如 `feat/your-amazing-feature` 或 `fix/issue-number`)。
4.  在您的分支上进行修改和提交。
5.  确保您的代码通过了核心功能测试（如果项目包含自动化测试）：
    ```bash
    python -m core.test.test_manga_batch_translate 
    ```
    *(请确认此测试命令及路径是否仍然有效和适用)*
6.  提交 Pull Request 到主仓库的 `main` 分支，并在 PR 描述中关联对应的 Issue。
7.  等待 Review 和合并。

## 📄 许可证

-   主项目: [MIT License](LICENSE) *(如果您的项目根目录有 LICENSE 文件，请确保此链接有效，否则可以移除此行或指向正确的许可证信息)*
-   OnnxOCR 子项目: 遵循其自身的许可证 [MIT License](https://github.com/jingsongliujing/OnnxOCR/blob/main/LICENSE)