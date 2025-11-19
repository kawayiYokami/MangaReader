<template>
  <div ref="scrollContainerRef" class="strip-view-container" @scroll="handleScroll">
    <div v-if="store.isLoading" class="loading-spinner">
      <el-icon class="is-loading" :size="50"><Loading /></el-icon>
    </div>
    <div v-else-if="store.error" class="error-message">
      {{ store.error }}
    </div>
    <div v-else class="image-list-wrapper">
      <div class="image-list" :style="{ maxWidth: `${imageListWidth}px` }">
        <div
          v-for="page in loadedPages"
          :key="page.pageIndex"
          class="manga-page"
          :data-page-index="page.pageIndex"
          :style="{ minHeight: page.isLoaded ? 'auto' : `${page.estimatedHeight}px` }"
        >
          <img
            v-if="page.src"
            :src="page.src"
            :alt="`第 ${page.pageIndex + 1} 页`"
            class="manga-image"
            loading="lazy"
            decoding="async"
          />
        </div>
        <div class="width-resizer-handle" @mousedown="onResizeMouseDown"></div>
      </div>
    </div>
    
    <!-- Floating Header -->
    <div class="floating-header" :class="{ visible: isHeaderVisible }">
      <div class="viewer-btn" title="返回浏览器" @click="goBack">arrow_back</div>
      <div class="manga-title">{{ store.mangaInfo.title }}</div>
      <div class="viewer-btn" title="切换到分页模式" @click="switchToPaginatedView">view_carousel</div>
    </div>

    <!-- Fast Scrubber -->
    <div 
      class="fast-scrubber-container" 
      :class="{ visible: isScrubberVisible, 'is-dragging': isDraggingScrubber }"
      @mousedown.stop="onScrubberPress"
      @touchstart.stop="onScrubberPress"
    >
      <div class="fast-scrubber-handle" :style="{ top: `${scrubberHandleTop}%` }">
        <span class="page-indicator">{{ currentPageForScrubber }} / {{ store.mangaInfo.totalPages }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useViewerStore } from '@/store/viewer';
import { useMangaStore } from '@/store/manga';
import { Loading } from '@element-plus/icons-vue';

interface LoadedPage {
  src: string | null;
  pageIndex: number;
  isLoaded: boolean;
  isLoading: boolean;
  estimatedHeight: number;
}

const store = useViewerStore();
const mangaStore = useMangaStore();
const route = useRoute();
const router = useRouter();

// --- DOM Refs ---
const scrollContainerRef = ref<HTMLElement | null>(null);

// --- State ---
const loadedPages = ref<LoadedPage[]>([]);
const isHeaderVisible = ref(true);
const isScrubberVisible = ref(false);
const isDraggingScrubber = ref(false);
const scrubberHandleTop = ref(0);
const currentPageForScrubber = ref(1);

// --- Width Resizer State ---
const imageListWidth = ref(800); // Default width
const isResizing = ref(false);
let initialMouseX = 0;
let initialWidth = 0;

let hideHeaderTimeout: number | null = null;
let hideScrubberTimeout: number | null = null;
let observer: IntersectionObserver | null = null;
let lastScrollTop = 0;

// --- Lifecycle ---
onMounted(async () => {
  // Load saved width from localStorage
  const savedWidth = localStorage.getItem('stripViewWidth');
  if (savedWidth) {
    imageListWidth.value = parseInt(savedWidth, 10);
  }

  await store.initializeViewer(route.query.path as string, 0);
  
  const screenWidth = window.innerWidth;
  const estimatedAspectRatio = 1.414;
  const estimatedHeight = screenWidth * estimatedAspectRatio;

  loadedPages.value = Array.from({ length: store.mangaInfo.totalPages }, (_, i) => ({
    src: null,
    pageIndex: i,
    isLoaded: false,
    isLoading: false,
    estimatedHeight: estimatedHeight,
  }));

  nextTick(() => {
    setupIntersectionObserver();
  });
});

onUnmounted(() => {
  if (observer) observer.disconnect();
  // Clean up global listeners to prevent memory leaks
  window.removeEventListener('mousemove', onResizeMouseMove);
  window.removeEventListener('mouseup', onResizeMouseUp);
});

