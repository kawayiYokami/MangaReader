"""
漫画翻译工具 - Web应用主文件

FastAPI应用的主入口，集成所有API路由和WebSocket处理。
复用现有的core业务逻辑，不修改任何现有代码。
"""

import sys
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn

# 确保可以导入core模块
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入统一接口层
try:
    from web.core_interface import get_core_interface, CoreInterface
    from utils import manga_logger as log
except ImportError as e:
    print(f"无法导入核心模块: {e}")
    raise

# 创建FastAPI应用
app = FastAPI(
    title="漫画翻译工具 Web UI",
    description="现代化漫画翻译工具的Web界面版本",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 设置静态文件和模板
web_dir = Path(__file__).parent
static_dir = web_dir / "static"
templates_dir = web_dir / "templates"

# 创建目录（如果不存在）
static_dir.mkdir(exist_ok=True)
templates_dir.mkdir(exist_ok=True)

# 挂载静态文件
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 设置模板引擎
templates = Jinja2Templates(directory=str(templates_dir))

# 全局变量：共享的接口实例
core_interface = None

@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    global core_interface

    log.info("Web应用启动中...")

    # 初始化Core接口
    core_interface = get_core_interface()
    log.info("Core接口初始化完成")

    log.info("Web应用启动完成")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理"""
    log.info("Web应用关闭中...")

    # 清理接口
    try:
        if core_interface:
            core_interface.close()
        log.info("Core接口已关闭")
    except Exception as e:
        log.error(f"关闭Core接口时出错: {e}")

    log.info("Web应用已关闭")

from core.config import config

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """主页"""
    theme_value = config.themeMode.value
    if hasattr(theme_value, 'value'):  # 如果是枚举类型
        initial_theme = theme_value.value
    else:  # 如果是字符串
        initial_theme = str(theme_value).lower()
    return templates.TemplateResponse("index.html", {"request": request, "initial_theme": initial_theme})

@app.get("/viewer.html", response_class=HTMLResponse)
async def manga_viewer():
    """漫画查看器页面"""
    # 直接返回HTML文件内容，不使用Jinja2模板
    with open("web/templates/viewer.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/cache", response_class=HTMLResponse)
async def cache_management(request: Request):
    """缓存管理页面"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/test-viewer", response_class=HTMLResponse)
async def test_viewer_page(request: Request):
    """翻译工厂架构测试页面"""
    return templates.TemplateResponse("test_viewer.html", {"request": request})

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "message": "漫画翻译工具 Web UI 运行正常",
        "version": "1.0.0"
    }

# ==================== 调试端点 ====================
@app.get("/api/show_routes")
async def show_routes():
    """调试接口：显示所有已注册的路由"""
    routes = []
    for route in app.routes:
        routes.append({
            "path": getattr(route, 'path', 'N/A'),
            "name": getattr(route, 'name', 'N/A'),
            "methods": sorted(list(getattr(route, 'methods', {}))) if hasattr(route, 'methods') else 'N/A'
        })
    return routes
# =================================================

# 导入API路由
try:
    from web.api import manga, translation, cache, settings, viewer

    # 注册API路由
    app.include_router(manga.router, prefix="/api/manga", tags=["漫画管理"])
    app.include_router(translation.router, prefix="/api/translation", tags=["翻译功能"])
    app.include_router(cache.router, prefix="/api/cache", tags=["缓存管理"])
    app.include_router(settings.router, prefix="/api/settings", tags=["设置管理"])

    app.include_router(viewer.router, prefix="/api/viewer", tags=["漫画查看器"])

    log.info("API路由注册完成")
    
except ImportError as e:
    log.warning(f"部分API模块未找到: {e}")
    print(f"警告: 部分API模块未找到: {e}")

# 导入WebSocket处理
try:
    from web.websocket.handlers import websocket_endpoint
    app.add_websocket_route("/ws", websocket_endpoint)
    log.info("WebSocket路由注册完成")
except ImportError as e:
    log.warning(f"WebSocket模块未找到: {e}")
    print(f"警告: WebSocket模块未找到: {e}")

def get_core_interface_instance():
    """获取全局Core接口实例"""
    global core_interface
    if core_interface is None:
        core_interface = get_core_interface()
    return core_interface

# 导出给其他模块使用
__all__ = ["app", "get_core_interface_instance"]

if __name__ == "__main__":
    """直接运行时启动服务器"""
    uvicorn.run(
        "web.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
