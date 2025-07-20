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
        <div class="viewer-btn" @click="store.previousPage()" :class="{ 'is-disabled': !store.canPrevious }">arrow_upward</div>

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

        <div class="viewer-btn" @click="store.nextPage()" :class="{ 'is-disabled': !store.canNext }">arrow_downward</div>
      </div>

      <div class="bottom-toolbar">
          <div class="viewer-btn" @click="goBack" title="返回浏览器">arrow_back</div>
          <div class="viewer-btn" @click="switchToStripView" title="切换到条漫模式">view_day</div>
          <div class="viewer-btn" :class="{ 'is-active': store.translationEnabled }" @click="store.toggleTranslation()" title="切换翻译">translate</div>
          
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
                @click.stop="store.toggleAutoPaging()"
              >
                {{ store.isAutoPaging ? 'pause' : 'play_arrow' }}
              </div>
              <el-slider
                v-model="store.autoPagingInterval"
                :min="1"
                :max="30"
                :step="1"
                class="popover-slider"
                @input="store.setAutoPagingInterval($event)"
              />
              <div class="autoplay-popover-value">{{ Math.round(store.autoPagingInterval) }}s</div>
            </div>
          </el-popover>
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
      <div v-else-if="displayedImages.length > 0" class="image-container">
        <img
           v-for="img in displayedImages"
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
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useViewerStore, type MangaImage } from '@/store/viewer';
import { useMangaStore } from '@/store/manga';
import { useEnvironment } from '@/composables/useEnvironment';
import { Loading } from '@element-plus/icons-vue';

// Environment
const { isPyWebView } = useEnvironment();

// Store and Router
const store = useViewerStore();
const mangaStore = useMangaStore();
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

// ==================== Seamless Page Turn Logic ====================

watch(() => store.currentImages, (newImages) => {
  if (newImages && newImages.length > 0) {
    preloadAndSwitchImages(newImages);
  } else {
    displayedImages.value = [];
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

onMounted(() => {
  // Initialize displayed images
  if (store.currentImages.length > 0) {
    displayedImages.value = store.currentImages;
  }
  document.addEventListener('keydown', handleKeydown);
  document.addEventListener('wheel', handleWheel, { passive: false });
});

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown);
  document.removeEventListener('wheel', handleWheel);
});

// ==================== Watchers ====================

watch(() => store.currentPage, (newPage) => {
    pageInputText.value = (newPage + 1).toString();
});

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
      store.previousPage();
      break;
    case 'ArrowRight':
    case 'd':
      store.nextPage();
      break;
  }
}

function handleWheel(event: WheelEvent) {
  event.preventDefault();
  if (showPageInput.value) return;

  const threshold = 1;
  if (event.deltaY > threshold) {
    store.nextPage();
  } else if (event.deltaY < -threshold) {
    store.previousPage();
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
    const container = event.currentTarget as HTMLElement | null;
    if (container && event.target instanceof HTMLImageElement) {
        const rect = container.getBoundingClientRect();
        const clickX = event.clientX - rect.left;
        const centerX = rect.width / 2;
        if (clickX < centerX) {
            store.previousPage();
        } else {
            store.nextPage();
        }
    }
}

function onTitleClick() {
  if (isPyWebView.value && window.pywebview?.api.open_in_explorer && store.mangaInfo.filePath) {
    window.pywebview.api.open_in_explorer(store.mangaInfo.filePath);
  }
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
</style>
