// 应用数据模块
window.AppData = {
    // 系统状态 - 保留本地访问检测，用于翻译和压缩功能
    isLocalAccess: ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname),
    // 桌面应用标识不再是数据属性

    activeMenu: 'home',
    currentTheme: 'auto',
    themeDisplayName: '跟随系统',
    themeIcon: 'brightness_auto', // Replaced Emoji with Material Symbol name
    sidebarCollapsed: false,

    // 漫画浏览相关数据
    mangaList: [],
    availableTags: [],
    selectedTags: [],
    searchQuery: '',
    isLoading: false,

    // 标签分类过滤
    tagsByCategory: {},
    activeTagCategory: '作者',
    tagCategoryShowAll: {},

    // 新的缩略图系统（优化版本）
    thumbnailCache: new Map(),
    loadingThumbnails: new Set(),
    thumbnailObserver: null,
    preloadQueue: new Set(),
    visibleCards: new Set(),

    // 漫画查看器iframe相关数据
    showMangaViewer: false,
    currentViewerUrl: '',

    // WebSocket连接相关数据
    websocket: null,

    // 请求去重机制
    pendingRequests: new Map(),

    // 缓存管理相关数据 - 全新设计
    cacheTypes: [
        { key: 'manga_list', name: '漫画列表', icon: 'menu_book', description: '漫画文件扫描结果缓存' }, // Replaced Emoji
        { key: 'ocr', name: 'OCR识别', icon: 'translate', description: '文字识别结果缓存' },        // Replaced Emoji
        { key: 'translation', name: '翻译结果', icon: 'language', description: '翻译结果缓存' },    // Replaced Emoji
        { key: 'persistent_translation', name: '持久化翻译', icon: 'save', description: '按页存储的完整翻译结果缓存' },
        { key: 'harmonization_map', name: '和谐映射', icon: 'shield', description: '内容和谐化映射缓存' } // Replaced Emoji
    ],
    selectedCacheType: null,
    cacheStats: {},
    cacheEntries: [],
    filteredCacheEntries: [],
    totalEntries: 0,
    currentPage: 1,
    pageSize: 20,
    cacheSearchQuery: '',

    // 简化的加载状态
    loadingStates: {
        manga_list: { clearing: false },
        ocr: { clearing: false },
        translation: { clearing: false },
        realtime_translation: { clearing: false },
        harmonization_map: { clearing: false }
    },
    isLoadingEntries: false,

    // 统一编辑对话框
    editDialog: {
        visible: false,
        type: '', // 'harmonization_map', 'translation', 'ocr', 'manga_list'
        title: '',
        isEditing: false,
        key: '',
        content: '',
        originalText: '',
        harmonizedText: '',
        isSensitive: false,
        currentEntry: null
    },

    // 和谐映射对话框
    harmonizationDialog: {
        visible: false,
        title: '',
        isEditing: false,
        originalText: '',
        harmonizedText: '',
        currentKey: null
    },

    // 批量压缩对话框
    batchCompressionDialog: {
        visible: false,
        webpQuality: 85,
        minCompressionRatio: 0.25,
        preserveOriginalNames: true,  // 默认保留原始文件名
        selectedFiles: [],
        selectAll: false,
        isProcessing: false,
        progress: 0,
        status: '',
        progressText: '',
        results: null
    },

    // 自动过滤对话框
    autoFilterDialog: {
        visible: false,
        currentStep: 0, // 0: 选择方法, 1: 预览结果, 2: 应用过滤
        filterMethod: '',
        threshold: 0.15,
        forceReanalyze: false, // 强制重新分析选项
        isPreviewing: false,
        previewResults: null,
        isProcessing: false,
        progress: 0,
        status: '',
        progressText: '',
        filterResults: null
    },

    // 过滤文件列表对话框
    filterFilesListDialog: {
        visible: false,
        title: '',
        type: '', // 'keep' 或 'remove'
        files: [],
        searchQuery: '',
        currentPage: 1
    },

    // 压缩警告对话框
    compressionWarningDialog: {
        visible: false,
        dontShowAgain: false
    },

    // 翻译功能数据
    translationSettings: {
        sourceLang: 'auto',
        targetLang: 'zh-CN',
        translator_type: '智谱', // 重命名以匹配后端
        zhipuApiKey: '',
        zhipuModel: 'glm-4-flash',
        googleApiKey: '',
        font_name: '', // 重命名以匹配后端
        availableFonts: [], // 用于存储字体列表
    },

    // 系统设置数据
    systemSettings: {
        logLevel: 'INFO', // 默认日志等级
    },
    translationTasks: [],
    generalDragOver: false,  // 通用拖拽状态（保留兼容性）
    translationDragOver: false,  // 翻译专用拖拽状态
    taskIsProcessing: false, // 通用处理状态
    translationStopped: false,  // 停止标志
    abortController: null,  // HTTP请求取消控制器

    // 压缩功能数据
    compressionSettings: {
        lossless: false,  // false=有损压缩, true=无损压缩
        quality: 75, // 压缩质量
        format: 'webp' // 明确默认输出格式为webp
    },
    compressionTasks: [],
    isCompressing: false,
    compressionDragOver: false,
    compressionStopped: false  // 停止标志
};

