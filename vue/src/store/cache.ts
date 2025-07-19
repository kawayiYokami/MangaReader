import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import * as cacheApi from '@/api/cache'
import type { CacheType, CacheEntry, CacheStat } from '@/api/cache'

export const useCacheStore = defineStore('cache', () => {
  // State
  const cacheTypes = ref<CacheType[]>([])
  const cacheStats = ref<Record<string, CacheStat>>({})
  const selectedCacheType = ref<string | null>(null)
  const entries = ref<CacheEntry[]>([])
  const pagination = reactive({
    currentPage: 1,
    pageSize: 20,
    totalEntries: 0,
  })
  const isLoading = reactive({
    types: false,
    stats: false,
    entries: false,
  })
  const searchQuery = ref('');
  const showOnlySensitive = ref(false);

  // Actions
  async function fetchInitialData() {
    isLoading.types = true;
    isLoading.stats = true;
    try {
      const [types, stats] = await Promise.all([
        cacheApi.getCacheTypes(),
        cacheApi.getCacheStats(),
      ]);
      cacheTypes.value = types;
      cacheStats.value = stats;
      if (types.length > 0) {
        await selectCacheType(types[0].key);
      }
    } catch (error) {
      console.error("Failed to fetch initial cache data:", error);
    } finally {
      isLoading.types = false;
      isLoading.stats = false;
    }
  }

  async function selectCacheType(type: string) {
    selectedCacheType.value = type;
    pagination.currentPage = 1;
    searchQuery.value = '';
    await fetchEntries();
  }

  async function fetchEntries() {
    if (!selectedCacheType.value) return;
    isLoading.entries = true;
    try {
      const response = await cacheApi.getCacheEntries(
        selectedCacheType.value,
        pagination.currentPage,
        pagination.pageSize,
        searchQuery.value,
        showOnlySensitive.value
      );
      entries.value = response.entries;
      pagination.totalEntries = response.total;
    } catch (error) {
      console.error(`Failed to fetch entries for ${selectedCacheType.value}:`, error);
      entries.value = [];
      pagination.totalEntries = 0;
    } finally {
      isLoading.entries = false;
    }
  }
  
  async function clearCache(type: string) {
    await cacheApi.clearCache(type);
    await fetchInitialData(); // Refresh all data
  }

  async function deleteEntry(type: string, key: string) {
    await cacheApi.deleteCacheEntry(type, key);
    await fetchEntries(); // Refresh entries for the current type
  }
  
  function changePage(page: number) {
    pagination.currentPage = page;
    fetchEntries();
  }

  async function addOrUpdateHarmonization(key: string, value: string) {
    await cacheApi.addOrUpdateEntry('harmonization_map', key, value);
    // Refresh entries for the current view
    await fetchEntries();
    // Separately refresh stats without resetting the view
    try {
      cacheStats.value = await cacheApi.getCacheStats();
    } catch (error) {
      console.error("Failed to refresh cache stats after harmonization update:", error);
    }
  }

  async function deleteHarmonization(key: string) {
    await cacheApi.deleteCacheEntry('harmonization_map', key);
    // Refresh entries for the current view
    await fetchEntries();
    // Separately refresh stats without resetting the view
    try {
      cacheStats.value = await cacheApi.getCacheStats();
    } catch (error) {
      console.error("Failed to refresh cache stats after harmonization delete:", error);
    }
  }

  return {
    cacheTypes,
    cacheStats,
    selectedCacheType,
    entries,
    pagination,
    isLoading,
    searchQuery,
    showOnlySensitive,
    fetchInitialData,
    selectCacheType,
    fetchEntries,
    clearCache,
    deleteEntry,
    changePage,
    addOrUpdateHarmonization,
    deleteHarmonization,
  }
})