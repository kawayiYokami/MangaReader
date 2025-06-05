// 工具函数模块
window.UtilsMethods = {
    // ==================== 基础工具方法 ====================

    handleMenuSelect(key) {
        this.activeMenu = key;
    },

    // 初始化iframe消息监听器
    initIframeMessageListener() {
        window.addEventListener('message', (event) => {
            // 安全检查：确保消息来源是可信的
            if (event.origin !== window.location.origin) {
                return;
            }

            // 处理iframe发送的消息
            if (event.data && event.data.type === 'closeMangaViewer') {
                console.log('📨 收到iframe关闭请求');
                if (this.closeCornerViewer) {
                    this.closeCornerViewer();
                }
            }
        });
        console.log('👂 iframe消息监听器已初始化');
    },

    getPageTitle() {
        const titles = {
            'home': '首页',
            'manga-browser': '漫画浏览',
            'translation': '漫画翻译',
            'compression': '漫画压缩',
            'cache': '缓存管理',
            'settings': '设置'
        };
        return titles[this.activeMenu] || '未知页面';
    },

    async checkHealth() {
        try {
            const response = await axios.get('/health');
            ElMessage.success('API连接正常: ' + response.data.message);
        } catch (error) {
            ElMessage.error('API连接失败: ' + error.message);
        }
    },
    // 检测是否运行在PyWebView桌面环境中
    isDesktop() {
        // 检查由desktop_main.py注入的全局变量或API对象
        return !!window.PYWEBVIEW_DESKTOP || (!!window.pywebview && !!window.pywebview.api); // Corrected logical AND
    },

    // ==================== 主题管理 ====================

    toggleTheme() {
        if (window.themeManager) {
            window.themeManager.toggleTheme();
            this.updateThemeState();
            ElMessage.success(`已切换到: ${this.themeDisplayName}`);
        }
    },

    updateThemeState() {
        if (window.themeManager) {
            this.currentTheme = window.themeManager.getCurrentTheme();
            this.themeDisplayName = window.themeManager.getThemeDisplayName();
            this.themeIcon = window.themeManager.getThemeIcon();

            // 如果有打开的iframe查看器，同步主题
            if (this.showMangaViewer && this.syncThemeToIframe) {
                this.syncThemeToIframe();
            }
        }
    },

    onThemeChange(theme) {
        if (window.themeManager) {
            window.themeManager.setTheme(theme);
            this.updateThemeState();
            ElMessage.success(`主题已切换到: ${this.themeDisplayName}`);
        }
    },

    // ==================== 界面控制 ====================

    toggleSidebar() {
        this.sidebarCollapsed = !this.sidebarCollapsed;
    },

    // ==================== 文件处理工具 ====================

    isImageFile(filename) {
        const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'];
        const extension = filename.toLowerCase().substring(filename.lastIndexOf('.'));
        return imageExtensions.includes(extension);
    },

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    // ==================== 通用工具函数 ====================

    generateId() {
        return Date.now() + Math.random();
    },

    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    },

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // ==================== 错误处理 ====================

    handleError(error, context = '') {
        console.error(`${context}错误:`, error);
        const message = error.response?.data?.detail || error.message || '未知错误';
        ElMessage.error(`${context}失败: ${message}`);
    },

    // ==================== 数据验证 ====================

    validateFile(file, allowedTypes = ['zip', 'cbz', 'cbr']) {
        if (!file) return false;

        const extension = file.name.toLowerCase().split('.').pop();
        return allowedTypes.includes(extension);
    },

    validateFiles(files, allowedTypes = ['zip', 'cbz', 'cbr']) {
        if (!files || files.length === 0) return [];

        return Array.from(files).filter(file => this.validateFile(file, allowedTypes));
    },

    // ==================== URL处理 ====================

    handleUrlFragment() {
        // 处理URL片段，用于从查看器返回时恢复正确的页面
        const hash = window.location.hash;
        if (hash) {
            const fragment = hash.substring(1); // 移除 # 号
            console.log('🔗 处理URL片段:', fragment);

            // 根据片段设置活动菜单
            if (fragment === 'manga-browser') {
                this.activeMenu = 'manga-browser';
                console.log('📚 切换到漫画浏览页面');
            } else if (['home', 'translation', 'compression', 'cache', 'settings'].includes(fragment)) {
                this.activeMenu = fragment;
                console.log(`📄 切换到${this.getPageTitle()}页面`);
            }

            // 清除URL片段，保持URL整洁
            window.history.replaceState(null, null, window.location.pathname);
        }
    }
};
