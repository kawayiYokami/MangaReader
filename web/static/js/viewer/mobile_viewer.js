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
                    fetchAllPages();
                } else {
                    ElMessage.error('无法加载漫画信息');
                }
            } catch (error) {
                console.error('初始化阅读器失败:', error);
                ElMessage.error('初始化阅读器失败');
            }
        }

        async function fetchAllPages() {
            const total = mangaInfo.value.total_pages;
            for (let i = 0; i < total; i++) {
                try {
                    const images = await viewerManager.getPageImages(i, 'single', false);
                    if (images && images.length > 0) {
                        loadedPages.value.push({
                            src: images[0].image_data,
                            pageIndex: images[0].page_index
                        });
                    }
                } catch (error) {
                    console.error(`加载第 ${i + 1} 页失败:`, error);
                }
            }
            isLoading.value = false;
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
            if (pageIntersectionObserver && event.target.parentElement) {
                pageIntersectionObserver.observe(event.target.parentElement);
            }
        }
        function onImageError(pageIndex) {}

        /**
         * 设置 Intersection Observer 来精确跟踪当前可见页面。
         */
        function setupIntersectionObserver() {
            const options = {
                root: scrollContainer.value,
                threshold: 0.5
            };

            pageIntersectionObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const pageIndex = parseInt(entry.target.dataset.pageIndex, 10);
                        if (!isNaN(pageIndex)) {
                            scrubberPageNumber.value = pageIndex + 1;
                        }
                    }
                });
            }, options);
        }

        // --- Lifecycle Hooks ---
        onMounted(() => {
            const urlParams = new URLSearchParams(window.location.search);
            const mangaPath = urlParams.get('path');
            if (!mangaPath) {
                ElMessage.error('缺少漫画路径参数');
                return;
            }
            setupIntersectionObserver();
            initializeReader(mangaPath);
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