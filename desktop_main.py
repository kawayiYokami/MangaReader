#!/usr/bin/env python3
"""
漫画翻译工具 - PyWebView桌面版
基于现有Web版本，使用PyWebView创建桌面应用
"""

import webview
import threading
import time
import sys
import os
import logging
from pathlib import Path
import traceback # 保留用于打印错误
import json # 用于创建JS事件的JSON payload
import asyncio

from utils.manga_logger import setup_logging

# ----- 辅助函数：在后台线程中运行异步任务 -----
def run_async_task(coro):
    """在一个新线程中为每个任务创建一个新的事件循环来运行它"""
    def thread_target():
        try:
            asyncio.run(coro)
        except Exception as e:
            # 在这里记录或处理线程内发生的异常
            logging.error(f"后台异步任务执行失败: {e}", exc_info=True)

    thread = threading.Thread(target=thread_target)
    thread.start()
# ---------------------------------------------


# ----- 全局变量 -----
desktop_app_instance = None # 用于全局函数/API方法访问应用实例
core_interface = None       # 全局 CoreInterface 实例
manga_manager = None        # 全局 MangaManager 实例
# --------------------

# 导入现有的Web应用和核心接口
def import_dependencies():
    """尝试导入必要的依赖"""
    app = None
    app_type = "unknown"
    core_interface_instance = None
    manga_manager_instance = None

    # 方案1: 尝试导入完整的Web应用和核心接口
    try:
        from web.app import app as fastapi_app
        from web.core_interface import get_core_interface
        from core.manga.manga_manager import MangaManager # 直接导入 MangaManager

        print("[SUCCESS] 成功导入完整Web应用、核心接口及漫画管理器")
        app = fastapi_app
        app_type = "full"
        core_interface_instance = get_core_interface() # 获取核心接口实例

        # 获取漫画管理器实例 - 通常核心接口会持有它
        if hasattr(core_interface_instance, 'manga_manager'):
             manga_manager_instance = core_interface_instance.manga_manager
             logging.info("[SUCCESS] 成功从核心接口获取漫画管理器实例")
        else:
             logging.error("[ERROR] 核心接口未能提供漫画管理器实例！")


        return app, app_type, core_interface_instance, manga_manager_instance
    except ImportError as e:
        print(f"[WARNING] 无法导入完整Web应用、核心接口或漫画管理器: {e}")
        logging.error(f"[WARNING] 无法导入完整Web应用、核心接口或漫画管理器: {e}", exc_info=True)


    # 方案2: 尝试创建简化版Web应用 (如果完整版失败)
    # (简化版代码省略)
    print("[WARNING] 简化版Web应用模式（或导入失败）")
    return None, "simple", None, None

# 导入依赖
app, app_type, core_interface, manga_manager = import_dependencies() # 使用全局变量

if app is None and app_type != "simple":
     logging.error("[ERROR] 无法加载Web应用！")
     sys.exit(1)

if app_type == "full":
    if core_interface is None:
        logging.warning("[WARNING] 无法获取核心接口实例，部分后端功能可能受限")
    if manga_manager is None:
         logging.warning("[WARNING] 无法获取漫画管理器实例，目录设置/扫描功能将不可用")


# ----- 后端逻辑实现 (供API或全局函数调用) -----

def _dispatch_feedback_event(success, message, added=0, failed=0):
    """
    辅助函数：向JavaScript发送反馈事件。
    重构说明：移除了所有前端逻辑，后端只负责发送带有数据的纯净事件。
    前端的Vue应用将监听'desktopImportComplete'事件并决定如何响应。
    """
    global desktop_app_instance
    target_window = None
    if desktop_app_instance and desktop_app_instance.window:
        target_window = desktop_app_instance.window
    elif webview.windows:
         target_window = webview.windows[0]

    if target_window:
        try:
            logging.debug(f"发送桌面事件反馈: success={success}, message='{message}'")
            detail_payload = {"success": success, "message": message, "added": added, "failed": failed}
            # 使用json.dumps确保特殊字符被正确转义
            detail_json = json.dumps(detail_payload, ensure_ascii=False)

            # 只发送一个干净的、携带数据的自定义事件
            js_code = f'window.dispatchEvent(new CustomEvent("desktopImportComplete", {{ detail: {detail_json} }}));'

            target_window.evaluate_js(js_code)
            logging.debug("桌面事件已成功发送")
        except Exception as e:
            logging.error(f"发送桌面事件失败: {e}", exc_info=True)
    else:
        logging.error("无法发送桌面事件，窗口实例不可用")


