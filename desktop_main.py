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

# ----- 全局变量 -----
desktop_app_instance = None # 用于全局函数/API方法访问应用实例
core_interface = None       # 全局 CoreInterface 实例
manga_manager = None        # 全局 MangaManager 实例
# --------------------

# 导入现有的Web应用和核心接口
def import_dependencies():
    """尝试导入必要的依赖"""
    app = None
    log_module = None
    app_type = "unknown"
    core_interface_instance = None
    manga_manager_instance = None

    # 方案1: 尝试导入完整的Web应用和核心接口
    try:
        from web.app import app as fastapi_app
        from utils import manga_logger as log
        from web.core_interface import get_core_interface
        from core.manga.manga_manager import MangaManager # 直接导入 MangaManager

        print("[SUCCESS] 成功导入完整Web应用、核心接口及漫画管理器")
        app = fastapi_app
        log_module = log
        app_type = "full"
        core_interface_instance = get_core_interface() # 获取核心接口实例

        # 获取漫画管理器实例 - 通常核心接口会持有它
        if hasattr(core_interface_instance, 'manga_manager'):
             manga_manager_instance = core_interface_instance.manga_manager
             log.info("[SUCCESS] 成功从核心接口获取漫画管理器实例")
        else:
             log.error("[ERROR] 核心接口未能提供漫画管理器实例！")


        return app, log_module, app_type, core_interface_instance, manga_manager_instance
    except ImportError as e:
        print(f"[WARNING] 无法导入完整Web应用、核心接口或漫画管理器: {e}")
        # 尝试获取日志模块以便后续使用
        try:
            from utils import manga_logger as log
            log_module = log
        except ImportError:
            class SimpleLogger: # 简单的日志替代品
                def info(self, msg): print(f"信息: {msg}")
                def error(self, msg, exc_info=False): print(f"错误: {msg}")
                def warning(self, msg): print(f"警告: {msg}")
            log_module = SimpleLogger()

    # 方案2: 尝试创建简化版Web应用 (如果完整版失败)
    # (简化版代码省略)
    print("[WARNING] 简化版Web应用模式（或导入失败）")
    return None, log_module, "simple", None, None

# 导入依赖
app, log, app_type, core_interface, manga_manager = import_dependencies() # 使用全局变量

if app is None and app_type != "simple":
     log.error("[ERROR] 无法加载Web应用！")
     sys.exit(1)

if app_type == "full":
    if core_interface is None:
        log.warning("[WARNING] 无法获取核心接口实例，部分后端功能可能受限")
    if manga_manager is None:
         log.warning("[WARNING] 无法获取漫画管理器实例，目录设置/扫描功能将不可用")


# ----- 后端逻辑实现 (供API或全局函数调用) -----

def _dispatch_feedback_event(success, message, added=0, failed=0):
    """辅助函数：向JavaScript发送反馈事件"""
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

            # 增强的JavaScript代码，包含漫画列表刷新逻辑
            js_code = f'''
            window.dispatchEvent(new CustomEvent("desktopImportComplete", {{ detail: {detail_json} }}));

            // 如果是成功的扫描操作，触发漫画列表刷新
            if ({json.dumps(success)} && ({added} > 0 || "{message}".includes("扫描") || "{message}".includes("设置目录"))) {{
                console.log(" 扫描操作成功，触发漫画列表刷新");
                // 延迟500ms后刷新，确保后端数据已更新
                setTimeout(() => {{
                    // 尝试多种方式触发刷新
                    if (window.Vue && window.Vue.loadMangaData) {{
                        window.Vue.loadMangaData();
                        console.log("[SUCCESS] 漫画列表已刷新 (Vue实例)");
                    }} else if (window.app && window.app.loadMangaData) {{
                        window.app.loadMangaData();
                        console.log("[SUCCESS] 漫画列表已刷新 (app实例)");
                    }} else {{
                        console.warn("[WARNING] 未找到Vue实例或loadMangaData方法，尝试事件触发");
                        // 尝试通过事件触发刷新
                        const refreshEvent = new CustomEvent("refreshMangaList");
                        window.dispatchEvent(refreshEvent);
                    }}
                }}, 500);
            }}
            '''

            target_window.evaluate_js(js_code)
            log.debug("桌面事件已发送")
        except Exception as e:
            log.error(f"发送桌面事件失败: {e}", exc_info=True)
    else:
        log.error("无法发送桌面事件，窗口实例不可用")


