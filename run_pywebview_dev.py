#!/usr/bin/env python3
"""
漫画翻译工具 - PyWebView桌面版 (开发模式启动器)

此脚本用于在开发Vue前端时，启动一个PyWebView窗口来加载Vue开发服务器。
它不启动任何后端Web服务器，而是依赖于独立运行的`run_api_server.py`。

功能:
1. 创建一个PyWebView窗口，加载 http://localhost:5173。
2. 将文件操作相关的Python函数暴露给前端JavaScript，以便在开发环境中
   测试需要与桌面环境交互的功能 (例如 "打开目录" 按钮)。
3. 通过HTTP API与后端服务通信，实现前后端完全解耦。
"""

import webview
import sys
import os
import logging
import json
import requests # 用于发送HTTP请求
import subprocess # 导入 subprocess 模块
from pathlib import Path

# 尝试从项目中导入日志模块
try:
    from utils.manga_logger import setup_logging
except ImportError:
    print("错误: 无法导入项目模块。请确保从项目根目录运行此脚本。")
    project_root = Path(__file__).parent.resolve()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
        print(f"已将 '{project_root}' 添加到 sys.path。请重试。")
    sys.exit(1)


# ----- 全局常量 -----
API_SERVER_URL = "http://localhost:8100"


# ----- 辅助函数 -----

def _dispatch_feedback_event(window, success, message, **kwargs):
    """辅助函数：向JavaScript发送反馈事件。"""
    if not window:
        logging.error("无法发送桌面事件，窗口实例不可用")
        return

    try:
        logging.debug(f"发送桌面事件反馈: success={success}, message='{message}'")
        detail_payload = {"success": success, "message": message, **kwargs}
        detail_json = json.dumps(detail_payload, ensure_ascii=False)
        js_code = f'window.dispatchEvent(new CustomEvent("desktopActionComplete", {{ detail: {detail_json} }}));'
        window.evaluate_js(js_code)
        logging.debug("桌面事件已成功发送")
    except Exception as e:
        logging.error(f"发送桌面事件失败: {e}", exc_info=True)


def _trigger_select_directory_logic(window):
    """打开目录选择对话框，并通过API请求后端进行扫描"""
    logging.info("目录选择逻辑: 开始执行")

    try:
        result = window.create_file_dialog(webview.FOLDER_DIALOG)
        logging.info(f"目录选择逻辑: 文件对话框结果: {result}")

        if result and isinstance(result, tuple) and len(result) > 0:
            selected_path = result[0]
            logging.info(f"目录选择逻辑: 已选择目录: {selected_path}，正在通过API请求后端扫描...")

            try:
                # 向后端API发送请求
                response = requests.post(
                    f"{API_SERVER_URL}/api/manga/scan-directory",
                    json={"directory_path": selected_path},
                    timeout=10 # 10秒超时
                )
                response.raise_for_status()  # 如果状态码是 4xx 或 5xx，则抛出异常

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


# ----- API 类 (用于 js_api) -----
class DesktopApi:
    """
    一个简单的类，其方法通过 js_api 暴露给前端。
    方法内部通过 webview.windows 动态获取当前窗口实例。
    """
    def _get_window(self):
        return webview.windows[0] if webview.windows else None

    def trigger_select_directory(self):
        """由前端调用，触发选择目录的流程"""
        logging.info("JS API: 收到选择目录请求")
        window = self._get_window()
        if not window:
            logging.error("无法触发目录选择：窗口不存在。")
            return {"success": False, "message": "窗口实例不可用"}
        try:
             # 在后台线程中运行，以避免阻塞UI线程
             import threading
             threading.Thread(target=_trigger_select_directory_logic, args=(window,)).start()
             return {"success": True, "message": "目录选择流程已启动"}
        except Exception as e:
             logging.error(f"启动目录选择失败: {e}", exc_info=True)
             return {"success": False, "message": f"启动目录选择时出错: {e}"}

    def open_in_explorer(self, file_path: str):
        """在文件浏览器中打开并选中指定文件"""
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
                # 在 Windows 上，使用 explorer 的 /select 参数
                command = ['explorer', '/select,', os.path.normpath(file_path)]
            elif sys.platform == "darwin":
                # 在 macOS 上，使用 open 的 -R 参数
                command = ['open', '-R', file_path]
            else:
                # 在 Linux 上，打开文件所在的目录
                dir_path = os.path.dirname(file_path)
                command = ['xdg-open', dir_path]
            
            logging.info(f"执行系统命令: {' '.join(command)}")
            # 在Windows上，explorer.exe即使成功也可能返回非零退出码，所以移除 check=True
            subprocess.run(command)
            
            msg = f"已成功在文件浏览器中打开: {os.path.basename(file_path)}"
            logging.info(msg)
            # 给前端发送一个非阻塞的通知事件
            _dispatch_feedback_event(window, success=True, message=msg)
            return {"success": True, "message": msg}

        except Exception as e:
            msg = f"在文件浏览器中打开失败: {e}"
            logging.error(msg, exc_info=True)
            _dispatch_feedback_event(window, success=False, message=msg)
            return {"success": False, "message": msg}



def main():
    """主函数"""
    print("漫画翻译工具 - PyWebView 开发模式")
    print("=" * 50)
    setup_logging() # 恢复原始调用

    # PyWebView 窗口相关设置
    vue_dev_server_url = "http://localhost:5173"
    window_title = "漫画翻译工具 (开发模式)"
    api = DesktopApi()

    logging.info("此脚本不启动后端服务，请确保 `run_api_server.py` 正在运行。")

    # 创建窗口时通过 js_api 参数直接暴露API
    webview.create_window(
        window_title,
        url=vue_dev_server_url,
        js_api=api,
        width=1280,
        height=800,
        resizable=True,
        min_size=(900, 600)
    )

    # 启动 PyWebView
    logging.info(f"正在启动 PyWebView，加载 URL: {vue_dev_server_url}")
    webview.start(debug=True, private_mode=False)
    logging.info("PyWebView 已关闭。")


if __name__ == "__main__":
    main()