def _trigger_select_directory_logic():
    """打开目录选择对话框并调用漫画管理器的设置目录方法"""
    global desktop_app_instance, manga_manager # 确保漫画管理器可用
    logging.info("目录选择逻辑: 开始执行")

    if not desktop_app_instance:
         logging.error("目录选择逻辑: 桌面应用实例不可用")
         _dispatch_feedback_event(success=False, message="应用实例不可用")
         return
    if not manga_manager:
         logging.error("目录选择逻辑: 漫画管理器实例不可用")
         _dispatch_feedback_event(success=False, message="漫画管理器不可用")
         return

    current_window = None
    if desktop_app_instance.window:
        current_window = desktop_app_instance.window
    elif webview.windows:
         current_window = webview.windows[0]

    if not current_window:
         logging.error("目录选择逻辑: 窗口实例不可用")
         _dispatch_feedback_event(success=False, message="窗口实例不可用")
         return

    try:
        logging.info(f"目录选择逻辑: 在窗口上调用文件对话框: {current_window}")
        result = current_window.create_file_dialog(webview.FOLDER_DIALOG)
        logging.info(f"目录选择逻辑: 文件对话框结果: {result}")

        if result and isinstance(result, tuple) and len(result) > 0:
            selected_path = result[0]
            logging.info(f"目录选择逻辑: 已选择目录: {selected_path}，正在后台线程中异步添加...")

            try:
                # 使用辅助函数在后台运行异步的 add_manga_from_path
                run_async_task(manga_manager.add_manga_from_path(selected_path))
                
                # 注意：这里立即返回，真正的结果将通过WebSocket事件在UI上更新
                logging.info(f"目录选择逻辑: 已成功分派异步添加任务: '{selected_path}'")
                _dispatch_feedback_event(success=True, message=f"已开始扫描目录 '{os.path.basename(selected_path)}'...")
            except Exception as e_dispatch:
                 logging.error(f"目录选择逻辑错误: 分派异步添加任务失败: {e_dispatch}", exc_info=True)
                 _dispatch_feedback_event(success=False, message=f"启动扫描时出错: {e_dispatch}")

        else:
            logging.info("目录选择逻辑: 用户未选择目录或对话框被取消")
            _dispatch_feedback_event(success=False, message="用户未选择目录")

    except Exception as e_dialog:
        error_msg = f"打开目录选择器时出错: {e_dialog}"
        logging.error(f"目录选择逻辑错误: {error_msg}", exc_info=True)
        _dispatch_feedback_event(success=False, message=f"打开目录选择器失败: {e_dialog}")


