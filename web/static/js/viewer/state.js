// 负责定义和导出所有共享的响应式状态
const { ref, reactive, computed } = Vue;

export function createState() {
    // 基础UI状态
    const mangaInfo = reactive({
        title: '加载中...',
        total_pages: 0
    });
    const currentPage = ref(0);
    const showPageInput = ref(false);
    const pageInputText = ref('1');
    const currentImages = ref([]); // 替换 currentImageUrls
    const isLoading = ref(false);
    const isFullscreen = ref(false);
    const displayMode = ref('auto'); // 'auto', 'single', 'double'
    const translationEnabled = ref(false);
    // isDragging 已被移除
    const isAutoPaging = ref(false);
    const autoPagingInterval = ref(10);
    const autoPagingTimerId = ref(null);
    const isAutoplaySettingsVisible = ref(false); // 新增：控制悬浮面板的显示
    const autoplaySettingsHideTimer = ref(null); // 新增：用于延迟隐藏设置面板
   const isDragging = ref(false); // 新增：用于跟踪进度条拖动状态

    // 屏幕信息
    const screenInfo = reactive({
        width: window.innerWidth,
        height: window.innerHeight,
        ratio: window.innerWidth / window.innerHeight
    });

    // DOM 引用
    const viewerContent = ref(null);
    const mangaImage = ref(null);
    const pageInputRef = ref(null);
    const autoPagePopover = ref(null); // 新增 Popover 的引用

    // ==================== 计算属性 ====================

    const actualDisplayMode = ref('single'); // 从 computed 改为 ref

    const progressPercentage = computed(() => {
        if (mangaInfo.total_pages === 0) return 0;
        return ((currentPage.value + 1) / mangaInfo.total_pages) * 100;
    });

    // 圆形进度条计算
    const progressCircumference = computed(() => 2 * Math.PI * 25);
    const progressOffset = computed(() => {
        const circumference = progressCircumference.value;
        return circumference - (progressPercentage.value / 100) * circumference;
    });

    // thumbStyle 已被移除，因为它依赖于一个不存在的 sliderContainer
    const displayModeText = computed(() => {
        const modes = {
            'auto': '自动',
            'single': '单页',
            'double': '双页'
        };
        return modes[displayMode.value] || '自动';
    });

    const canPrevious = computed(() => currentPage.value > 0);
    const canNext = computed(() => currentPage.value < mangaInfo.total_pages - 1);


    return {
        // 数据
        mangaInfo,
        currentPage,
        showPageInput,
        pageInputText,
        currentImages,
        isLoading,
        isFullscreen,
        displayMode,
        translationEnabled,
       isDragging,
        screenInfo,

        // DOM 引用
        viewerContent,
        mangaImage,
        pageInputRef,
        autoPagePopover, // 导出 popover 引用

        // 自动翻页状态
        isAutoPaging,
        autoPagingInterval,
        autoPagingTimerId,
        isAutoplaySettingsVisible,
        autoplaySettingsHideTimer,

        // 计算属性
        actualDisplayMode,
        progressPercentage,
        progressCircumference,
        progressOffset,
        displayModeText,
        canPrevious,
        canNext,
    };
}