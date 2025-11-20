import { API_BASE_URL } from './base';

/**
 * @interface SettingItem
 * @description 后端返回的单个设置项的结构
 */
export interface SettingItem {
  key: string;
  name: string;
  description: string;
  value: string | number | boolean;
  type: string;
  options?: (string | number | boolean)[];
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
    value: string | number | boolean;
}

/**
 * @function updateSetting
 * @description 更新单个设置项到后端
 * @param {string} key - 设置项的键
 * @param {string | number | boolean} value - 设置项的新值
 * @returns {Promise<UpdateSettingResponse>}
 */
export const updateSetting = async (key: string, value: string | number | boolean): Promise<UpdateSettingResponse> => {
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
