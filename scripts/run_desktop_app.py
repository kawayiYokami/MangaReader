#!/usr/bin/env python3
"""
漫画翻译工具 - 桌面版应用启动器 (生产模式)

此脚本用于启动最终的桌面应用程序。

功能:
1. 在后台线程中启动 FastAPI (uvicorn) 后端服务器。
2. 创建一个 PyWebView 窗口。
3. 将 PyWebView 窗口指向由 'npm run build' 命令生成的、位于 'vue/dist' 目录下的
   静态前端文件 (index.html)。
4. 将文件操作相关的 Python 函数 (DesktopApi) 暴露给前端 JavaScript。
5. 这是一个统一的启动器，最终可以用于 PyInstaller 打包。
"""

import webview
from webview.dom import DOMEventHandler
import sys
import os
import logging
import json
import requests
import subprocess
import threading
import time
import uvicorn
import argparse
from pathlib import Path

# 将项目根目录添加到Python路径
if hasattr(sys, '_MEIPASS'):
    # 在 PyInstaller 打包的环境中，使用MEIPASS作为资源根目录
    project_root = Path(sys._MEIPASS)
else:
    # 在开发环境中，使用脚本的上上级目录
    project_root = Path(__file__).parent.parent

sys.path.insert(0, str(project_root))

# 尝试从项目中导入日志模块
try:
    from src.backend.utils.manga_logger import setup_logging
    from src.backend.web.utils.port_manager import PortManager
    from src.backend.web.utils.singleton_checker import SingletonChecker
    from src.backend.web.utils.port_config_manager import PortConfigManager
    setup_logging()
except ImportError as e:
    print(f"错误: 无法导入项目模块: {e}")
    print(f"项目根目录: {project_root}")
    print("请确保从项目根目录运行此脚本，并已安装所有依赖。")
    print("\n按任意键退出...")
    try:
        input()
    except Exception:
        import time
        time.sleep(10)
    sys.exit(1)


# ----- 全局常量 -----
DEFAULT_PORT = 9000
DEFAULT_HOST = "127.0.0.1"

# 全局变量，用于存储实际使用的端口
actual_port = DEFAULT_PORT
actual_host = DEFAULT_HOST

try:
    from src.backend.web.api_server import app as fastapi_app
    from fastapi.staticfiles import StaticFiles
except ImportError as e:
    print(f"ERROR: 关键模块导入失败: {e}")
    print("请确保所有依赖都已正确安装，并且脚本在正确的项目结构中运行。")
    print("\n按任意键退出...")
    try:
        input()
    except Exception:
        import time
        time.sleep(10)  # 如果input()失败，等待10秒
    sys.exit(1)

def run_server():
    """在后台线程中运行 uvicorn 服务器，并预先挂载静态文件。"""
    global actual_port, actual_host
    logging.info(f"准备在后台线程启动API服务器，地址 http://{actual_host}:{actual_port}")

    # 挂载静态文件目录 - 处理打包后的路径问题
    if hasattr(sys, '_MEIPASS'):
        # 在 PyInstaller 打包的环境中
        static_files_path = Path(sys._MEIPASS) / "src" / "frontend" / "dist"
    else:
        # 在开发环境中
        project_root = Path(__file__).parent.parent
        static_files_path = project_root / "src" / "frontend" / "dist"

    if not static_files_path.exists() or not (static_files_path / "index.html").exists():
        logging.error(f"前端静态文件目录不存在或不完整: {static_files_path}")
        logging.error("请先在 'src/frontend' 目录下运行 'npm run build' 来生成前端文件。")
        # 在桌面应用中，我们不能直接退出，但至少要记录错误
        return

    fastapi_app.mount("/", StaticFiles(directory=static_files_path, html=True), name="static")

    try:
        uvicorn.run(
            fastapi_app, # 直接传递修改后的 app 对象
            host=actual_host,
            port=actual_port,
            log_level="info",
            reload=False
        )
        logging.info("Uvicorn 服务器已正常关闭。")
    except Exception as e:
        logging.error(f"Uvicorn 服务器启动或运行时发生严重错误: {e}", exc_info=True)

# ----- 辅助函数 (与 dev 启动器相同) -----
def _dispatch_feedback_event(window, success, message, **kwargs):
    """辅助函数：向JavaScript发送反馈事件。"""
    if not window:
        logging.error("无法发送桌面事件，窗口实例不可用")
        return
    try:
        detail_payload = {"success": success, "message": message, **kwargs}
        detail_json = json.dumps(detail_payload, ensure_ascii=False)
        js_code = f'window.dispatchEvent(new CustomEvent("desktopActionComplete", {{ detail: {detail_json} }}));'
        window.evaluate_js(js_code)
    except Exception as e:
        logging.error(f"发送桌面事件失败: {e}", exc_info=True)