# ----- 修改：触发文件选择的逻辑 (修正文件类型格式) -----
def _trigger_select_file_logic():
    """打开文件选择对话框并直接处理导入（修正文件类型格式）"""
    global desktop_app_instance, core_interface # 需要核心接口
    logging.info("文件选择逻辑: 开始执行")

    if not desktop_app_instance:
         logging.error("文件选择逻辑: 桌面应用实例不可用")
         _dispatch_feedback_event(success=False, message="应用实例不可用")
         return
    if not core_interface: # 检查核心接口
         logging.error("文件选择逻辑: 核心接口不可用")
         _dispatch_feedback_event(success=False, message="核心接口不可用，无法导入文件")
         return

    current_window = None
    if desktop_app_instance.window:
        current_window = desktop_app_instance.window
    elif webview.windows:
         current_window = webview.windows[0]

    if not current_window:
         logging.error("文件选择逻辑: 窗口实例不可用")
         _dispatch_feedback_event(success=False, message="窗口实例不可用")
         return

    try:
        logging.info(f"文件选择逻辑: 在窗口上调用文件对话框(打开对话框): {current_window}")
        # 修正Windows下的文件类型格式
        file_types = ('漫画压缩包 (*.zip;*.cbz;*.cbr;*.rar)', '所有文件 (*.*)')
        # 另一种可能的格式，如果上面不行可以尝试:
        # file_types = ('漫画压缩包', '*.zip;*.cbz;*.cbr;*.rar', '所有文件', '*.*')

        result = current_window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=file_types # 使用修正后的格式
        )
        logging.info(f"文件选择逻辑: 文件对话框结果: {result}")

        if result and isinstance(result, tuple) and len(result) > 0:
            selected_files = result
            logging.info(f"文件选择逻辑: 已选择 {len(selected_files)} 个文件，开始直接处理...")

            added_count = 0
            failed_count = 0
            errors = []

            # 直接在此处循环处理，不使用额外线程
            # 这个逻辑需要改变，因为add_manga_from_path是异步的
            # 我们应该为每个文件分派一个任务，并在最后给出一个统一的反馈
            logging.info(f"文件选择逻辑: 正在为 {len(selected_files)} 个文件分派异步添加任务...")
            
            for file_path in selected_files:
                # 为每个文件在后台启动一个异步任务
                run_async_task(core_interface.add_manga_from_path(file_path))

            # 立即向用户反馈，告知任务已开始
            # 详细的进度和结果将通过WebSocket和事件在UI上更新
            final_message = f"已开始在后台处理 {len(selected_files)} 个文件。完成后列表将自动刷新。"
            _dispatch_feedback_event(success=True, message=final_message, added=len(selected_files), failed=0)
            logging.info("文件选择逻辑: 所有异步任务分派完成。")

        else:
            logging.info("文件选择逻辑: 用户未选择文件或对话框被取消")
            _dispatch_feedback_event(success=False, message="用户未选择文件")

    except Exception as e_dialog:
        # 捕获特定于文件过滤器的错误
        if "not a valid file filter" in str(e_dialog):
            error_msg = f"文件过滤器格式错误: {e_dialog}"
            logging.error(f"文件选择逻辑错误: 文件过滤器格式无效，尝试使用: {file_types}", exc_info=True)
        else:
            error_msg = f"打开文件选择器时出错: {e_dialog}"
            logging.error(f"文件选择逻辑错误: {error_msg}", exc_info=True)
        _dispatch_feedback_event(success=False, message=f"打开文件选择器失败: {e_dialog}") # 将原始错误发给前端


# ----- 简单的 API 类 (用于 js_api) -----
class DesktopApi:
    """一个极其简单的类，其方法用于触发后端逻辑，通过 js_api 传递"""
    def trigger_select_directory(self):
        """由前端调用，触发选择目录的流程"""
        logging.info("收到选择目录请求")
        try:
             _trigger_select_directory_logic()
             return {"success": True, "message": "目录选择流程已启动"}
        except Exception as e:
             logging.error(f"启动目录选择失败: {e}", exc_info=True)
             return {"success": False, "message": f"启动目录选择时出错: {e}"}

    # ----- 恢复：触发文件选择的API方法 -----
    def trigger_select_file(self):
        """由JavaScript调用，触发选择文件的流程"""
        logging.info("JavaScript API: 收到文件选择请求")
        try:
            _trigger_select_file_logic() # 直接调用重写后的逻辑函数
            # 同步返回成功，表示调用已收到。实际结果通过事件反映。
            return {"success": True, "message": "文件选择流程已启动"}
        except Exception as e:
            logging.error(f"JavaScript API错误: 文件选择失败: {e}", exc_info=True)
            return {"success": False, "message": f"启动文件选择时出错: {e}"}
# -----------------------------------------

