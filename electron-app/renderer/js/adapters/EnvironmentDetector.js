/**
 * 环境检测器
 * 检测当前运行环境（Electron或Web）
 */
class EnvironmentDetector {
    /**
     * 检测是否在Electron环境中运行
     */
    static isElectron() {
        return typeof window !== 'undefined' && 
               window.electronAPI !== undefined && 
               window.electronAPI.isElectron === true;
    }

    /**
     * 检测是否在Web环境中运行
     */
    static isWeb() {
        return !this.isElectron();
    }

    /**
     * 获取平台信息
     */
    static getPlatform() {
        if (this.isElectron()) {
            return window.electronAPI.platform || 'unknown';
        } else {
            return navigator.platform || 'web';
        }
    }

    /**
     * 获取Electron版本
     */
    static getElectronVersion() {
        if (this.isElectron()) {
            return window.electronAPI.version || 'unknown';
        }
        return null;
    }

    /**
     * 检测是否支持文件系统API
     */
    static supportsFileSystemAPI() {
        return this.isElectron();
    }

    /**
     * 检测是否支持系统通知
     */
    static supportsSystemNotification() {
        if (this.isElectron()) {
            return true;
        } else {
            return 'Notification' in window && Notification.permission !== 'denied';
        }
    }

    /**
     * 检测是否支持进度条
     */
    static supportsProgressBar() {
        return this.isElectron();
    }

    /**
     * 获取环境信息摘要
     */
    static getEnvironmentInfo() {
        return {
            isElectron: this.isElectron(),
            isWeb: this.isWeb(),
            platform: this.getPlatform(),
            electronVersion: this.getElectronVersion(),
            supportsFileSystemAPI: this.supportsFileSystemAPI(),
            supportsSystemNotification: this.supportsSystemNotification(),
            supportsProgressBar: this.supportsProgressBar(),
            userAgent: navigator.userAgent
        };
    }

    /**
     * 打印环境信息到控制台
     */
    static logEnvironmentInfo() {
        const info = this.getEnvironmentInfo();
        console.log('🔍 环境检测结果:', info);
        
        if (info.isElectron) {
            console.log('⚡ 运行在Electron环境');
            console.log(`📱 平台: ${info.platform}`);
            console.log(`🔧 Electron版本: ${info.electronVersion}`);
        } else {
            console.log('🌐 运行在Web环境');
            console.log(`📱 平台: ${info.platform}`);
        }
    }
}

// 自动检测并打印环境信息
if (typeof window !== 'undefined') {
    // 等待DOM加载完成后检测
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            EnvironmentDetector.logEnvironmentInfo();
        });
    } else {
        EnvironmentDetector.logEnvironmentInfo();
    }
}

// 导出到全局作用域
if (typeof window !== 'undefined') {
    window.EnvironmentDetector = EnvironmentDetector;
}

// 支持模块化导入
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EnvironmentDetector;
}
