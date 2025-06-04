/**
 * Electron应用测试启动脚本
 * 用于快速测试Electron应用的基础功能
 */

const { app, BrowserWindow } = require('electron');
const path = require('path');

// 简化的测试应用
class TestElectronApp {
    constructor() {
        this.mainWindow = null;
    }

    async createWindow() {
        console.log('🪟 创建测试窗口...');

        this.mainWindow = new BrowserWindow({
            width: 1000,
            height: 700,
            webPreferences: {
                nodeIntegration: false,
                contextIsolation: true,
                preload: path.join(__dirname, 'src/main/preload.js')
            },
            title: '漫画翻译工具 - 测试版',
            show: false
        });

        // 加载测试页面
        const testPagePath = path.join(__dirname, 'renderer/index.html');
        await this.mainWindow.loadFile(testPagePath);

        // 显示窗口
        this.mainWindow.show();

        // 开发模式下打开开发者工具
        this.mainWindow.webContents.openDevTools();

        console.log('✅ 测试窗口创建完成');
    }

    setupEvents() {
        this.mainWindow.on('closed', () => {
            this.mainWindow = null;
        });
    }
}

// 创建应用实例
const testApp = new TestElectronApp();

// Electron应用事件
app.whenReady().then(async () => {
    console.log('🚀 Electron测试应用启动...');
    
    try {
        await testApp.createWindow();
        testApp.setupEvents();
        
        console.log('🎉 测试应用启动成功！');
        console.log('📝 这是一个简化的测试版本，不包含Python服务');
        
    } catch (error) {
        console.error('❌ 测试应用启动失败:', error);
    }
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        await testApp.createWindow();
    }
});

console.log('📋 测试说明:');
console.log('1. 这是一个简化的Electron测试应用');
console.log('2. 测试适配器和基础功能');
console.log('3. 不包含Python服务集成');
console.log('4. 用于验证Electron架构是否正确');
