# web/api_server.py
"""
纯API服务器 - 应用定义文件

负责创建和组装FastAPI应用实例，加载所有API路由和中间件。
"""
import logging
import sys
import asyncio
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 将项目根目录添加到Python路径
# Path(__file__) -> src/backend/web/api_server.py
# Path(__file__).parent -> src/backend/web/
# Path(__file__).parent.parent -> src/backend/
# Path(__file__).parent.parent.parent -> 项目根目录
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    # 从新的依赖模块导入
    from src.backend.web.dependencies import core_interface
    from src.backend.web.api import manga, cache, settings, viewer, translator
    # 显式导入广播函数
    from src.backend.web.websocket.handlers import websocket_endpoint, broadcast_manga_list_update
except ImportError as e:
    print(f"ERROR: 关键模块导入失败: {e}")
    print("请确保所有依赖都已正确安装，并且脚本在正确的项目结构中运行。")
    sys.exit(1)

# 创建FastAPI应用
app = FastAPI(
    title="Manga API Server",
    description="为漫画管理工具提供后端API服务",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 允许所有来源，对于桌面应用是安全的
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 绑定应用生命周期事件
@app.on_event("startup")
async def startup_event():
    # 在启动时，可以访问全局实例来执行预热等操作
    logging.info(f"API服务启动，CoreInterface实例 ({id(core_interface)}) 已通过依赖模块加载。")

    # --- 异步事件监听器 ---
    async def manga_update_listener():
        logging.info("[WebSocket] 启动 MangaManager 事件监听器...")
        # 直接使用全局实例
        manga_manager = core_interface.manga_manager
        while True:
            try:
                event = await manga_manager.update_queue.get()
                logging.info(f"[WebSocket] 从队列中收到 MangaManager 事件: {event}")

                if event['type'] == 'data_loaded':
                    logging.info("[WebSocket] 检测到 'data_loaded' 事件, 准备广播...")
                    await broadcast_manga_list_update(event.get('data', {}))

                manga_manager.update_queue.task_done()
            except asyncio.CancelledError:
                logging.info("MangaManager 事件监听器被取消。")
                break
            except Exception as e:
                logging.error(f"处理 MangaManager 事件时出错: {e}", exc_info=True)
                await asyncio.sleep(1)

    # 启动后台任务来监听事件
    asyncio.create_task(manga_update_listener())
    logging.info("MangaManager 事件监听任务已在后台启动。")


@app.on_event("shutdown")
async def shutdown_event():
    # 直接使用全局实例
    core_interface.close()
    logging.info("API服务已关闭。")

# 健康检查端点
@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok"}

# 注册所有API路由
app.include_router(manga.router, prefix="/api/manga", tags=["漫画管理"])

app.include_router(cache.router, prefix="/api/cache", tags=["缓存管理"])
app.include_router(settings.router, prefix="/api/settings", tags=["设置管理"])
app.include_router(viewer.router, prefix="/api/viewer", tags=["漫画查看器"])
app.include_router(translator.router, tags=["AI翻译器"]) # AI翻译器API没有统一前缀

# 注册WebSocket
app.add_websocket_route("/ws", websocket_endpoint)