<项目上手简报>

<核心架构思维模型>
<系统本质>
前后端分离的漫画管理系统 — 基于 FastAPI + Vue 3 的现代化桌面/Web 应用，核心价值在于漫画元数据解析与高效浏览体验。
</系统本质>

<架构模式>
分层架构 + 事件驱动 + 双模式部署
后端: Core → Interface → API 三层架构
前端: Store → Component → View 响应式架构
通信: RESTful API + WebSocket 实时更新
部署: 桌面模式(PyWebView) / Web 模式(Uvicorn)双轨制
</架构模式>
</核心架构思维模型>

<核心数据流与控制流>
<数据流向>
文件系统 → Core(MangaManager) → CoreInterface → API → Store → Component
WebSocket 广播: Core(Event) → 缓存系统 → Store
</数据流向>

<关键控制流>

1. 漫画扫描流: 目录设置 → 文件遍历 → 元数据解析 → 数据库存储 → 事件广播
2. 浏览请求流: 搜索/过滤 → 分页查询 → 缩略图生成 → 响应返回
3. 阅读体验流: 页面请求 → 缓存检查 → 图像处理 → 流式传输
   </关键控制流>
   </核心数据流与控制流>

<核心设计模式>
<后端模式>
策略模式: DataSource (src/backend/core/manga/data_source.py) 抽象不同漫画格式
工厂模式: DataSourceFactory (src/backend/core/manga/data_source.py) 创建数据源实例
门面模式: CoreInterface (src/backend/web/core_interface.py) 统一业务接口
观察者模式: MangaManager (src/backend/core/manga/manga_manager.py) 事件队列机制
单例模式: dependencies (src/backend/web/dependencies.py) 全局依赖管理
</后端模式>

<前端模式>
状态管理: Pinia Store 集中式状态
组件化: Vue 3 Composition API
路由守卫: 声明式导航控制
懒加载: 异步组件与代码分割
</前端模式>
</核心设计模式>

<开发场景导航>
<新增业务逻辑>
场景: 添加新的漫画处理功能
路径:

1. Core 层: src/backend/core/manga/ 新增业务模块
2. Interface 层: CoreInterface (src/backend/web/core_interface.py) 添加封装方法
3. API 层: src/backend/web/api/ 创建路由
4. Store 层: src/frontend/src/store/ 管理状态
5. Component 层: src/frontend/src/components/ 实现 UI
   </新增业务逻辑>

<修改数据定义>
场景: 扩展漫画元数据结构
路径:

1. 模型层: MangaInfo (src/backend/core/manga/manga_model.py) 数据类定义
2. 解析层: MetadataParser (src/backend/core/manga/metadata_parser.py) 解析逻辑
3. 接口层: WebMangaInfo (src/backend/web/core_interface.py) 传输模型
4. 前端类型: Manga (src/frontend/src/api/manga.ts) 接口定义
   </修改数据定义>

<配置环境>
场景: 调整系统运行参数
路径:

1. 后端配置: config.py (src/backend/core/config.py) Config 类
2. 前端配置: settings.ts (src/frontend/src/store/settings.ts) Store 状态
3. 启动脚本: run_desktop_app.py / run_web_server.py
   </配置环境>
   </开发场景导航>

<关键技术决策>
<数据存储>
LMDB: 轻量级嵌入式数据库，用于漫画元数据和缓存
文件系统: 原始漫画文件和缩略图存储
内存缓存: 分页图像缓存与会话数据
</数据存储>

<性能优化>
懒加载: 漫画列表分页与缩略图按需生成
缓存策略: 多级缓存(LMDB/内存/浏览器)
图像处理: OpenCV + PIL 高效图像处理
WebSocket: 实时更新减少轮询开销
</性能优化>

<安全控制>
本地访问限制: @local_only (src/backend/web/api/manga.py) 装饰器
路径验证: 文件系统访问安全检查
输入验证: Pydantic 模型验证
</安全控制>
</关键技术决策>

<核心扩展点>
<插件化架构>
数据源扩展: 继承 DataSource (src/backend/core/manga/data_source.py) 支持新格式
翻译服务: AITranslatorFacade (src/backend/core/ai_translator/facade.py) 接入不同 LLM
缓存策略: CacheHandler (src/backend/web/api/cache.py) 实现自定义缓存
</插件化架构>

<自定义配置>
元数据解析: MetadataParser (src/backend/core/manga/metadata_parser.py) 适配不同命名规则
UI 主题: Element Plus 主题定制
阅读模式: ViewerStore (src/frontend/src/store/viewer.ts) 扩展显示模式
</自定义配置>
</核心扩展点>

<开发调试指南>
<后端调试>

1. 日志系统: manga_logger.py (src/backend/utils/manga_logger.py) 统一日志输出
2. API 文档: FastAPI 自动生成 /docs 接口文档
3. 健康检查: /health (src/backend/web/api_server.py) 端点状态监控
   </后端调试>

<前端调试>

1. 状态追踪: Vue Devtools Pinia 状态可视化
2. 网络监控: 浏览器开发者工具 API 调用分析
3. 组件调试: Vue 3 Composition API 响应式追踪
   </前端调试>

<常见问题>
路径问题: 注意开发环境与打包环境的路径差异
异步处理: Core 层大量使用 async/await，注意错误传播
状态同步: WebSocket 事件与 Store 状态的一致性维护
</常见问题>
</开发调试指南>

<部署与运维>
<开发环境>
后端: uv pip install . && python scripts/run_web_server.py
前端: cd src/frontend && npm install && npm run dev
</开发环境>

<生产环境>
桌面应用: python scripts/run_desktop_app.py
Web 服务: python scripts/run_web_server.py --host 0.0.0.0 --port 8100
</生产环境>

<性能监控>
缓存统计: /api/cache/stats (src/backend/web/api/cache.py) 接口监控
批量任务: batch_compression_manager.py (src/backend/core/image/batch_compression_manager.py) 任务状态
WebSocket 连接: ConnectionManager (src/backend/web/websocket/handlers.py) 连接状态
</性能监控>
</部署与运维>

<核心原则>
单一职责、松耦合、高内聚。遵循此架构，可确保系统可维护性与扩展性。
</核心原则>

</项目上手简报>