// --- Intersection Observer ---
function setupIntersectionObserver() {
  const options = {
    root: scrollContainerRef.value,
    rootMargin: '500px 0px',
    threshold: 0.01,
  };

  observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      const pageIndex = parseInt((entry.target as HTMLElement).dataset.pageIndex || '0', 10);
      if (entry.isIntersecting) {
        loadPageIfNeeded(pageIndex);
        currentPageForScrubber.value = pageIndex + 1;
      }
    });
  }, options);

  const pageElements = scrollContainerRef.value?.querySelectorAll('.manga-page');
  if (pageElements) {
    pageElements.forEach(el => observer!.observe(el));
  }
}

async function loadPageIfNeeded(pageIndex: number) {
  if (pageIndex < 0 || pageIndex >= loadedPages.value.length) return;
  const page = loadedPages.value[pageIndex];
  if (page.isLoaded || page.isLoading) return;

  page.isLoading = true;
  try {
    const images = await store.loadPageImages(pageIndex, 'single');
    if (images && images.length > 0) {
      page.src = images[0].src;
      page.isLoaded = true;
    }
  } catch (error) {
    console.error(`Failed to load page ${pageIndex + 1}`, error);
  } finally {
    page.isLoading = false;
  }
}

// --- UI Logic ---
function handleScroll() {
  const container = scrollContainerRef.value;
  if (!container) return;

  const scrollTop = container.scrollTop;
  if (scrollTop > lastScrollTop && scrollTop > 100) {
    isHeaderVisible.value = false;
  } else {
    isHeaderVisible.value = true;
  }
  lastScrollTop = scrollTop <= 0 ? 0 : scrollTop;

  if (isDraggingScrubber.value) return;
  
  showScrubber();
  const { scrollHeight, clientHeight } = container;
  const scrollableHeight = scrollHeight - clientHeight;
  const scrollPercentage = scrollableHeight > 0 ? (scrollTop / scrollableHeight) * 100 : 0;
  scrubberHandleTop.value = Math.min(Math.max(scrollPercentage, 0), 100);
}

function showScrubber() {
    isScrubberVisible.value = true;
    if (hideScrubberTimeout) clearTimeout(hideScrubberTimeout);
    hideScrubberTimeout = window.setTimeout(() => {
        if (!isDraggingScrubber.value) {
            isScrubberVisible.value = false;
        }
    }, 1500);
}

// --- Width Resizer Logic ---
function onResizeMouseDown(event: MouseEvent) {
  event.preventDefault();
  isResizing.value = true;
  initialMouseX = event.clientX;
  initialWidth = imageListWidth.value;
  window.addEventListener('mousemove', onResizeMouseMove);
  window.addEventListener('mouseup', onResizeMouseUp);
}

function onResizeMouseMove(event: MouseEvent) {
  if (!isResizing.value) return;
  const deltaX = event.clientX - initialMouseX;
  const newWidth = initialWidth + deltaX;
  // Set min and max width constraints
  imageListWidth.value = Math.max(400, Math.min(newWidth, window.innerWidth - 100));
}

function onResizeMouseUp() {
  if (!isResizing.value) return;
  isResizing.value = false;
  window.removeEventListener('mousemove', onResizeMouseMove);
  window.removeEventListener('mouseup', onResizeMouseUp);
  // Persist the new width
  localStorage.setItem('stripViewWidth', imageListWidth.value.toString());
}


// --- Scrubber Drag Logic ---
function onScrubberPress(e: MouseEvent | TouchEvent) {
  isDraggingScrubber.value = true;
  document.body.style.cursor = 'grabbing';
  
  window.addEventListener('mousemove', handleDragMove);
  window.addEventListener('mouseup', handleDragEnd);
  window.addEventListener('touchmove', handleDragMove, { passive: false });
  window.addEventListener('touchend', handleDragEnd);
  
  e.preventDefault();
  handleDragMove(e);
}

function handleDragMove(e: MouseEvent | TouchEvent) {
  if (!isDraggingScrubber.value || !scrollContainerRef.value) return;
  e.preventDefault();

  const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
  const containerRect = scrollContainerRef.value.getBoundingClientRect();
  
  let percentage = ((clientY - containerRect.top) / containerRect.height) * 100;
  percentage = Math.min(Math.max(percentage, 0), 100);
  
  scrubberHandleTop.value = percentage;
  
  const targetScrollTop = (percentage / 100) * (scrollContainerRef.value.scrollHeight - scrollContainerRef.value.clientHeight);
  scrollContainerRef.value.scrollTop = targetScrollTop;

  const estimatedPage = Math.floor((percentage / 100) * store.mangaInfo.totalPages);
  currentPageForScrubber.value = Math.min(store.mangaInfo.totalPages, Math.max(1, estimatedPage));
}

