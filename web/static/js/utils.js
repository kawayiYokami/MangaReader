// 工具函数模块
window.UtilsMethods = {
    // ==================== 基础工具方法 ====================

    handleMenuSelect(key) {
        this.activeMenu = key;

        // 模块懒加载调度中心
        // 检查模块是否已定义且尚未初始化
        if (this.moduleInitialized.hasOwnProperty(key) && !this.moduleInitialized[key]) {
            console.log(`[LazyLoad] 首次初始化模块: ${key}`);

            // 执行对应模块的初始化逻辑
            switch (key) {
                case 'cache':
                    if (this.initCacheManagement) {
                        console.log('[LazyLoad] 调用 initCacheManagement()');
                        this.initCacheManagement();
                    }
                    break;
                case 'translation':
                    // 翻译模块的初始化逻辑（如果存在）
                    // 暂时没有，留作扩展点
                    break;
                case 'compression':
                    // 压缩模块的初始化逻辑（如果存在）
                    // 暂时没有，留作扩展点
                    break;
                case 'settings':
                    // 设置模块需要加载字体和翻译器选项
                    if (this.fetchAvailableFonts) {
                        console.log('[LazyLoad] 调用 fetchAvailableFonts() 用于设置页面');
                        this.fetchAvailableFonts();
                    }
                    if (this.fetchTranslatorOptions) {
                        console.log('[LazyLoad] 调用 fetchTranslatorOptions() 用于设置页面');
                        this.fetchTranslatorOptions();
                    }
                    break;
            }

            // 将标志位置为true，防止重复初始化
            this.moduleInitialized[key] = true;
        }
    },

    // ==================== WebSocket 连接管理 ====================

    initWebSocket() {
        if (this.websocket) {
            return; // 已经连接
        }

        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;

            this.websocket = new WebSocket(wsUrl);

            this.websocket.onopen = () => {
                console.log('WebSocket连接已建立');
                // 订阅缓存事件
                this.websocket.send(JSON.stringify({
                    type: 'subscribe',
                    subscription: 'cache_events'
                }));
            };

            this.websocket.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleWebSocketMessage(message);
                } catch (error) {
                    console.error('解析WebSocket消息失败:', error);
                }
            };

            this.websocket.onclose = () => {
                console.log('WebSocket连接已关闭');
                this.websocket = null;
                // 5秒后尝试重连
                setTimeout(() => {
                    this.initWebSocket();
                }, 5000);
            };

            this.websocket.onerror = (error) => {
                console.error('WebSocket连接错误:', error);
            };

        } catch (error) {
            console.error('初始化WebSocket失败:', error);
        }
    },

    handleWebSocketMessage(message) {
        console.log('收到WebSocket消息:', message);

        if (message.type === 'cache_event') {
            this.handleCacheEvent(message);
        }
    },

    handleCacheEvent(event) {
        console.log('处理缓存事件:', event);

        // 如果是漫画列表缓存更新事件
        if (event.cache_type === 'manga_list') {
            // 检查事件类型
            if (event.event_type === 'updated' && event.data) {
                // 确保数据存在且格式正确
                if (Array.isArray(event.data.manga_list) && Array.isArray(event.data.tags)) {
                    console.log('通过WebSocket更新漫画列表和标签');
                    this.mangaList = event.data.manga_list;
                    this.tags = event.data.tags;
                } else {
                    console.warn('收到格式不正确的漫画列表更新事件，将完全刷新');
                    if (this.activeMenu === 'manga-browser' && this.loadInitialData) {
                        this.loadInitialData();
                    }
                }
            } else if (event.event_type === 'cleared') {
                console.log('漫画列表缓存已清空，刷新漫画浏览页面');
                // 如果当前在漫画浏览页面，刷新数据
                if (this.activeMenu === 'manga-browser' && this.loadInitialData) {
                    this.loadInitialData();
                }
            }
        }
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
                if (this.closeCornerViewer) {
                    this.closeCornerViewer();
                }
            }
        });
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
    // 检测是否运行在桌面环境中（增强版本）
    isDesktop() {
        return !!window.PYWEBVIEW_DESKTOP || (!!window.pywebview && !!window.pywebview.api);
    },

    // 检测并设置桌面模式标识（简化版）
    detectAndSetDesktopMode() {
        // 直接读取由后端注入的、100%可靠的状态
        if (window.IS_DESKTOP_MODE === true) {
            this.isDesktopMode = true;
            console.log('🖥️ 后端确认桌面模式，已激活桌面功能');
        } else {
            console.log('🌐 后端确认非桌面模式');
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
    },
    // ==================== 翻译设置相关方法 ====================

    async fetchAvailableFonts() {
        console.log('[fetchAvailableFonts] 开始获取可用字体...'); // Log 1: Start
        try {
            const response = await axios.get('/api/settings/available-fonts');
            console.log('[fetchAvailableFonts] API 响应:', response.data); // Log 2: API Response

            if (response.data && response.data.success) {
                // **重要**: 确保直接更新 AppData 中的数组，而不是替换整个 translationSettings 对象
                const fetchedFonts = response.data.fonts || [];
                // 添加检查，确保 availableFonts 是数组再调用 splice
                if (!Array.isArray(this.translationSettings.availableFonts)) {
                    // console.warn('[fetchAvailableFonts] this.translationSettings.availableFonts was not an array! Initializing to [].'); // 移除调试日志
                    this.translationSettings.availableFonts = [];
                }
                // 使用 splice 清空并插入新元素，以触发变更检测
                this.translationSettings.availableFonts.splice(0, this.translationSettings.availableFonts.length, ...fetchedFonts);
                console.log('[fetchAvailableFonts] 通过 splice 更新后的 AppData.availableFonts:', this.translationSettings.availableFonts); // 添加日志确认

                // --- 现有逻辑，用于设置默认字体 ---
                const currentFont = this.translationSettings.font_name; // 使用修正后的键名
                const foundFont = this.translationSettings.availableFonts.find(f => f.file_name === currentFont);
                if (foundFont) {
                    console.log(`[fetchAvailableFonts] 当前字体 ${currentFont} 在列表中找到.`);
                    // font_name 已经是正确的了，无需重新设置
                } else if (this.translationSettings.availableFonts.length > 0) {
                    const defaultFont = this.translationSettings.availableFonts[0].file_name;
                    console.log(`[fetchAvailableFonts] 当前字体无效或未设置, 设置为默认字体: ${defaultFont}`);
                    this.translationSettings.font_name = defaultFont; // 使用修正后的键名
                    // 异步更新后端设置 - 使用 snake_case
                    this.updateSetting('font_name', defaultFont).then(() => {
                         console.log(`[fetchAvailableFonts] 后端字体设置已更新为: ${defaultFont}`);
                    });
                } else {
                    console.log('[fetchAvailableFonts] 没有可用的字体，清空字体设置.');
                    this.translationSettings.font_name = ''; // 使用修正后的键名
                }
                // --- 结束：现有逻辑 ---

            } else {
                 // 处理 API 请求成功但返回 success: false 的情况
                 console.error('[fetchAvailableFonts] API 请求成功但返回失败状态:', response.data);
                 ElMessage.error('获取可用字体失败: ' + (response.data.message || '未知错误'));
                 this.translationSettings.availableFonts = []; // 确保在失败时清空
            }
        } catch (error) {
            console.error('[fetchAvailableFonts] API 请求失败:', error); // Log 4: API Error
            this.handleError(error, '获取可用字体');
            this.translationSettings.availableFonts = []; // 确保在失败时清空
        }
    },

    async updateSetting(key, value) {
        try {
            // 修正：确保发送的请求体包含 key 和 value
            const response = await axios.put(`/api/settings/${key}`, { key: key, value: value });
            if (response.data.success) {
                // 设置更新成功，无需显示消息
            } else {
                ElMessage.error(`更新设置 ${key} 失败: ` + (response.data.message || '未知错误'));
            }
        } catch (error) {
            this.handleError(error, `更新设置 ${key}`);
        }
    },

    onTranslationEngineChange(value) {
        // 使用后端的 snake_case 命名
        this.updateSetting('translator_type', value);
    },

    onZhipuApiKeyChange(value) {
        // 使用后端的 snake_case 命名
        this.updateSetting('zhipu_api_key', value);
    },

    onZhipuModelChange(value) {
        // 使用后端的 snake_case 命名
        this.updateSetting('zhipu_model', value);
    },


    onFontChange(value) {
        // 使用 snake_case
        this.updateSetting('font_name', value);
    },

    onOpenaiApiKeyChange(value) {
        this.updateSetting('openai_api_key', value);
        if (value) {
            this.fetchModels('openai');
        } else {
            this.translationSettings.openaiModels = [];
        }
    },
    onOpenaiApiBaseUrlChange(value) {
        this.updateSetting('openai_api_base_url', value);
        if (this.translationSettings.openaiApiKey && value) {
            this.fetchModels('openai');
        }
    },
    onOpenaiModelChange(value) {
        this.updateSetting('openai_model', value);
    },
    onGeminiApiKeyChange(value) {
        this.updateSetting('gemini_api_key', value);
        if (value) {
            this.fetchModels('gemini');
        } else {
            this.translationSettings.geminiModels = [];
        }
    },
    onGeminiModelChange(value) {
        this.updateSetting('gemini_model', value);
    },

    async fetchModels(provider) {
        const settings = this.translationSettings;
        if ((provider === 'openai' && (!settings.openaiApiKey || !settings.openaiApiBaseUrl)) ||
            (provider === 'gemini' && !settings.geminiApiKey)) {
            return;
        }

        settings.modelsLoading = true;
        const url = `/api/settings/${provider}/models`;
        const payload = {
            apiKey: provider === 'openai' ? settings.openaiApiKey : settings.geminiApiKey,
            baseUrl: provider === 'openai' ? settings.openaiApiBaseUrl : undefined
        };

        try {
            const response = await axios.post(url, payload);
            if (response.data && response.data.success) {
                if (provider === 'openai') {
                    settings.openaiModels = response.data.models;
                    // 如果当前选择的模型不在新列表中，则清空
                    if (settings.openaiModel && !settings.openaiModels.includes(settings.openaiModel)) {
                        settings.openaiModel = '';
                        this.updateSetting('openai_model', '');
                    }
                } else {
                    settings.geminiModels = response.data.models;
                     // 如果当前选择的模型不在新列表中，则清空
                    if (settings.geminiModel && !settings.geminiModels.includes(settings.geminiModel)) {
                        settings.geminiModel = '';
                        this.updateSetting('gemini_model', '');
                    }
                }
                ElMessage.success(`成功获取 ${provider} 模型列表`);
            } else {
                this.handleError({ message: response.data.message }, `获取 ${provider} 模型`);
            }
        } catch (error) {
            this.handleError(error, `获取 ${provider} 模型`);
        } finally {
            settings.modelsLoading = false;
        }
    },

    // ==================== 系统设置相关方法 ====================

    onLogLevelChange(value) {
        console.log('🔧 日志等级变更为:', value);
        this.updateSetting('log_level', value);
        ElMessage.success(`日志等级已设置为: ${this.getLogLevelDisplayName(value)}`);
    },

    getLogLevelDisplayName(level) {
        const levelNames = {
            'DEBUG': '调试',
            'INFO': '信息',
            'WARNING': '警告',
            'ERROR': '错误',
            'CRITICAL': '严重'
        };
        return levelNames[level] || level;
    },

    // 新增：获取翻译器选项
    async fetchTranslatorOptions() {
        try {
            const response = await axios.get('/api/settings/translator-options');
            if (response.data && response.data.success) {
                window.AppData.translationSettings.availableTranslators = response.data.translators || [];
            } else {
                this.handleError({ message: response.data.message || '未知错误' }, '获取翻译器选项');
                window.AppData.translationSettings.availableTranslators = [];
            }
        } catch (error) {
            this.handleError(error, '获取翻译器选项');
            window.AppData.translationSettings.availableTranslators = [];
        }
    },

    // 加载初始设置
    async loadInitialSettings() {
        // 并行加载所有设置数据
        await Promise.all([
            this.fetchTranslatorOptions(),
            (async () => {
                try {
                    const response = await axios.get('/api/settings/all');
                    if (response.data && response.data.settings) {
                        const settingsMap = response.data.settings.reduce((acc, setting) => {
                            acc[setting.key] = setting.value;
                            return acc;
                        }, {});

                        // 更新翻译设置
                        const ts = window.AppData.translationSettings;
                        ts.translator_type = settingsMap.translator_type ?? ts.translator_type;
                        ts.zhipuApiKey = settingsMap.zhipu_api_key ?? ts.zhipuApiKey;
                        ts.zhipuModel = settingsMap.zhipu_model ?? ts.zhipuModel;
                        ts.openaiApiKey = settingsMap.openai_api_key ?? ts.openaiApiKey;
                        ts.openaiApiBaseUrl = settingsMap.openai_api_base_url ?? ts.openaiApiBaseUrl;
                        ts.openaiModel = settingsMap.openai_model ?? ts.openaiModel;
                        ts.geminiApiKey = settingsMap.gemini_api_key ?? ts.geminiApiKey;
                        ts.geminiModel = settingsMap.gemini_model ?? ts.geminiModel;
                        ts.font_name = settingsMap.font_name ?? ts.font_name;

                        // 更新系统设置
                        window.AppData.systemSettings.logLevel = settingsMap.logLevel ?? window.AppData.systemSettings.logLevel;

                        // 更新主题
                        if (settingsMap.hasOwnProperty('themeMode')) {
                            window.AppData.currentTheme = settingsMap.themeMode;
                            if (this.updateThemeState) {
                                this.updateThemeState.call(window.AppData);
                            }
                        }
                    } else {
                        console.error('[Utils] 获取设置失败: 无效的响应格式', response.data);
                        ElMessage.error('加载初始设置失败: 无效的响应格式');
                    }
                } catch (error) {
                    console.error('[Utils] 加载初始设置时出错:', error);
                    ElMessage.error('加载初始设置失败: ' + (error.response?.data?.detail || error.message));
                }
            })()
        ]);
    },

    // 新增：用于重新加载应用程序的方法
    reloadApp() {
        console.log('🔄 请求重新加载应用程序...');
        location.reload();
    }
};