def _trigger_select_directory_logic(window):
    """打开目录选择对话框，并通过API请求后端进行扫描"""
    global actual_port, actual_host
    api_server_url = f"http://{actual_host}:{actual_port}"

    logging.info("目录选择逻辑: 开始执行")
    try:
        result = window.create_file_dialog(webview.FOLDER_DIALOG)
        if result and isinstance(result, tuple) and len(result) > 0:
            selected_path = result[0]
            logging.info(f"目录选择逻辑: 已选择目录: {selected_path}，正在通过API请求后端扫描...")
            try:
                response = requests.post(
                    f"{api_server_url}/api/manga/scan-directory",
                    json={"directory_path": selected_path},
                    timeout=10
                )
                response.raise_for_status()
                api_response = response.json()
                logging.info(f"API响应: {api_response}")
                _dispatch_feedback_event(window, success=True, message=f"已成功请求后端扫描目录: '{os.path.basename(selected_path)}'。列表将在完成后自动刷新。")
            except requests.exceptions.RequestException as e:
                error_msg = f"调用后端API失败: {e}"
                logging.error(error_msg, exc_info=True)
                _dispatch_feedback_event(window, success=False, message=error_msg)
        else:
            logging.info("目录选择逻辑: 用户未选择目录或对话框被取消")
            _dispatch_feedback_event(window, success=False, message="用户未选择目录")
    except Exception as e_dialog:
        error_msg = f"打开目录选择器时出错: {e_dialog}"
        logging.error(f"目录选择逻辑错误: {error_msg}", exc_info=True)
        _dispatch_feedback_event(window, success=False, message=f"打开目录选择器失败: {e_dialog}")


# ----- API 类 (用于 js_api, 与 dev 启动器相同) -----
class DesktopApi:
    def _get_window(self):
        return webview.windows[0] if webview.windows else None

    def trigger_select_directory(self):
        logging.info("JS API: 收到选择目录请求")
        window = self._get_window()
        if not window:
            logging.error("无法触发目录选择：窗口不存在。")
            return {"success": False, "message": "窗口实例不可用"}
        try:
             threading.Thread(target=_trigger_select_directory_logic, args=(window,)).start()
             return {"success": True, "message": "目录选择流程已启动"}
        except Exception as e:
             logging.error(f"启动目录选择失败: {e}", exc_info=True)
             return {"success": False, "message": f"启动目录选择时出错: {e}"}

    def open_in_explorer(self, file_path: str):
        logging.info(f"JS API: 收到在文件浏览器中打开的请求: {file_path}")
        window = self._get_window()
        if not file_path or not os.path.exists(file_path):
            msg = f"文件路径不存在或无效: {file_path}"
            logging.error(msg)
            _dispatch_feedback_event(window, success=False, message=msg)
            return {"success": False, "message": msg}
        try:
            command = []
            if sys.platform == "win32":
                command = ['explorer', '/select,', os.path.normpath(file_path)]
            elif sys.platform == "darwin":
                command = ['open', '-R', file_path]
            else:
                dir_path = os.path.dirname(file_path)
                command = ['xdg-open', dir_path]
            logging.info(f"执行系统命令: {' '.join(command)}")
            subprocess.run(command)
            msg = f"已成功在文件浏览器中打开: {os.path.basename(file_path)}"
            logging.info(msg)
            _dispatch_feedback_event(window, success=True, message=msg)
            return {"success": True, "message": msg}
        except Exception as e:
            msg = f"在文件浏览器中打开失败: {e}"
            logging.error(msg, exc_info=True)
            _dispatch_feedback_event(window, success=False, message=msg)
            return {"success": False, "message": msg}

# ----- 拖放功能 (纯Python实现) -----
def on_dragover(e):
    """阻止默认行为以允许放置。"""
    pass

def on_drop(e):
    """处理文件放置事件。"""
    global actual_port, actual_host
    api_server_url = f"http://{actual_host}:{actual_port}"

    window = webview.windows[0] if webview.windows else None
    if not window:
        logging.error("无法处理文件放置：窗口实例不可用。")
        return

    try:
        files = e.get('dataTransfer', {}).get('files', [])
        if not files:
            logging.info("拖放事件未包含文件。")
            return

        # 提取由pywebview后端附加的完整路径
        paths = [f.get('pywebviewFullPath') for f in files if f.get('pywebviewFullPath')]
        if not paths:
            logging.warning("从拖放事件中未能提取任何有效文件路径。")
            return

        logging.info(f"文件放置事件: 检测到 {len(paths)} 个项目。准备通过API添加...")

        # 在后台线程中调用API，避免阻塞UI
        def call_api():
            try:
                response = requests.post(
                    f"{api_server_url}/api/manga/add",
                    json={"paths": paths},
                    timeout=60
                )
                response.raise_for_status()
                message = f"已成功接收 {len(paths)} 个拖放项目，正在后台处理..."
                logging.info(message)
                _dispatch_feedback_event(window, success=True, message=message)
            except requests.exceptions.RequestException as req_e:
                error_msg = f"调用后端API失败: {req_e}"
                logging.error(error_msg, exc_info=True)
                _dispatch_feedback_event(window, success=False, message=error_msg)

        threading.Thread(target=call_api).start()

    except Exception as drop_e:
        error_msg = f"处理文件放置时发生未知错误: {drop_e}"
        logging.error(error_msg, exc_info=True)
        _dispatch_feedback_event(window, success=False, message=error_msg)

