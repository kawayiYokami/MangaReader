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
 * 从指定的 API 服务提供商获取可用模型列表
 * @param baseUrl - API 的基础 URL
 * @param apiKey - API 密钥
 */
export const fetchModelsFromProvider = async (baseUrl: string, apiKey: string): Promise<string[]> => {
  // 确保 baseUrl 以 /v1 结尾，这是 OpenAI 兼容 API 的标准
  const endpoint = `${baseUrl.replace(/\/v1\/?$/, '')}/v1/models`;

  try {
    const response = await fetch(endpoint, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
      },
    });

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('认证失败: API Key 无效或缺少权限。');
      }
      if (response.status === 404) {
        throw new Error('API端点未找到，请检查URL是否正确。');
      }
      throw new Error(`服务器错误: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();

    if (!data || !Array.isArray(data.data)) {
      throw new Error('返回的数据格式不正确，无法解析模型列表。');
    }

    // 提取并返回模型ID
    return data.data.map((model: any) => model.id).sort();

  } catch (error: any) {
    // 捕获网络错误 (如 CORS) 或上面抛出的错误
    if (error.message.includes('Failed to fetch')) {
        throw new Error('网络请求失败。请检查浏览器控制台，并确认目标服务器是否配置了正确的CORS策略。');
    }
    throw error; // 重新抛出其他已知错误
  }
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