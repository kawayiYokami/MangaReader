const { contextBridge, ipcRenderer } = require('electron');

/**
 * Electron API桥接
 * 安全地暴露Electron功能给渲染进程
 */
contextBridge.exposeInMainWorld('electronAPI', {
    // 环境信息
    isElectron: true,
    platform: process.platform,
    version: process.versions.electron,

    // 文件系统操作
    file: {
        selectFile: (options) => ipcRenderer.invoke('file:select-file', options),
        selectDirectory: (options) => ipcRenderer.invoke('file:select-directory', options),
        selectMultipleFiles: (options) => ipcRenderer.invoke('file:select-multiple-files', options),
        saveFile: (options) => ipcRenderer.invoke('file:save-file', options),
        showItemInFolder: (path) => ipcRenderer.invoke('file:show-item-in-folder', path),
        openPath: (path) => ipcRenderer.invoke('file:open-path', path)
    },

    // 系统集成
    system: {
        showNotification: (title, body, options) => 
            ipcRenderer.invoke('system:show-notification', title, body, options),
        setProgressBar: (progress) => 
            ipcRenderer.invoke('system:set-progress-bar', progress),
        setBadgeCount: (count) => 
            ipcRenderer.invoke('system:set-badge-count', count),
        flashFrame: (flag) => 
            ipcRenderer.invoke('system:flash-frame', flag)
    },

    // 窗口操作
    window: {
        minimize: () => ipcRenderer.invoke('window:minimize'),
        maximize: () => ipcRenderer.invoke('window:maximize'),
        close: () => ipcRenderer.invoke('window:close'),
        isMaximized: () => ipcRenderer.invoke('window:is-maximized'),
        setTitle: (title) => ipcRenderer.invoke('window:set-title', title),
        setSize: (width, height) => ipcRenderer.invoke('window:set-size', width, height)
    },

    // Python服务管理
    python: {
        getStatus: () => ipcRenderer.invoke('python:get-status'),
        restart: () => ipcRenderer.invoke('python:restart'),
        getPort: () => ipcRenderer.invoke('python:get-port'),
        getLogs: () => ipcRenderer.invoke('python:get-logs')
    },

    // 应用信息
    app: {
        getVersion: () => ipcRenderer.invoke('app:get-version'),
        getName: () => ipcRenderer.invoke('app:get-name'),
        getPath: (name) => ipcRenderer.invoke('app:get-path', name),
        quit: () => ipcRenderer.invoke('app:quit'),
        relaunch: () => ipcRenderer.invoke('app:relaunch')
    },

    // 事件监听
    on: (channel, callback) => {
        const validChannels = [
            'python:status-changed',
            'window:focus',
            'window:blur',
            'app:update-available',
            'app:update-downloaded'
        ];
        
        if (validChannels.includes(channel)) {
            ipcRenderer.on(channel, callback);
        }
    },

    // 移除事件监听
    off: (channel, callback) => {
        ipcRenderer.removeListener(channel, callback);
    },

    // 一次性事件监听
    once: (channel, callback) => {
        const validChannels = [
            'python:status-changed',
            'window:focus',
            'window:blur',
            'app:update-available',
            'app:update-downloaded'
        ];
        
        if (validChannels.includes(channel)) {
            ipcRenderer.once(channel, callback);
        }
    }
});

// 开发模式下的调试工具
if (process.argv.includes('--dev')) {
    contextBridge.exposeInMainWorld('electronDev', {
        openDevTools: () => ipcRenderer.invoke('dev:open-dev-tools'),
        reload: () => ipcRenderer.invoke('dev:reload'),
        toggleDevTools: () => ipcRenderer.invoke('dev:toggle-dev-tools')
    });
}

// 安全检查：确保只在Electron环境中运行
if (!process.versions.electron) {
    throw new Error('This script should only run in Electron environment');
}

console.log('✅ Preload script loaded successfully');
console.log('🔧 Electron API exposed to renderer process');
console.log(`📱 Platform: ${process.platform}`);
console.log(`⚡ Electron version: ${process.versions.electron}`);
