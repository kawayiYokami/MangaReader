import { get, set, del, createStore, clear } from 'idb-keyval';

// --- 内存缓存 (L1 Cache) ---
class LRUCache<K, V> {
  private maxSize: number;
  private cache: Map<K, V>;

  constructor(maxSize: number = 100) {
    this.maxSize = maxSize;
    this.cache = new Map<K, V>();
  }

  get(key: K): V | undefined {
    const item = this.cache.get(key);
    if (item) {
      // 移动到最近使用的位置
      this.cache.delete(key);
      this.cache.set(key, item);
    }
    return item;
  }

  set(key: K, value: V): void {
    if (this.cache.has(key)) {
      this.cache.delete(key);
    } else if (this.cache.size >= this.maxSize) {
      // 移除最久未使用的
      const oldestKey = this.cache.keys().next().value;
      if (oldestKey !== undefined) {
        this.cache.delete(oldestKey);
      }
    }
    this.cache.set(key, value);
  }

  clear(): void {
    this.cache.clear();
  }
}

// --- IndexedDB 缓存 (L2 Cache) ---
const DB_NAME = 'thumbnail-db';
const STORE_NAME = 'thumbnail-store';
const METADATA_KEY = '__metadata__';
const MAX_DB_SIZE_MB = 200;

const customStore = createStore(DB_NAME, STORE_NAME);

interface Metadata {
  [key: string]: {
    size: number;
    lastAccessed: number;
  };
}

class ThumbnailDBService {
  private memoryCache: LRUCache<string, Blob>;

  constructor() {
    this.memoryCache = new LRUCache(100); // L1 缓存最多100个项目
  }

  async getThumbnail(key: string): Promise<Blob | null> {
    // 1. 尝试从内存缓存获取
    const memBlob = this.memoryCache.get(key);
    if (memBlob) {
      this.updateMetadata(key, memBlob.size); // 更新访问时间
      return memBlob;
    }

    // 2. 尝试从 IndexedDB 获取
    const dbBlob = await get<Blob>(key, customStore);
    if (dbBlob) {
      this.memoryCache.set(key, dbBlob); // 存入内存缓存
      this.updateMetadata(key, dbBlob.size); // 更新访问时间
      return dbBlob;
    }

    return null;
  }

  async setThumbnail(key: string, blob: Blob): Promise<void> {
    this.memoryCache.set(key, blob);
    await set(key, blob, customStore);
    await this.updateMetadata(key, blob.size);
    await this.enforceSizeLimit();
  }

  private async getMetadata(): Promise<Metadata> {
    return (await get<Metadata>(METADATA_KEY, customStore)) || {};
  }

  private async saveMetadata(metadata: Metadata): Promise<void> {
    await set(METADATA_KEY, metadata, customStore);
  }

  private async updateMetadata(key: string, size: number): Promise<void> {
    const metadata = await this.getMetadata();
    metadata[key] = {
      size,
      lastAccessed: Date.now(),
    };
    await this.saveMetadata(metadata);
  }

  private async enforceSizeLimit(): Promise<void> {
    const metadata = await this.getMetadata();
    const allKeys = Object.keys(metadata);

    let currentSize = allKeys.reduce((sum, key) => sum + (metadata[key]?.size || 0), 0);
    const maxSize = MAX_DB_SIZE_MB * 1024 * 1024;

    if (currentSize <= maxSize) {
      return;
    }

    // 按 LRU 排序
    const sortedKeys = allKeys.sort((a, b) =>
      (metadata[a]?.lastAccessed || 0) - (metadata[b]?.lastAccessed || 0)
    );

    for (const key of sortedKeys) {
      if (currentSize <= maxSize) break;

      const itemSize = metadata[key]?.size || 0;
      await del(key, customStore);
      delete metadata[key];
      currentSize -= itemSize;

      console.log(`[Cache Cleanup] Removed ${key} (${(itemSize / 1024).toFixed(2)} KB)`);
    }

    await this.saveMetadata(metadata);
  }

  async clearAllCache(): Promise<void> {
    this.memoryCache.clear();
    await clear(customStore);
    console.log('Thumbnail cache cleared.');
  }
}

export const thumbnailService = new ThumbnailDBService();
