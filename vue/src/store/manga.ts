import { defineStore } from 'pinia'
import { getMangaList, getAllTags } from '@/api/manga'
import type { Manga } from '@/api/manga'
import { debounce } from 'lodash-es'

// ==================== TYPE DEFINITIONS ====================
export interface TagInfo {
  full: string;
  display: string;
}

export interface TagsByCategory {
  [category: string]: TagInfo[];
}

export interface MangaState {
  mangaList: Manga[];
  availableTags: string[];
  tagsByCategory: TagsByCategory;
  
  // Filtering and Sorting State
  selectedTags: string[];
  searchQuery: string;
  sort: string;

  // Pagination State
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;

  mangaToScrollTo: Manga | null;
  isLoading: boolean;
  isLoadingMore: boolean;
  error: string | null;
  isWebSocketInitialized: boolean;
}

// ==================== STORE DEFINITION ====================
export const useMangaStore = defineStore('manga', {
  state: (): MangaState => ({
    mangaList: [],
    availableTags: [],
    tagsByCategory: {},
    selectedTags: [],
    searchQuery: '',
    sort: 'last_modified DESC',
    page: 1,
    pageSize: 20,
    totalItems: 0,
    totalPages: 0,
    mangaToScrollTo: null,
    isLoading: false,
    isLoadingMore: false,
    error: null,
    isWebSocketInitialized: false,
  }),

  getters: {
    hasMore(state): boolean {
      return state.page < state.totalPages;
    }
  },

  actions: {
    async fetchInitialData() {
      await this.fetchMangaPage({ mode: 'new' });
      await this.fetchTags();
      
      if (!this.isWebSocketInitialized) {
        this.initializeWebSocket();
      }
    },

    async fetchMangaPage({ mode = 'new' }: { mode: 'new' | 'append' }) {
      if (this.isLoading) return;

      if (mode === 'new') {
        this.page = 1;
        this.isLoading = true;
      } else { // append
        if (!this.hasMore || this.isLoadingMore) return;
        this.page += 1;
        this.isLoadingMore = true;
      }
      
      this.error = null;

      try {
        const response = await getMangaList({
          page: this.page,
          pageSize: this.pageSize,
          sort: this.sort,
          tags: this.selectedTags,
          query: this.searchQuery,
        });
        
        if (mode === 'new') {
          this.mangaList = response.items;
        } else {
          this.mangaList.push(...response.items);
        }
        
        this.totalItems = response.total;
        this.totalPages = response.total_pages;

      } catch (e: any) {
        this.error = e.message || 'An unknown error occurred';
      } finally {
        this.isLoading = false;
        this.isLoadingMore = false;
      }
    },
    
    async fetchTags() {
      try {
        this.availableTags = await getAllTags();
        this.processTagsByCategory();
      } catch (e: any) {
        console.error("Failed to fetch tags:", e.message);
      }
    },

    async applyFilters() {
      await this.fetchMangaPage({ mode: 'new' });
    },

    setSort(sort: string) {
      this.sort = sort;
      this.applyFilters();
    },

    setSearchQuery: debounce(function(this: any, query: string) {
      this.searchQuery = query;
      this.applyFilters();
    }, 300),

    toggleTag(tag: string) {
      const index = this.selectedTags.indexOf(tag);
      if (index > -1) {
        this.selectedTags.splice(index, 1);
      } else {
        this.selectedTags.push(tag);
      }
      this.applyFilters();
    },

    clearFilters() {
      this.selectedTags = [];
      this.searchQuery = '';
      this.applyFilters();
    },

    initializeWebSocket() {
      if (this.isWebSocketInitialized) return;

      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProtocol}//${window.location.hostname}:8100/ws`;

      console.log(`[MangaStore] Initializing WebSocket connection to ${wsUrl}`);
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('[MangaStore] WebSocket connection established.');
        this.isWebSocketInitialized = true;
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('[MangaStore] WebSocket message received:', message);

          if (message.type === 'manga_list_updated') {
            console.log('[MangaStore] Manga list update detected, refreshing data...');
            this.applyFilters(); // Re-fetch current view
          }
        } catch (error) {
          console.error('[MangaStore] Failed to parse WebSocket message:', error);
        }
      };

      ws.onclose = () => {
        console.log('[MangaStore] WebSocket connection closed. Reconnecting in 5 seconds...');
        this.isWebSocketInitialized = false;
        setTimeout(() => this.initializeWebSocket(), 5000);
      };

      ws.onerror = (error) => {
        console.error('[MangaStore] WebSocket error:', error);
        ws.close();
      };
    },
    
    processTagsByCategory() {
      const categories: Record<string, TagInfo[]> = {};
      const prefixes = ['作者:', '作品:', '组:', '平台:', '汉化:', '会场:', '其他:'];

      for (const tag of this.availableTags) {
        if (tag.startsWith('标题:')) continue;

        let category = '其他';
        let displayName = tag;
        
        for (const prefix of prefixes) {
          if (tag.startsWith(prefix)) {
            category = prefix.slice(0, -1);
            displayName = tag.substring(prefix.length);
            break;
          }
        }

        if (!categories[category]) {
          categories[category] = [];
        }
        categories[category].push({ full: tag, display: displayName });
      }

      for (const category in categories) {
        categories[category].sort((a, b) => a.display.localeCompare(b.display, 'zh-CN'));
      }
      
      this.tagsByCategory = categories;
    },

    setScrollToManga(manga: Manga | null) {
      this.mangaToScrollTo = manga;
    }
  }
})