<template>
  <div class="paginated-view-container" ref="viewerContentRef">
    <!-- Left Sidebar -->
    <div class="left-sidebar">
      <div
        class="manga-title-section"
        :class="{ 'is-clickable': isPyWebView }"
        @click="onTitleClick"
        title="在文件浏览器中显示"
      >
        <div class="manga-title-vertical">{{ store.mangaInfo.title }}</div>
      </div>

      <div class="page-navigation">
        <div class="viewer-btn" @click="goToPreviousPage" :class="{ 'is-disabled': !store.canPrevious }">arrow_upward</div>

        <div class="page-info" @click="showPageInput = true">
          <div v-if="!showPageInput" class="page-display">
            <span class="current-page">{{ store.currentPage + 1 }}</span>
            <span class="page-divider">/</span>
            <span class="total-pages">{{ store.mangaInfo.totalPages }}</span>
          </div>
          <el-input
            v-else
            ref="pageInputRef"
            v-model="pageInputText"
            class="page-input"
            @keyup.enter="onPageInputEnter"
            @blur="showPageInput = false"
          />
        </div>

        <div class="progress-bar-container" @mousedown="onProgressMouseDown">
          <div class="progress-bar-track">
            <div class="progress-bar-thumb" :style="{ top: `${store.progressPercentage}%` }"></div>
          </div>
        </div>

        <div class="viewer-btn" @click="goToNextPage" :class="{ 'is-disabled': !store.canNext }">arrow_downward</div>
      </div>

      <div class="bottom-toolbar">
          <div class="viewer-btn" @click="goBack" title="返回浏览器">arrow_back</div>
          <div class="viewer-btn" @click="switchToStripView" title="切换到条漫模式">view_day</div>
          <div class="viewer-btn" @click="toggleTranslation" :class="{ 'is-active': store.isTranslationMode }" title="AI翻译">translate</div>
          
          <!-- Correct Autoplay Control with Popover -->
          <el-popover
            ref="autoplayPopoverRef"
            placement="right-end"
            :width="240"
            trigger="click"
            popper-class="viewer-popover"
          >
            <template #reference>
              <div class="viewer-btn" :class="{ 'is-active': store.isAutoPaging }" title="自动翻页设置">
                <span v-if="store.isAutoPaging" class="autoplay-indicator-text">{{ Math.round(store.autoPagingInterval) }}</span>
                <span v-else>slideshow</span>
              </div>
            </template>
            <div
              class="autoplay-popover-content"
              @mouseenter="clearPopoverCloseTimer"
              @mouseleave="startPopoverCloseTimer"
            >
              <div
                class="viewer-btn popover-play-btn"
                :class="{ 'is-active': store.isAutoPaging }"
                @click.stop="toggleAutoPaging"
              >
                {{ store.isAutoPaging ? 'pause' : 'play_arrow' }}
              </div>
              <el-slider
                v-model="autoPagingIntervalForSlider"
                :min="1"
                :max="30"
                :step="1"
                class="popover-slider"
                @input="setAutoPagingInterval"
              />
              <div class="autoplay-popover-value">{{ Math.round(store.autoPagingInterval) }}s</div>
            </div>
          </el-popover>
      </div>
    </div>

    <!-- Translation Sidebar -->
    <div class="translation-sidebar" :class="{ 'is-visible': store.isTranslationMode }">
      <div class="translation-header">
        <h3>AI 翻译</h3>
      </div>
      <div class="translation-content">
        <div v-if="isTranslating" class="loading-spinner">
          <el-icon class="is-loading" :size="30"><Loading /></el-icon>
          <span>翻译中...</span>
        </div>
        <div v-else-if="translationError" class="error-message">
          {{ translationError }}
        </div>
        <div v-else-if="translationScript && translationScript.script.length > 0">
          <div
            v-for="(line, index) in translationScript.script"
            :key="index"
            class="dialogue-line"
            :data-speaker-id="line.speaker_id"
          >
            <p class="translated-text">{{ line.translated_text }}</p>
            <p class="original-text">{{ line.original_text }}</p>
          </div>
        </div>
        <el-empty v-else description="无翻译内容" />
      </div>
    </div>

    <!-- Main Content -->
    <div class="viewer-content" @click="onImageClick">
      <div v-if="store.isLoading && displayedImages.length === 0" class="loading-spinner">
        <el-icon class="is-loading" :size="50"><Loading /></el-icon>
      </div>
      <div v-else-if="store.error" class="error-message">
        {{ store.error }}
      </div>
      <div v-else-if="imagesToActuallyRender.length > 0" class="image-container">
        <img
           v-for="img in imagesToActuallyRender"
           :key="img.pageIndex"
           :src="img.src"
           class="manga-image"
           :class="store.actualDisplayMode === 'single' ? 'single-page' : 'double-page'"
           alt="Manga Page"
       />
      </div>
       <el-empty v-else description="没有图像" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useElementSize } from '@vueuse/core';
