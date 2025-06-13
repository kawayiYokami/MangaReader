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
    const currentImageUrls = ref([]);
    const isLoading = ref(false);
    const isFullscreen = ref(false);
    const displayMode = ref('auto'); // 'auto', 'single', 'double'
    const translationEnabled = ref(false);
    const isDragging = ref(false);

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
    const sliderContainer = ref(null);

    // ==================== 计算属性 ====================

    const actualDisplayMode = computed(() => {
        if (displayMode.value === 'single') return 'single';
        if (displayMode.value === 'double') return 'double';
        // 自动模式：根据屏幕比例和宽度决定
        return (screenInfo.ratio > 1.5 && screenInfo.width > 1200) ? 'double' : 'single';
    });

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

    // 滑块样式
    const thumbStyle = computed(() => {
        if (!sliderContainer.value || mangaInfo.total_pages <= 1) {
            return { top: '0px' };
        }
        const containerHeight = sliderContainer.value.offsetHeight;
        const thumbHeight = 30; // 与CSS中设置的高度一致
        const trackHeight = containerHeight - thumbHeight;
        const percentage = currentPage.value / (mangaInfo.total_pages - 1);
        const top = percentage * trackHeight;
        return { top: `${top}px` };
    });

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
        currentImageUrls,
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
        sliderContainer,

        // 计算属性
        actualDisplayMode,
        progressPercentage,
        progressCircumference,
        progressOffset,
        thumbStyle,
        displayModeText,
        canPrevious,
        canNext,
    };
}