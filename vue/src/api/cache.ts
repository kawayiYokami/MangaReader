import { API_BASE_URL } from './base';

export interface CacheType {
  key: string;
  name: string;
  description: string;
  icon?: string; // Add icon for UI
}

export interface CacheStat {
  entries: number;
  size: string;
}

export interface CacheEntry {
  key: string;
  value_preview: string;
  [key: string]: any; // For dynamic properties
}

export interface CacheEntriesResponse {
  entries: CacheEntry[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export async function getCacheTypes(): Promise<CacheType[]> {
  const response = await fetch(`${API_BASE_URL}/api/cache/types`);
  if (!response.ok) throw new Error('Failed to fetch cache types');
  const data = await response.json();
  // Manually add icons for a better UI
  return data.cache_types.map((type: CacheType) => ({
    ...type,
    icon: {
      'manga_list': 'menu_book',
      'harmonization_map': 'rule',
      'persistent_translation': 'save'
    }[type.key] || 'database'
  }));
}

export async function getCacheStats(): Promise<Record<string, CacheStat>> {
  const response = await fetch(`${API_BASE_URL}/api/cache/stats`);
  if (!response.ok) throw new Error('Failed to fetch cache stats');
  const data = await response.json();
  return data.stats;
}

export async function getCacheEntries(
  type: string,
  page: number,
  pageSize: number,
  search?: string
): Promise<CacheEntriesResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (search) {
    params.append('search', search);
  }
  const response = await fetch(`${API_BASE_URL}/api/cache/${type}/entries?${params.toString()}`);
  if (!response.ok) throw new Error(`Failed to fetch entries for ${type}`);
  return response.json();
}

export async function clearCache(type: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/api/cache/${type}/clear`, { method: 'POST' });
  if (!response.ok) throw new Error(`Failed to clear cache for ${type}`);
  return response.json();
}

export async function deleteCacheEntry(type: string, key: string): Promise<any> {
  console.log(`[Cache API] Attempting to delete entry in '${type}' with key:`, key);

  try {
    const response = await fetch(`${API_BASE_URL}/api/cache/${type}/entries/${encodeURIComponent(key)}`, { method: 'DELETE' });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: `HTTP error! status: ${response.status}` }));
      console.error(`[Cache API] Failed to delete entry. Server responded with:`, errorData);
      throw new Error(errorData.detail || `Failed to delete entry ${key} from ${type}`);
    }

    const responseData = await response.json();
    console.log(`[Cache API] Entry deleted successfully. Response:`, responseData);
    return responseData;
  } catch (error) {
    console.error(`[Cache API] Network or other error during deleteCacheEntry:`, error);
    throw error;
  }
}

export async function addOrUpdateEntry(type: string, key: string, content: any): Promise<any> {
  const payload = { key, content };
  console.log(`[Cache API] Attempting to add/update entry in '${type}' with payload:`, payload);

  try {
    const response = await fetch(`${API_BASE_URL}/api/cache/${type}/entries`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: `HTTP error! status: ${response.status}` }));
      console.error(`[Cache API] Failed to update entry. Server responded with:`, errorData);
      throw new Error(errorData.detail || `Failed to update entry in ${type}`);
    }

    const responseData = await response.json();
    console.log(`[Cache API] Entry updated successfully. Response:`, responseData);
    return responseData;
  } catch (error) {
    console.error(`[Cache API] Network or other error during addOrUpdateEntry:`, error);
    throw error; // Re-throw the error to be caught by the caller
  }
}