import { useViewerStore, type MangaImage } from '@/store/viewer';
import { useMangaStore } from '@/store/manga';
import { useSettingsStore } from '@/store/settings';
import { useEnvironment } from '@/composables/useEnvironment';
import { Loading } from '@element-plus/icons-vue';
import { translateMangaPage, getTranslatorConfigs } from '@/api/translator';
import type { TranslationScript, APIConfig } from '@/types/translator';
import { ElMessage } from 'element-plus';

// Environment
const { isPyWebView } = useEnvironment();

// Store and Router
const store = useViewerStore();
const mangaStore = useMangaStore();
const settingsStore = useSettingsStore();
const route = useRoute();
const router = useRouter();

// DOM Refs
const viewerContentRef = ref<HTMLElement | null>(null);
const pageInputRef = ref<HTMLInputElement | null>(null);
const autoplayPopoverRef = ref<any>(null);

// Local State for Seamless Page Turn
const displayedImages = ref<MangaImage[]>([]);
const isLoadingNextPage = ref(false);

// Local State
const showPageInput = ref(false);
const pageInputText = ref('1');
const isDragging = ref(false);
let popoverCloseTimer: number | null = null;

// Translation State
const isTranslating = ref(false);
const translationScript = ref<TranslationScript | null>(null);
const translationError = ref<string | null>(null);
const translatorConfigs = ref<APIConfig[]>([]);


// ==================== 智能布局引擎 (单向数据流) ====================

const pageTurnDirection = ref<'forward' | 'backward' | null>(null);
const isInitialBackwardTurn = ref(false); // 一次性令牌，用于防止修正逻辑无限循环

// 1. 决策结果状态
const finalDisplayMode = ref<'single' | 'double'>('single');

// 2. 渲染层 (聪明厨师)
const imagesToActuallyRender = computed(() => {
  if (!displayedImages.value || displayedImages.value.length === 0) {
    return [];
  }
  // 根据决策，从“食材库”拿出正确的份量
  if (finalDisplayMode.value === 'single') {
    return displayedImages.value.slice(0, 1);
  }
  return displayedImages.value;
});

// 3. 计算层
const { width: containerWidth, height: containerHeight } = useElementSize(viewerContentRef);

watch(
  [() => store.currentImages, containerWidth, containerHeight, () => store.isTranslationMode],
  ([images, width, height, isTranslation]) => {
    if (!images || images.length === 0 || width === 0 || height === 0) {
      finalDisplayMode.value = 'single';
      return;
    }

    let decision: 'single' | 'double' = 'single';
    let reason = "默认或特殊情况";

    // 规则1：翻译模式强制单页
    if (isTranslation) {
      reason = "翻译模式";
      decision = 'single';
    }
    // 规则2：只有一张图，强制单页
    else if (images.length === 1) {
      reason = "只有一张图片";
      decision = 'single';
    }
    // 规则3：核心计算逻辑
    else {
        const image1 = images[0];
        const image2 = images[1];
        const doublePageScaledWidth1 = (image1.width / image1.height) * height;
        const doublePageScaledWidth2 = (image2.width / image2.height) * height;
        const totalDoublePageScaledWidth = doublePageScaledWidth1 + doublePageScaledWidth2;

        if (totalDoublePageScaledWidth > width) {
            decision = 'single';
            reason = `双页总宽(${totalDoublePageScaledWidth.toFixed(0)}) > 容器宽度(${width.toFixed(0)})`;
        } else {
            decision = 'double';
            reason = `双页总宽(${totalDoublePageScaledWidth.toFixed(0)}) <= 容器宽度(${width.toFixed(0)})`;
        }
    }
    
    // 唯一的副作用：更新决策状态
    finalDisplayMode.value = decision;
  },
  { deep: true }
);


