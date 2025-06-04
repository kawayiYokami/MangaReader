/**
 * Electron桥接器
 * 提供Electron特有功能的统一接口，在Web环境中提供降级方案
 */
class ElectronBridge {
    constructor() {
        this.isElectron = EnvironmentDetector.isElectron();
        console.log(`🌉 ElectronBridge initialized for ${this.isElectron ? 'Electron' : 'Web'} environment`);
    }

    /**
     * 显示系统通知
     */
    async showNotification(title, body, options = {}) {
        try {
            if (this.isElectron) {
                // Electron环境：使用原生通知
                return await window.electronAPI.system.showNotification(title, body, options);
            } else {
                // Web环境：使用Web Notification API
                if ('Notification' in window) {
                    if (Notification.permission === 'granted') {
                        new Notification(title, { body, ...options });
                        return true;
                    } else if (Notification.permission !== 'denied') {
                        const permission = await Notification.requestPermission();
                        if (permission === 'granted') {
                            new Notification(title, { body, ...options });
                            return true;
                        }
                    }
                }
                
                // 降级方案：控制台输出
                console.log(`📢 通知: ${title} - ${body}`);
                return false;
            }
        } catch (error) {
            console.error('❌ 显示通知失败:', error);
            return false;
        }
    }

    /**
     * 设置进度条
     */
    async setProgressBar(progress) {
        try {
            if (this.isElectron) {
                // Electron环境：设置任务栏进度条
                return await window.electronAPI.system.setProgressBar(progress);
            } else {
                // Web环境：无操作（可以在这里更新页面进度条）
                console.log(`📊 进度: ${Math.round(progress * 100)}%`);
                return true;
            }
        } catch (error) {
            console.error('❌ 设置进度条失败:', error);
            return false;
        }
    }

    /**
     * 设置徽章计数
     */
    async setBadgeCount(count) {
        try {
            if (this.isElectron) {
                // Electron环境：设置应用徽章
                return await window.electronAPI.system.setBadgeCount(count);
            } else {
                // Web环境：无操作
                console.log(`🔢 徽章计数: ${count}`);
                return true;
            }
        } catch (error) {
            console.error('❌ 设置徽章计数失败:', error);
            return false;
        }
    }

    /**
     * 闪烁窗口
     */
    async flashFrame(flag = true) {
        try {
            if (this.isElectron) {
                // Electron环境：闪烁窗口
                return await window.electronAPI.system.flashFrame(flag);
            } else {
                // Web环境：改变页面标题
                if (flag) {
                    const originalTitle = document.title;
                    let isFlashing = true;
                    
                    const flashInterval = setInterval(() => {
                        document.title = isFlashing ? '🔔 ' + originalTitle : originalTitle;
                        isFlashing = !isFlashing;
                    }, 1000);
                    
                    // 5秒后停止闪烁
                    setTimeout(() => {
                        clearInterval(flashInterval);
                        document.title = originalTitle;
                    }, 5000);
                }
                return true;
            }
        } catch (error) {
            console.error('❌ 闪烁窗口失败:', error);
            return false;
        }
    }

    /**
     * 窗口操作
     */
    async minimizeWindow() {
        try {
            if (this.isElectron) {
                return await window.electronAPI.window.minimize();
            } else {
                console.log('⚠️ Web环境不支持最小化窗口');
                return false;
            }
        } catch (error) {
            console.error('❌ 最小化窗口失败:', error);
            return false;
        }
    }

    async maximizeWindow() {
        try {
            if (this.isElectron) {
                return await window.electronAPI.window.maximize();
            } else {
                console.log('⚠️ Web环境不支持最大化窗口');
                return false;
            }
        } catch (error) {
            console.error('❌ 最大化窗口失败:', error);
            return false;
        }
    }

    async closeWindow() {
        try {
            if (this.isElectron) {
                return await window.electronAPI.window.close();
            } else {
                window.close();
                return true;
            }
        } catch (error) {
            console.error('❌ 关闭窗口失败:', error);
            return false;
        }
    }

    async setWindowTitle(title) {
        try {
            if (this.isElectron) {
                return await window.electronAPI.window.setTitle(title);
            } else {
                document.title = title;
                return true;
            }
        } catch (error) {
            console.error('❌ 设置窗口标题失败:', error);
            return false;
        }
    }

    /**
     * 应用信息
     */
    async getAppVersion() {
        try {
            if (this.isElectron) {
                return await window.electronAPI.app.getVersion();
            } else {
                return '1.0.0 (Web)';
            }
        } catch (error) {
            console.error('❌ 获取应用版本失败:', error);
            return 'unknown';
        }
    }

    async getAppName() {
        try {
            if (this.isElectron) {
                return await window.electronAPI.app.getName();
            } else {
                return '漫画翻译工具 (Web版)';
            }
        } catch (error) {
            console.error('❌ 获取应用名称失败:', error);
            return 'unknown';
        }
    }

    /**
     * Python服务管理
     */
    async getPythonStatus() {
        try {
            if (this.isElectron) {
                return await window.electronAPI.python.getStatus();
            } else {
                // Web环境：假设Python服务正在运行
                return {
                    isRunning: true,
                    port: 8080,
                    environment: 'web'
                };
            }
        } catch (error) {
            console.error('❌ 获取Python状态失败:', error);
            return { isRunning: false, error: error.message };
        }
    }

    async restartPythonService() {
        try {
            if (this.isElectron) {
                return await window.electronAPI.python.restart();
            } else {
                console.log('⚠️ Web环境不支持重启Python服务');
                return false;
            }
        } catch (error) {
            console.error('❌ 重启Python服务失败:', error);
            return false;
        }
    }

    /**
     * 事件监听
     */
    onPythonStatusChanged(callback) {
        if (this.isElectron && window.electronAPI.on) {
            window.electronAPI.on('python:status-changed', callback);
        }
    }

    onWindowFocus(callback) {
        if (this.isElectron && window.electronAPI.on) {
            window.electronAPI.on('window:focus', callback);
        } else {
            window.addEventListener('focus', callback);
        }
    }

    onWindowBlur(callback) {
        if (this.isElectron && window.electronAPI.on) {
            window.electronAPI.on('window:blur', callback);
        } else {
            window.addEventListener('blur', callback);
        }
    }

    /**
     * 开发工具
     */
    async openDevTools() {
        try {
            if (this.isElectron && window.electronDev) {
                return await window.electronDev.openDevTools();
            } else {
                console.log('⚠️ 开发工具仅在Electron开发模式下可用');
                return false;
            }
        } catch (error) {
            console.error('❌ 打开开发工具失败:', error);
            return false;
        }
    }

    async reloadPage() {
        try {
            if (this.isElectron && window.electronDev) {
                return await window.electronDev.reload();
            } else {
                window.location.reload();
                return true;
            }
        } catch (error) {
            console.error('❌ 重新加载页面失败:', error);
            return false;
        }
    }

    /**
     * 获取环境能力
     */
    getCapabilities() {
        return {
            fileSystemAPI: this.isElectron,
            systemNotification: true,
            progressBar: this.isElectron,
            badgeCount: this.isElectron,
            windowControl: this.isElectron,
            pythonServiceControl: this.isElectron,
            devTools: this.isElectron
        };
    }
}

// 导出到全局作用域
if (typeof window !== 'undefined') {
    window.ElectronBridge = ElectronBridge;
}

// 支持模块化导入
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ElectronBridge;
}
