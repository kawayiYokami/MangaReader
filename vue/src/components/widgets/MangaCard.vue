<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useIntersectionObserver } from '@vueuse/core'
import { storeToRefs } from 'pinia'
import type { Manga } from '@/api/manga'
import { API_BASE_URL } from '@/api/base'
import { thumbnailService } from '@/services/thumbnailService'
import { useMangaStore } from '@/store/manga'

const props = defineProps({
  manga: {
    type: Object as () => Manga,
    required: true
  }
})

const emit = defineEmits(['select', 'tag-click'])
const router = useRouter()
const mangaStore = useMangaStore()
const { selectedTags } = storeToRefs(mangaStore)

const thumbnailUrl = ref<string | null>(null)
const isLoadingThumbnail = ref(false)
const isImageLoaded = ref(false)

// Reset loaded state when manga prop changes
watch(() => props.manga, () => {
  // Revoke the old object URL to prevent memory leaks
  if (thumbnailUrl.value) {
    URL.revokeObjectURL(thumbnailUrl.value);
  }
  thumbnailUrl.value = null;
  isImageLoaded.value = false;
  // The intersection observer will re-trigger fetchThumbnail
});

async function fetchThumbnail() {
  if (thumbnailUrl.value || isLoadingThumbnail.value) return;

  isLoadingThumbnail.value = true;
  try {
    // 1. Check cache first (L1 Memory & L2 IndexedDB)
    const cachedBlob = await thumbnailService.getThumbnail(props.manga.file_path);
    if (cachedBlob) {
      thumbnailUrl.value = URL.createObjectURL(cachedBlob);
      return;
    }

    // 2. If not in cache, fetch from network (L3 HTTP Cache)
    const encodedPath = encodeURIComponent(props.manga.file_path);
    const response = await fetch(`${API_BASE_URL}/api/manga/thumbnail?manga_path=${encodedPath}`);
    
    if (!response.ok) {
      throw new Error(`Failed to fetch thumbnail: ${response.statusText}`);
    }

    const imageBlob = await response.blob();
    
    // Store in L2 cache for future use
    await thumbnailService.setThumbnail(props.manga.file_path, imageBlob);
    
    thumbnailUrl.value = URL.createObjectURL(imageBlob);

  } catch (error) {
    console.error('Error fetching thumbnail for:', props.manga.file_path, error);
    thumbnailUrl.value = null;
  } finally {
    isLoadingThumbnail.value = false;
  }
}

onUnmounted(() => {
  if (thumbnailUrl.value) {
    URL.revokeObjectURL(thumbnailUrl.value);
  }
});

// Tag processing logic, strictly following the legacy implementation.
const getTitleTag = (tags: string[]) => {
  if (!tags || tags.length === 0) return props.manga.title;
  const titleTag = tags.find(tag => tag && tag.startsWith('标题:'));
  if (titleTag) return titleTag.substring(3).trim();
  const workTag = tags.find(tag => tag && tag.startsWith('作品:'));
  if (workTag) return workTag.substring(3).trim();
  return props.manga.title;
}

const getOtherTags = (tags: string[]) => {
  if (!tags || tags.length === 0) return [];
  return tags.filter(tag => tag && !tag.startsWith('标题:'));
}

// Event handlers
const selectManga = () => {
  if (props.manga.file_path) {
    mangaStore.setScrollToManga(props.manga);
    const preferredMode = localStorage.getItem('viewer_default_mode') || 'paginated';
    router.push({
      name: 'viewer',
      query: {
        path: props.manga.file_path,
        mode: preferredMode
      }
    });
  }
}

const onTagClick = (tag: string) => {
  emit('tag-click', tag)
}

// --- Self-managed Lazy Loading ---
const cardRef = ref<HTMLElement | null>(null)
const { stop } = useIntersectionObserver(
  cardRef,
  ([{ isIntersecting }]) => {
    if (isIntersecting) {
      fetchThumbnail()
      stop() // Stop observing once triggered
    }
  },
  { rootMargin: '200px' }
)

defineExpose({
  manga: props.manga
})
</script>

<template>
  <article ref="cardRef" class="manga-card-desktop" @click="selectManga">
    <div class="cover-container">
      <!-- Cover Image -->
      <img
        v-if="thumbnailUrl"
        :src="thumbnailUrl"
        :alt="getTitleTag(manga.tags) || '漫画封面'"
        decoding="async"
        :class="{ 'image-loaded': isImageLoaded }"
        @load="isImageLoaded = true"
      >
      <!-- Loading State -->
      <div v-else-if="isLoadingThumbnail" class="cover-loading">
        <span class="material-symbols-rounded">progress_activity</span>
      </div>
      <!-- Placeholder -->
      <div v-else class="cover-placeholder">
        <span v-if="manga.file_type === 'folder'" class="material-symbols-rounded">folder</span>
        <span v-else-if="manga.file_type === 'zip'" class="material-symbols-rounded">archive</span>
        <span v-else class="material-symbols-rounded">draft</span>
      </div>
      
      <!-- Page Count -->
      <span class="page-count">{{ manga.total_pages }}</span>

      <!-- Title (Inside Cover Container) -->
      <h3 class="manga-title" :title="getTitleTag(manga.tags)">
        {{ getTitleTag(manga.tags) }}
      </h3>
    </div>

    <div class="info-container" v-if="getOtherTags(manga.tags).length > 0">
      <!-- Other Tags (Inside Info Container) -->
      <div class="manga-tags">
        <span
          class="tag"
          v-for="tag in getOtherTags(manga.tags)"
          :key="tag"
          @click.stop="onTagClick(tag)"
          :title="`点击搜索: ${tag}`"
          :class="{ 'is-active': selectedTags.includes(tag) }"
        >
          {{ tag.split(':').pop() }}
        </span>
      </div>
    </div>
  </article>
</template>

<style scoped>
@keyframes card-enter {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.manga-card-desktop {
  animation: card-enter 0.3s ease-out forwards;
  transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
}

/* Styles for thumbnail fade-in animation */
.cover-container img {
  opacity: 0;
  transition: opacity 0.5s ease-in-out;
}

.cover-container img.image-loaded {
  opacity: 1;
}

.manga-card-desktop:hover {
  transform: scale(1.03);
  box-shadow: 0 8px 25px rgba(0,0,0,0.15);
}
</style>