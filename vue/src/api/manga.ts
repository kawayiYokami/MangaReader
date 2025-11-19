// vue/src/api/manga.ts
import { API_BASE_URL } from './base';

export interface Manga {
  file_path: string;
  title: string;
  tags: string[];
  total_pages: number;
  file_type: string;
  last_modified: string;
  file_size: number;
  [key: string]: string | number | boolean | string[]; // Allow other properties
}

export interface PaginatedMangaResponse {
  items: Manga[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface GetMangaListParams {
  page?: number;
  pageSize?: number;
  sort?: string;
  tags?: string[];
  query?: string;
}

/**
 * 获取分页的漫画列表
 */
export async function getMangaList(params: GetMangaListParams = {}): Promise<PaginatedMangaResponse> {
  const urlParams = new URLSearchParams();

  if (params.page) urlParams.append('page', String(params.page));
  if (params.pageSize) urlParams.append('page_size', String(params.pageSize));
  if (params.sort) urlParams.append('sort_by', params.sort);
  if (params.query) urlParams.append('query', params.query);
  if (params.tags && params.tags.length > 0) {
    urlParams.append('tag_filters', params.tags.join(','));
  }

  const response = await fetch(`${API_BASE_URL}/api/manga/list?${urlParams.toString()}`);

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: '获取漫画列表失败' }));
    throw new Error(errorData.detail);
  }

  return response.json();
}

/**
 * 获取所有可用的标签
 */
export async function getAllTags(): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/api/manga/tags`);

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: '获取标签列表失败' }));
    throw new Error(errorData.detail);
  }

  return response.json();
}


export interface BatchCompressOptions {
  webp_quality: number;
  min_compression_ratio: number;
  preserve_original_names: boolean;
  delete_source_on_success: boolean;
}


/**
 * 启动批量压缩任务
 * @param options - 压缩选项
 */
export async function startBatchCompression(options: BatchCompressOptions) {
  const response = await fetch(`${API_BASE_URL}/api/manga/batch-compress`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(options),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: '批量压缩任务启动失败' }));
    throw new Error(errorData.detail);
  }
  return response.json();
}

/**
 * 获取批量压缩任务状态
 * @param taskId 任务ID
 */
export async function getBatchCompressionStatus(taskId: string) {
  const response = await fetch(`${API_BASE_URL}/api/manga/batch-compress/status/${taskId}`);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: '获取批量压缩状态失败' }));
    throw new Error(errorData.detail);
  }
  return response.json();
}

/**
 * 取消批量压缩任务
 * @param taskId 任务ID
 */
export async function cancelBatchCompression(taskId: string) {
  const response = await fetch(`${API_BASE_URL}/api/manga/batch-compress/cancel/${taskId}`, {
    method: 'POST',
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: '取消批量压缩任务失败' }));
    throw new Error(errorData.detail);
  }
  return response.json();
}
