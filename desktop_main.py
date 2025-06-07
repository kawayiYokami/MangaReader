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

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# ----- 全局变量 -----
desktop_app_instance = None # 用于全局函数/API方法访问应用实例
core_interface = None       # 全局 CoreInterface 实例
manga_manager = None        # 全局 MangaManager 实例
# --------------------

# 导入现有的Web应用 和 Core Interface
def import_dependencies():
    """尝试导入必要的依赖"""
    app = None
    log_module = None
    app_type = "unknown"
    core_interface_instance = None
    manga_manager_instance = None

    # 方案1: 尝试导入完整的Web应用 和 Core Interface
    try:
        from web.app import app as fastapi_app
        from utils import manga_logger as log
        from web.core_interface import get_core_interface
        from core.manga_manager import MangaManager # 直接导入 MangaManager

        print("✅ 成功导入完整Web应用、Core Interface及MangaManager")
        app = fastapi_app
        log_module = log
        app_type = "full"
        core_interface_instance = get_core_interface() # 获取 CoreInterface 实例

        # 获取 MangaManager 实例 - 通常 CoreInterface 会持有它
        if hasattr(core_interface_instance, 'manga_manager'):
             manga_manager_instance = core_interface_instance.manga_manager
             log.info("✅ 成功从 CoreInterface 获取 MangaManager 实例")
        else:
             log.error("❌ CoreInterface 未能提供 MangaManager 实例！")


        return app, log_module, app_type, core_interface_instance, manga_manager_instance
    except ImportError as e:
        print(f"⚠️ 无法导入完整Web应用、Core Interface或MangaManager: {e}")
        # 尝试获取日志模块以便后续使用
        try:
            from utils import manga_logger as log
            log_module = log
        except ImportError:
            class SimpleLogger: # 简单的日志替代品
                def info(self, msg): print(f"INFO: {msg}")
                def error(self, msg, exc_info=False): print(f"ERROR: {msg}")
                def warning(self, msg): print(f"WARNING: {msg}")
            log_module = SimpleLogger()

    # 方案2: 尝试创建简化版Web应用 (如果完整版失败)
    # (简化版代码省略)
    print("⚠️ 简化版Web应用模式（或导入失败）")
    return None, log_module, "simple", None, None

# 导入依赖
app, log, app_type, core_interface, manga_manager = import_dependencies() # 使用全局变量

if app is None and app_type != "simple":
     log.error("❌ 无法加载Web应用！")
     sys.exit(1)

if app_type == "full":
    if core_interface is None:
        log.warning("⚠️ 无法获取 Core Interface 实例，部分后端功能可能受限。")
    if manga_manager is None:
         log.warning("⚠️ 无法获取 MangaManager 实例，目录设置/扫描功能将不可用。")


# ----- 后端逻辑实现 (供API或全局函数调用) -----

def _dispatch_feedback_event(success, message, added=0, failed=0):
    """Helper function to dispatch feedback event to JS."""
    global desktop_app_instance
    target_window = None
    if desktop_app_instance and desktop_app_instance.window:
        target_window = desktop_app_instance.window
    elif webview.windows:
         target_window = webview.windows[0]

    if target_window:
        try:
            log.debug(f"发送桌面事件反馈: 成功={success}, 消息={message}")
            detail_payload = {"success": success, "message": message, "added": added, "failed": failed}
            detail_json = json.dumps(detail_payload, ensure_ascii=False)
            js_code = f'window.dispatchEvent(new CustomEvent("desktopImportComplete", {{ detail: {detail_json} }}));'
            target_window.evaluate_js(js_code)
            log.debug("桌面事件已发送")
        except Exception as e:
            log.error(f"发送桌面事件失败: {e}", exc_info=True)
    else:
        log.error("无法发送桌面事件，窗口实例不可用")


