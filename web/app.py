"""
漫画翻译工具 - Web应用主文件

FastAPI应用的主入口，集成所有API路由和WebSocket处理。
复用现有的core业务逻辑，不修改任何现有代码。
"""

import sys # 保留 sys 以便未来可能的调试或特定检查
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn

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

# --- 修改开始: 简化路径设置，依赖 __file__ 和 PyInstaller 的数据结构 ---
# Path(__file__) 在开发时指向 web/app.py
# 在 PyInstaller 打包后，如果 app.py 位于例如 _MEIPASS/web/app.py,
# 那么 Path(__file__).parent 就会指向 _MEIPASS/web/
# 此方案要求 PyInstaller 将 static 和 templates 目录也相应地放置在
# _MEIPASS/web/static 和 _MEIPASS/web/templates (如果 app.py 在 _MEIPASS/web/ 下)
# 或者，如果 app.py 在 _MEIPASS/app.py, 那么 static/templates 需在 _MEIPASS/static 等。
# 关键是保持与 app.py 的相对路径一致。

# 假设 app.py 始终和 static/templates 目录处于同一父目录下（无论是 web/还是 _MEIPASS/web/）
current_script_dir = Path(__file__).resolve().parent

static_dir = (current_script_dir / "static").resolve()
templates_dir = (current_script_dir / "templates").resolve()

# 确保目录存在 (主要用于开发环境，打包后 PyInstaller 应已创建)
# 如果路径解析不正确，这里可能会在错误的地方创建目录，或因权限问题失败
try:
    static_dir.mkdir(parents=True, exist_ok=True)
    templates_dir.mkdir(parents=True, exist_ok=True)
except Exception as e:
    log.error(f"创建静态或模板目录失败: {e}. Static: {static_dir}, Templates: {templates_dir}")
    # 在打包环境中，如果目录不存在，这通常意味着 PyInstaller --add-data 配置问题
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        log.error("打包环境错误：请检查 PyInstaller 的 --add-data 配置是否正确地将 static 和 templates 目录包含进来，并放到了相对于 app.py 的正确位置。")
        log.error(f"期望 app.py 位于: {current_script_dir}")
        log.error(f"期望 static 目录位于: {static_dir}")
        log.error(f"期望 templates 目录位于: {templates_dir}")
        log.error(f"sys._MEIPASS (如果可用): {getattr(sys, '_MEIPASS', '不可用')}")

log.info(f"静态文件目录 (使用 __file__): {static_dir}")
log.info(f"模板文件目录 (使用 __file__): {templates_dir}")
# --- 修改结束 ---

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
    viewer_html_path = templates_dir / "viewer.html"
    log.info(f"尝试打开 viewer.html at: {viewer_html_path}")
    if not viewer_html_path.exists():
        log.error(f"viewer.html 未找到 at {viewer_html_path}")
        return HTMLResponse(content="Error: viewer.html not found.", status_code=404)
    with open(viewer_html_path, "r", encoding="utf-8") as f:
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
    log.info("直接运行 web/app.py, 启动uvicorn服务器...")
    uvicorn.run(
        "web.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True, 
        log_level="info"
    )
