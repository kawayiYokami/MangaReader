const { ipcMain, app, BrowserWindow, Notification } = require('electron');

/**
 * IPC处理器
 * 负责处理主进程和渲染进程之间的通信
 */
class IPCHandler {
    constructor(fileSystemAPI, pythonServiceManager) {
        this.fileSystemAPI = fileSystemAPI;
        this.pythonServiceManager = pythonServiceManager;
        
        console.log('🔗 IPCHandler initialized');
    }

    /**
     * 设置所有IPC处理器
     */
    setupHandlers() {
        console.log('🔗 设置IPC处理器...');
        
        this.setupFileHandlers();
        this.setupSystemHandlers();
        this.setupWindowHandlers();
        this.setupPythonHandlers();
        this.setupAppHandlers();
        this.setupDevHandlers();
        
        console.log('✅ IPC处理器设置完成');
    }

    /**
     * 文件操作处理器
     */
    setupFileHandlers() {
        // 选择单个文件
        ipcMain.handle('file:select-file', async (event, options) => {
            try {
                return await this.fileSystemAPI.selectFile(options);
            } catch (error) {
                console.error('IPC文件选择失败:', error);
                throw error;
            }
        });

        // 选择文件夹
        ipcMain.handle('file:select-directory', async (event, options) => {
            try {
                return await this.fileSystemAPI.selectDirectory(options);
            } catch (error) {
                console.error('IPC文件夹选择失败:', error);
                throw error;
            }
        });

        // 选择多个文件
        ipcMain.handle('file:select-multiple-files', async (event, options) => {
            try {
                return await this.fileSystemAPI.selectMultipleFiles(options);
            } catch (error) {
                console.error('IPC多文件选择失败:', error);
                throw error;
            }
        });

        // 保存文件
        ipcMain.handle('file:save-file', async (event, options) => {
            try {
                return await this.fileSystemAPI.saveFile(options);
            } catch (error) {
                console.error('IPC文件保存失败:', error);
                throw error;
            }
        });

        // 在文件管理器中显示
        ipcMain.handle('file:show-item-in-folder', async (event, filePath) => {
            try {
                return await this.fileSystemAPI.showItemInFolder(filePath);
            } catch (error) {
                console.error('IPC显示文件失败:', error);
                throw error;
            }
        });

        // 打开路径
        ipcMain.handle('file:open-path', async (event, filePath) => {
            try {
                return await this.fileSystemAPI.openPath(filePath);
            } catch (error) {
                console.error('IPC打开路径失败:', error);
                throw error;
            }
        });
    }

    /**
     * 系统集成处理器
     */
    setupSystemHandlers() {
        // 显示通知
        ipcMain.handle('system:show-notification', async (event, title, body, options = {}) => {
            try {
                if (Notification.isSupported()) {
                    const notification = new Notification({
                        title,
                        body,
                        ...options
                    });
                    
                    notification.show();
                    return true;
                } else {
                    console.warn('系统不支持通知');
                    return false;
                }
            } catch (error) {
                console.error('IPC显示通知失败:', error);
                throw error;
            }
        });

        // 设置进度条
        ipcMain.handle('system:set-progress-bar', async (event, progress) => {
            try {
                const mainWindow = BrowserWindow.getFocusedWindow();
                if (mainWindow) {
                    mainWindow.setProgressBar(progress);
                }
                return true;
            } catch (error) {
                console.error('IPC设置进度条失败:', error);
                throw error;
            }
        });

        // 设置徽章计数 (macOS)
        ipcMain.handle('system:set-badge-count', async (event, count) => {
            try {
                if (process.platform === 'darwin') {
                    app.setBadgeCount(count);
                }
                return true;
            } catch (error) {
                console.error('IPC设置徽章计数失败:', error);
                throw error;
            }
        });

        // 闪烁窗口
        ipcMain.handle('system:flash-frame', async (event, flag) => {
            try {
                const mainWindow = BrowserWindow.getFocusedWindow();
                if (mainWindow) {
                    mainWindow.flashFrame(flag);
                }
                return true;
            } catch (error) {
                console.error('IPC闪烁窗口失败:', error);
                throw error;
            }
        });
    }