// 计算属性
window.AppComputed = {
    // 重新添加：计算是否在桌面应用中运行（增强版本）
    runningInDesktopApp() {
        // 多重检测机制确保桌面模式的正确识别
        const checks = {
            pywebview: typeof window.pywebview !== 'undefined',
            userAgent: window.navigator.userAgent.includes('pywebview'),
            hostname: window.location.hostname === '127.0.0.1',
            protocol: window.location.protocol === 'http:',
            port: window.location.port === '8082', // 桌面版专用端口
            localStorage: localStorage.getItem('DESKTOP_MODE') === 'true'
        };

        // 如果pywebview存在，确保设置桌面模式标识
        if (checks.pywebview) {
            localStorage.setItem('DESKTOP_MODE', 'true');
            localStorage.setItem('DESKTOP_MODE_TIMESTAMP', Date.now().toString());
        }

        // 桌面模式判断：pywebview存在 或 localStorage中有桌面模式标识
        const isDesktop = checks.pywebview || checks.localStorage;

        // 如果检测到桌面模式但localStorage中没有标识，设置标识
        if ((checks.userAgent || (checks.hostname && checks.protocol && checks.port)) && !checks.localStorage) {
            localStorage.setItem('DESKTOP_MODE', 'true');
            localStorage.setItem('DESKTOP_MODE_TIMESTAMP', Date.now().toString());
        }

        return isDesktop;
    }, // 注意这里的逗号

    filteredMangaList() {
        let filtered = this.mangaList;

        // 搜索过滤
        if (this.searchQuery) {
            const query = this.searchQuery.toLowerCase();
            filtered = filtered.filter(manga =>
                manga.title.toLowerCase().includes(query)
            );
        }

        // 标签过滤
        if (this.selectedTags.length > 0) {
            filtered = filtered.filter(manga =>
                this.selectedTags.some(tag => manga.tags.includes(tag))
            );
        }

        return filtered;
    },

    // 检查是否有已完成的翻译任务
    hasCompletedTasks() {
        return this.translationTasks.some(task => task.status === 'completed');
    },

    // 批量压缩相关计算属性
    selectedFilesCount() {
        return this.batchCompressionDialog?.selectedFiles?.length || 0;
    },

    totalFilesCount() {
        return this.filteredCacheEntries?.length || 0;
    },

    isIndeterminate() {
        const selected = this.selectedFilesCount;
        const total = this.totalFilesCount;
        return selected > 0 && selected < total;
    },

    // 漫画总数计算属性
    totalMangaCount() {
        return this.mangaList ? this.mangaList.length : 0;
    },

    // 过滤文件列表（基于搜索）
    filteredFilesList() {
        if (!this.filterFilesListDialog.searchQuery) {
            return this.filterFilesListDialog.files;
        }

        const query = this.filterFilesListDialog.searchQuery.toLowerCase();
        return this.filterFilesListDialog.files.filter(file => {
            const title = (file.title || '').toLowerCase();
            const path = (file.file_path || '').toLowerCase();
            return title.includes(query) || path.includes(query);
        });
    },

    // 分页文件列表
    paginatedFilesList() {
        const start = (this.filterFilesListDialog.currentPage - 1) * this.filesPerPage;
        const end = start + this.filesPerPage;
        return this.filteredFilesList.slice(start, end);
    },

    // 每页文件数
    filesPerPage() {
        return 20;
    }
};