// ==================== Seamless Page Turn Logic ====================

watch(() => store.currentImages, (newImages) => {
  if (newImages && newImages.length > 0) {
    preloadAndSwitchImages(newImages);
  } else {
    displayedImages.value = [];
  }

  // 如果在翻译模式下，图片更新时自动重新翻译
  if (store.isTranslationMode && newImages && newImages.length > 0) {
    runTranslation();
  }
}, { deep: true });

function preloadAndSwitchImages(newImages: MangaImage[]) {
  isLoadingNextPage.value = true;
  const imageUrls = newImages.map(img => img.src);
  
  const promises = imageUrls.map(src => {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = resolve;
      img.onerror = reject;
      img.src = src;
    });
  });

  Promise.all(promises)
    .then(() => {
      displayedImages.value = newImages;
    })
    .catch((error) => {
      console.error("图片预加载失败:", error);
      // 即使失败，也切换过去，避免卡住
      displayedImages.value = newImages;
    })
    .finally(() => {
      isLoadingNextPage.value = false;
    });
}


// ==================== Lifecycle Hooks ====================

onMounted(async () => {
  // Initialize displayed images
  if (store.currentImages.length > 0) {
    displayedImages.value = store.currentImages;
  }
  document.addEventListener('keydown', handleKeydown);
  document.addEventListener('wheel', handleWheel, { passive: false });

  // Fetch translator configs for later use
  try {
    translatorConfigs.value = await getTranslatorConfigs();
  } catch (error) {
    console.error("Failed to fetch translator configs:", error);
    // Don't block the page, but translation might fail
  }
});

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown);
  document.removeEventListener('wheel', handleWheel);
  stopAutoPaging(); // 确保组件销毁时停止计时器
});

// ==================== Watchers ====================

watch(() => store.currentPage, (newPage) => {
    pageInputText.value = (newPage + 1).toString();
});

// 核心翻页状态机：监听图片数据的变化，以驱动翻页的完成和修正
watch(() => store.currentImages, () => {
    // 检查是否是“首次向后翻页”这个特殊情况，并且令牌存在
    if (pageTurnDirection.value === 'backward' && isInitialBackwardTurn.value) {
        // 消耗令牌，确保此修正逻辑在单次“上一页”操作中只执行一次
        isInitialBackwardTurn.value = false;

        if (finalDisplayMode.value === 'single' && store.currentPage > 0) {
            // 需要修正，我们发起二次跳转。
            // 因为令牌已被消耗，这次跳转触发的 watch 将不会再次进入此逻辑。
            store.goToPage(store.currentPage + 1);
            return; // 中断当前流程，等待修正跳转完成
        }
    }

    // 在以下情况下，一次完整的翻页动作结束，可以安全地重置主标志位：
    // 1. 向前翻页。
    // 2. 首次向后翻页但无需修正。
    // 3. 修正跳转完成后的那一次。
    pageTurnDirection.value = null;
}, { deep: true });


watch(showPageInput, (isShown) => {
    if (isShown) {
        nextTick(() => {
            pageInputRef.value?.focus();
            pageInputRef.value?.select();
        });
    }
});

// ==================== Event Handlers ====================

function handleKeydown(event: KeyboardEvent) {
  if (showPageInput.value) return;
  switch (event.key) {
    case 'ArrowLeft':
    case 'a':
      goToPreviousPage();
      break;
    case 'ArrowRight':
    case 'd':
      goToNextPage();
      break;
  }
}

function handleWheel(event: WheelEvent) {
  event.preventDefault();
  if (showPageInput.value) return;

  const threshold = 1;
  if (event.deltaY > threshold) {
    goToNextPage();
  } else if (event.deltaY < -threshold) {
    goToPreviousPage();
  }
}

function goBack() {
    if (store.mangaInfo.filePath) {
        const mangaToReturnTo = mangaStore.mangaList.find(
            m => m.file_path === store.mangaInfo.filePath
        );
        if (mangaToReturnTo) {
            mangaStore.setScrollToManga(mangaToReturnTo);
        }
    }
    router.push('/browser');
}

