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

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入现有的Web应用
def import_web_app():
    """尝试导入现有的Web应用"""

    # 方案1: 尝试导入完整的Web应用
    try:
        from web.app import app
        from utils import manga_logger as log
        print("✅ 成功导入完整Web应用")
        return app, log, "full"
    except ImportError as e:
        print(f"⚠️ 无法导入完整Web应用: {e}")

    # 方案2: 尝试直接运行web_main.py的逻辑
    try:
        # 模拟web_main.py的启动逻辑
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), 'web'))

        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import HTMLResponse
        import uvicorn

        app = FastAPI(title="漫画翻译工具")

        # 挂载静态文件
        if os.path.exists("web/static"):
            app.mount("/static", StaticFiles(directory="web/static"), name="static")

        @app.get("/")
        async def root():
            # 尝试读取主页面
            try:
                with open("web/templates/index.html", "r", encoding="utf-8") as f:
                    content = f.read()
                return HTMLResponse(content)
            except FileNotFoundError:
                return HTMLResponse("""
                <!DOCTYPE html>
                <html lang="zh-CN">
                <head>
                    <meta charset="UTF-8">
                    <title>漫画翻译工具 - 桌面版</title>
                    <style>
                        body { font-family: Arial, sans-serif; margin: 40px; }
                        .container { max-width: 800px; margin: 0 auto; text-align: center; }
                        .status { background: #e8f5e8; padding: 20px; border-radius: 8px; margin: 20px 0; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>🎌 漫画翻译工具 - 桌面版</h1>
                        <div class="status">
                            <h3>✅ PyWebView桌面应用运行中</h3>
                            <p>这是一个简化版本，用于测试PyWebView功能</p>
                            <p>完整功能正在开发中...</p>
                        </div>
                        <div>
                            <h3>🚀 桌面版特性</h3>
                            <ul style="text-align: left; display: inline-block;">
                                <li>✅ 原生桌面窗口</li>
                                <li>✅ 本地文件系统访问</li>
                                <li>✅ 系统集成功能</li>
                                <li>✅ 轻量级架构</li>
                                <li>⏳ 完整Web UI集成（开发中）</li>
                            </ul>
                        </div>
                    </div>
                </body>
                </html>
                """)

        # 简单的日志类
        class SimpleLogger:
            def info(self, msg): print(f"INFO: {msg}")
            def error(self, msg): print(f"ERROR: {msg}")
            def warning(self, msg): print(f"WARNING: {msg}")

        log = SimpleLogger()
        print("✅ 创建简化版Web应用")
        return app, log, "simple"

    except Exception as e:
        print(f"❌ 创建简化版Web应用失败: {e}")
        sys.exit(1)

# 导入Web应用
app, log, app_type = import_web_app()