// 生命周期方法
window.AppLifecycle = {
    mounted() {
        // 首先检测并设置桌面模式标识
        this.detectAndSetDesktopMode();

        // 首先加载初始设置
        this.loadInitialSettings();

        this.updateThemeState();
        window.addEventListener('themechange', () => {
            this.updateThemeState();
        });

        // 初始化iframe消息监听器
        if (this.initIframeMessageListener) {
            this.initIframeMessageListener();
        }

        // 初始化缩略图观察器
        if (this.initThumbnailObserver) {
            this.initThumbnailObserver();
        }

        // 处理URL片段（如果有的话）
        this.handleUrlFragment();

        // 恢复浏览状态
        if (this.restoreBrowsingState) {
            this.restoreBrowsingState();
        }

        // 初始化漫画数据
        if (this.loadInitialData) {
            this.loadInitialData();
        }

        // 初始化缓存管理数据
        if (this.initCacheManagement) {
            this.initCacheManagement();
        }

        // 添加：初始化时加载可用字体列表
        if (this.fetchAvailableFonts) {
            console.log('[Mounted] 调用 this.fetchAvailableFonts()'); // 添加日志
            this.fetchAvailableFonts();
        } else {
            console.warn('[Mounted] this.fetchAvailableFonts 未找到'); // 添加警告日志
        }

        // 重新添加桌面导入完成事件监听器
        // 确保 handleDesktopImportComplete 方法已混入 Vue 实例
        if (typeof this.handleDesktopImportComplete === 'function') {
            // 使用 .bind(this) 确保事件处理器内部的 this 指向 Vue 实例
            window.addEventListener('desktopImportComplete', this.handleDesktopImportComplete.bind(this));
            console.log('[Mounted] Added desktopImportComplete event listener.');
        } else {
            console.warn('[Mounted] handleDesktopImportComplete method not found on Vue instance, listener not added.');
        }

        // 添加漫画列表刷新事件监听器
        this.refreshMangaListHandler = () => {
            console.log('🔄 收到刷新漫画列表事件');
            if (this.loadMangaData) {
                this.loadMangaData();
            }
        };
        window.addEventListener('refreshMangaList', this.refreshMangaListHandler);
        console.log('[Mounted] Added refreshMangaList event listener.');

        // 初始化WebSocket连接
        if (this.initWebSocket) {
            this.initWebSocket();
            console.log('[Mounted] WebSocket连接已初始化');
        }
    },

    beforeUnmount() {
        // 清理观察器
        if (this.thumbnailObserver) {
            this.thumbnailObserver.disconnect();
        }

        // 清理WebSocket连接
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
            console.log('[beforeUnmount] WebSocket连接已关闭');
        }

        // 移除事件监听器 (可选但推荐)
        // 重新添加桌面导入完成事件监听器移除
        if (typeof this.handleDesktopImportComplete === 'function') {
            window.removeEventListener('desktopImportComplete', this.handleDesktopImportComplete.bind(this));
             console.log('[beforeUnmount] Removed desktopImportComplete event listener.');
        }

        // 移除漫画列表刷新事件监听器
        if (this.refreshMangaListHandler) {
            window.removeEventListener('refreshMangaList', this.refreshMangaListHandler);
            console.log('[beforeUnmount] Removed refreshMangaList event listener.');
        }
    }
    // loadInitialSettings 函数已移至 utils.js
};
