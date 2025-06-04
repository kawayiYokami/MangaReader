// 工具函数模块
window.UtilsMethods = {
    // ==================== 基础工具方法 ====================

    handleMenuSelect(key) {
        this.activeMenu = key;
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
    }
};
