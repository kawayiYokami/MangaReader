// file: vue/src/api/translator.ts
import { API_BASE_URL } from './base';
import type { APIConfig, ImageTranslationResult } from '../types/translator';

/**
 * 获取所有 AI 翻译器配置
 */
export const getTranslatorConfigs = async (): Promise<APIConfig[]> => {
  const response = await fetch(`${API_BASE_URL}/api/translators/configs`);
  if (!response.ok) {
    throw new Error('Failed to fetch translator configs');
  }
  return response.json();
};

/**
 * 更新 AI 翻译器配置
 * @param configs - 最新的配置列表
 */
export const updateTranslatorConfigs = async (configs: APIConfig[]): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/api/translators/configs`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(configs),
  });
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Failed to update translator configs');
  }
};

/**
 * 获取所有可用的翻译智能体
 */
export const getTranslatorAgents = async (): Promise<any[]> => {
  const response = await fetch(`${API_BASE_URL}/api/translators/agents`);
  if (!response.ok) {
    throw new Error('Failed to fetch translator agents');
  }
  return response.json();
};

/**
 * 对指定的漫画页面执行 AI 翻译
 * @param payload - 包含所有翻译所需参数的请求体
 */
export const translateMangaPage = async (payload: any): Promise<ImageTranslationResult[]> => {
  const response = await fetch(`${API_BASE_URL}/api/actions/translate_page`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Failed to translate manga page');
  }
  return response.json();
};