def _trigger_select_directory_logic():
    """打开目录选择对话框并调用 MangaManager.set_manga_dir"""
    global desktop_app_instance, manga_manager # 确保 manga_manager 可用
    log.info("SELECT_DIR_LOGIC: Called.")

    if not desktop_app_instance:
         log.error("SELECT_DIR_LOGIC: desktop_app instance unavailable.")
         _dispatch_feedback_event(success=False, message="应用实例不可用")
         return
    if not manga_manager:
         log.error("SELECT_DIR_LOGIC: MangaManager instance unavailable.")
         _dispatch_feedback_event(success=False, message="漫画管理器不可用")
         return

    current_window = None
    if desktop_app_instance.window:
        current_window = desktop_app_instance.window
    elif webview.windows:
         current_window = webview.windows[0]

    if not current_window:
         log.error("SELECT_DIR_LOGIC: Window instance unavailable.")
         _dispatch_feedback_event(success=False, message="窗口实例不可用")
         return

    try:
        log.info(f"SELECT_DIR_LOGIC: Calling create_file_dialog on window: {current_window}")
        result = current_window.create_file_dialog(webview.FOLDER_DIALOG)
        log.info(f"SELECT_DIR_LOGIC: File dialog result: {result}")

        if result and isinstance(result, tuple) and len(result) > 0:
            selected_path = result[0]
            log.info(f"SELECT_DIR_LOGIC: Directory selected: {selected_path}. Calling MangaManager.set_manga_dir...")

            try:
                manga_manager.set_manga_dir(selected_path, force_rescan=True)
                log.info(f"SELECT_DIR_LOGIC: MangaManager.set_manga_dir('{selected_path}') called successfully.")
                _dispatch_feedback_event(success=True, message=f"已设置目录为 '{os.path.basename(selected_path)}'，正在扫描...")
            except Exception as e_set_dir:
                 log.error(f"SELECT_DIR_LOGIC ERROR: Error calling MangaManager.set_manga_dir: {e_set_dir}", exc_info=True)
                 _dispatch_feedback_event(success=False, message=f"设置目录时出错: {e_set_dir}")

        else:
            log.info("SELECT_DIR_LOGIC: No directory selected or dialog cancelled.")
            _dispatch_feedback_event(success=False, message="用户未选择目录")

    except Exception as e_dialog:
        error_msg = f"打开目录选择器时出错: {e_dialog}"
        log.error(f"SELECT_DIR_LOGIC ERROR: {error_msg}", exc_info=True)
        _dispatch_feedback_event(success=False, message=f"打开目录选择器失败: {e_dialog}")


