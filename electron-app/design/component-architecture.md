# Electron桌面版组件架构设计

## 🏗️ 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Electron应用                             │
├─────────────────────────────────────────────────────────────┤
│  主进程 (Main Process)                                       │
│  ├─ PythonServiceManager                                    │
│  ├─ FileSystemAPI                                          │
│  ├─ WindowManager                                          │
│  └─ IPCHandler                                             │
├─────────────────────────────────────────────────────────────┤
│  渲染进程 (Renderer Process)                                 │
│  ├─ EnvironmentDetector                                    │
│  ├─ FileAPIAdapter                                         │
│  ├─ ElectronBridge                                         │
│  └─ 现有Vue组件 (100%复用)                                  │
├─────────────────────────────────────────────────────────────┤
│  Python后端服务 (内嵌)                                       │
│  └─ 现有FastAPI服务 (95%复用)                               │
└─────────────────────────────────────────────────────────────┘
```

## 🧩 主进程组件设计

### PythonServiceManager
```javascript
class PythonServiceManager {
    constructor(config) {
        this.pythonPath = config.pythonPath;
        this.scriptPath = config.scriptPath;
        this.port = config.port;
        this.process = null;
    }
    
    async start() { /* 启动Python服务 */ }
    async stop() { /* 停止Python服务 */ }
    async restart() { /* 重启Python服务 */ }
    isRunning() { /* 检查服务状态 */ }
    getPort() { /* 获取服务端口 */ }
}
```

### FileSystemAPI
```javascript
class FileSystemAPI {
    async selectFile(options) { /* 文件选择 */ }
    async selectDirectory(options) { /* 文件夹选择 */ }
    async selectMultipleFiles(options) { /* 多文件选择 */ }
    async saveFile(options) { /* 保存文件 */ }
    async readFile(path) { /* 读取文件 */ }
    async writeFile(path, data) { /* 写入文件 */ }
    async copyFile(src, dest) { /* 复制文件 */ }
    async deleteFile(path) { /* 删除文件 */ }
}
```

### WindowManager
```javascript
class WindowManager {
    constructor() {
        this.mainWindow = null;
    }
    
    createMainWindow() { /* 创建主窗口 */ }
    setupMenu() { /* 设置菜单 */ }
    setupTray() { /* 设置托盘 */ }
    handleWindowEvents() { /* 处理窗口事件 */ }
}
```

### IPCHandler
```javascript
class IPCHandler {
    constructor(fileSystemAPI, pythonServiceManager) {
        this.fileSystemAPI = fileSystemAPI;
        this.pythonServiceManager = pythonServiceManager;
    }
    
    setupHandlers() { /* 设置IPC处理器 */ }
    handleFileOperations() { /* 处理文件操作 */ }
    handleServiceOperations() { /* 处理服务操作 */ }
}
```

## 🖥️ 渲染进程组件设计

### EnvironmentDetector
```javascript
class EnvironmentDetector {
    static isElectron() {
        return window.electronAPI !== undefined;
    }
    
    static isWeb() {
        return !this.isElectron();
    }
    
    static getPlatform() {
        return window.electronAPI?.platform || 'web';
    }
}
```

### FileAPIAdapter
```javascript
class FileAPIAdapter {
    constructor() {
        this.implementation = EnvironmentDetector.isElectron() 
            ? new ElectronFileAPI() 
            : new WebFileAPI();
    }
    
    async selectFiles(options) {
        return this.implementation.selectFiles(options);
    }
    
    async saveFile(data, options) {
        return this.implementation.saveFile(data, options);
    }
}

// 统一接口
class IFileAPI {
    async selectFiles(options) { throw new Error('Not implemented'); }
    async saveFile(data, options) { throw new Error('Not implemented'); }
}

// Electron实现
class ElectronFileAPI extends IFileAPI {
    async selectFiles(options) {
        return window.electronAPI.selectMultipleFiles();
    }
    
    async saveFile(data, options) {
        const path = await window.electronAPI.saveFile(options.defaultName);
        // 处理保存逻辑
    }
}

// Web实现
class WebFileAPI extends IFileAPI {
    async selectFiles(options) {
        return new Promise((resolve) => {
            const input = document.createElement('input');
            input.type = 'file';
            input.multiple = true;
            input.accept = options.accept;
            input.onchange = (e) => resolve(Array.from(e.target.files));
            input.click();
        });
    }
    
    async saveFile(data, options) {
        // Web下载实现
        const blob = new Blob([data]);
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = options.defaultName;
        a.click();
    }
}
```

### ElectronBridge
```javascript
class ElectronBridge {
    constructor() {
        this.isElectron = EnvironmentDetector.isElectron();
    }
    
    async showNotification(title, body) {
        if (this.isElectron) {
            return window.electronAPI.showNotification(title, body);
        } else {
            // Web Notification API fallback
            if (Notification.permission === 'granted') {
                new Notification(title, { body });
            }
        }
    }
    
    async setProgressBar(progress) {
        if (this.isElectron) {
            return window.electronAPI.setProgressBar(progress);
        }
        // Web版本无操作
    }
}
```

## 🔗 依赖关系图

```
主进程:
WindowManager → IPCHandler → FileSystemAPI
                         → PythonServiceManager

渲染进程:
Vue组件 → FileAPIAdapter → ElectronFileAPI/WebFileAPI
       → ElectronBridge → window.electronAPI
       → EnvironmentDetector

IPC通信:
主进程 ←→ 渲染进程 (通过preload script)
```

## 📋 接口定义

### IPC通信接口
```javascript
// preload.js 暴露的API
window.electronAPI = {
    // 文件操作
    selectFile: () => ipcRenderer.invoke('select-file'),
    selectDirectory: () => ipcRenderer.invoke('select-directory'),
    selectMultipleFiles: () => ipcRenderer.invoke('select-multiple-files'),
    saveFile: (defaultName) => ipcRenderer.invoke('save-file', defaultName),
    
    // 系统集成
    showNotification: (title, body) => ipcRenderer.invoke('show-notification', title, body),
    setProgressBar: (progress) => ipcRenderer.invoke('set-progress-bar', progress),
    
    // 环境信息
    platform: process.platform,
    isElectron: true
};
```

## 🎯 实现优先级

1. **核心组件**: PythonServiceManager, FileSystemAPI
2. **IPC通信**: IPCHandler, preload script
3. **适配层**: EnvironmentDetector, FileAPIAdapter
4. **增强功能**: ElectronBridge, WindowManager

## 🔧 配置管理

```javascript
// config/electron.config.js
export default {
    python: {
        scriptPath: './python-backend/web_main.py',
        port: 8080,
        args: ['--port', '8080']
    },
    window: {
        width: 1200,
        height: 800,
        minWidth: 800,
        minHeight: 600
    },
    security: {
        nodeIntegration: false,
        contextIsolation: true,
        enableRemoteModule: false
    }
};
```

---
**设计原则**: 组件化、低耦合、接口抽象、依赖注入