    /**
     * 窗口操作处理器
     */
    setupWindowHandlers() {
        // 最小化窗口
        ipcMain.handle('window:minimize', async (event) => {
            try {
                const window = BrowserWindow.fromWebContents(event.sender);
                if (window) {
                    window.minimize();
                }
                return true;
            } catch (error) {
                console.error('IPC最小化窗口失败:', error);
                throw error;
            }
        });

        // 最大化/还原窗口
        ipcMain.handle('window:maximize', async (event) => {
            try {
                const window = BrowserWindow.fromWebContents(event.sender);
                if (window) {
                    if (window.isMaximized()) {
                        window.unmaximize();
                    } else {
                        window.maximize();
                    }
                }
                return true;
            } catch (error) {
                console.error('IPC最大化窗口失败:', error);
                throw error;
            }
        });

        // 关闭窗口
        ipcMain.handle('window:close', async (event) => {
            try {
                const window = BrowserWindow.fromWebContents(event.sender);
                if (window) {
                    window.close();
                }
                return true;
            } catch (error) {
                console.error('IPC关闭窗口失败:', error);
                throw error;
            }
        });

        // 检查窗口是否最大化
        ipcMain.handle('window:is-maximized', async (event) => {
            try {
                const window = BrowserWindow.fromWebContents(event.sender);
                return window ? window.isMaximized() : false;
            } catch (error) {
                console.error('IPC检查窗口状态失败:', error);
                throw error;
            }
        });

        // 设置窗口标题
        ipcMain.handle('window:set-title', async (event, title) => {
            try {
                const window = BrowserWindow.fromWebContents(event.sender);
                if (window) {
                    window.setTitle(title);
                }
                return true;
            } catch (error) {
                console.error('IPC设置窗口标题失败:', error);
                throw error;
            }
        });

        // 设置窗口大小
        ipcMain.handle('window:set-size', async (event, width, height) => {
            try {
                const window = BrowserWindow.fromWebContents(event.sender);
                if (window) {
                    window.setSize(width, height);
                }
                return true;
            } catch (error) {
                console.error('IPC设置窗口大小失败:', error);
                throw error;
            }
        });
    }

    /**
     * Python服务处理器
     */
    setupPythonHandlers() {
        // 获取Python服务状态
        ipcMain.handle('python:get-status', async (event) => {
            try {
                return this.pythonServiceManager.getStatus();
            } catch (error) {
                console.error('IPC获取Python状态失败:', error);
                throw error;
            }
        });

        // 重启Python服务
        ipcMain.handle('python:restart', async (event) => {
            try {
                return await this.pythonServiceManager.restart();
            } catch (error) {
                console.error('IPC重启Python服务失败:', error);
                throw error;
            }
        });

        // 获取Python服务端口
        ipcMain.handle('python:get-port', async (event) => {
            try {
                return this.pythonServiceManager.getPort();
            } catch (error) {
                console.error('IPC获取Python端口失败:', error);
                throw error;
            }
        });

        // 获取Python服务日志
        ipcMain.handle('python:get-logs', async (event) => {
            try {
                return this.pythonServiceManager.getLogs();
            } catch (error) {
                console.error('IPC获取Python日志失败:', error);
                throw error;
            }
        });
    }

    /**
     * 应用信息处理器
     */
    setupAppHandlers() {
        // 获取应用版本
        ipcMain.handle('app:get-version', async (event) => {
            try {
                return app.getVersion();
            } catch (error) {
                console.error('IPC获取应用版本失败:', error);
                throw error;
            }
        });

        // 获取应用名称
        ipcMain.handle('app:get-name', async (event) => {
            try {
                return app.getName();
            } catch (error) {
                console.error('IPC获取应用名称失败:', error);
                throw error;
            }
        });

        // 获取应用路径
        ipcMain.handle('app:get-path', async (event, name) => {
            try {
                return app.getPath(name);
            } catch (error) {
                console.error('IPC获取应用路径失败:', error);
                throw error;
            }
        });

        // 退出应用
        ipcMain.handle('app:quit', async (event) => {
            try {
                app.quit();
                return true;
            } catch (error) {
                console.error('IPC退出应用失败:', error);
                throw error;
            }
        });

        // 重启应用
        ipcMain.handle('app:relaunch', async (event) => {
            try {
                app.relaunch();
                app.exit();
                return true;
            } catch (error) {
                console.error('IPC重启应用失败:', error);
                throw error;
            }
        });
    }

    /**
     * 开发模式处理器
     */
    setupDevHandlers() {
        // 打开开发者工具
        ipcMain.handle('dev:open-dev-tools', async (event) => {
            try {
                const window = BrowserWindow.fromWebContents(event.sender);
                if (window) {
                    window.webContents.openDevTools();
                }
                return true;
            } catch (error) {
                console.error('IPC打开开发者工具失败:', error);
                throw error;
            }
        });

        // 重新加载页面
        ipcMain.handle('dev:reload', async (event) => {
            try {
                const window = BrowserWindow.fromWebContents(event.sender);
                if (window) {
                    window.webContents.reload();
                }
                return true;
            } catch (error) {
                console.error('IPC重新加载页面失败:', error);
                throw error;
            }
        });

        // 切换开发者工具
        ipcMain.handle('dev:toggle-dev-tools', async (event) => {
            try {
                const window = BrowserWindow.fromWebContents(event.sender);
                if (window) {
                    window.webContents.toggleDevTools();
                }
                return true;
            } catch (error) {
                console.error('IPC切换开发者工具失败:', error);
                throw error;
            }
        });
    }
}

module.exports = IPCHandler;
