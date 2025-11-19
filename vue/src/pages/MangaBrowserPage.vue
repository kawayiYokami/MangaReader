<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted, onBeforeUpdate } from 'vue'
import MangaCard from '../components/widgets/MangaCard.vue'
import { useMangaStore } from '@/store/manga'
import { storeToRefs } from 'pinia'
import type { Manga } from '@/api/manga'
import { useEnvironment } from '@/composables/useEnvironment'

const { isPyWebView } = useEnvironment();
const mangaStore = useMangaStore()
const {
  mangaList,
  isLoading,
  isLoadingMore,
  error,
  hasMore,
  tagsByCategory,
  selectedTags,
  searchQuery,
  sort,
  mangaToScrollTo,
} = storeToRefs(mangaStore)

// --- Infinite Scroll ---
const mangaCardRefs = ref<InstanceType<typeof MangaCard>[]>([])
const loaderRef = ref<HTMLElement | null>(null);
let observer: IntersectionObserver | null = null;

const loadMore = () => {
  mangaStore.fetchMangaPage({ mode: 'append' });
};

onMounted(() => {
  // Initial data fetch
  if (mangaList.value.length === 0) {
    mangaStore.fetchInitialData();
  }

  // Setup observer
  observer = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting && hasMore.value) {
        loadMore();
      }
    },
    { rootMargin: '200px' }
  );

  if (loaderRef.value) {
    observer.observe(loaderRef.value);
  }
});

onUnmounted(() => {
  if (observer) {
    observer.disconnect();
  }
});

onBeforeUpdate(() => {
  mangaCardRefs.value = [];
});

// When the list is completely replaced (e.g., after sorting/filtering),
// we need to re-attach the observer to the new loader element.
watch(mangaList, () => {
  nextTick(() => {
    if (observer && loaderRef.value) {
      observer.disconnect();
      observer.observe(loaderRef.value);
    }
  });
});

// Watch for scroll requests
watch(mangaToScrollTo, (targetManga) => {
  if (!targetManga) return;

  const scrollToTarget = () => {
    const cardComponent = mangaCardRefs.value.find(
      (comp) => comp && comp.manga.file_path === targetManga.file_path
    );
    if (cardComponent && cardComponent.$el) {
      cardComponent.$el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    mangaStore.setScrollToManga(null);
  };

  // With backend pagination, we can only scroll if the item is already in the list.
  const isTargetVisible = mangaList.value.some((m: Manga) => m.file_path === targetManga.file_path);

  if (isTargetVisible) {
    nextTick(scrollToTarget);
  } else {
    // If not visible, we can't jump to a page. We just clear the state.
    // A more advanced implementation could try to calculate and fetch the target page.
    mangaStore.setScrollToManga(null);
  }
}, { immediate: true });


// --- UI state & Event Handlers ---
const isFilterDrawerVisible = ref(false)
const activeAccordion = ref<string | null>(null)

function onTagClick(tag: string, mangaContext?: Manga) {
  const isDeselecting = selectedTags.value.includes(tag);
  const isLastTag = selectedTags.value.length === 1;

  if (isDeselecting && isLastTag && mangaContext) {
    mangaStore.setScrollToManga(mangaContext);
  }

  mangaStore.toggleTag(tag);
}

function toggleAccordion(category: string) {
    activeAccordion.value = activeAccordion.value === category ? null : category
}

function selectDirectory() {
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.trigger_select_directory();
  } else {
    console.error('PyWebView API is not available.');
  }
}
</script>

<template>
  <div class="manga-browser">
    <!-- Search and Filter Bar -->
    <div class="manga-filters" style="margin-bottom: 20px;">
      <div class="filter-header">
        <el-input
          :model-value="searchQuery"
          placeholder="搜索漫画标题..."
          prefix-icon="Search"
          clearable
          style="flex: 1;"
          @update:model-value="mangaStore.setSearchQuery"
        />
        <el-tooltip content="过滤器" placement="bottom">
          <el-button :class="{ 'is-active': selectedTags.length > 0 }" text @click="isFilterDrawerVisible = true">
            <span class="material-symbols-rounded">filter_list</span>
          </el-button>
        </el-tooltip>

        <el-tooltip :content="sort === 'random' ? '当前为随机排序' : '当前为默认排序'" placement="bottom">
            <el-button text @click="mangaStore.setSort(sort !== 'random' ? 'random' : 'last_modified DESC')">
                <span class="material-symbols-rounded">{{ sort === 'random' ? 'shuffle' : 'sort' }}</span>
            </el-button>
        </el-tooltip>

        <!-- PyWebView 专属按钮 -->
        <el-tooltip v-if="isPyWebView" content="选择目录" placement="bottom">
            <el-button text @click="selectDirectory">
                <span class="material-symbols-rounded">folder_open</span>
            </el-button>
        </el-tooltip>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="loading-container">
      <p>正在加载漫画列表...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-container">
      <p>加载失败: {{ error }}</p>
    </div>

    <!-- Manga Grid & Loader Container -->
    <div v-else-if="mangaList.length > 0">
      <div class="manga-grid">
        <MangaCard
          v-for="manga in mangaList"
          :key="manga.file_path"
          :ref="(el: any) => { if (el) mangaCardRefs.push(el) }"
          :manga="manga"
          @tag-click="(tag) => onTagClick(tag, manga)"
        />
      </div>
      <!-- Infinite Scroll Loader -->
      <div ref="loaderRef" class="loader-trigger">
          <p v-if="isLoadingMore">正在加载更多...</p>
      </div>
    </div>

    <!-- Empty State (No match or empty library) -->
    <div v-else>
      <el-empty description="没有找到匹配的漫画"></el-empty>
    </div>

    <!-- Filter Drawer -->
    <el-drawer v-model="isFilterDrawerVisible" title="标签筛选" direction="rtl" size="360px">
        <div class="filter-drawer-content">
            <div v-if="Object.keys(tagsByCategory).length > 0" class="accordion-filter">
                <div v-for="(tags, category) in tagsByCategory" :key="category" class="accordion-item">
                    <div class="accordion-header" @click="toggleAccordion(String(category))">
                        <span class="header-title">{{ category }} ({{ tags.length }})</span>
                        <span class="material-symbols-rounded" :class="{ 'is-active': activeAccordion === String(category) }">
                            expand_more
                        </span>
                    </div>
                    <transition name="accordion">
                      <div v-show="activeAccordion === String(category)" class="accordion-content">
                          <div class="tag-list">
                              <span
v-for="tag in tags"
                                    :key="tag.full"
                                    class="tag"
                                    :class="{ 'is-active': selectedTags.includes(tag.full) }"
                                    @click="onTagClick(tag.full)"
                                    v-text="tag.display">
                              </span>
                          </div>
                      </div>
                    </transition>
                </div>
            </div>
            <div v-else class="empty-state-in-drawer">
                <el-empty description="没有可用的标签"></el-empty>
            </div>
        </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.filter-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.loader-trigger {
  height: 50px;
}

.accordion-header .material-symbols-rounded {
  transition: transform 0.3s ease;
}
.accordion-header .material-symbols-rounded.is-active {
  transform: rotate(180deg);
}

.accordion-enter-active,
.accordion-leave-active {
  transition: all 0.3s ease;
  max-height: 500px; /* Adjust as needed */
  overflow: hidden;
}
.accordion-enter-from,
.accordion-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>
