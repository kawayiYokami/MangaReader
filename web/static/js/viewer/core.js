import { createState } from './state.js';
import { createControls } from './controls.js';

// 移除了 watch 的导入，因为它现在只在 controls.js 中使用
const { createApp, onMounted, onUnmounted } = Vue;
const { ElMessage } = ElementPlus;

const app = createApp({
    setup() {
        // 1. 创建状态和DOM引用
        const state = createState();

        // 2. 创建查看器管理器实例
        const viewerManager = new ViewerManager();

        // 3. 创建所有控制方法
        const controls = createControls(state, viewerManager);

        // ==================== 初始化和生命周期 ====================

        onMounted(async () => {
            // 从URL获取参数
            const urlParams = new URLSearchParams(window.location.search);
            const mangaPath = urlParams.get('path');
            const initialPage = parseInt(urlParams.get('page') || '0');

            if (!mangaPath) {
                ElMessage.error('缺少漫画路径参数');
                return;
            }

            // 初始化管理器并加载第一页
            await initializeViewer(mangaPath, initialPage);

            // 添加全局事件监听
            document.addEventListener('keydown', controls.handleKeydown);
            document.addEventListener('fullscreenchange', controls.handleFullscreenChange);
            document.addEventListener('wheel', controls.handleWheel, { passive: false });
            window.addEventListener('resize', controls.handleResize);
        });

        onUnmounted(() => {
            // 移除全局事件监听
            document.removeEventListener('keydown', controls.handleKeydown);
            document.removeEventListener('fullscreenchange', controls.handleFullscreenChange);
            document.removeEventListener('wheel', controls.handleWheel);
            window.removeEventListener('resize', controls.handleResize);

            // 销毁会话
            if (viewerManager) {
                viewerManager.destroySession();
            }
        });

        async function initializeViewer(mangaPath, initialPage) {
            try {
                // 不再需要在这里设置 isLoading，因为闪烁问题已经通过修改HTML结构解决
                // state.isLoading.value = true; 
                
                await viewerManager.createSession();
                const result = await viewerManager.setCurrentManga(mangaPath, initialPage);

                if (result) {
                    state.mangaInfo.title = result.manga_info.title;
                    state.mangaInfo.total_pages = result.manga_info.total_pages;
                    state.currentPage.value = result.current_page;
                    state.pageInputText.value = (result.current_page + 1).toString();
                }

                await controls.loadCurrentPage();

            } catch (error) {
                ElMessage.error('初始化查看器失败');
                console.error(error);
            } finally {
                // 同样，不再需要重置 isLoading
                // state.isLoading.value = false;
            }
        }
        
        // 此处的 watch 代码块已被移除，因为它的逻辑已经合并到 controls.js 中

        // 4. 返回所有需要在模板中使用的数据和方法
        return {
            ...state,
            ...controls
        };
    }
});

app.use(ElementPlus).mount('#app');