# ----- 修改：触发文件选择的逻辑 (修正 file_types 格式) -----
def _trigger_select_file_logic():
    """打开文件选择对话框并直接处理导入（修正 file_types 格式）"""
    global desktop_app_instance, core_interface # 需要 core_interface
    log.info("SELECT_FILE_LOGIC: Called.")

    if not desktop_app_instance:
         log.error("SELECT_FILE_LOGIC: desktop_app instance unavailable.")
         _dispatch_feedback_event(success=False, message="应用实例不可用")
         return
    if not core_interface: # 检查 CoreInterface
         log.error("SELECT_FILE_LOGIC: Core Interface unavailable.")
         _dispatch_feedback_event(success=False, message="核心接口不可用，无法导入文件")
         return

    current_window = None
    if desktop_app_instance.window:
        current_window = desktop_app_instance.window
    elif webview.windows:
         current_window = webview.windows[0]

    if not current_window:
         log.error("SELECT_FILE_LOGIC: Window instance unavailable.")
         _dispatch_feedback_event(success=False, message="窗口实例不可用")
         return

    try:
        log.info(f"SELECT_FILE_LOGIC: Calling create_file_dialog (OPEN_DIALOG) on window: {current_window}")
        # 修正 Windows 下的 file_types 格式
        file_types = ('Manga Archives (*.zip;*.cbz;*.cbr;*.rar)', 'All files (*.*)')
        # 另一种可能的格式，如果上面不行可以尝试:
        # file_types = ('Manga Archives', '*.zip;*.cbz;*.cbr;*.rar', 'All files', '*.*')

        result = current_window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=file_types # 使用修正后的格式
        )
        log.info(f"SELECT_FILE_LOGIC: File dialog result: {result}")

        if result and isinstance(result, tuple) and len(result) > 0:
            selected_files = result
            log.info(f"SELECT_FILE_LOGIC: {len(selected_files)} files selected. Processing directly...")

            added_count = 0
            failed_count = 0
            errors = []

            # 直接在此处循环处理，不使用额外线程
            for file_path in selected_files:
                try:
                    log.info(f"SELECT_FILE_LOGIC: Processing file: {file_path}")
                    core_interface.add_manga_from_path(file_path)
                    log.info(f"SELECT_FILE_LOGIC: Successfully processed {file_path}")
                    added_count += 1
                except Exception as e:
                    log.error(f"SELECT_FILE_LOGIC: Failed to process {file_path}: {e}", exc_info=True)
                    failed_count += 1
                    errors.append(f"{os.path.basename(file_path)}: {e}")

            # 处理完成后发送最终反馈
            if failed_count == 0:
                final_message = f"成功导入 {added_count} 个文件。"
                _dispatch_feedback_event(success=True, message=final_message, added=added_count, failed=failed_count)
            else:
                final_message = f"导入完成：成功 {added_count} 个，失败 {failed_count} 个。"
                _dispatch_feedback_event(success=False, message=final_message, added=added_count, failed=failed_count)
            log.info("SELECT_FILE_LOGIC: Processing finished.")

        else:
            log.info("SELECT_FILE_LOGIC: No files selected or dialog cancelled.")
            _dispatch_feedback_event(success=False, message="用户未选择文件")

    except Exception as e_dialog:
        # 捕获特定于文件过滤器的错误
        if "not a valid file filter" in str(e_dialog):
            error_msg = f"文件过滤器格式错误: {e_dialog}"
            log.error(f"SELECT_FILE_LOGIC ERROR: Invalid file filter format. Attempted: {file_types}", exc_info=True)
        else:
            error_msg = f"打开文件选择器时出错: {e_dialog}"
            log.error(f"SELECT_FILE_LOGIC ERROR: {error_msg}", exc_info=True)
        _dispatch_feedback_event(success=False, message=f"打开文件选择器失败: {e_dialog}") # 将原始错误发给前端


# ----- 简单的 API 类 (用于 js_api) -----
class DesktopApi:
    """一个极其简单的类，其方法用于触发后端逻辑，通过 js_api 传递"""
    def trigger_select_directory(self):
        """由前端调用，触发选择目录的流程"""
        log.info("收到选择目录请求")
        try:
             _trigger_select_directory_logic()
             return {"success": True, "message": "目录选择流程已启动"}
        except Exception as e:
             log.error(f"启动目录选择失败: {e}", exc_info=True)
             return {"success": False, "message": f"启动目录选择时出错: {e}"}

    # ----- 恢复：触发文件选择的 API 方法 -----
    def trigger_select_file(self):
        """由 JS 调用，触发选择文件的流程"""
        log.info("JS_API: trigger_select_file() called.")
        try:
            _trigger_select_file_logic() # 直接调用重写后的逻辑函数
            # 同步返回成功，表示调用已收到。实际结果通过事件反映。
            return {"success": True, "message": "File selection process initiated."}
        except Exception as e:
            log.error(f"JS_API ERROR in trigger_select_file: {e}", exc_info=True)
            return {"success": False, "message": f"Error initiating file selection: {e}"}
# -----------------------------------------