function switchToStripView() {
    localStorage.setItem('viewer_default_mode', 'strip');
    router.push({ query: { ...route.query, mode: 'strip' } });
}

function onImageClick(event: MouseEvent) {
  if (store.isTranslationMode) return; // 翻译模式下禁用点击翻页

  const target = event.target as HTMLElement;
  // 如果点击的是容器而不是图片，则使用容器的尺寸
  const rect = target.classList.contains('manga-image')
    ? target.getBoundingClientRect()
    : (event.currentTarget as HTMLElement).getBoundingClientRect();
  
  const clickX = event.clientX - rect.left;

  if (clickX < rect.width / 3) {
    goToPreviousPage();
  } else if (clickX > rect.width * 2 / 3) {
    goToNextPage();
  }
}

function onTitleClick() {
  if (isPyWebView.value && window.pywebview?.api.open_in_explorer && store.mangaInfo.filePath) {
    window.pywebview.api.open_in_explorer(store.mangaInfo.filePath);
  }
}

async function goToPreviousPage() {
  if (!store.canPrevious) return;
  if (pageTurnDirection.value) return;

  pageTurnDirection.value = 'backward';
  isInitialBackwardTurn.value = true; // 举起一次性令牌
  const targetPage = Math.max(0, store.currentPage - 2);
  store.goToPage(targetPage);
}


function goToNextPage() {
  if (!store.canNext) return;
  if (pageTurnDirection.value) return;

  pageTurnDirection.value = 'forward';
  isInitialBackwardTurn.value = false; // 确保向前翻页时，令牌是放下的
  const step = finalDisplayMode.value === 'double' && imagesToActuallyRender.value.length > 1 ? 2 : 1;
  const newPage = store.currentPage + step;
  store.goToPage(newPage);
}

function onPageInputEnter() {
    const newPage = parseInt(pageInputText.value, 10);
    if (!isNaN(newPage) && newPage > 0 && newPage <= store.mangaInfo.totalPages) {
        store.goToPage(newPage - 1);
    }
    showPageInput.value = false;
}

