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
import argparse
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
    from src.backend.web.utils.port_manager import PortManager
    from src.backend.web.utils.singleton_checker import SingletonChecker
    from src.backend.web.utils.port_config_manager import PortConfigManager
except ImportError as e:
    print(f"错误: 无法导入项目模块: {e}")
    print("请确保从项目根目录运行此脚本，并已安装所有依赖。")
    sys.exit(1)

# ----- 全局常量 -----
HOST = "0.0.0.0"  # 监听所有网络接口
DEFAULT_PORT = 9000  # 默认端口

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="漫画翻译工具 - Web 服务器")
    parser.add_argument("--port", type=int, 
                       help="指定端口号 (覆盖配置文件设置)")
    parser.add_argument("--host", type=str, 
                       help="指定主机地址 (覆盖配置文件设置)")
    parser.add_argument("--auto-kill", action="store_true", 
                       help="自动杀死占用端口的进程 (覆盖配置文件设置)")
    parser.add_argument("--port-range", type=int, 
                       help="端口搜索范围 (覆盖配置文件设置)")
    parser.add_argument("--config-show", action="store_true", 
                       help="显示当前配置并退出")
    return parser.parse_args()

def main():
    """主函数"""
    singleton = None
    
    try:
        # 解析命令行参数
        args = parse_arguments()
        
        # 初始化配置管理器
        config_manager = PortConfigManager()
        
        # 如果只是显示配置，显示后退出
        if args.config_show:
            config_manager.print_config()
            return
        
        # 加载配置
        web_config = config_manager.get_web_server_config()
        
        # 命令行参数覆盖配置文件
        port = args.port if args.port is not None else web_config.get("preferred_port", DEFAULT_PORT)
        host = args.host if args.host is not None else web_config.get("host", HOST)
        auto_kill = args.auto_kill if args.auto_kill else web_config.get("auto_kill", False)
        port_range = args.port_range if args.port_range is not None else web_config.get("port_range", 100)
        
        # 初始化日志系统
        setup_logging()

        # 检查应用单例
        singleton = SingletonChecker("MangaReader-Web")
        if singleton.is_another_instance_running():
            info = singleton.get_running_instance_info()
            if info:
                print(f"错误: Web服务器已在运行 (PID: {info.get('PID', 'Unknown')})")
                print(f"启动时间: {info.get('Start time', 'Unknown')}")
            else:
                print("错误: Web服务器已在运行")
            print("请先关闭正在运行的实例。")
            sys.exit(1)

        # 获取单例锁
        try:
            singleton.acquire_lock()
        except Exception as e:
            print(f"错误: 无法获取应用锁: {e}")
            sys.exit(1)

        # 确保端口可用
        try:
            available_port = PortManager.ensure_port_available(
                preferred_port=port,
                auto_kill=auto_kill
            )
            if available_port != port:
                print(f"端口 {port} 被占用，已自动切换到端口 {available_port}")
        except RuntimeError as e:
            print(f"错误: {e}")
            sys.exit(1)
        
        # 保存最后使用的端口
        config_manager.set_last_used_port("web_server", available_port)

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
        print(f"服务正在启动，请通过 http://<你的IP地址>:{available_port} 访问")
        if available_port != port:
            print(f"注意: 端口已从 {port} 自动切换到 {available_port}")
        print("=" * 50)

        # 启动 uvicorn 服务器
        uvicorn.run(
            app,
            host=host,
            port=available_port,
            reload=False,  # 生产模式下禁用自动重载
            log_level="info",
        )
        
    except KeyboardInterrupt:
        print("\n用户中断，正在关闭服务器...")
    except Exception as e:
        print(f"启动服务器时发生错误: {e}")
        sys.exit(1)
    finally:
        # 释放单例锁
        if singleton:
            singleton.release_lock()

if __name__ == "__main__":
    main()