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

    // 新的缩略图系统
    thumbnailCache: new Map(),
    loadingThumbnails: new Set(),
    thumbnailObserver: null,
    preloadObserver: null,
    preloadQueue: new Set(),
    visibleCards: new Set(),

    // 漫画查看器iframe相关数据
    showMangaViewer: false,
    currentViewerUrl: '',

    // 缓存管理相关数据 - 全新设计
    cacheTypes: [
        { key: 'manga_list', name: '漫画列表', icon: 'menu_book', description: '漫画文件扫描结果缓存' }, // Replaced Emoji
        { key: 'ocr', name: 'OCR识别', icon: 'translate', description: '文字识别结果缓存' },        // Replaced Emoji
        { key: 'translation', name: '翻译结果', icon: 'language', description: '翻译结果缓存' },    // Replaced Emoji
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
        isPreviewing: false,
        previewResults: null,
        isProcessing: false,
        progress: 0,
        status: '',
        progressText: '',
        filterResults: null
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
    // 重新添加：计算是否在桌面应用中运行
    runningInDesktopApp() {
        // 检查 window.pywebview 是否存在
        const isDesktop = typeof window.pywebview !== 'undefined';
        // console.log(`[Computed] runningInDesktopApp: ${isDesktop}`); // 减少日志
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
    }
};

// 生命周期方法
window.AppLifecycle = {
    mounted() {

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
    },

    beforeUnmount() {
        // 清理观察器
        if (this.thumbnailObserver) {
            this.thumbnailObserver.disconnect();
        }
        // 移除事件监听器 (可选但推荐)
        // 重新添加桌面导入完成事件监听器移除
        if (typeof this.handleDesktopImportComplete === 'function') {
            window.removeEventListener('desktopImportComplete', this.handleDesktopImportComplete.bind(this));
             console.log('[beforeUnmount] Removed desktopImportComplete event listener.');
        }
    }
    // loadInitialSettings 函数已移至 utils.js
};