function onProgressMouseDown(event: MouseEvent) {
    isDragging.value = true;
    const container = event.currentTarget as HTMLElement;
    updatePageFromProgress(event, container);

    const onMouseMove = (moveEvent: MouseEvent) => {
        if (isDragging.value) {
            updatePageFromProgress(moveEvent, container);
        }
    };

    const onMouseUp = () => {
        isDragging.value = false;
        window.removeEventListener('mousemove', onMouseMove);
        window.removeEventListener('mouseup', onMouseUp);
        store.goToPage(store.currentPage);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
}

function updatePageFromProgress(event: MouseEvent, container: HTMLElement) {
    const track = container.querySelector('.progress-bar-track') as HTMLElement;
    if (!track) return;

    const rect = track.getBoundingClientRect();
    const clickY = event.clientY - rect.top;
    const percentage = Math.max(0, Math.min(1, clickY / rect.height));
    
    if (store.mangaInfo.totalPages > 0) {
        const targetPage = Math.floor(percentage * (store.mangaInfo.totalPages -1));
        store.currentPage = targetPage;
    }
}

// ==================== Autoplay Logic (Component-Managed) ====================

const autoPagingTimerId = ref<number | null>(null);
// 创建一个本地的 ref 来同步 slider，避免直接修改 store state 导致问题
const autoPagingIntervalForSlider = ref(store.autoPagingInterval);

function startAutoPaging() {
  if (autoPagingTimerId.value) return;
  autoPagingTimerId.value = window.setInterval(() => {
    if (store.canNext) {
      goToNextPage();
    } else {
      stopAutoPaging();
    }
  }, store.autoPagingInterval * 1000);
}

function stopAutoPaging() {
  if (autoPagingTimerId.value) {
    clearInterval(autoPagingTimerId.value);
    autoPagingTimerId.value = null;
  }
}

function restartAutoPagingTimer() {
  stopAutoPaging();
  if (store.isAutoPaging) {
    startAutoPaging();
  }
}

function toggleAutoPaging() {
  // 调用 store action 来改变全局状态
  store.toggleAutoPaging();
}

function setAutoPagingInterval(value: number | number[]) {
    const interval = Array.isArray(value) ? value[0] : value;
    autoPagingIntervalForSlider.value = interval;
    store.setAutoPagingInterval(interval);
}

// 监听来自 store 的状态变化，以驱动组件内的行为
watch(() => store.isAutoPaging, (isPaging) => {
  if (isPaging) {
    restartAutoPagingTimer();
  } else {
    stopAutoPaging();
  }
});

// 监听来自 store 的间隔变化
watch(() => store.autoPagingInterval, (newInterval) => {
    autoPagingIntervalForSlider.value = newInterval;
    restartAutoPagingTimer();
});


// --- Autoplay Popover Timer Logic ---
function startPopoverCloseTimer() {
  clearPopoverCloseTimer();
  popoverCloseTimer = window.setTimeout(() => {
    if (autoplayPopoverRef.value) {
      autoplayPopoverRef.value.hide();
    }
  }, 1000);
}

function clearPopoverCloseTimer() {
  if (popoverCloseTimer) {
    clearTimeout(popoverCloseTimer);
    popoverCloseTimer = null;
  }
}

// ==================== Translation Logic ====================

const toggleTranslation = () => {
  store.toggleTranslationMode();
};

// 监听翻译模式的开启，首次开启时运行翻译
watch(() => store.isTranslationMode, (isModeOn) => {
  if (isModeOn && !translationScript.value) {
    runTranslation();
  }
});

async function runTranslation() {
  if (store.currentImages.length === 0) return;

  isTranslating.value = true;
  translationError.value = null;
  translationScript.value = null;

  try {
    // 假设我们总是翻译当前页的第一张图片
    const imageToTranslate = store.currentImages[0];
    const imageData = await imageToBlob(imageToTranslate.src);

    // 确定要使用的配置名称
    if (translatorConfigs.value.length === 0) {
      throw new Error("未找到任何 AI 翻译器配置。请先在设置页面添加一个。");
    }
    const configName = translatorConfigs.value[0].name;

    // 从图片对象本身获取页码，确保数据绝对同步
    const pageIndexToTranslate = imageToTranslate.pageIndex;

    const results = await translateMangaPage({
      manga_path: store.mangaInfo.filePath,
      page_index: pageIndexToTranslate + 1, // 前端页码从0开始，后端从1开始
      image_data: await blobToBase64(imageData),
      config_name: configName,
      // agent_name 已在后端固定，此处不再需要传递
    });

    if (results && results[0] && results[0].status === 'success') {
      translationScript.value = results[0].translation_script || { script: [] };
    } else {
      throw new Error(results[0]?.error_message || '翻译失败');
    }
  } catch (error: any) {
    const errorMessage = error.message || '翻译时发生未知错误';
    translationError.value = errorMessage;
    ElMessage.error(errorMessage);
  } finally {
    isTranslating.value = false;
  }
}

// --- Helper functions for image data ---
async function imageToBlob(src: string): Promise<Blob> {
  const response = await fetch(src);
  return response.blob();
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve((reader.result as string).split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}
</script>

<style>
/* Global styles for viewer components like popovers */
@import '@/assets/styles/viewer.css';
</style>

<style scoped>
/* =================================
   Main Container & Layout
   ================================= */
.paginated-view-container {
  display: flex;
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: #1a1a1a;
  color: #e0e0e0;
  z-index: 1000; /* Ensure it covers the main app */
}
.left-sidebar {
  width: 80px;
  flex-shrink: 0;
  background: #2b2b2b;
  border-right: 1px solid #424242;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 0;
}
.page-navigation {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}
.bottom-toolbar {
  flex-shrink: 0;
  border-top: 1px solid #424242;
  padding-top: 8px;
  width: 100%;
}

/* =================================
   Autoplay Popover
   ================================= */
.autoplay-indicator-text {
  font-family: Arial, Helvetica, sans-serif; /* Use a standard, clear font */
  font-size: 18px;
  font-weight: 500;
}
.autoplay-popover-content {
  display: flex;
  align-items: center;
  gap: 12px;
}
.popover-play-btn {
  flex-shrink: 0; /* Prevent button from shrinking */
  margin: 0;
}
.popover-slider {
  flex-grow: 1; /* Allow slider to take remaining space */
}
.autoplay-popover-value {
  font-size: 14px;
  color: #ccc;
  text-align: right;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0; /* Prevent this element from shrinking */
  padding-left: 4px; /* Add a small gap from the slider */
}

/* =================================
   Simplified Viewer Button
   ================================= */
.viewer-btn {
  font-family: 'Material Symbols Rounded', sans-serif;
  font-size: 28px;
  width: 56px;
  height: 56px;
  margin: 4px 0;
  border-radius: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s ease, color 0.2s ease;
  color: #e0e0e0;
}
.viewer-btn:hover {
  background-color: #3c3c3c;
}
.viewer-btn.is-active {
  background-color: #007acc;
  color: white;
}
.viewer-btn.is-disabled {
  color: #6a6a6a;
  cursor: not-allowed;
  background-color: transparent;
}

/* =================================
   Misc Sidebar Elements
   ================================= */
.manga-title-section {
  width: 100%;
  height: 180px; /* Increased height for better spacing */
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  overflow: hidden; /* Hide overflow */
  transition: background-color 0.2s ease;
}

.manga-title-section.is-clickable {
  cursor: pointer;
}

.manga-title-section.is-clickable:hover {
  background-color: rgba(255, 255, 255, 0.05);
}

.manga-title-vertical {
  color: #aaa;
  font-size: 14px;
  font-weight: 500;
  padding: 0 8px;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3; /* Limit to 3 lines */
  line-clamp: 3; /* Standard property for compatibility */
  -webkit-box-orient: vertical;
  white-space: normal;
}
.page-info {
  margin: 16px 0;
  font-size: 16px;
  color: #aaa;
  cursor: pointer;
  text-align: center;
}
.page-divider {
  margin: 0 2px;
}
.page-input {
  width: 60px;
  text-align: center;
}
.progress-bar-container {
  flex-grow: 1;
  width: 100%;
  position: relative;
  cursor: ns-resize;
  display: flex;
  justify-content: center;
  min-height: 100px;
}
.progress-bar-track {
  position: relative;
  width: 4px;
  height: 100%;
  background-color: #444;
  border-radius: 2px;
}
.progress-bar-thumb {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  width: 16px;
  height: 16px;
  background-color: #007acc;
  border-radius: 50%;
  border: 2px solid #fff;
  z-index: 10;
}

/* =================================
   Translation Sidebar
   ================================= */
.translation-sidebar {
  width: 320px;
  flex-shrink: 0;
  background: #242424;
  border-left: 1px solid #424242;
  display: flex;
  flex-direction: column;
  transition: margin-right 0.3s ease;
  margin-right: -320px;
  position: fixed;
  right: 0;
  top: 0;
  height: 100%;
  z-index: 1001;
}
.translation-sidebar.is-visible {
  margin-right: 0;
}
.translation-header {
  padding: 16px;
  border-bottom: 1px solid #424242;
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.translation-header h3 {
  margin: 0;
  font-size: 18px;
}
.translation-content {
  padding: 16px;
  overflow-y: auto;
  flex-grow: 1;
}
.dialogue-line {
  margin-bottom: 12px;
  padding-left: 12px;
  border-left: 3px solid #4a4a4a; /* 默认边框颜色 */
  background: transparent; /* 移除背景色 */
}

/* 为不同发言人设置不同颜色 */
.dialogue-line[data-speaker-id="1"] { border-left-color: #42a5f5; } /* 浅蓝 */
.dialogue-line[data-speaker-id="2"] { border-left-color: #66bb6a; } /* 浅绿 */
.dialogue-line[data-speaker-id="3"] { border-left-color: #ffee58; } /* 黄色 */
.dialogue-line[data-speaker-id="4"] { border-left-color: #ef5350; } /* 红色 */
.dialogue-line[data-speaker-id="5"] { border-left-color: #ab47bc; } /* 紫色 */
/* 可以根据需要添加更多颜色 */

.translated-text {
  font-size: 15px; /* 稍微减小字体 */
  color: #e0e0e0;
  line-height: 1.5;
  margin: 0;
}
.original-text {
  font-size: 11px; /* 显著减小字体 */
  color: #757575; /* 颜色更暗 */
  line-height: 1.4;
  margin: 2px 0 0 0; /* 减小与译文的间距 */
  padding: 0;
  border: none; /* 移除分隔线 */
}
</style>