class MangaTranslatorDesktop:
    """漫画翻译工具桌面版主类"""
    
    def __init__(self):
        self.app = app
        self.port = 8081  # 使用不同的端口避免冲突
        self.host = '127.0.0.1'
        self.server_thread = None
        self.window = None
        self.viewer_windows = {}  # 存储查看器窗口 {manga_path: window}

        # 设置日志
        self.setup_logging()

        log.info("🚀 漫画翻译工具桌面版启动中...")
    
    def setup_logging(self):
        """设置日志配置"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def start_web_server(self):
        """在后台线程中启动Web服务器"""
        try:
            log.info(f"🌐 启动Web服务器: http://{self.host}:{self.port}")

            # 使用uvicorn启动FastAPI应用
            import uvicorn
            uvicorn.run(
                self.app,
                host=self.host,
                port=self.port,
                log_level="warning",  # 减少日志输出
                access_log=False
            )

        except Exception as e:
            log.error(f"❌ Web服务器启动失败: {e}")
            raise
    
    def wait_for_server(self, timeout=10):
        """等待Web服务器启动"""
        import requests
        
        start_time = time.time()
        url = f"http://{self.host}:{self.port}"
        
        log.info("⏳ 等待Web服务器启动...")
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, timeout=1)
                if response.status_code == 200:
                    log.info("✅ Web服务器启动成功")
                    return True
            except requests.exceptions.RequestException:
                pass
            
            time.sleep(0.5)
        
        log.error("❌ Web服务器启动超时")
        return False
    
    def create_desktop_window(self):
        """创建桌面窗口"""
        try:
            log.info("🪟 创建桌面窗口...")

            # 窗口配置
            window_config = {
                'title': '🎌 漫画翻译工具',
                'url': f"http://{self.host}:{self.port}",
                'width': 1200,
                'height': 800,
                'min_size': (800, 600),
                'resizable': True,
                'fullscreen': False,
                'minimized': False,
                'on_top': False,
                'shadow': True,
                'focus': True
            }

            # 创建窗口
            self.window = webview.create_window(**window_config)

            # 设置窗口事件处理
            self.setup_window_events()

            # 注入JavaScript标识
            self.inject_desktop_identifier()

            log.info("✅ 桌面窗口创建成功")
            return self.window

        except Exception as e:
            log.error(f"❌ 桌面窗口创建失败: {e}")
            raise

    def setup_window_events(self):
        """设置窗口事件处理"""
        # PyWebView不支持new_window事件，已改用iframe方案
        # 窗口事件处理已简化
        log.info("✅ 窗口事件处理设置完成（使用iframe方案）")

    def inject_desktop_identifier(self):
        """注入JavaScript标识，明确标识桌面环境"""
        try:
            # 等待窗口加载完成后注入JavaScript
            def on_loaded():
                try:
                    # 注入全局变量标识桌面环境
                    js_code = """
                    window.PYWEBVIEW_DESKTOP = true;
                    window.DESKTOP_APP_VERSION = '1.0.0';

                    // JavaScript日志函数，输出到Python控制台
                    window.jsLog = function(level, message) {
                        if (window.pywebview && window.pywebview.api && window.pywebview.api.js_log) {
                            window.pywebview.api.js_log(level, message);
                        } else {
                            console.log('[JS-' + level.toUpperCase() + ']', message);
                        }
                    };

                    // 重写window.open，对查看器创建新窗口
                    const originalOpen = window.open;
                    window.open = function(url, target, features) {
                        window.jsLog('info', '🚫 拦截window.open调用: ' + url + ', target: ' + target);

                        console.log('🚫 拦截window.open调用:', {
                            url: url,
                            target: target,
                            features: features,
                            isViewer: url && url.includes('/viewer.html'),
                            isLocal: url && (url.startsWith('/') || url.includes('127.0.0.1:8081'))
                        });

                        // 如果是查看器URL，尝试创建新窗口
                        if (url && url.includes('/viewer.html')) {
                            window.jsLog('info', '📖 检测到查看器URL，尝试创建新窗口');

                            // 尝试通过API创建窗口
                            if (window.pywebview && window.pywebview.api && window.pywebview.api.create_viewer_window) {
                                window.jsLog('info', '� 使用PyWebView API创建窗口');
                                try {
                                    const result = window.pywebview.api.create_viewer_window(url);
                                    window.jsLog('info', '📖 API调用结果: ' + result);
                                    return null; // 阻止默认行为
                                } catch (error) {
                                    window.jsLog('error', '❌ API调用失败: ' + error);
                                }
                            }

                            // 如果API不可用，使用原始window.open
                            window.jsLog('info', '📖 API不可用，使用原始window.open');
                            const result = originalOpen.call(window, url, '_blank', 'width=1000,height=700,resizable=yes');
                            window.jsLog('info', '📖 window.open返回结果: ' + result);
                            return result;
                        }

                        // 如果是其他本地URL，在当前窗口导航
                        if (url && (url.startsWith('/') || url.includes('127.0.0.1:8081'))) {
                            window.jsLog('info', '📍 在当前窗口导航: ' + url);
                            window.location.href = url;
                            return null;
                        }

                        // 外部URL仍然使用原始方法
                        window.jsLog('info', '🌐 外部URL，使用原始window.open');
                        return originalOpen.call(window, url, target, features);
                    };

                    window.jsLog('info', '🖥️ PyWebView桌面环境标识已注入，window.open已重写');
                    window.jsLog('info', '🖥️ 原始window.open函数类型: ' + typeof originalOpen);

                    // 5秒后检查API可用性
                    setTimeout(function() {
                        if (window.pywebview && window.pywebview.api) {
                            window.jsLog('info', '✅ PyWebView API可用');
                            window.jsLog('info', '📋 可用API方法: ' + Object.keys(window.pywebview.api).join(', '));
                        } else {
                            window.jsLog('warn', '⚠️ PyWebView API不可用');
                        }
                    }, 5000);
                    """
                    self.window.evaluate_js(js_code)
                    log.info("✅ 桌面环境标识注入成功")
                except Exception as e:
                    log.warning(f"⚠️ JavaScript注入失败: {e}")

            # 设置加载完成回调
            if hasattr(self.window, 'loaded'):
                self.window.loaded += on_loaded
            else:
                # 如果没有loaded事件，延迟注入
                import threading
                def delayed_inject():
                    import time
                    time.sleep(2)  # 等待页面加载
                    on_loaded()

                threading.Thread(target=delayed_inject, daemon=True).start()

        except Exception as e:
            log.warning(f"⚠️ 桌面标识注入设置失败: {e}")
            # 不影响主要功能，继续运行
    
    def setup_webview_api(self):
        """设置WebView API，提供桌面特有功能"""
        
        class DesktopAPI:
            """桌面API类，暴露给前端JavaScript"""
            
            def __init__(self, desktop_app):
                self.desktop_app = desktop_app
            
            def get_platform_info(self):
                """获取平台信息"""
                import platform
                return {
                    'platform': platform.system(),
                    'version': platform.version(),
                    'architecture': platform.architecture()[0],
                    'python_version': platform.python_version(),
                    'is_desktop': True
                }
            
            def select_file(self, file_types=None):
                """选择文件"""
                try:
                    file_types = file_types or [
                        '漫画文件 (*.zip;*.rar;*.cbz;*.cbr)',
                        'All files (*.*)'
                    ]
                    
                    result = webview.windows[0].create_file_dialog(
                        webview.OPEN_DIALOG,
                        allow_multiple=False,
                        file_types=file_types
                    )
                    
                    if result and len(result) > 0:
                        file_path = result[0]
                        file_info = {
                            'path': file_path,
                            'name': os.path.basename(file_path),
                            'size': os.path.getsize(file_path) if os.path.exists(file_path) else 0
                        }
                        log.info(f"📁 用户选择文件: {file_info['name']}")
                        return file_info
                    
                    return None
                    
                except Exception as e:
                    log.error(f"❌ 文件选择失败: {e}")
                    return None
            
            def select_multiple_files(self, file_types=None):
                """选择多个文件"""
                try:
                    file_types = file_types or [
                        '漫画文件 (*.zip;*.rar;*.cbz;*.cbr)',
                        'All files (*.*)'
                    ]
                    
                    result = webview.windows[0].create_file_dialog(
                        webview.OPEN_DIALOG,
                        allow_multiple=True,
                        file_types=file_types
                    )
                    
                    if result:
                        files_info = []
                        for file_path in result:
                            file_info = {
                                'path': file_path,
                                'name': os.path.basename(file_path),
                                'size': os.path.getsize(file_path) if os.path.exists(file_path) else 0
                            }
                            files_info.append(file_info)
                        
                        log.info(f"📁 用户选择了 {len(files_info)} 个文件")
                        return files_info
                    
                    return []
                    
                except Exception as e:
                    log.error(f"❌ 多文件选择失败: {e}")
                    return []
            
            def select_directory(self):
                """选择文件夹"""
                try:
                    result = webview.windows[0].create_file_dialog(
                        webview.FOLDER_DIALOG
                    )
                    
                    if result and len(result) > 0:
                        dir_path = result[0]
                        dir_info = {
                            'path': dir_path,
                            'name': os.path.basename(dir_path)
                        }
                        log.info(f"📂 用户选择文件夹: {dir_info['name']}")
                        return dir_info
                    
                    return None
                    
                except Exception as e:
                    log.error(f"❌ 文件夹选择失败: {e}")
                    return None
            
            def save_file(self, default_name="translated_manga.zip", file_types=None):
                """保存文件对话框"""
                try:
                    file_types = file_types or [
                        'ZIP文件 (*.zip)',
                        'All files (*.*)'
                    ]
                    
                    result = webview.windows[0].create_file_dialog(
                        webview.SAVE_DIALOG,
                        save_filename=default_name,
                        file_types=file_types
                    )
                    
                    if result:
                        save_path = result
                        log.info(f"💾 用户选择保存路径: {save_path}")
                        return save_path
                    
                    return None
                    
                except Exception as e:
                    log.error(f"❌ 保存文件对话框失败: {e}")
                    return None
            
            def show_notification(self, title, message):
                """显示系统通知"""
                try:
                    # 在Windows上可以使用win10toast
                    # 这里先用简单的日志记录
                    log.info(f"🔔 通知: {title} - {message}")
                    return True
                except Exception as e:
                    log.error(f"❌ 显示通知失败: {e}")
                    return False
            
            def open_file_location(self, file_path):
                """在文件管理器中显示文件"""
                try:
                    import subprocess
                    import platform

                    system = platform.system()
                    if system == "Windows":
                        subprocess.run(['explorer', '/select,', file_path])
                    elif system == "Darwin":  # macOS
                        subprocess.run(['open', '-R', file_path])
                    elif system == "Linux":
                        subprocess.run(['xdg-open', os.path.dirname(file_path)])

                    log.info(f"📂 在文件管理器中显示: {file_path}")
                    return True

                except Exception as e:
                    log.error(f"❌ 打开文件位置失败: {e}")
                    return False

            def js_log(self, level, message):
                """JavaScript日志输出到Python控制台"""
                if level == 'info':
                    log.info(f"🟦 JS: {message}")
                elif level == 'warn':
                    log.warning(f"🟨 JS: {message}")
                elif level == 'error':
                    log.error(f"🟥 JS: {message}")
                else:
                    log.debug(f"🟪 JS: {message}")

            def create_viewer_window(self, url):
                """通过JavaScript API创建查看器窗口"""
                try:
                    log.info(f"📡 JavaScript请求创建查看器窗口: {url}")

                    # 提取漫画路径参数
                    from urllib.parse import urlparse, parse_qs, unquote
                    parsed_url = urlparse(url)
                    query_params = parse_qs(parsed_url.query)
                    manga_path = query_params.get('path', [''])[0]

                    if manga_path:
                        manga_path = unquote(manga_path)
                        manga_name = os.path.basename(manga_path)
                        window_title = f'📖 {manga_name}'

                        # 检查是否已经有这个漫画的窗口打开
                        if manga_path in self.desktop_app.viewer_windows:
                            existing_window = self.desktop_app.viewer_windows[manga_path]
                            if existing_window:
                                log.info(f"🔍 聚焦到已存在的查看器窗口: {manga_name}")
                                return True
                    else:
                        window_title = '📖 漫画查看器'
                        manga_path = url  # 使用URL作为key

                    # 创建新的查看器窗口
                    log.info(f"🪟 创建新的查看器窗口: {window_title}")
                    viewer_window = webview.create_window(
                        title=window_title,
                        url=url,
                        width=1000,
                        height=700,
                        min_size=(800, 600),
                        resizable=True,
                        fullscreen=False,
                        minimized=False,
                        on_top=False,
                        shadow=True,
                        focus=True
                    )

                    # 存储窗口引用
                    self.desktop_app.viewer_windows[manga_path] = viewer_window

                    log.info(f"✅ 查看器窗口创建成功: {window_title}")
                    return True

                except Exception as e:
                    log.error(f"❌ 创建查看器窗口失败: {e}")
                    import traceback
                    log.error(f"❌ 详细错误: {traceback.format_exc()}")
                    return False
        
        # 将API暴露给WebView
        return DesktopAPI(self)
    
    def run(self):
        """运行桌面应用"""
        try:
            # 1. 启动Web服务器
            self.server_thread = threading.Thread(
                target=self.start_web_server,
                daemon=True
            )
            self.server_thread.start()
            
            # 2. 等待服务器启动
            if not self.wait_for_server():
                log.error("❌ 无法启动Web服务器")
                return False
            
            # 3. 创建桌面窗口（API在create_desktop_window中设置）
            self.create_desktop_window()

            # 4. 启动WebView
            log.info("🎉 启动桌面应用...")
            webview.start(debug=False)
            
            log.info("👋 桌面应用已关闭")
            return True
            
        except KeyboardInterrupt:
            log.info("👋 用户中断，正在关闭...")
            return True
        except Exception as e:
            log.error(f"❌ 桌面应用运行失败: {e}")
            return False

def main():
    """主函数"""
    print("🎌 漫画翻译工具 - PyWebView桌面版")
    print("=" * 50)
    
    try:
        # 创建并运行桌面应用
        desktop_app = MangaTranslatorDesktop()
        success = desktop_app.run()
        
        if success:
            print("✅ 应用正常退出")
        else:
            print("❌ 应用异常退出")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ 应用启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
