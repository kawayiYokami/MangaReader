const { BrowserWindow, Menu, Tray, nativeImage } = require('electron');
const path = require('path');

/**
 * 窗口管理器
 * 负责创建和管理应用窗口
 */
class WindowManager {
    constructor(config) {
        this.config = {
            isDev: config.isDev || false,
            preloadPath: config.preloadPath,
            width: config.width || 1200,
            height: config.height || 800,
            minWidth: config.minWidth || 800,
            minHeight: config.minHeight || 600
        };
        
        this.mainWindow = null;
        this.tray = null;
        
        console.log('🪟 WindowManager initialized:', this.config);
    }

    /**
     * 创建主窗口
     */
    async createMainWindow() {
        if (this.mainWindow) {
            this.mainWindow.focus();
            return this.mainWindow;
        }

        console.log('🪟 创建主窗口...');

        this.mainWindow = new BrowserWindow({
            width: this.config.width,
            height: this.config.height,
            minWidth: this.config.minWidth,
            minHeight: this.config.minHeight,
            webPreferences: {
                nodeIntegration: false,
                contextIsolation: true,
                enableRemoteModule: false,
                preload: this.config.preloadPath,
                webSecurity: !this.config.isDev
            },
            icon: this.getAppIcon(),
            title: '漫画翻译工具',
            titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
            show: false, // 先不显示，等加载完成后再显示
            backgroundColor: '#ffffff'
        });

        // 设置窗口事件
        this.setupWindowEvents();

        // 设置菜单
        this.setupMenu();

        // 设置托盘（可选）
        if (process.platform !== 'darwin') {
            this.setupTray();
        }

        // 开发模式下打开开发者工具
        if (this.config.isDev) {
            this.mainWindow.webContents.openDevTools();
        }

        console.log('✅ 主窗口创建完成');
        return this.mainWindow;
    }

    /**
     * 加载URL
     */
    async loadURL(url) {
        if (!this.mainWindow) {
            throw new Error('主窗口未创建');
        }

        console.log('🪟 加载URL:', url);

        try {
            await this.mainWindow.loadURL(url);

            // 加载完成后显示窗口
            this.mainWindow.show();

            console.log('✅ URL加载完成');

        } catch (error) {
            console.error('❌ URL加载失败:', error);
            throw error;
        }
    }

    /**
     * 加载本地文件
     */
    async loadFile(filePath) {
        if (!this.mainWindow) {
            throw new Error('主窗口未创建');
        }

        console.log('🪟 加载本地文件:', filePath);

        try {
            await this.mainWindow.loadFile(filePath);

            // 加载完成后显示窗口
            this.mainWindow.show();

            console.log('✅ 本地文件加载完成');

        } catch (error) {
            console.error('❌ 本地文件加载失败:', error);
            throw error;
        }
    }

    /**
     * 设置窗口事件
     */
    setupWindowEvents() {
        // 窗口关闭事件
        this.mainWindow.on('closed', () => {
            console.log('🪟 主窗口已关闭');
            this.mainWindow = null;
        });

        // 窗口最小化事件
        this.mainWindow.on('minimize', () => {
            if (this.tray && process.platform !== 'darwin') {
                this.mainWindow.hide();
            }
        });

        // 窗口准备显示事件
        this.mainWindow.once('ready-to-show', () => {
            console.log('🪟 窗口准备显示');
            this.mainWindow.show();
            
            if (this.config.isDev) {
                this.mainWindow.webContents.openDevTools();
            }
        });

        // 窗口焦点事件
        this.mainWindow.on('focus', () => {
            this.mainWindow.webContents.send('window:focus');
        });

        this.mainWindow.on('blur', () => {
            this.mainWindow.webContents.send('window:blur');
        });

        // 页面加载完成事件
        this.mainWindow.webContents.once('dom-ready', () => {
            console.log('🪟 页面DOM加载完成');
        });

        // 页面导航事件
        this.mainWindow.webContents.on('will-navigate', (event, navigationUrl) => {
            const parsedUrl = new URL(navigationUrl);
            
            // 只允许导航到本地服务器
            if (parsedUrl.hostname !== '127.0.0.1' && parsedUrl.hostname !== 'localhost') {
                event.preventDefault();
                console.log('🚫 阻止导航到外部URL:', navigationUrl);
            }
        });

        // 新窗口事件
        this.mainWindow.webContents.setWindowOpenHandler(({ url }) => {
            // 在外部浏览器中打开链接
            require('electron').shell.openExternal(url);
            return { action: 'deny' };
        });
    }

    /**
     * 设置应用菜单
     */
    setupMenu() {
        const template = this.createMenuTemplate();
        const menu = Menu.buildFromTemplate(template);
        Menu.setApplicationMenu(menu);
        
        console.log('🪟 应用菜单设置完成');
    }