def _trigger_select_directory_logic():
    """打开目录选择对话框并调用漫画管理器的设置目录方法"""
    global desktop_app_instance, manga_manager # 确保漫画管理器可用
    log.info("目录选择逻辑: 开始执行")

    if not desktop_app_instance:
         log.error("目录选择逻辑: 桌面应用实例不可用")
         _dispatch_feedback_event(success=False, message="应用实例不可用")
         return
    if not manga_manager:
         log.error("目录选择逻辑: 漫画管理器实例不可用")
         _dispatch_feedback_event(success=False, message="漫画管理器不可用")
         return

    current_window = None
    if desktop_app_instance.window:
        current_window = desktop_app_instance.window
    elif webview.windows:
         current_window = webview.windows[0]

    if not current_window:
         log.error("目录选择逻辑: 窗口实例不可用")
         _dispatch_feedback_event(success=False, message="窗口实例不可用")
         return

    try:
        log.info(f"目录选择逻辑: 在窗口上调用文件对话框: {current_window}")
        result = current_window.create_file_dialog(webview.FOLDER_DIALOG)
        log.info(f"目录选择逻辑: 文件对话框结果: {result}")

        if result and isinstance(result, tuple) and len(result) > 0:
            selected_path = result[0]
            log.info(f"目录选择逻辑: 已选择目录: {selected_path}，正在调用漫画管理器设置目录...")

            try:
                manga_manager.set_manga_dir(selected_path, force_rescan=True)
                log.info(f"目录选择逻辑: 漫画管理器设置目录成功: '{selected_path}'")
                _dispatch_feedback_event(success=True, message=f"已设置目录为 '{os.path.basename(selected_path)}'，正在扫描...")
            except Exception as e_set_dir:
                 log.error(f"目录选择逻辑错误: 调用漫画管理器设置目录失败: {e_set_dir}", exc_info=True)
                 _dispatch_feedback_event(success=False, message=f"设置目录时出错: {e_set_dir}")

        else:
            log.info("目录选择逻辑: 用户未选择目录或对话框被取消")
            _dispatch_feedback_event(success=False, message="用户未选择目录")

    except Exception as e_dialog:
        error_msg = f"打开目录选择器时出错: {e_dialog}"
        log.error(f"目录选择逻辑错误: {error_msg}", exc_info=True)
        _dispatch_feedback_event(success=False, message=f"打开目录选择器失败: {e_dialog}")


