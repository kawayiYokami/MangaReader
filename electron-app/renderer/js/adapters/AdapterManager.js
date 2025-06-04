/**
 * 适配器管理器
 * 统一管理所有适配器的初始化和配置
 */
class AdapterManager {
    constructor() {
        this.isInitialized = false;
        this.adapters = {};
        
        console.log('🔧 AdapterManager created');
    }

    /**
     * 初始化所有适配器
     */
    async initialize() {
        if (this.isInitialized) {
            console.log('⚠️ AdapterManager already initialized');
            return this.adapters;
        }

        console.log('🚀 Initializing AdapterManager...');

        try {
            // 检测环境
            const envInfo = EnvironmentDetector.getEnvironmentInfo();
            console.log('🔍 Environment detected:', envInfo);

            // 初始化适配器
            this.adapters.fileAPI = new FileAPIAdapter();
            this.adapters.electronBridge = new ElectronBridge();

            // 设置全局引用
            this.setupGlobalReferences();

            // 设置事件监听
            this.setupEventListeners();

            this.isInitialized = true;
            console.log('✅ AdapterManager initialized successfully');

            return this.adapters;

        } catch (error) {
            console.error('❌ AdapterManager initialization failed:', error);
            throw error;
        }
    }

    /**
     * 设置全局引用
     */
    setupGlobalReferences() {
        // 将适配器挂载到全局对象
        window.adapters = this.adapters;
        
        // 为了向后兼容，也挂载到window对象
        window.fileAPI = this.adapters.fileAPI;
        window.electronBridge = this.adapters.electronBridge;

        console.log('🔗 Global adapter references set up');
    }

    /**
     * 设置事件监听
     */
    setupEventListeners() {
        // 监听Python服务状态变化
        this.adapters.electronBridge.onPythonStatusChanged((status) => {
            console.log('🐍 Python service status changed:', status);
            this.notifyStatusChange('python-service', status);
        });

        // 监听窗口焦点变化
        this.adapters.electronBridge.onWindowFocus(() => {
            console.log('🪟 Window focused');
            this.notifyStatusChange('window-focus', true);
        });

        this.adapters.electronBridge.onWindowBlur(() => {
            console.log('🪟 Window blurred');
            this.notifyStatusChange('window-focus', false);
        });

        console.log('👂 Event listeners set up');
    }

    /**
     * 通知状态变化
     */
    notifyStatusChange(type, data) {
        const event = new CustomEvent('adapter-status-change', {
            detail: { type, data }
        });
        window.dispatchEvent(event);
    }

    /**
     * 获取适配器
     */
    getAdapter(name) {
        if (!this.isInitialized) {
            throw new Error('AdapterManager not initialized');
        }
        return this.adapters[name];
    }

    /**
     * 获取所有适配器
     */
    getAllAdapters() {
        if (!this.isInitialized) {
            throw new Error('AdapterManager not initialized');
        }
        return this.adapters;
    }

    /**
     * 检查是否已初始化
     */
    isReady() {
        return this.isInitialized;
    }

    /**
     * 获取环境能力摘要
     */
    getCapabilities() {
        if (!this.isInitialized) {
            return null;
        }

        return {
            environment: EnvironmentDetector.getEnvironmentInfo(),
            fileAPI: {
                type: this.adapters.fileAPI.getImplementationType(),
                supportsDirectorySelection: EnvironmentDetector.isElectron(),
                supportsFileSystemAccess: EnvironmentDetector.isElectron()
            },
            electronBridge: this.adapters.electronBridge.getCapabilities()
        };
    }

    /**
     * 销毁适配器管理器
     */
    destroy() {
        if (!this.isInitialized) {
            return;
        }

        console.log('🧹 Destroying AdapterManager...');

        // 清理全局引用
        delete window.adapters;
        delete window.fileAPI;
        delete window.electronBridge;

        // 清理适配器
        this.adapters = {};
        this.isInitialized = false;

        console.log('✅ AdapterManager destroyed');
    }
}

/**
 * 自动初始化适配器管理器
 */
async function initializeAdapters() {
    try {
        // 创建全局适配器管理器实例
        window.adapterManager = new AdapterManager();
        
        // 初始化适配器
        await window.adapterManager.initialize();
        
        // 触发初始化完成事件
        const event = new CustomEvent('adapters-ready', {
            detail: window.adapterManager.getCapabilities()
        });
        window.dispatchEvent(event);
        
        console.log('🎉 Adapters ready!');
        
    } catch (error) {
        console.error('❌ Failed to initialize adapters:', error);
        
        // 触发初始化失败事件
        const event = new CustomEvent('adapters-error', {
            detail: { error: error.message }
        });
        window.dispatchEvent(event);
    }
}

// 等待DOM加载完成后自动初始化
if (typeof window !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeAdapters);
    } else {
        // DOM已经加载完成，立即初始化
        setTimeout(initializeAdapters, 0);
    }
}

// 导出到全局作用域
if (typeof window !== 'undefined') {
    window.AdapterManager = AdapterManager;
    window.initializeAdapters = initializeAdapters;
}

// 支持模块化导入
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { AdapterManager, initializeAdapters };
}