class MangaTranslatorDesktop:
    """漫画翻译工具桌面版主类"""

    def __init__(self):
        global core_interface, manga_manager # 确保我们使用的是全局实例
        self.app = app
        self.port = 8082
        self.host = '127.0.0.1'
        self.server_thread = None
        self.window = None
        self.core_interface = core_interface # 从全局获取
        self.manga_manager = manga_manager   # 从全局获取
        self.api = DesktopApi() # 创建简单的 API 实例

        logging.info(" 漫画翻译工具桌面版初始化中...")
        if app_type == "full":
            if not self.core_interface: logging.warning("[WARNING] 核心接口未加载")
            if not self.manga_manager: logging.warning("[WARNING] 漫画管理器未加载，目录功能不可用")
        elif app_type != "full":
             logging.warning("[WARNING] 运行在简化模式或应用导入失败，桌面功能不可用")

    def start_web_server(self):
        # (Web服务器启动逻辑保持不变)
        try:
            logging.info(f" 启动Web服务器: http://{self.host}:{self.port}")
            import uvicorn
            uvicorn.run(self.app, host=self.host, port=self.port, log_level="warning", access_log=False)
        except Exception as e:
            logging.error(f"[ERROR] Web服务器启动失败: {e}", exc_info=True); raise

    def wait_for_server(self, timeout=10):
        # (等待服务器逻辑保持不变)
        import requests
        start_time = time.time(); url = f"http://{self.host}:{self.port}"
        logging.info(" 等待Web服务器启动...")
        while time.time() - start_time < timeout:
            try:
                if requests.get(url, timeout=1).status_code == 200: logging.info("[SUCCESS] Web服务器已就绪"); return True
            except requests.exceptions.RequestException: pass
            time.sleep(0.5)
        logging.error("[ERROR] Web服务器启动超时"); return False

    def create_desktop_window(self):
        logging.info(" 创建桌面窗口...")
        try:
            window_config = {
                'title': ' 漫画翻译工具',
                'url': f"http://{self.host}:{self.port}",
                'width': 1200, 'height': 800, 'min_size': (800, 600),
                'resizable': True, 'fullscreen': False, 'minimized': False,
                'on_top': False, 'shadow': True, 'focus': True,
                'js_api': self.api # 传递简单实例
            }
            logging.info(f"使用JavaScript API创建窗口: {self.api}")
            webview.settings['ALLOW_DOWNLOADS'] = True
            self.window = webview.create_window(**window_config)

            if self.window:
                 logging.info(f"[SUCCESS] 桌面窗口创建成功，包含JavaScript API，窗口对象: {self.window}")
            else:
                 logging.error("[ERROR] 窗口对象创建失败！")
                 raise Exception("创建PyWebView窗口失败")

            return self.window
        except Exception as e:
            logging.error(f"[ERROR] 创建桌面窗口失败: {e}", exc_info=True)
            raise

    def run(self):
        global desktop_app_instance # 设置全局实例引用
        desktop_app_instance = self

        try:
            logging.info("启动服务器线程...")
            self.server_thread = threading.Thread(target=self.start_web_server, daemon=True)
            self.server_thread.start()
            if not self.wait_for_server(): return False

            logging.info("创建窗口...")
            self.create_desktop_window()
            logging.info(f"窗口创建后的实例: {self.window}")

            logging.info(" 启动PyWebView事件循环...")
            
            # 启用持久化存储，解决缓存问题
            # 必须设置 private_mode=False 并提供一个 storage_path
            storage_path = Path.home() / ".manga_translator_cache" / "pywebview"
            if not storage_path.exists():
                storage_path.mkdir(parents=True, exist_ok=True)
            logging.info(f"设置PyWebView持久化存储路径: {storage_path}")

            webview.start(
                debug=False,
                private_mode=False,  # 禁用私有模式以保留缓存
                # storage_path=str(storage_path) # 指定持久化存储路径
            )

            logging.info(" 桌面应用程序已关闭")
            return True
        except KeyboardInterrupt:
            logging.info(" 用户中断，正在关闭..."); return True
        except Exception as e:
            logging.error(f"[ERROR] 桌面应用程序运行失败: {e}", exc_info=True); return False
        finally:
             logging.info("清理全局实例")
             desktop_app_instance = None

def main():
    print(" 漫画翻译工具 - PyWebView桌面版")
    print("=" * 50)
    setup_logging() # 在应用启动时设置日志
    try:
        # 确保 MangaManager 和 CoreInterface 实例在创建 MangaTranslatorDesktop 之前已准备好
        if app_type == "full":
             if core_interface is None:
                  logging.error("无法获取核心接口实例，桌面文件导入功能将不可用")
                  # 考虑是否退出
             if manga_manager is None:
                  logging.error("无法获取漫画管理器实例，目录设置功能将不可用")
             
        desktop_app = MangaTranslatorDesktop()
        success = desktop_app.run()
        print("[SUCCESS] Application exited." if success else "[ERROR] Application exited abnormally.")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"[ERROR] 应用程序启动失败: {e}")
        logging.error(f"应用程序启动失败: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