# ----- 修改：触发文件选择的逻辑 (修正文件类型格式) -----
def _trigger_select_file_logic():
    """打开文件选择对话框并直接处理导入（修正文件类型格式）"""
    global desktop_app_instance, core_interface # 需要核心接口
    log.info("文件选择逻辑: 开始执行")

    if not desktop_app_instance:
         log.error("文件选择逻辑: 桌面应用实例不可用")
         _dispatch_feedback_event(success=False, message="应用实例不可用")
         return
    if not core_interface: # 检查核心接口
         log.error("文件选择逻辑: 核心接口不可用")
         _dispatch_feedback_event(success=False, message="核心接口不可用，无法导入文件")
         return

    current_window = None
    if desktop_app_instance.window:
        current_window = desktop_app_instance.window
    elif webview.windows:
         current_window = webview.windows[0]

    if not current_window:
         log.error("文件选择逻辑: 窗口实例不可用")
         _dispatch_feedback_event(success=False, message="窗口实例不可用")
         return

    try:
        log.info(f"文件选择逻辑: 在窗口上调用文件对话框(打开对话框): {current_window}")
        # 修正Windows下的文件类型格式
        file_types = ('漫画压缩包 (*.zip;*.cbz;*.cbr;*.rar)', '所有文件 (*.*)')
        # 另一种可能的格式，如果上面不行可以尝试:
        # file_types = ('漫画压缩包', '*.zip;*.cbz;*.cbr;*.rar', '所有文件', '*.*')

        result = current_window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=file_types # 使用修正后的格式
        )
        log.info(f"文件选择逻辑: 文件对话框结果: {result}")

        if result and isinstance(result, tuple) and len(result) > 0:
            selected_files = result
            log.info(f"文件选择逻辑: 已选择 {len(selected_files)} 个文件，开始直接处理...")

            added_count = 0
            failed_count = 0
            errors = []

            # 直接在此处循环处理，不使用额外线程
            for file_path in selected_files:
                try:
                    log.info(f"文件选择逻辑: 正在处理文件: {file_path}")
                    core_interface.add_manga_from_path(file_path)
                    log.info(f"文件选择逻辑: 成功处理文件 {file_path}")
                    added_count += 1
                except Exception as e:
                    log.error(f"文件选择逻辑: 处理文件失败 {file_path}: {e}", exc_info=True)
                    failed_count += 1
                    errors.append(f"{os.path.basename(file_path)}: {e}")

            # 处理完成后发送最终反馈
            if failed_count == 0:
                final_message = f"成功导入 {added_count} 个文件"
                _dispatch_feedback_event(success=True, message=final_message, added=added_count, failed=failed_count)
            else:
                final_message = f"导入完成：成功 {added_count} 个，失败 {failed_count} 个"
                _dispatch_feedback_event(success=False, message=final_message, added=added_count, failed=failed_count)
            log.info("文件选择逻辑: 处理完成")

        else:
            log.info("文件选择逻辑: 用户未选择文件或对话框被取消")
            _dispatch_feedback_event(success=False, message="用户未选择文件")

    except Exception as e_dialog:
        # 捕获特定于文件过滤器的错误
        if "not a valid file filter" in str(e_dialog):
            error_msg = f"文件过滤器格式错误: {e_dialog}"
            log.error(f"文件选择逻辑错误: 文件过滤器格式无效，尝试使用: {file_types}", exc_info=True)
        else:
            error_msg = f"打开文件选择器时出错: {e_dialog}"
            log.error(f"文件选择逻辑错误: {error_msg}", exc_info=True)
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

    # ----- 恢复：触发文件选择的API方法 -----
    def trigger_select_file(self):
        """由JavaScript调用，触发选择文件的流程"""
        log.info("JavaScript API: 收到文件选择请求")
        try:
            _trigger_select_file_logic() # 直接调用重写后的逻辑函数
            # 同步返回成功，表示调用已收到。实际结果通过事件反映。
            return {"success": True, "message": "文件选择流程已启动"}
        except Exception as e:
            log.error(f"JavaScript API错误: 文件选择失败: {e}", exc_info=True)
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

        self.setup_logging()
        log.info(" 漫画翻译工具桌面版初始化中...")
        if app_type == "full":
            if not self.core_interface: log.warning("[WARNING] 核心接口未加载")
            if not self.manga_manager: log.warning("[WARNING] 漫画管理器未加载，目录功能不可用")
        elif app_type != "full":
             log.warning("[WARNING] 运行在简化模式或应用导入失败，桌面功能不可用")

    def setup_logging(self):
        # (日志配置保持不变)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        if hasattr(log, 'setup_logging'): log.setup_logging()

    def start_web_server(self):
        # (Web服务器启动逻辑保持不变)
        try:
            log.info(f" 启动Web服务器: http://{self.host}:{self.port}")
            import uvicorn
            uvicorn.run(self.app, host=self.host, port=self.port, log_level="warning", access_log=False)
        except Exception as e:
            log.error(f"[ERROR] Web服务器启动失败: {e}", exc_info=True); raise

    def wait_for_server(self, timeout=10):
        # (等待服务器逻辑保持不变)
        import requests
        start_time = time.time(); url = f"http://{self.host}:{self.port}"
        log.info(" 等待Web服务器启动...")
        while time.time() - start_time < timeout:
            try:
                if requests.get(url, timeout=1).status_code == 200: log.info("[SUCCESS] Web服务器已就绪"); return True
            except requests.exceptions.RequestException: pass
            time.sleep(0.5)
        log.error("[ERROR] Web服务器启动超时"); return False

    def create_desktop_window(self):
        log.info(" 创建桌面窗口...")
        try:
            window_config = {
                'title': ' 漫画翻译工具',
                'url': f"http://{self.host}:{self.port}",
                'width': 1200, 'height': 800, 'min_size': (800, 600),
                'resizable': True, 'fullscreen': False, 'minimized': False,
                'on_top': False, 'shadow': True, 'focus': True,
                'js_api': self.api # 传递简单实例
            }
            log.info(f"使用JavaScript API创建窗口: {self.api}")
            webview.settings['ALLOW_DOWNLOADS'] = True
            self.window = webview.create_window(**window_config)

            if self.window:
                 log.info(f"[SUCCESS] 桌面窗口创建成功，包含JavaScript API，窗口对象: {self.window}")
            else:
                 log.error("[ERROR] 窗口对象创建失败！")
                 raise Exception("创建PyWebView窗口失败")

            return self.window
        except Exception as e:
            log.error(f"[ERROR] 创建桌面窗口失败: {e}", exc_info=True)
            raise

    def run(self):
        global desktop_app_instance # 设置全局实例引用
        desktop_app_instance = self

        try:
            log.info("启动服务器线程...")
            self.server_thread = threading.Thread(target=self.start_web_server, daemon=True)
            self.server_thread.start()
            if not self.wait_for_server(): return False

            log.info("创建窗口...")
            self.create_desktop_window()
            log.info(f"窗口创建后的实例: {self.window}")

            log.info(" 启动PyWebView事件循环...")
            webview.start(debug=False) # 启用调试模式

            log.info(" 桌面应用程序已关闭")
            return True
        except KeyboardInterrupt:
            log.info(" 用户中断，正在关闭..."); return True
        except Exception as e:
            log.error(f"[ERROR] 桌面应用程序运行失败: {e}", exc_info=True); return False
        finally:
             log.info("清理全局实例")
             desktop_app_instance = None

def main():
    print(" 漫画翻译工具 - PyWebView桌面版")
    print("=" * 50)
    try:
        # 确保 MangaManager 和 CoreInterface 实例在创建 MangaTranslatorDesktop 之前已准备好
        if app_type == "full":
             if core_interface is None:
                  log.error("无法获取核心接口实例，桌面文件导入功能将不可用")
                  # 考虑是否退出
             if manga_manager is None:
                  log.error("无法获取漫画管理器实例，目录设置功能将不可用")

        desktop_app = MangaTranslatorDesktop()
        success = desktop_app.run()
        print("[SUCCESS] Application exited." if success else "[ERROR] Application exited abnormally.")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"[ERROR] 应用程序启动失败: {e}")
        if 'log' in globals() and log: log.error(f"应用程序启动失败: {e}", exc_info=True)
        else: print(f"错误: 应用程序启动失败: {e}\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