    /**
     * 创建菜单模板
     */
    createMenuTemplate() {
        const isMac = process.platform === 'darwin';

        const template = [
            // macOS应用菜单
            ...(isMac ? [{
                label: '漫画翻译工具',
                submenu: [
                    { label: '关于漫画翻译工具', role: 'about' },
                    { type: 'separator' },
                    { label: '隐藏漫画翻译工具', role: 'hide' },
                    { label: '隐藏其他', role: 'hideothers' },
                    { label: '显示全部', role: 'unhide' },
                    { type: 'separator' },
                    { label: '退出', role: 'quit' }
                ]
            }] : []),

            // 文件菜单
            {
                label: '文件',
                submenu: [
                    {
                        label: '选择漫画文件',
                        accelerator: 'CmdOrCtrl+O',
                        click: () => {
                            this.mainWindow.webContents.send('menu:select-files');
                        }
                    },
                    {
                        label: '选择文件夹',
                        accelerator: 'CmdOrCtrl+Shift+O',
                        click: () => {
                            this.mainWindow.webContents.send('menu:select-folder');
                        }
                    },
                    { type: 'separator' },
                    isMac ? { label: '关闭', role: 'close' } : { label: '退出', role: 'quit' }
                ]
            },

            // 编辑菜单
            {
                label: '编辑',
                submenu: [
                    { label: '撤销', role: 'undo' },
                    { label: '重做', role: 'redo' },
                    { type: 'separator' },
                    { label: '剪切', role: 'cut' },
                    { label: '复制', role: 'copy' },
                    { label: '粘贴', role: 'paste' },
                    ...(isMac ? [
                        { label: '粘贴并匹配样式', role: 'pasteAndMatchStyle' },
                        { label: '删除', role: 'delete' },
                        { label: '全选', role: 'selectAll' }
                    ] : [
                        { label: '删除', role: 'delete' },
                        { type: 'separator' },
                        { label: '全选', role: 'selectAll' }
                    ])
                ]
            },

            // 视图菜单
            {
                label: '视图',
                submenu: [
                    { label: '重新加载', role: 'reload' },
                    { label: '强制重新加载', role: 'forceReload' },
                    { label: '切换开发者工具', role: 'toggleDevTools' },
                    { type: 'separator' },
                    { label: '实际大小', role: 'resetZoom' },
                    { label: '放大', role: 'zoomIn' },
                    { label: '缩小', role: 'zoomOut' },
                    { type: 'separator' },
                    { label: '切换全屏', role: 'togglefullscreen' }
                ]
            },

            // 窗口菜单
            {
                label: '窗口',
                submenu: [
                    { label: '最小化', role: 'minimize' },
                    { label: '关闭', role: 'close' },
                    ...(isMac ? [
                        { type: 'separator' },
                        { label: '前置所有窗口', role: 'front' }
                    ] : [])
                ]
            },

            // 帮助菜单
            {
                label: '帮助',
                submenu: [
                    {
                        label: '关于',
                        click: () => {
                            this.showAboutDialog();
                        }
                    },
                    {
                        label: '检查更新',
                        click: () => {
                            this.mainWindow.webContents.send('menu:check-updates');
                        }
                    }
                ]
            }
        ];

        return template;
    }

    /**
     * 设置系统托盘
     */
    setupTray() {
        try {
            const trayIcon = this.getAppIcon();
            this.tray = new Tray(trayIcon);

            const contextMenu = Menu.buildFromTemplate([
                {
                    label: '显示主窗口',
                    click: () => {
                        if (this.mainWindow) {
                            this.mainWindow.show();
                            this.mainWindow.focus();
                        }
                    }
                },
                { type: 'separator' },
                {
                    label: '退出',
                    click: () => {
                        require('electron').app.quit();
                    }
                }
            ]);

            this.tray.setToolTip('漫画翻译工具');
            this.tray.setContextMenu(contextMenu);

            // 双击托盘图标显示窗口
            this.tray.on('double-click', () => {
                if (this.mainWindow) {
                    this.mainWindow.show();
                    this.mainWindow.focus();
                }
            });

            console.log('🪟 系统托盘设置完成');

        } catch (error) {
            console.error('❌ 设置系统托盘失败:', error);
        }
    }

    /**
     * 获取应用图标
     */
    getAppIcon() {
        const iconPath = path.join(__dirname, '../../../build/icon.png');
        
        try {
            return nativeImage.createFromPath(iconPath);
        } catch {
            // 如果图标文件不存在，返回空图标
            return nativeImage.createEmpty();
        }
    }

    /**
     * 显示关于对话框
     */
    showAboutDialog() {
        const { dialog } = require('electron');
        
        dialog.showMessageBox(this.mainWindow, {
            type: 'info',
            title: '关于漫画翻译工具',
            message: '漫画翻译工具',
            detail: '基于Electron的桌面版漫画翻译应用\n\n版本: 1.0.0\n作者: Manga Translator Team',
            buttons: ['确定']
        });
    }

    /**
     * 获取主窗口
     */
    getMainWindow() {
        return this.mainWindow;
    }

    /**
     * 销毁托盘
     */
    destroyTray() {
        if (this.tray) {
            this.tray.destroy();
            this.tray = null;
            console.log('🪟 系统托盘已销毁');
        }
    }
}

module.exports = WindowManager;
