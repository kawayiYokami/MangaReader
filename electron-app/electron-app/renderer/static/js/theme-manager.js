/**
 * 主题管理器 - 统一配色管理
 * 支持浅色模式和深色模式切换
 */

class ThemeManager {
    constructor() {
        this.currentTheme = 'auto'; // 'light', 'dark', 'auto'
        this.init();
    }

    init() {
        // 从localStorage读取保存的主题设置
        const savedTheme = localStorage.getItem('manga-translator-theme');
        if (savedTheme) {
            this.currentTheme = savedTheme;
        }
        
        // 应用主题
        this.applyTheme();
        
        // 监听系统主题变化
        this.watchSystemTheme();
    }

    /**
     * 设置主题
     * @param {string} theme - 'light', 'dark', 'auto'
     */
    setTheme(theme) {
        this.currentTheme = theme;
        localStorage.setItem('manga-translator-theme', theme);
        this.applyTheme();
        
        // 触发主题变化事件
        this.dispatchThemeChange();
    }

    /**
     * 应用主题到页面
     */
    applyTheme() {
        const html = document.documentElement;
        
        // 移除现有的主题类
        html.classList.remove('theme-light', 'theme-dark');
        
        let actualTheme = this.currentTheme;
        
        // 如果是auto模式，根据系统设置决定
        if (this.currentTheme === 'auto') {
            actualTheme = this.getSystemTheme();
        }
        
        // 应用主题类
        html.classList.add(`theme-${actualTheme}`);
        
        // 设置data属性，方便CSS选择器使用
        html.setAttribute('data-theme', actualTheme);
        
        console.log(`主题已切换到: ${actualTheme} (设置: ${this.currentTheme})`);
    }

    /**
     * 获取系统主题偏好
     */
    getSystemTheme() {
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }
        return 'light';
    }

    /**
     * 监听系统主题变化
     */
    watchSystemTheme() {
        if (window.matchMedia) {
            const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            mediaQuery.addEventListener('change', () => {
                if (this.currentTheme === 'auto') {
                    this.applyTheme();
                }
            });
        }
    }

    /**
     * 获取当前主题
     */
    getCurrentTheme() {
        return this.currentTheme;
    }

    /**
     * 获取实际应用的主题（解析auto模式）
     */
    getActualTheme() {
        if (this.currentTheme === 'auto') {
            return this.getSystemTheme();
        }
        return this.currentTheme;
    }

    /**
     * 切换到下一个主题
     */
    toggleTheme() {
        const themes = ['light', 'dark', 'auto'];
        const currentIndex = themes.indexOf(this.currentTheme);
        const nextIndex = (currentIndex + 1) % themes.length;
        this.setTheme(themes[nextIndex]);
    }

    /**
     * 触发主题变化事件
     */
    dispatchThemeChange() {
        const event = new CustomEvent('themechange', {
            detail: {
                theme: this.currentTheme,
                actualTheme: this.getActualTheme()
            }
        });
        window.dispatchEvent(event);
    }

    /**
     * 获取主题显示名称
     */
    getThemeDisplayName(theme = this.currentTheme) {
        const names = {
            'light': '浅色模式',
            'dark': '深色模式',
            'auto': '跟随系统'
        };
        return names[theme] || theme;
    }

    /**
     * 获取主题图标
     */
    getThemeIcon(theme = this.currentTheme) {
        const icons = {
            'light': '☀️',
            'dark': '🌙',
            'auto': '🔄'
        };
        return icons[theme] || '🎨';
    }
}

// 创建全局主题管理器实例
window.themeManager = new ThemeManager();

// 导出给其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ThemeManager;
}
