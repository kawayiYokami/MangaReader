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

## 模块说明

### core - 核心业务逻辑
- 负责漫画文件的管理、加载和数据模型定义
- 处理漫画元数据解析和标签管理

### ui - 用户界面
- components: 包含所有可重用的UI组件
- layouts: 自定义布局管理器
- 主要的视图和窗口类

### styles - 样式管理
- 提供统一的样式定义和主题支持
- 支持明暗主题切换

### utils - 工具类
- 提供日志记录功能
- 系统主题色获取等辅助功能