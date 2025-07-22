# run_api_server.py
"""
漫画翻译工具 - 纯API服务器启动脚本
"""
import uvicorn
import argparse
import sys
from pathlib import Path

# 添加项目根目录到sys.path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    parser = argparse.ArgumentParser(description="Manga API Server Launcher")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8100, help="Port to bind (default: 8100)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    print("🚀 启动纯API服务器...")
    print(f"   - 地址: http://{args.host}:{args.port}")
    print(f"   - 文档: http://{args.host}:{args.port}/api/docs")
    print(f"   - 热加载: {'开启' if args.reload else '关闭'}")
    print("==================================================")

    uvicorn.run(
        "web.api_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="debug",
    )

if __name__ == "__main__":
    main()