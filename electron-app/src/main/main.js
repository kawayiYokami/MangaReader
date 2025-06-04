const { app, BrowserWindow } = require('electron');
const path = require('path');
const isDev = process.argv.includes('--dev');

// 导入组件
const PythonServiceManager = require('./components/PythonServiceManager');
const WindowManager = require('./components/WindowManager');
const IPCHandler = require('./components/IPCHandler');
const FileSystemAPI = require('./components/FileSystemAPI');

class MangaTranslatorApp {
    constructor() {
        this.pythonService = null;
        this.windowManager = null;
        this.ipcHandler = null;
        this.fileSystemAPI = null;
        this.isReady = false;
    }

    async initialize() {
        console.log('🚀 初始化漫画翻译工具桌面版...');
        
        try {
            // 初始化组件
            this.fileSystemAPI = new FileSystemAPI();
            this.pythonService = new PythonServiceManager({
                scriptPath: this.getPythonScriptPath(),
                port: 8080,
                isDev: isDev
            });
            this.windowManager = new WindowManager({
                isDev: isDev,
                preloadPath: path.join(__dirname, 'preload.js')
            });
            this.ipcHandler = new IPCHandler(this.fileSystemAPI, this.pythonService);

            // 启动Python服务
            console.log('🐍 启动Python后端服务...');
            await this.pythonService.start();
            console.log('✅ Python服务启动成功');

            // 设置IPC处理器
            this.ipcHandler.setupHandlers();
            console.log('✅ IPC处理器设置完成');

            // 创建主窗口
            await this.windowManager.createMainWindow();
            console.log('✅ 主窗口创建完成');

            // 加载应用
            if (isDev) {
                // 开发模式：加载本地HTML文件进行测试
                const localPath = path.join(__dirname, '../../renderer/main.html');
                await this.windowManager.loadFile(localPath);
                console.log('✅ 本地页面加载完成');
            } else {
                // 生产模式：加载Python服务
                const serverUrl = `http://127.0.0.1:${this.pythonService.getPort()}`;
                await this.windowManager.loadURL(serverUrl);
                console.log('✅ 应用加载完成');
            }

            this.isReady = true;
            console.log('🎉 漫画翻译工具桌面版启动完成！');

        } catch (error) {
            console.error('❌ 应用初始化失败:', error);
            this.handleStartupError(error);
        }
    }

    getPythonScriptPath() {
        if (isDev) {
            // 开发模式：使用相对路径
            return path.join(__dirname, '../../../web_main.py');
        } else {
            // 生产模式：使用打包后的路径
            return path.join(process.resourcesPath, 'python-backend/web_main.py');
        }
    }

    handleStartupError(error) {
        const { dialog } = require('electron');
        
        dialog.showErrorBox(
            '启动失败',
            `漫画翻译工具启动失败：\n\n${error.message}\n\n请检查Python环境是否正确安装。`
        );
        
        app.quit();
    }

    async cleanup() {
        console.log('🧹 清理资源...');
        
        if (this.pythonService) {
            await this.pythonService.stop();
            console.log('✅ Python服务已停止');
        }
        
        console.log('✅ 清理完成');
    }
}

// 应用实例
const mangaApp = new MangaTranslatorApp();

// Electron应用事件处理
app.whenReady().then(async () => {
    await mangaApp.initialize();
});

app.on('window-all-closed', async () => {
    await mangaApp.cleanup();
    
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        if (mangaApp.isReady) {
            await mangaApp.windowManager.createMainWindow();
        }
    }
});

app.on('before-quit', async () => {
    await mangaApp.cleanup();
});

// 处理未捕获的异常
process.on('uncaughtException', (error) => {
    console.error('未捕获的异常:', error);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('未处理的Promise拒绝:', reason);
});

module.exports = MangaTranslatorApp;
