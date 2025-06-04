// 应用数据模块
window.AppData = {
    // 系统状态 - 保留本地访问检测，用于翻译和压缩功能
    isLocalAccess: ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname),

    activeMenu: 'home',
    currentTheme: 'auto',
    themeDisplayName: '跟随系统',
    themeIcon: '🔄',
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

    // 新的缩略图系统
    thumbnailCache: new Map(),
    loadingThumbnails: new Set(),
    thumbnailObserver: null,
    visibleCards: new Set(),

    // 漫画查看器iframe相关数据
    showMangaViewer: false,
    currentViewerUrl: '',

    // 缓存管理相关数据 - 全新设计
    cacheTypes: [
        { key: 'manga_list', name: '漫画列表', icon: '📚', description: '漫画文件扫描结果缓存' },
        { key: 'ocr', name: 'OCR识别', icon: '🔤', description: '文字识别结果缓存' },
        { key: 'translation', name: '翻译结果', icon: '🌐', description: '翻译结果缓存' },
        { key: 'harmonization_map', name: '和谐映射', icon: '🛡️', description: '内容和谐化映射缓存' }
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

    // 翻译功能数据
    translationSettings: {
        sourceLang: 'auto',
        targetLang: 'zh-CN',
        engine: '智谱',
        webpQuality: 75  // Google推荐的默认质量
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
        quality: 75  // 压缩质量
    },
    compressionTasks: [],
    isCompressing: false,
    compressionDragOver: false,
    compressionStopped: false  // 停止标志
};

// 计算属性
window.AppComputed = {
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
    }
};

// 生命周期方法
window.AppLifecycle = {
    mounted() {

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


    },

    beforeUnmount() {
        // 清理观察器
        if (this.thumbnailObserver) {
            this.thumbnailObserver.disconnect();
        }
    }
};