def bind_drag_drop_events(window):
    """将拖放事件处理器绑定到窗口的DOM上。"""
    logging.info("正在为桌面窗口绑定拖放事件...")
    window.dom.document.events.dragover += DOMEventHandler(on_dragover, prevent_default=True)
    window.dom.document.events.drop += DOMEventHandler(on_drop, prevent_default=True)
    logging.info("拖放事件绑定完成。")


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="漫画翻译工具 - 桌面应用")
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
    global actual_port, actual_host
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
        desktop_config = config_manager.get_desktop_app_config()

        # 命令行参数覆盖配置文件
        port = args.port if args.port is not None else desktop_config.get("preferred_port", DEFAULT_PORT)
        host = args.host if args.host is not None else desktop_config.get("host", DEFAULT_HOST)
        auto_kill = args.auto_kill if args.auto_kill else desktop_config.get("auto_kill", True)
        # port_range = args.port_range if args.port_range is not None else desktop_config.get("port_range", 100)

        print("漫画翻译工具 - 桌面应用 (生产模式)")
        print("=" * 50)
        setup_logging()

        # 检查应用单例
        singleton = SingletonChecker("MangaReader-Desktop")
        if singleton.is_another_instance_running():
            info = singleton.get_running_instance_info()
            if info:
                print(f"错误: 桌面应用已在运行 (PID: {info.get('PID', 'Unknown')})")
                print(f"启动时间: {info.get('Start time', 'Unknown')}")
            else:
                print("错误: 桌面应用已在运行")
            print("请先关闭正在运行的实例。")
            print("\n按任意键退出...")
            try:
                input()
            except Exception:
                time.sleep(10)
            sys.exit(1)

        # 获取单例锁
        try:
            singleton.acquire_lock()
        except Exception as e:
            print(f"错误: 无法获取应用锁: {e}")
            print("\n按任意键退出...")
            try:
                input()
            except Exception:
                time.sleep(10)
            sys.exit(1)

        # 设置实际使用的主机和端口
        actual_host = host

        # 确保端口可用
        try:
            actual_port = PortManager.ensure_port_available(
                preferred_port=port,
                auto_kill=auto_kill
            )
            if actual_port != port:
                print(f"端口 {port} 被占用，已自动切换到端口 {actual_port}")
        except RuntimeError as e:
            print(f"错误: {e}")
            print("\n按任意键退出...")
            try:
                input()
            except Exception:
                time.sleep(10)
            sys.exit(1)

        # 保存最后使用的端口
        config_manager.set_last_used_port("desktop_app", actual_port)

        api_server_url = f"http://{actual_host}:{actual_port}"

        # 在后台启动API服务器
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        logging.info("API服务器线程已启动。等待服务器初始化...")
        time.sleep(3) # 等待3秒，确保服务器完全启动

        # PyWebView 窗口相关设置
        window_title = "Manga Manager"
        api = DesktopApi()

        logging.info(f"即将创建PyWebView窗口，加载后端URL: {api_server_url}")

        # 创建窗口，直接加载 FastAPI 服务器的 URL
        # 这是解决 405 Method Not Allowed 问题的关键
        window = webview.create_window(
            window_title,
            url=api_server_url,
            js_api=api,
            width=1280,
            height=800,
            resizable=True,
            min_size=(900, 600)
        )

        # 启动 PyWebView，并传入事件绑定函数
        webview.settings['ALLOW_DOWNLOADS'] = True
        logging.info("正在启动 PyWebView (生产模式)...")
        webview.start(bind_drag_drop_events, window, debug=False, private_mode=True)
        logging.info("PyWebView 已关闭。应用程序退出。")

    except KeyboardInterrupt:
        print("\n用户中断，正在关闭应用...")
    except Exception as e:
        print(f"启动桌面应用时发生错误: {e}")
        print("\n按任意键退出...")
        try:
            input()
        except Exception:
            time.sleep(10)
        sys.exit(1)
    finally:
        # 释放单例锁
        if singleton:
            singleton.release_lock()

if __name__ == "__main__":
    main()