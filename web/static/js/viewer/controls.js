// 负责处理所有用户交互逻辑
const { nextTick, watch } = Vue;
const { ElMessage } = ElementPlus;

export function createControls(state, viewerManager) {
    const {
        mangaInfo, currentPage, showPageInput, pageInputText,
        currentImages, isLoading, isFullscreen, displayMode,
        actualDisplayMode, translationEnabled, isDragging,
        isAutoPaging, autoPagingInterval, autoPagingTimerId,
        isAutoplaySettingsVisible, autoplaySettingsHideTimer,
        screenInfo, pageInputRef, viewerContent
    } = state;

    // ==================== 页面加载 ====================

    async function loadCurrentPage() {
       try {
           const modeToSend = displayMode.value === 'auto' ? 'double' : displayMode.value;
           
           const result = await viewerManager.getPageImages(
               currentPage.value,
               modeToSend,
               translationEnabled.value
           );

           if (result && Array.isArray(result) && result.length > 0) {
               currentImages.value = result.map(img => ({
                   src: img.image_data,
                   width: img.width,
                   height: img.height,
                   pageIndex: img.page_index
               }));
           } else {
               currentImages.value = [];
           }
           
           // 在图片数据更新后，手动计算并设置显示模式
           updateActualDisplayMode();

       } catch (error) {
           ElMessage.error(`加载第 ${currentPage.value + 1} 页失败`);
           console.error(error);
           currentImages.value = [];
       }
   }

    // ==================== 页面控制 ====================

    function previousPage() {
        if (currentPage.value <= 0) return;
        const step = actualDisplayMode.value === 'double' ? 2 : 1;
        const newPage = Math.max(0, currentPage.value - step);
        onPageChange(newPage);
        if (isAutoPaging.value) restartAutoPagingTimer(); // 重置计时器
    }

    function nextPage() {
        if (currentPage.value >= mangaInfo.total_pages - 1) return;
        const step = actualDisplayMode.value === 'double' ? 2 : 1;
        const newPage = Math.min(mangaInfo.total_pages - 1, currentPage.value + step);
        onPageChange(newPage);
        if (isAutoPaging.value) restartAutoPagingTimer(); // 重置计时器
    }

    async function onPageChange(newPage) {
        currentPage.value = newPage;
        pageInputText.value = (newPage + 1).toString();
        await loadCurrentPage();
        // 注意：onPageChange 通常由其他函数调用，所以重置计时器的逻辑放在调用它的地方
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
        // 在 blur 时不再自动应用，避免与悬浮面板的交互冲突
        // 如果需要，可以保留 applyPageInput();
    }

    function cancelPageInput() {
        showPageInput.value = false;
        pageInputText.value = (currentPage.value + 1).toString();
    }

    function applyPageInput() {
        const newPage = parseInt(pageInputText.value);
        if (newPage && newPage >= 1 && newPage <= mangaInfo.total_pages) {
            onPageChange(newPage - 1);
            if (isAutoPaging.value) restartAutoPagingTimer(); // 重置计时器
        } else {
            pageInputText.value = (currentPage.value + 1).toString();
        }
        showPageInput.value = false;
    }

    // ==================== 自动翻页 (重构后) ====================

    function startAutoPaging() {
        isAutoPaging.value = true;
        restartAutoPagingTimer();
    }
    
    function stopAutoPaging() {
        if (autoPagingTimerId.value) {
            clearInterval(autoPagingTimerId.value);
            autoPagingTimerId.value = null;
        }
        isAutoPaging.value = false;
    }

    // 新增：重置计时器的核心函数
    function restartAutoPagingTimer() {
        // 先清除旧的
        if (autoPagingTimerId.value) {
            clearInterval(autoPagingTimerId.value);
        }
        // 设置新的
        autoPagingTimerId.value = setInterval(() => {
            if (currentPage.value < mangaInfo.total_pages - 1) {
                nextPage(); // nextPage 内部会再次调用 restart
            } else {
                stopAutoPaging(); // 到达最后一页，自动停止
            }
        }, autoPagingInterval.value * 1000);
    }

    function toggleAutoPaging() {
        if (isAutoPaging.value) {
            stopAutoPaging();
        } else {
            startAutoPaging();
        }
    }

    // 新增：自动播放设置面板交互
    function handleAutoplayMouseEnter() {
        if (autoplaySettingsHideTimer.value) {
            clearTimeout(autoplaySettingsHideTimer.value);
            autoplaySettingsHideTimer.value = null;
        }
        isAutoplaySettingsVisible.value = true;
    }

    function handleAutoplayMouseLeave() {
        autoplaySettingsHideTimer.value = setTimeout(() => {
            isAutoplaySettingsVisible.value = false;
        }, 2000); // 延迟2秒隐藏
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
        // 只更新屏幕信息，不再触发页面重载
        screenInfo.width = window.innerWidth;
        screenInfo.height = window.innerHeight;
        screenInfo.ratio = window.innerWidth / window.innerHeight;
    }

    // 新增：手动更新显示模式的函数
    function updateActualDisplayMode() {
        if (displayMode.value === 'single') {
            actualDisplayMode.value = 'single';
            return;
        }
        if (displayMode.value === 'double') {
            actualDisplayMode.value = currentImages.value.length === 1 ? 'single' : 'double';
            return;
        }

        // 自动模式核心逻辑
        if (currentImages.value.length === 0) {
            actualDisplayMode.value = 'single';
            return;
        }
        if (currentImages.value.length === 1) {
            actualDisplayMode.value = 'single';
            return;
        }

        const containerWidth = viewerContent.value ? viewerContent.value.clientWidth : window.innerWidth;
        if (containerWidth < 900) {
            actualDisplayMode.value = 'single';
            return;
        }
        
        const containerHeight = viewerContent.value ? viewerContent.value.clientHeight : window.innerHeight;
        let totalWidth = 0;
        for (const img of currentImages.value) {
            if (!img.height || img.height === 0) {
                actualDisplayMode.value = 'single';
                return;
            }
            const scaleRatio = containerHeight / img.height;
            totalWidth += img.width * scaleRatio;
        }

        actualDisplayMode.value = totalWidth > containerWidth ? 'single' : 'double';
    }
// 监听翻页间隔的变化，如果正在翻页，则重置计时器
watch(autoPagingInterval, () => {
    if (isAutoPaging.value) {
        restartAutoPagingTimer();
    }
});

   // ==================== 进度条控制 (支持拖拽) ====================
   
   // 拖动时仅更新页码，不加载图片，以保证流畅
   function setPageFromProgress(event, container) {
       const track = container.querySelector('.progress-bar-track');
       if (!track) return;

       const rect = track.getBoundingClientRect(); // 精确使用轨道的位置和尺寸
       const clickY = event.clientY - rect.top;
       const percentage = Math.max(0, Math.min(1, clickY / rect.height));
       
       if (mangaInfo.total_pages > 0) {
           const targetPage = Math.floor(percentage * mangaInfo.total_pages);
           const clampedPage = Math.max(0, Math.min(targetPage, mangaInfo.total_pages - 1));
           
           // 仅更新 ref，UI 上的页码会响应式更新
           if (clampedPage !== currentPage.value) {
               currentPage.value = clampedPage;
               pageInputText.value = (clampedPage + 1).toString();
           }
       }
   }

   function onProgressMouseDown(event) {
       isDragging.value = true;
       event.preventDefault(); // 阻止默认的文本选择行为
       
       const container = event.currentTarget;
       setPageFromProgress(event, container); // 立即响应第一次点击

       const onMouseMove = (moveEvent) => {
           if (isDragging.value) {
               // 拖动时实时更新页码
               setPageFromProgress(moveEvent, container);
           }
       };

       const onMouseUp = () => {
           isDragging.value = false;
           window.removeEventListener('mousemove', onMouseMove);
           window.removeEventListener('mouseup', onMouseUp);

           // 拖动结束后，才真正加载图片
           loadCurrentPage();
           if (isAutoPaging.value) restartAutoPagingTimer();
       };

       window.addEventListener('mousemove', onMouseMove);
       window.addEventListener('mouseup', onMouseUp);
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
        toggleAutoPaging,
        handleAutoplayMouseEnter,
        handleAutoplayMouseLeave,
        onProgressMouseDown,
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