# 漫画阅读器

## 项目结构

```
.
├── core/               # 核心业务逻辑
│   ├── manga_manager.py  # 漫画管理器
│   ├── manga_model.py    # 漫画数据模型
├── ui/                 # 用户界面组件
│   ├── components/       # UI组件
│   │   ├── image_label.py   # 图片显示组件
│   │   ├── manga_image_viewer.py # 漫画图片查看器
│   │   ├── manga_list_manager.py # 漫画列表管理器
│   │   ├── navigation_controller.py # 导航控制器
│   │   ├── page_slider.py   # 页面滑动器
│   │   ├── tag_manager.py   # 标签管理器
│   │   ├── title_bar.py     # 标题栏组件
│   │   ├── vertical_zoom_slider.py # 垂直缩放滑动器
│   │   └── zoom_slider.py   # 缩放滑动器
│   ├── layouts/          # 布局组件
│   │   └── flow_layout.py   # 流式布局
│   ├── base_window.py    # 基础窗口类
│   ├── manga_viewe.py    # 漫画视图(旧)
│   └── manga_viewer_new.py # 新漫画视图
├── styles/             # 样式相关
│   ├── dark_style.py     # 暗色主题
│   ├── light_style.py    # 亮色主题
│   ├── style.py          # 基础样式
│   └── win_theme_color.py # Windows主题色工具
├── utils/              # 工具类
│   └── manga_logger.py   # 日志工具
└── main.py             # 程序入口
```

  ## 维护指南

### 清理临时文件
运行以下命令清除所有Python缓存文件：
```bash
python clean.py
```
该操作会自动删除所有__pycache__目录和.pyc/.pyo文件，同时保留logs目录下的日志文件

## 模块说明

### core - 核心业务逻辑
- manga_manager.py：漫画管理器，负责目录扫描、配置加载、文件过滤
- manga_model.py：漫画数据模型，定义MangaInfo数据结构和MangaLoader加载器

### ui - 用户界面
- components/：包含图片显示、导航控制、标签管理等交互组件
- layouts/flow_layout.py：实现自动换行的流式布局
- manga_viewer_new.py：主视图窗口，整合各UI组件

### styles - 样式管理
- dark_style.py：深色主题样式表
- light_style.py：浅色主题样式表
- win_theme_color.py：Windows系统主题色同步工具

### utils - 工具模块
- manga_logger.py：日志记录模块，支持多级别日志输出

## 开发指南

1. 环境配置：
```bash
# 安装开发依赖
pip install -r requirements.txt

# 启用代码格式检查
pre-commit install
```

2. 代码规范：
- 遵循PEP8规范
- UI组件命名采用大驼峰式
- 业务逻辑模块使用小写蛇形命名

3. 测试方法：
```bash
# 运行单元测试
python -m unittest discover tests
```

### utils - 工具类
- 提供日志记录功能
- 系统主题色获取等辅助功能