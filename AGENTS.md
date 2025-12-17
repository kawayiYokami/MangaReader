<项目上手简报>

<核心架构思维模型>
<系统本质>
前后端分离的漫画管理系统 — 基于 FastAPI + Vue 3 的现代化桌面/Web 应用，核心价值在于漫画元数据解析与高效浏览体验。
</系统本质>

<架构模式>
分层架构 + 事件驱动 + 双模式部署
- 后端: Core → Interface → API 三层架构
- 前端: Store → Component → View 响应式架构
- 通信: RESTful API + WebSocket 实时更新
- 部署: 桌面模式(PyWebView) / Web 模式(Uvicorn)双轨制
</架构模式>
</核心架构思维模型>

<核心数据流与控制流>
<数据流向>
文件系统 → Core([`data_source.py`](src/backend/core/manga/data_source.py)) → Core([`manga_manager.py`](src/backend/core/manga/manga_manager.py)) → Interface([`core_interface.py`](src/backend/web/core_interface.py)) → API([`manga.py`](src/backend/web/api/manga.py)) → Store([`manga.ts`](src/frontend/src/store/manga.ts)) → Component
- WebSocket 广播: Core([`manga_manager.py`](src/backend/core/manga/manga_manager.py) 的事件队列) → API Server([`api_server.py`](src/backend/web/api_server.py)) → WebSocket Handler([`handlers.py`](src/backend/web/websocket/handlers.py)) → Store([`manga.ts`](src/frontend/src/store/manga.ts))
</数据流向>

<关键控制流>
1.  **漫画扫描流**: 目录设置 → 文件遍历与元数据解析 ([`manga_manager.py`](src/backend/core/manga/manga_manager.py)) → LMDB存储 (`MangaListCacheManager`) → 事件广播 (`update_queue`)
2.  **浏览请求流**: 搜索/过滤/分页请求 → API ([`manga.py`](src/backend/web/api/manga.py)) → [`core_interface.py`](src/backend/web/core_interface.py) → LMDB查询 (`manga_repo`) → 缩略图生成 → 响应返回
3.  **阅读体验流**: 页面请求 → 缓存检查 → 图像处理 ([`processor.py`](src/backend/core/image/processor.py)) → 流式传输
</关键控制流>
</核心数据流与控制流>

<核心设计模式>
<后端模式>
- **策略模式 (Strategy)**: [`DataSource`](src/backend/core/manga/data_source.py:33) 抽象不同漫画格式（文件夹/ZIP）。
- **工厂模式 (Factory)**: [`DataSourceFactory`](src/backend/core/manga/data_source.py:209) 根据路径创建具体的数据源实例。
- **门面模式 (Facade)**: [`CoreInterface`](src/backend/web/core_interface.py:80) 统一并简化了对整个 Core 子系统的访问。
- **观察者模式 (Observer/Event-Driven)**: [`MangaManager`](src/backend/core/manga/manga_manager.py:18) 通过 `update_queue` 发出状态变更事件，[`api_server.py`](src/backend/web/api_server.py:58) 监听并广播。
- **单例模式 (Singleton)**: [`dependencies.py`](src/backend/web/dependencies.py) 创建全局唯一的 `core_interface` 实例，解决循环导入并保证状态唯一。
</后端模式>

<前端模式>
- **状态管理 (State Management)**: Pinia Store ([`src/frontend/src/store/`](src/frontend/src/store/)) 作为全局状态中心，如 [`manga.ts`](src/frontend/src/store/manga.ts)。
- **组件化 (Componentization)**: Vue 3 Composition API 构建可复用的UI单元。
- **懒加载 (Lazy Loading)**: 异步组件与代码分割优化初始加载。
</前端模式>
</核心设计模式>

<开发场景导航>
<新增业务逻辑>
场景: 添加新的漫画处理功能（如“收藏夹”）
路径:
1.  Core 层: 在 [`src/backend/core/manga/`](src/backend/core/manga/) 新增业务模块。
2.  Interface 层: 在 [`CoreInterface`](src/backend/web/core_interface.py) 中添加封装方法。
3.  API 层: 在 [`src/backend/web/api/`](src/backend/web/api/) 创建新路由。
4.  Store 层: 在 [`src/frontend/src/store/`](src/frontend/src/store/) 管理新功能的状态。
5.  Component/Page 层: 在 [`src/frontend/src/components/`](src/frontend/src/components/) 或 [`src/frontend/src/pages/`](src/frontend/src/pages/) 实现 UI。
</新增业务逻辑>