function handleDragEnd() {
  isDraggingScrubber.value = false;
  document.body.style.cursor = 'default';
  
  window.removeEventListener('mousemove', handleDragMove);
  window.removeEventListener('mouseup', handleDragEnd);
  window.removeEventListener('touchmove', handleDragMove);
  window.removeEventListener('touchend', handleDragEnd);
  
  showScrubber(); // Reset hide timer
}

// --- Navigation ---
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

function switchToPaginatedView() {
  localStorage.setItem('viewer_default_mode', 'paginated');
  router.push({ query: { ...route.query, mode: 'paginated' } });
}
</script>

<style scoped>
/* =================================
   Material Symbols Font Definition
   ================================= */
.material-symbols-rounded {
  font-family: 'Material Symbols Rounded', sans-serif;
  font-weight: normal;
  font-style: normal;
  font-size: 24px;
  line-height: 1;
  letter-spacing: normal;
  text-transform: none;
  display: inline-block;
  white-space: nowrap;
  word-wrap: normal;
  direction: ltr;
  -webkit-font-feature-settings: 'liga';
  font-feature-settings: 'liga';
  -webkit-font-smoothing: antialiased;
}

.strip-view-container {
  width: 100%;
  height: 100%;
  overflow-y: scroll;
  overflow-x: hidden;
  background-color: #1a1a1a;
  position: relative;
  -webkit-overflow-scrolling: touch;
  /* Hide scrollbar for Firefox */
  scrollbar-width: none;
}

/* Hide scrollbar for Chrome, Safari and Opera */
.strip-view-container::-webkit-scrollbar {
  display: none;
}

.image-list-wrapper {
  display: flex;
  justify-content: center;
}

.image-list {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%; /* Fallback for when maxWidth is not set */
  transition: max-width 0.1s linear;
  position: relative; /* Positioning context for the handle */
}
.manga-page {
  width: 100%;
}
.manga-image {
  width: 100%;
  display: block;
}
.loading-spinner, .error-message {
  color: white;
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 1.5rem;
}

/* =================================
   Width Resizer Handle
   ================================= */
.width-resizer-handle {
  position: absolute;
  right: -10px; /* Position it half outside */
  top: 0;
  bottom: 0;
  width: 20px; /* Wider handle for easier grabbing */
  cursor: col-resize;
  z-index: 200;
}

/* =================================
   Floating Header
   ================================= */
.floating-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px;
  background: #2b2b2b; /* Solid background */
  color: #e0e0e0;
  transition: transform 0.3s ease;
  transform: translateY(-100%);
  z-index: 100;
  border-bottom: 1px solid #424242;
}
.floating-header.visible {
  transform: translateY(0);
}
.manga-title {
  font-size: 1rem;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding: 0 16px;
  flex-grow: 1;
  text-align: center;
}

/* =================================
   Viewer Button (Copied from PaginatedView)
   ================================= */
.viewer-btn {
  font-family: 'Material Symbols Rounded', sans-serif;
  font-size: 28px;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s ease, color 0.2s ease;
  color: #e0e0e0;
  flex-shrink: 0;
}
.viewer-btn:hover {
  background-color: #3c3c3c;
}

/* Fast Scrubber (existing styles) */
.fast-scrubber-container {
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  width: 40px;
  display: flex;
  justify-content: center;
  align-items: center;
  opacity: 0;
  transition: opacity 0.3s ease;
  cursor: grab;
}
.fast-scrubber-container.visible {
  opacity: 1;
}
.fast-scrubber-container:active {
  cursor: grabbing;
}
.fast-scrubber-handle {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  width: 8px;
  height: 40px;
  background-color: rgba(255,255,255,0.5);
  border-radius: 4px;
  transition: background-color 0.2s;
}
.fast-scrubber-container.is-dragging .fast-scrubber-handle {
  background-color: rgba(255,255,255,0.9);
}
.page-indicator {
  position: absolute;
  right: 150%;
  top: 50%;
  transform: translateY(-50%);
  background-color: rgba(0,0,0,0.8);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.9rem;
  white-space: nowrap;
  opacity: 0;
  transition: opacity 0.2s;
}
.fast-scrubber-container.is-dragging .page-indicator {
  opacity: 1;
}
</style>