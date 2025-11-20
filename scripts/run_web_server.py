#!/usr/bin/env python3
"""
漫画翻译工具 - 纯 Web 服务器启动器

功能:
1. 导入由 web.api_server 定义的 FastAPI 应用实例。
2. 将 'vue/dist' 目录挂载为静态文件服务，用于提供前端应用。
3. 启动 uvicorn 服务器，监听所有网络接口，使其可以被局域网或公网访问。
"""

import uvicorn
import sys
from pathlib import Path
from fastapi.staticfiles import StaticFiles

# 将项目根目录添加到Python路径，确保模块能被正确导入
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    # 导入预先配置好的FastAPI应用实例
    from src.backend.web.api_server import app
    from src.backend.utils.manga_logger import setup_logging
except ImportError as e:
    print(f"错误: 无法导入项目模块: {e}")
    print("请确保从项目根目录运行此脚本，并已安装所有依赖。")
    sys.exit(1)

# ----- 全局常量 -----
HOST = "0.0.0.0"  # 监听所有网络接口
PORT = 9000       # 使用指定的 9000 端口

def main():
    """主函数"""
    # 初始化日志系统
    setup_logging()

    # 挂载静态文件目录
    # 这会告诉FastAPI，任何不匹配API路由的请求都应尝试从'vue/dist'目录中查找文件
    # html=True 确保了对于像 '/' 这样的路径，它会提供 'index.html'
    static_files_path = project_root / "src" / "frontend" / "dist"
    if not static_files_path.exists():
        print(f"错误: 前端静态文件目录不存在: {static_files_path}")
        print("请先在 'src/frontend' 目录下运行 'npm run build' 来生成前端文件。")
        sys.exit(1)

    app.mount("/", StaticFiles(directory=static_files_path, html=True), name="static")

    print("=" * 50)
    print("漫画翻译工具 - Web 服务器模式")
    print(f"服务正在启动，请通过 http://<你的IP地址>:{PORT} 访问")
    print("=" * 50)

    # 启动 uvicorn 服务器
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        reload=False,  # 生产模式下禁用自动重载
        log_level="info",
    )

if __name__ == "__main__":
    main()