class MangaTranslatorDesktop:
    """漫画翻译工具桌面版主类"""

    def __init__(self):
        global core_interface, manga_manager # 确保我们使用的是全局实例
        self.app = app
        self.port = 8081
        self.host = '127.0.0.1'
        self.server_thread = None
        self.window = None
        self.core_interface = core_interface # 从全局获取
        self.manga_manager = manga_manager   # 从全局获取
        self.api = DesktopApi() # 创建简单的 API 实例

        self.setup_logging()
        log.info("🚀 MangaTranslatorDesktop Initializing...")
        if app_type == "full":
            if not self.core_interface: log.warning("⚠️ Core Interface not loaded.")
            if not self.manga_manager: log.warning("⚠️ MangaManager not loaded. Directory features unavailable.")
        elif app_type != "full":
             log.warning("⚠️ Running in simple mode or app import failed. Desktop features unavailable.")

    def setup_logging(self):
        # (日志配置保持不变)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        if hasattr(log, 'setup_logging'): log.setup_logging()

    def start_web_server(self):
        # (Web服务器启动逻辑保持不变)
        try:
            log.info(f"🌐 Starting web server: http://{self.host}:{self.port}")
            import uvicorn
            uvicorn.run(self.app, host=self.host, port=self.port, log_level="warning", access_log=False)
        except Exception as e:
            log.error(f"❌ Web server start failed: {e}", exc_info=True); raise

    def wait_for_server(self, timeout=10):
        # (等待服务器逻辑保持不变)
        import requests
        start_time = time.time(); url = f"http://{self.host}:{self.port}"
        log.info("⏳ Waiting for web server...")
        while time.time() - start_time < timeout:
            try:
                if requests.get(url, timeout=1).status_code == 200: log.info("✅ Web server ready."); return True
            except requests.exceptions.RequestException: pass
            time.sleep(0.5)
        log.error("❌ Web server timed out."); return False

    def create_desktop_window(self):
        log.info("🪟 Creating desktop window...")
        try:
            window_config = {
                'title': '🎌 漫画翻译工具',
                'url': f"http://{self.host}:{self.port}",
                'width': 1200, 'height': 800, 'min_size': (800, 600),
                'resizable': True, 'fullscreen': False, 'minimized': False,
                'on_top': False, 'shadow': True, 'focus': True,
                'js_api': self.api # 传递简单实例
            }
            log.info(f"Creating window with js_api: {self.api}")
            self.window = webview.create_window(**window_config)

            if self.window:
                 log.info(f"✅ Desktop window created successfully with js_api. Window object: {self.window}")
            else:
                 log.error("❌ Window object creation failed!")
                 raise Exception("Failed to create PyWebView window")

            return self.window
        except Exception as e:
            log.error(f"❌ Failed to create desktop window: {e}", exc_info=True)
            raise

    def run(self):
        global desktop_app_instance # 设置全局实例引用
        desktop_app_instance = self

        try:
            log.info("Starting server thread...")
            self.server_thread = threading.Thread(target=self.start_web_server, daemon=True)
            self.server_thread.start()
            if not self.wait_for_server(): return False

            log.info("Creating window...")
            self.create_desktop_window()
            log.info(f"Window instance after creation: {self.window}")

            log.info("🎉 Starting PyWebView event loop...")
            webview.start(debug=False) # 启用调试模式

            log.info("👋 Desktop application closed.")
            return True
        except KeyboardInterrupt:
            log.info("👋 User interrupted. Closing..."); return True
        except Exception as e:
            log.error(f"❌ Desktop application run failed: {e}", exc_info=True); return False
        finally:
             log.info("Cleaning up global instance.")
             desktop_app_instance = None

def main():
    print("🎌 漫画翻译工具 - PyWebView桌面版")
    print("=" * 50)
    try:
        # 确保 MangaManager 和 CoreInterface 实例在创建 MangaTranslatorDesktop 之前已准备好
        if app_type == "full":
             if core_interface is None:
                  log.error("无法获取 CoreInterface 实例，桌面文件导入功能将不可用。")
                  # 考虑是否退出
             if manga_manager is None:
                  log.error("无法获取 MangaManager 实例，目录设置功能将不可用。")

        desktop_app = MangaTranslatorDesktop()
        success = desktop_app.run()
        print("✅ Application exited." if success else "❌ Application exited abnormally.")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Application startup failed: {e}")
        if 'log' in globals() and log: log.error(f"App startup failed: {e}", exc_info=True)
        else: print(f"ERROR: App startup failed: {e}\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
