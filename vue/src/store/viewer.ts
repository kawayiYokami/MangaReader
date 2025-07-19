import { defineStore } from 'pinia';
import { viewerApi } from '@/api/viewer';
import { ElMessage } from 'element-plus';

// ==================== 类型定义 ====================

interface MangaInfo {
    title: string;
    totalPages: number;
    filePath: string;
}

interface MangaImage {
    src: string;
    width: number;
    height: number;
    pageIndex: number;
}

type DisplayMode = 'auto' | 'single' | 'double';

interface ViewerState {
    mangaInfo: MangaInfo;
    currentPage: number;
    currentImages: MangaImage[];
    
    // 新增：用于分页模式的内存缓存
    pageImageCache: Map<number, MangaImage[]>;

    displayMode: DisplayMode;
    actualDisplayMode: 'single' | 'double';
    translationEnabled: boolean;
    
    isLoading: boolean;
    isSettingsPanelVisible: boolean; // 控制整体设置面板
    isAutoplaySettingsVisible: boolean; // 控制自动播放的悬浮设置
    isAutoPaging: boolean;
    autoPagingInterval: number; // in seconds

    error: string | null;
    
    // 内部状态
    _autoPagingTimerId: number | null;
}

// ==================== Store 定义 ====================

export const useViewerStore = defineStore('viewer', {
    state: (): ViewerState => ({
        mangaInfo: {
            title: '加载中...',
            totalPages: 0,
            filePath: '',
        },
        currentPage: 0,
        currentImages: [],
        pageImageCache: new Map(), // 初始化缓存
        displayMode: 'auto',
        actualDisplayMode: 'single',
        translationEnabled: false,
        
        isLoading: false,
        isSettingsPanelVisible: false,
        isAutoplaySettingsVisible: false,
        isAutoPaging: false,
        autoPagingInterval: 10,

        error: null,

        _autoPagingTimerId: null,
    }),

    getters: {
        canPrevious(state): boolean {
            return state.currentPage > 0;
        },
        canNext(state): boolean {
            return state.currentPage < state.mangaInfo.totalPages - 1;
        },
        progressPercentage(state): number {
            if (state.mangaInfo.totalPages === 0) return 0;
            return ((state.currentPage + 1) / state.mangaInfo.totalPages) * 100;
        },
    },

    actions: {
        // ==================== 初始化与销毁 ====================
        async initializeViewer(mangaPath: string, initialPage: number = 0) {
            this.isLoading = true;
            this.error = null;
            
            // 如果是新的漫画，清空缓存
            if (this.mangaInfo.filePath !== mangaPath) {
                this.pageImageCache.clear();
            }

            try {
                // API会自动创建会话
                const mangaData = await viewerApi.setCurrentManga(mangaPath, initialPage);
                if (mangaData && mangaData.manga_info) {
                    this.mangaInfo.title = mangaData.manga_info.title;
                    this.mangaInfo.totalPages = mangaData.manga_info.total_pages;
                    this.mangaInfo.filePath = mangaPath;
                    // 在这里只设置元数据，不设置 currentPage
                }
                // 使用 goToPage 来加载初始页面，确保逻辑统一
                await this.goToPage(mangaData.current_page || initialPage);
                
            } catch (err: any) {
                this.error = '初始化查看器失败';
                ElMessage.error(err.message || this.error);
                console.error(err);
            } finally {
                this.isLoading = false;
            }
        },

        async destroyViewerSession() {
            this.stopAutoPaging();
            await viewerApi.destroySession();
            this.$reset(); // 重置 store 状态，会自动清空 pageImageCache
        },

        // ==================== 核心页面加载 ====================
        async _fetchPageImagesFromServer(pageToFetch: number): Promise<MangaImage[]> {
            if (this.mangaInfo.totalPages === 0) return [];
            try {
                const modeToSend = this.displayMode === 'auto' ? 'double' : this.displayMode;
                const images = await viewerApi.getPageImages(pageToFetch, modeToSend, this.translationEnabled);

                if (images && Array.isArray(images)) {
                    return images.map(img => ({
                        src: img.image_data,
                        width: img.width,
                        height: img.height,
                        pageIndex: img.page_index
                    }));
                }
                return [];
            } catch (err: any) {
                this.error = `加载第 ${pageToFetch + 1} 页失败`;
                ElMessage.error(err.message || this.error);
                console.error(err);
                return [];
            }
        },

        /**
         * For strip view: fetches page images without setting state.
         */
        async loadPageImages(page: number, displayMode: 'single' | 'double'): Promise<MangaImage[] | null> {
            try {
                const images = await viewerApi.getPageImages(page, displayMode, this.translationEnabled);
                if (images && Array.isArray(images)) {
                    return images.map(img => ({
                        src: img.image_data,
                        width: img.width,
                        height: img.height,
                        pageIndex: img.page_index
                    }));
                }
                return null;
            } catch (err: any) {
                console.error(`Failed to fetch images for page ${page}`, err);
                return null;
            }
        },

        // ==================== 页面导航 ====================
        async goToPage(page: number) {
            const newPage = Math.max(0, Math.min(page, this.mangaInfo.totalPages - 1));

            let newImages: MangaImage[] = [];

            // 1. 检查缓存
            if (this.pageImageCache.has(newPage)) {
                newImages = this.pageImageCache.get(newPage)!;
            } else {
                // 2. 如果缓存未命中，则从服务器获取
                newImages = await this._fetchPageImagesFromServer(newPage);
                // 3. 将新获取的数据存入缓存
                this.pageImageCache.set(newPage, newImages);
            }

            // 4. 数据准备好后，再同时更新状态
            this.currentImages = newImages;
            this.currentPage = newPage;
            
            // 5. 如果在自动翻页，则重置计时器
            if (this.isAutoPaging) {
                this.restartAutoPagingTimer();
            }
        },
        
        async nextPage() {
            if (!this.canNext) return;
            const step = this.actualDisplayMode === 'double' ? 2 : 1;
            const newPage = Math.min(this.mangaInfo.totalPages - 1, this.currentPage + step);
            this.goToPage(newPage);
        },

        async previousPage() {
            if (!this.canPrevious) return;
            const step = this.actualDisplayMode === 'double' ? 2 : 1;
            const newPage = Math.max(0, this.currentPage - step);
            this.goToPage(newPage);
        },

        // ==================== 功能切换 ====================
        async setDisplayMode(mode: DisplayMode) {
            this.displayMode = mode;
            // 切换模式后需要重新加载当前页，清空缓存以应对可能的模式变化（单页/双页）
            this.pageImageCache.clear();
            await this.goToPage(this.currentPage);
        },

        async toggleTranslation() {
            try {
                const newState = !this.translationEnabled;
                await viewerApi.toggleTranslation(newState);
                this.translationEnabled = newState;
                // 切换翻译状态后，所有缓存都失效了，需要清空
                this.pageImageCache.clear();
                await this.goToPage(this.currentPage);
            } catch (err: any) {
                ElMessage.error(err.message || '切换翻译状态失败');
                console.error(err);
            }
        },

        // ==================== 自动翻页 ====================
        startAutoPaging() {
            this.isAutoPaging = true;
            this.restartAutoPagingTimer();
        },

        stopAutoPaging() {
            this.isAutoPaging = false;
            if (this._autoPagingTimerId) {
                clearInterval(this._autoPagingTimerId);
                this._autoPagingTimerId = null;
            }
        },

        toggleAutoPaging() {
            if (this.isAutoPaging) {
                this.stopAutoPaging();
            } else {
                this.startAutoPaging();
            }
        },

        restartAutoPagingTimer() {
            // **THE FIX IS HERE**: Only clear the timer, do not call stopAutoPaging() which changes the state.
            if (this._autoPagingTimerId) {
                clearInterval(this._autoPagingTimerId);
                this._autoPagingTimerId = null;
            }

            if (this.isAutoPaging) { // Now this check will be correctly true
                this._autoPagingTimerId = setInterval(() => {
                    if (this.canNext) {
                        this.nextPage();
                    } else {
                        this.stopAutoPaging(); // Reached the end, stop.
                    }
                }, this.autoPagingInterval * 1000);
            }
        },
        
        setAutoPagingInterval(interval: number) {
            this.autoPagingInterval = interval;
            if (this.isAutoPaging) {
                this.restartAutoPagingTimer();
            }
        }
    },
});