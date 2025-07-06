#!/usr/bin/env python3
"""
漫画翻译工具 - Web UI 启动器

这是Web版本的启动器，提供与Qt版本相同的功能，但通过Web界面访问。
不会影响或修改现有的Qt应用程序。

使用方法:
    python web_main.py                    # 启动Web服务器，默认端口8000
    python web_main.py --port 8080       # 指定端口
    python web_main.py --host 0.0.0.0    # 指定主机地址
    python web_main.py --debug           # 开发模式
"""

import sys
import argparse
import uvicorn
from pathlib import Path

# 添加项目根目录到Python路径，确保可以导入core模块
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入端口管理器
from web.utils.port_manager import PortManager

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="漫画翻译工具 Web UI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python web_main.py                    # 默认配置启动
  python web_main.py --port 8080       # 指定端口8080
  python web_main.py --host 0.0.0.0    # 允许外部访问
  python web_main.py --debug           # 开发模式，自动重载
        """
    )
    
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="服务器主机地址 (默认: 0.0.0.0, 允许局域网访问)"
    )
    
    parser.add_argument(
        "--port", 
        type=int, 
        default=8100,
        help="服务器端口 (默认: 8100)"
    )
    
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="启用调试模式，代码变更时自动重载"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="工作进程数量 (默认: 1)"
    )

    parser.add_argument(
        "--auto-port",
        action="store_true",
        help="自动选择可用端口"
    )

    parser.add_argument(
        "--kill-port",
        action="store_true",
        help="如果端口被占用，自动杀死占用进程"
    )

    return parser.parse_args()

def check_dependencies():
    """检查必要的依赖是否已安装"""
    required_packages = [
        "fastapi",
        "uvicorn",
        "jinja2",
        "python-multipart"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ 缺少以下依赖包:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n请运行以下命令安装:")
        print(f"   pip install {' '.join(missing_packages)}")
        return False
    
    return True

def main():
    """主函数"""
    print("🌐 漫画翻译工具 - Web UI 启动器")
    print("=" * 50)
    
    # 解析命令行参数
    args = parse_arguments()
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 检查核心模块是否可用
    try:
        from core.config import config
        from core.manga.manga_manager import MangaManager
        print("✅ 核心业务逻辑模块加载成功")
    except ImportError as e:
        print(f"❌ 无法导入核心模块: {e}")
        print("请确保在项目根目录下运行此脚本")
        sys.exit(1)
    
    # 导入Web应用
    try:
        from web.app import app
        print("✅ Web应用模块加载成功")
    except ImportError as e:
        print(f"❌ 无法导入Web应用: {e}")
        print("Web模块可能尚未完全设置")
        sys.exit(1)

    # 端口管理
    try:
        if args.auto_port:
            # 自动选择可用端口
            available_port = PortManager.find_available_port(args.port, args.port + 100, args.host)
            if available_port:
                args.port = available_port
                print(f"🔍 自动选择可用端口: {args.port}")
            else:
                print(f"❌ 无法找到可用端口 (范围: {args.port}-{args.port + 100})")
                sys.exit(1)
        else:
            # 检查指定端口是否可用
            if not PortManager.is_port_available(args.port, args.host):
                process_info = PortManager.get_port_process_info(args.port)
                if process_info:
                    print(f"⚠️  端口 {args.port} 被进程 {process_info['process_name']} (PID: {process_info['pid']}) 占用")

                    if args.kill_port:
                        print(f"🔄 尝试杀死占用进程...")
                        if PortManager.kill_port_process(args.port):
                            print(f"✅ 成功释放端口 {args.port}")
                            import time
                            time.sleep(1)  # 等待端口释放
                        else:
                            print(f"❌ 无法释放端口 {args.port}")
                            sys.exit(1)
                    else:
                        print(f"💡 提示: 使用 --kill-port 参数自动杀死占用进程，或使用 --auto-port 自动选择可用端口")
                        sys.exit(1)
                else:
                    print(f"❌ 端口 {args.port} 被占用，但无法获取进程信息")
                    sys.exit(1)
    except Exception as e:
        print(f"❌ 端口管理失败: {e}")
        sys.exit(1)

    # 显示启动信息
    print(f"🚀 启动Web服务器...")
    print(f"   主机地址: {args.host}")
    print(f"   端口: {args.port}")
    print(f"   调试模式: {'开启' if args.debug else '关闭'}")
    print(f"   访问地址: http://{args.host}:{args.port}")
    print("=" * 50)
    print("按 Ctrl+C 停止服务器")
    
    # 启动服务器
    try:
        uvicorn.run(
            "web.app:app",
            host=args.host,
            port=args.port,
            reload=args.debug,
            workers=args.workers if not args.debug else 1,
            access_log=args.debug
        )
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
    except Exception as e:
        print(f"❌ 服务器启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
