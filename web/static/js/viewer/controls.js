// 负责处理所有用户交互逻辑
const { nextTick, watch } = Vue;
const { ElMessage } = ElementPlus;

export function createControls(state, viewerManager) {
    const {
        mangaInfo, currentPage, showPageInput, pageInputText,
        currentImageUrls, isLoading, isFullscreen, displayMode,
        actualDisplayMode, translationEnabled, isDragging,
        screenInfo, pageInputRef, sliderContainer, viewerContent
    } = state;

    // ==================== 页面加载 ====================

    async function loadCurrentPage() {
        try {
            const images = await viewerManager.getPageImages(
                currentPage.value,
                actualDisplayMode.value,
                translationEnabled.value
            );

            if (images && images.length > 0) {
                currentImageUrls.value = images.map(img => img.image_data);
            } else {
                throw new Error('无法加载页面图像');
            }
        } catch (error) {
            ElMessage.error(`加载第 ${currentPage.value + 1} 页失败`);
            console.error(error);
        }
    }

    // ==================== 页面控制 ====================

    function previousPage() {
        if (currentPage.value <= 0) return;
        const step = actualDisplayMode.value === 'double' ? 2 : 1;
        const newPage = Math.max(0, currentPage.value - step);
        onPageChange(newPage);
    }

    function nextPage() {
        if (currentPage.value >= mangaInfo.total_pages - 1) return;
        const step = actualDisplayMode.value === 'double' ? 2 : 1;
        const newPage = Math.min(mangaInfo.total_pages - 1, currentPage.value + step);
        onPageChange(newPage);
    }

    async function onPageChange(newPage) {
        currentPage.value = newPage;
        pageInputText.value = (newPage + 1).toString();
        await loadCurrentPage();
    }


    // ==================== 翻译控制 ====================

    async function toggleTranslation() {
        try {
            const newState = !translationEnabled.value;
            const result = await viewerManager.toggleTranslation(newState);
            if (result) {
                translationEnabled.value = newState;
                await loadCurrentPage();
            }
        } catch (error) {
            ElMessage.error('切换翻译状态失败');
        }
    }

    // ==================== 显示模式控制 ====================

    function toggleDisplayMode() {
        const modes = ['auto', 'single', 'double'];
        const currentIndex = modes.indexOf(displayMode.value);
        const nextIndex = (currentIndex + 1) % modes.length;
        displayMode.value = modes[nextIndex];
        nextTick(loadCurrentPage);
    }

    // ==================== 页码输入 ====================

    function onPageInputEnter() {
        applyPageInput();
    }

    function onPageInputBlur() {
        applyPageInput();
    }

    function cancelPageInput() {
        showPageInput.value = false;
        pageInputText.value = (currentPage.value + 1).toString();
    }

    function applyPageInput() {
        const newPage = parseInt(pageInputText.value);
        if (newPage && newPage >= 1 && newPage <= mangaInfo.total_pages) {
            onPageChange(newPage - 1);
        } else {
            pageInputText.value = (currentPage.value + 1).toString();
        }
        showPageInput.value = false;
    }

    // ==================== 自定义滑块 ====================

    function onThumbMouseDown(event) {
        isDragging.value = true;
        const thumb = event.target;
        const container = sliderContainer.value;
        const initialY = event.clientY;
        const initialTop = thumb.offsetTop;

        const onMouseMove = (moveEvent) => {
            if (!isDragging.value) return;
            const deltaY = moveEvent.clientY - initialY;
            let newTop = initialTop + deltaY;
            const containerHeight = container.offsetHeight;
            const thumbHeight = thumb.offsetHeight;
            newTop = Math.max(0, Math.min(newTop, containerHeight - thumbHeight));
            const percentage = newTop / (containerHeight - thumbHeight);
            const newPage = Math.round(percentage * (mangaInfo.total_pages - 1));
            pageInputText.value = (newPage + 1).toString();
            thumb.style.top = `${newTop}px`;
        };

        const onMouseUp = () => {
            isDragging.value = false;
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            const finalPercentage = thumb.offsetTop / (container.offsetHeight - thumb.offsetHeight);
            const finalPage = Math.round(finalPercentage * (mangaInfo.total_pages - 1));
            if (finalPage !== currentPage.value) {
                onPageChange(finalPage);
            }
        };

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    }

    function onTrackClick(event) {
        if (isDragging.value) return;
        const container = sliderContainer.value;
        const rect = container.getBoundingClientRect();
        const clickY = event.clientY - rect.top;
        const containerHeight = container.offsetHeight;
        const thumbHeight = 30;
        let percentage = (clickY - (thumbHeight / 2)) / (containerHeight - thumbHeight);
        percentage = Math.max(0, Math.min(1, percentage));
        const newPage = Math.round(percentage * (mangaInfo.total_pages - 1));
        if (newPage !== currentPage.value) {
            onPageChange(newPage);
        }
    }

    // ==================== 事件处理 ====================

    function handleKeydown(event) {
        // 当输入框激活时，不触发快捷键
        if (showPageInput.value) return;
        
        switch (event.key) {
            case 'ArrowLeft':
                event.preventDefault();
                previousPage();
                break;
            case 'ArrowRight':
                event.preventDefault();
                nextPage();
                break;
            case 'Escape':
                if (isFullscreen.value) exitFullscreen();
                break;
            case 'F11':
                event.preventDefault();
                toggleFullscreen();
                break;
        }
    }

    function onImageClick(event) {
        const rect = event.currentTarget.getBoundingClientRect();
        const clickX = event.clientX - rect.left;
        const centerX = rect.width / 2;
        if (clickX < centerX) {
            previousPage();
        } else {
            nextPage();
        }
    }
    
    function onImageLoad() { /* 图片加载完成 */ }
    function onImageError() { ElMessage.error('图片加载失败'); }

    // ==================== 全屏控制 ====================

    function toggleFullscreen() {
        if (isFullscreen.value) {
            exitFullscreen();
        } else {
            enterFullscreen();
        }
    }

    function enterFullscreen() {
        const element = viewerContent.value;
        if (element.requestFullscreen) element.requestFullscreen();
        else if (element.webkitRequestFullscreen) element.webkitRequestFullscreen();
        else if (element.msRequestFullscreen) element.msRequestFullscreen();
    }

    function exitFullscreen() {
        if (document.exitFullscreen) document.exitFullscreen();
        else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
        else if (document.msExitFullscreen) document.msExitFullscreen();
    }

    function handleFullscreenChange() {
        isFullscreen.value = !!document.fullscreenElement;
    }

    // ==================== 其他事件 ====================

    function handleWheel(event) {
        if (event.deltaY > 0) nextPage();
        else previousPage();
        event.preventDefault();
    }

    function handleResize() {
        screenInfo.width = window.innerWidth;
        screenInfo.height = window.innerHeight;
        screenInfo.ratio = window.innerWidth / window.innerHeight;
        if (displayMode.value === 'auto') {
            nextTick(loadCurrentPage);
        }
    }

    // 监听页码输入框显示状态，自动聚焦
    watch(showPageInput, (newValue) => {
        if (newValue) {
            nextTick(() => {
                if (pageInputRef.value) {
                    pageInputRef.value.focus();
                    pageInputRef.value.select();
                }
            });
        }
    });

    return {
        loadCurrentPage,
        previousPage,
        nextPage,
        onPageChange,
        toggleTranslation,
        toggleDisplayMode,
        onPageInputEnter,
        onPageInputBlur,
        cancelPageInput,
        applyPageInput,
        onThumbMouseDown,
        onTrackClick,
        handleKeydown,
        onImageClick,
        onImageLoad,
        onImageError,
        toggleFullscreen,
        enterFullscreen,
        exitFullscreen,
        handleFullscreenChange,
        handleWheel,
        handleResize,
    };
}