<template>
  <div class="manga-viewer-container">
    <component :is="activeView" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, defineAsyncComponent } from 'vue';
import { useRoute } from 'vue-router';
import { useViewerStore } from '@/store/viewer';

// Async components for lazy loading views
const PaginatedView = defineAsyncComponent(() => import('./viewer/PaginatedView.vue'));
const StripView = defineAsyncComponent(() => import('./viewer/StripView.vue'));

const route = useRoute();
const store = useViewerStore();

// Determine which view to show based on route query param
const activeView = computed(() => {
  const mode = route.query.mode as string;
  if (mode === 'strip') {
    return StripView;
  }
  // Default to paginated view
  return PaginatedView;
});

onMounted(() => {
  const mangaPath = route.query.path as string;
  const page = parseInt(route.query.page as string || '0', 10);

  if (mangaPath) {
    store.initializeViewer(mangaPath, page);
  }
});

onUnmounted(() => {
  store.destroyViewerSession();
});
</script>

<style scoped>
.manga-viewer-container {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background-color: #000;
}
</style>
