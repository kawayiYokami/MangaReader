import { defineStore } from 'pinia';
import { viewerApi } from '@/api/viewer';
import { ElMessage } from 'element-plus';
import { API_BASE_URL } from '@/api/base';

// ==================== 类型定义 ====================

interface MangaInfo {
    title: string;
    totalPages: number;
    filePath: string;
}

export interface MangaImage {
    src: string;
    pageIndex: number;
    width: number;
    height: number;
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

    isLoading: boolean;
    isSettingsPanelVisible: boolean; // 控制整体设置面板
    isAutoplaySettingsVisible: boolean; // 控制自动播放的悬浮设置
    isAutoPaging: boolean;
    autoPagingInterval: number; // in seconds

    isTranslationMode: boolean; // 新增：翻译模式标志

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

        isLoading: false,
        isSettingsPanelVisible: false,
        isAutoplaySettingsVisible: false,
        isAutoPaging: false,
        autoPagingInterval: 10,

        isTranslationMode: false,

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
            this.isTranslationMode = false; // 重置翻译模式

            // 如果是新的漫画，清空缓存
            if (this.mangaInfo.filePath !== mangaPath) {
                this.pageImageCache.clear();
            }

            try {
                // API会自动创建会话
                const mangaData = await viewerApi.setCurrentManga(mangaPath, initialPage);
                if (mangaData && typeof mangaData === 'object' && 'manga_info' in mangaData) {
                    const info = mangaData.manga_info as { title: string; total_pages: number };
                    this.mangaInfo.title = info.title;
                    this.mangaInfo.totalPages = info.total_pages;
                    this.mangaInfo.filePath = mangaPath;
                    // 在这里只设置元数据，不设置 currentPage
                }
                // 使用 goToPage 来加载初始页面，确保逻辑统一
                const currentPage = typeof mangaData === 'object' && mangaData !== null && 'current_page' in mangaData
                    ? (mangaData.current_page as number)
                    : initialPage;
                await this.goToPage(currentPage);

            } catch (err) {
                const errorMessage = err instanceof Error ? err.message : '未知错误';
                this.error = '初始化查看器失败';
                ElMessage.error(errorMessage || this.error);
                console.error(err);
            } finally {
                this.isLoading = false;
            }
        },

        async destroyViewerSession() {
            this.stopAutoPagingOnDestroy();
            await viewerApi.destroySession();
            this.$reset(); // 重置 store 状态，会自动清空 pageImageCache
        },

        // ==================== 核心页面加载（新架构） ====================
        async _fetchPageMetadata(pageToFetch: number): Promise<MangaImage[]> {
            if (this.mangaInfo.totalPages === 0) return [];
            try {
                let modeToSend = this.displayMode === 'auto' ? 'double' : this.displayMode;
                // 如果处于翻译模式，则强制使用单页
                if (this.isTranslationMode) {
                    modeToSend = 'single';
                }
                const metadata = await viewerApi.getPageMetadata(pageToFetch, modeToSend);

                if (metadata && typeof metadata === 'object' && 'images' in metadata) {
                    const images = metadata.images as Array<{ pageIndex: number; url: string; width: number; height: number }>;
                    return images.map((img) => ({
                        pageIndex: img.pageIndex,
                        src: `${API_BASE_URL}${img.url}`, // 构造成绝对 URL
                        width: img.width,
                        height: img.height
                    }));
                }
                return [];
            } catch (err) {
                const errorMessage = err instanceof Error ? err.message : '未知错误';
                this.error = `加载第 ${pageToFetch + 1} 页元数据失败`;
                ElMessage.error(errorMessage || this.error);
                console.error(err);
                return [];
            }
        },

        /**
         * For strip view: fetches page images without setting state.
         */
        async loadPageImages(page: number, displayMode: 'single' | 'double'): Promise<MangaImage[] | null> {
            try {
                const metadata = await viewerApi.getPageMetadata(page, displayMode);
                if (metadata && typeof metadata === 'object' && 'images' in metadata) {
                    const images = metadata.images as Array<{ pageIndex: number; url: string; width: number; height: number }>;
                    return images.map((img) => ({
                        pageIndex: img.pageIndex,
                        src: `${API_BASE_URL}${img.url}`,
                        width: img.width,
                        height: img.height
                    }));
                }
                return null;
            } catch (err) {
                const errorMessage = err instanceof Error ? err.message : '未知错误';
                console.error(`Failed to fetch images for page ${page}`, errorMessage);
                return null;
            }
        },

        // ==================== 页面导航（新架构） ====================
        async goToPage(page: number) {
            const newPage = Math.max(0, Math.min(page, this.mangaInfo.totalPages - 1));

            // 立即更新页面编号，让UI响应
            this.currentPage = newPage;

            let newImages: MangaImage[] = [];

            // 检查缓存
            if (this.pageImageCache.has(newPage)) {
                newImages = this.pageImageCache.get(newPage)!;
            } else {
                // 如果缓存未命中，则从服务器获取元数据
                // 这个过程很快，所以我们不设置 isLoading
                newImages = await this._fetchPageMetadata(newPage);
                this.pageImageCache.set(newPage, newImages);
            }

            // 更新图片URL列表，浏览器将开始在后台加载
            this.currentImages = newImages;

            // 计时器重置的逻辑已完全移交 PaginatedView.vue 组件处理
        },

        // nextPage 和 previousPage 的逻辑已完全移至 PaginatedView.vue 组件层

        // ==================== 功能切换 ====================
        async setDisplayMode(mode: DisplayMode) {
            this.displayMode = mode;
            // 切换模式后需要重新加载当前页，清空缓存以应对可能的模式变化（单页/双页）
            this.pageImageCache.clear();
            await this.goToPage(this.currentPage);
        },

        async toggleTranslationMode() {
            this.isTranslationMode = !this.isTranslationMode;
            // 切换翻译模式需要重新获取页面元数据以应用正确的显示模式
            this.pageImageCache.clear();
            await this.goToPage(this.currentPage);
        },

        // ==================== 自动翻页 (仅管理状态) ====================

        // 自动翻页的计时器和执行逻辑已移至 PaginatedView.vue 组件层
        // Store 只负责维护 isAutoPaging 和 autoPagingInterval 这两个全局状态

        toggleAutoPaging() {
            this.isAutoPaging = !this.isAutoPaging;
        },

        setAutoPagingInterval(interval: number) {
            this.autoPagingInterval = interval;
        },

        // 供组件在销毁时调用，确保状态正确
        stopAutoPagingOnDestroy() {
            this.isAutoPaging = false;
        }
    },
});
