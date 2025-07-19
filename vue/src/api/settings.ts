import { API_BASE_URL } from './base';

/**
 * @interface TranslatorOption
 * @description 定义翻译器选项的结构
 */
export interface TranslatorOption {
  label: string; // 显示名称，例如 "OpenAI"
  value: string; // 实际值，例如 "OpenAI"
}

/**
 * @interface ProviderModelsResponse
 * @description 获取模型列表API的响应结构
 */
export interface ProviderModelsResponse {
  success: boolean;
  models: string[];
  message?: string;
}

/**
 * @interface TranslatorOptionsResponse
 * @description 获取翻译器选项API的响应结构
 */
interface TranslatorOptionsResponse {
    success: boolean;
    translators: TranslatorOption[];
}

/**
 * @function getTranslatorOptions
 * @description 从后端获取可用的翻译服务商选项
 * @returns {Promise<TranslatorOption[]>}
 */
export const getTranslatorOptions = async (): Promise<TranslatorOption[]> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/settings/translator-options`);
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data: TranslatorOptionsResponse = await response.json();
    if (data && data.success) {
      return data.translators || [];
    }
    return [];
  } catch (error) {
    console.error('Failed to fetch translator options:', error);
    throw error;
  }
};

/**
 * @function fetchProviderModels
 * @description 从后端获取指定服务商的模型列表
 * @param {string} provider - 服务商名称 (e.g., 'openai', 'gemini')
 * @param {string} apiKey - 用户提供的API Key
 * @param {string} [baseUrl] - (可选) OpenAI的Base URL
 * @returns {Promise<string[]>}
 */
export const fetchProviderModels = async (provider: string, apiKey: string, baseUrl?: string): Promise<string[]> => {
  try {
    const payload: { apiKey: string; baseUrl?: string } = { apiKey };
    if (provider === 'openai' && baseUrl) {
      payload.baseUrl = baseUrl;
    }

    const response = await fetch(`${API_BASE_URL}/api/settings/${provider}/models`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data: ProviderModelsResponse = await response.json();
    if (data && data.success) {
      return data.models || [];
    }
    return [];
  } catch (error) {
    console.error(`Failed to fetch models for ${provider}:`, error);
    throw error;
  }
};


/**
 * @interface FontOption
 * @description 定义字体选项的结构
 */
export interface FontOption {
  display_name: string;
  file_name: string;
}

/**
 * @function getAvailableFonts
 * @description 从后端获取可用的字体列表
 * @returns {Promise<FontOption[]>}
 */
export const getAvailableFonts = async (): Promise<FontOption[]> => {
    try {
        const response = await fetch(`${API_BASE_URL}/api/settings/available-fonts`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (data && data.success) {
            return data.fonts || [];
        }
        return [];
    } catch (error) {
        console.error('Failed to fetch available fonts:', error);
        throw error;
    }
};

/**
 * @interface SettingItem
 * @description 后端返回的单个设置项的结构
 */
export interface SettingItem {
  key: string;
  name: string;
  description: string;
  value: any;
  type: string;
  options?: any[];
  min_value?: number;
  max_value?: number;
}

/**
 * @interface AllSettingsResponse
 * @description 获取所有设置API的响应结构
 */
interface AllSettingsResponse {
  settings: SettingItem[];
}

/**
 * @function getAllSettings
 * @description 从后端获取所有设置项
 * @returns {Promise<SettingItem[]>}
 */
export const getAllSettings = async (): Promise<SettingItem[]> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/settings/all`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data: AllSettingsResponse = await response.json();
    return data.settings || [];
  } catch (error) {
    console.error('Failed to fetch all settings:', error);
    throw error;
  }
};


/**
 * @interface UpdateSettingResponse
 * @description 更新设置API的响应结构
 */
export interface UpdateSettingResponse {
    success: boolean;
    message: string;
    key: string;
    value: any;
}

/**
 * @function updateSetting
 * @description 更新单个设置项到后端
 * @param {string} key - 设置项的键
 * @param {any} value - 设置项的新值
 * @returns {Promise<UpdateSettingResponse>}
 */
export const updateSetting = async (key: string, value: any): Promise<UpdateSettingResponse> => {
    try {
        const response = await fetch(`${API_BASE_URL}/api/settings/${key}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ key, value }),
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error(`Failed to update setting ${key}:`, error);
        throw error;
    }
};