<修改数据定义>
场景: 扩展漫画元数据结构（如添加“发布年份”）
路径:
1.  模型层: 修改 [`MangaInfo`](src/backend/core/manga/manga_model.py) 数据类。
2.  解析层: 修改 [`MetadataParser`](src/backend/core/manga/metadata_parser.py) 的解析逻辑。
3.  接口层: 修改 [`WebMangaInfo`](src/backend/web/core_interface.py:45) 数据传输对象。
4.  前端类型: 修改 [`Manga` type in `manga.ts`](src/frontend/src/api/manga.ts)。
</修改数据定义>

<配置环境>
场景: 调整系统运行参数
路径:
1.  后端配置: [`config.py`](src/backend/core/config.py) 中的 `Config` 类。
2.  前端配置: [`settings.ts`](src/frontend/src/store/settings.ts) Store 状态。
3.  启动脚本: [`run_desktop_app.py`](scripts/run_desktop_app.py) / [`run_web_server.py`](scripts/run_web_server.py)。
</配置环境>
</开发场景导航>

<关键技术决策>
<数据存储>
- LMDB: 通过 `MangaListCacheManager` ([`src/backend/core/core_cache/manga_cache.py`](src/backend/core/core_cache/manga_cache.py)) 实现，用于漫画元数据的高性能读写。
- 文件系统: 存储原始漫画文件和生成的缩略图。
</数据存储>

<性能优化>
- **懒加载**: 漫画列表分页加载与缩略图按需生成。
- **多级缓存**: LMDB（元数据）、内存（会话数据）、文件系统（缩略图）构成多级缓存体系。
- **图像处理**: OpenCV + Pillow ([`processor.py`](src/backend/core/image/processor.py)) 实现高效图像读写和处理。
- **WebSocket**: 实时更新代替轮询，减少网络开销 ([`api_server.py`](src/backend/web/api_server.py), [`handlers.py`](src/backend/web/websocket/handlers.py))。
</性能优化>

<安全控制>
- **本地访问限制**: (推断) API 装饰器可用于限制某些接口只能本地访问。
- **路径验证**: 在文件系统交互前进行安全检查。
- **输入验证**: Pydantic 模型自动进行 API 输入验证。
</安全控制>
</关键技术决策>

<核心扩展点>
<插件化架构>
- **数据源扩展**: 继承 [`DataSource`](src/backend/core/manga/data_source.py:33) 并更新 [`DataSourceFactory`](src/backend/core/manga/data_source.py:209) 以支持新格式（如 RAR, CBR）。
- **翻译服务扩展**: 实现 `AITranslator` 接口并注入到 [`facade.py`](src/backend/core/ai_translator/facade.py) 中。
</插件化架构>
</核心扩展点>

<开发调试指南>
<后端调试>
1.  日志系统: [`manga_logger.py`](src/backend/utils/manga_logger.py) 提供统一日志。
2.  API 文档: FastAPI 自动在 `/docs` 生成交互式 API 文档。
3.  健康检查: 访问 `/health` 端点 ([`api_server.py`](src/backend/web/api_server.py:91)) 确认服务状态。
</后端调试>

<前端调试>
1.  状态追踪: 使用 Vue Devtools 检查 Pinia store 的状态变化。
2.  网络监控: 使用浏览器开发者工具分析 API 调用和 WebSocket 消息。
</前端调试>
</开发调试指南>

<部署与运维>
<开发环境>
- 后端: `python scripts/run_web_server.py`
- 前端: `cd src/frontend && npm run dev`
</开发环境>

<生产环境>
- 桌面应用: `python scripts/run_desktop_app.py`
- Web 服务: `python scripts/run_web_server.py --host 0.0.0.0`
</生产环境>
</部署与运维>

<核心原则>
单一职责、松耦合、高内聚。遵循此架构，可确保系统可维护性与扩展性。
</核心原则>

</项目上手简报>
