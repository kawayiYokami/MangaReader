const { createApp, ref, onMounted, onUnmounted, nextTick } = Vue;
const { ElMessage } = ElementPlus;

const app = createApp({
    setup() {
        // --- DOM Refs ---
        const scrollContainer = ref(null);

        // --- State ---
        const mangaInfo = ref({ title: '', total_pages: 0 });
        const loadedPages = ref([]);
        const isLoading = ref(true);

        // --- Fast Scrubber State ---
        const isScrubberVisible = ref(false);
        const scrubberHandleTop = ref(0); // 百分比
        const scrubberPageNumber = ref(1);
        const isDraggingScrubber = ref(false);
        let hideScrubberTimeout = null;
        
        // --- 滚动方向检测 ---
        let lastScrollTop = 0;

        // --- Intersection Observer ---
        let pageIntersectionObserver = null;

        // --- Viewer Manager ---
        const viewerManager = new ViewerManager();

        // --- Core Logic ---
        async function initializeReader(mangaPath) {
            try {
                await viewerManager.createSession();
                const result = await viewerManager.setCurrentManga(mangaPath, 0);

                if (result) {
                    mangaInfo.value.title = result.manga_info.title;
                    mangaInfo.value.total_pages = result.manga_info.total_pages;
                    document.title = result.manga_info.title || '漫画查看器';

                    // --- 懒加载高度预估 ---
                    // 在图片加载前，为占位符提供一个预估高度，防止IntersectionObserver一次性触发所有加载
                    const screenWidth = window.innerWidth;
                    const estimatedAspectRatio = 1.414; // 使用一个常见的高宽比 (如 A4 纸)
                    const estimatedHeight = screenWidth * estimatedAspectRatio;
                    
                    // 创建占位符数组，不再预加载所有图片
                    loadedPages.value = Array.from({ length: mangaInfo.value.total_pages }, (_, i) => ({
                        src: '', // 初始为空
                        pageIndex: i,
                        isLoading: false, // 新增：跟踪单页加载状态
                        isLoaded: false,   // 新增：标记是否已加载
                        estimatedHeight: estimatedHeight // 为每个占位符设置预估高度
                    }));
                    isLoading.value = false;

                } else {
                    ElMessage.error('无法加载漫画信息');
                    isLoading.value = false;
                }
            } catch (error) {
                console.error('初始化阅读器失败:', error);
                ElMessage.error('初始化阅读器失败');
                isLoading.value = false;
            }
        }

        // 新的懒加载函数
        async function loadPageIfNeeded(pageIndex) {
            if (pageIndex < 0 || pageIndex >= loadedPages.value.length) return;

            const page = loadedPages.value[pageIndex];
            if (page.isLoaded || page.isLoading) return; // 防止重复加载

            page.isLoading = true;

            try {
                // 获取容器尺寸
                const container = scrollContainer.value;
                const maxWidth = container ? container.clientWidth : window.innerWidth;
                const maxHeight = container ? container.clientHeight : window.innerHeight;

                const images = await viewerManager.getPageImages(pageIndex, 'single', false, maxWidth, maxHeight);
                if (images && images.length > 0) {
                    page.src = images[0].image_data;
                    page.isLoaded = true;
                }
            } catch (error) {
                console.error(`加载第 ${pageIndex + 1} 页失败:`, error);
            } finally {
                page.isLoading = false;
            }
        }

        // --- Fast Scrubber Logic ---

        function handleScroll() {
            if (isDraggingScrubber.value || !scrollContainer.value) return;

            const scrollTop = scrollContainer.value.scrollTop;

            // --- 非对称吸附逻辑 ---
            if (scrollTop > lastScrollTop) {
                scrollContainer.value.classList.add('is-snapping');
            } else {
                scrollContainer.value.classList.remove('is-snapping');
            }
            lastScrollTop = scrollTop <= 0 ? 0 : scrollTop;

            updateScrubberFromScroll();
        }
        
        function updateScrubberFromScroll() {
            if (!scrollContainer.value) return;
            const { scrollTop, scrollHeight, clientHeight } = scrollContainer.value;
            const scrollableHeight = scrollHeight - clientHeight;
            const scrollPercentage = scrollableHeight > 0 ? (scrollTop / scrollableHeight) * 100 : 0;
            scrubberHandleTop.value = Math.min(Math.max(scrollPercentage, 0), 100);
        }
        
        /**
         * 当用户在右侧边缘按下并开始拖动时。
         */
        function onScrubberPress(e) {
            if (hideScrubberTimeout) clearTimeout(hideScrubberTimeout);

            isScrubberVisible.value = true;
            isDraggingScrubber.value = true;
            document.body.style.cursor = 'grabbing';

            window.addEventListener('mousemove', handleDragMove);
            window.addEventListener('mouseup', handleDragEnd);
            window.addEventListener('touchmove', handleDragMove, { passive: false });
            window.addEventListener('touchend', handleDragEnd);
            
            e.preventDefault();

            // 立即根据按下的位置更新滑块和滚动位置
            handleDragMove(e);
        }

        function handleDragMove(e) {
            if (!isDraggingScrubber.value) return;
            
            e.preventDefault();
            
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;
            const containerRect = scrollContainer.value.getBoundingClientRect();
            const handleHeight = 40;
            
            let newY = clientY - containerRect.top - (handleHeight / 2);
            let percentage = (newY / (containerRect.height - handleHeight)) * 100;
            percentage = Math.min(Math.max(percentage, 0), 100);
            
            scrubberHandleTop.value = percentage;
            
            const targetScrollTop = (percentage / 100) * (scrollContainer.value.scrollHeight - scrollContainer.value.clientHeight);
            scrollContainer.value.scrollTop = targetScrollTop;
            
            const estimatedPage = Math.floor((percentage / 100) * mangaInfo.value.total_pages);
            scrubberPageNumber.value = Math.min(mangaInfo.value.total_pages, Math.max(1, estimatedPage + 1));
        }

        function handleDragEnd() {
            isDraggingScrubber.value = false;
            document.body.style.cursor = 'default';

            window.removeEventListener('mousemove', handleDragMove);
            window.removeEventListener('mouseup', handleDragEnd);
            window.removeEventListener('touchmove', handleDragMove);
            window.removeEventListener('touchend', handleDragEnd);
            
            if (hideScrubberTimeout) clearTimeout(hideScrubberTimeout);
            hideScrubberTimeout = setTimeout(() => {
                isScrubberVisible.value = false;
            }, 1500);
        }

        // --- Event Handlers for template ---
        function onImageLoad(event, pageIndex) {
            // 图片加载完成后，可以停止观察，因为我们不再需要对它做任何事
            const pageElement = event.target.parentElement;
            if (pageIntersectionObserver && pageElement) {
                pageIntersectionObserver.unobserve(pageElement);
            }
        }
        function onImageError(pageIndex) {}

        /**
         * 设置 Intersection Observer 来精确跟踪当前可见页面。
         */
        function setupIntersectionObserver() {
            const options = {
                root: scrollContainer.value,
                rootMargin: '200px 0px', // 预加载视窗上下200px的图片
                threshold: 0.01
            };

            pageIntersectionObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    const pageIndex = parseInt(entry.target.dataset.pageIndex, 10);
                    if (isNaN(pageIndex)) return;

                    if (entry.isIntersecting) {
                        // 更新当前页码
                        scrubberPageNumber.value = pageIndex + 1;
                        // 触发懒加载
                        loadPageIfNeeded(pageIndex);
                    }
                });
            }, options);

            // 初始化时，让Observer观察所有占位符
            nextTick(() => {
                // DOM更新后，每个 .manga-page 已经有了 min-height，可以直接观察
                const pageElements = scrollContainer.value.querySelectorAll('.manga-page');
                pageElements.forEach(el => pageIntersectionObserver.observe(el));
            });
        }

        // --- Lifecycle Hooks ---
        onMounted(async () => {
            const urlParams = new URLSearchParams(window.location.search);
            const mangaPath = urlParams.get('path');
            if (!mangaPath) {
                ElMessage.error('缺少漫画路径参数');
                return;
            }
            // 必须先等待阅读器初始化完成，拿到页面数据
            await initializeReader(mangaPath);

            // 在数据加载完成，DOM更新后，再设置Observer
            setupIntersectionObserver();
        });

        onUnmounted(() => {
            if (pageIntersectionObserver) {
                pageIntersectionObserver.disconnect();
            }
        });

        // --- Expose to Template ---
        return {
            scrollContainer,
            mangaInfo,
            loadedPages,
            isLoading,
            isScrubberVisible,
            scrubberHandleTop,
            scrubberPageNumber,
            isDraggingScrubber,
            handleScroll,
            onScrubberPress,
            onImageLoad,
            onImageError
        };
    }
});

app.use(ElementPlus).mount('#app');