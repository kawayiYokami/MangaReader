import { defineStore } from 'pinia';
import {
  getAllSettings,
  updateSetting as apiUpdateSetting,
  type SettingItem
} from '@/api/settings';

// 定义 State 的类型
export interface SettingsState {
  logLevel: string;
  
  isLoading: boolean; // 通用加载状态

  // 页面缓存设置
  pageCacheEnabled: boolean;
  pageCacheQuality: number;
  pageCacheMaxSizeMb: number;
  pageCacheStandardHeight: number;
  pageCacheDecisionRatio: number;
  pageCacheDecisionSizeMb: number;
  pageCacheDecisionDimension: number;

}

export const useSettingsStore = defineStore('settings', {
  state: (): SettingsState => ({
    // 初始化为空值，等待从后端加载
    logLevel: '',
    isLoading: false,

    // 页面缓存设置
    pageCacheEnabled: true,
    pageCacheQuality: 85,
    pageCacheMaxSizeMb: 2048,
    pageCacheStandardHeight: 1280,
    pageCacheDecisionRatio: 0.25,
    pageCacheDecisionSizeMb: 2.0,
    pageCacheDecisionDimension: 4000,

  }),

  actions: {
    /**
     * 从后端初始化所有设置
     */
    async initializeSettings() {
      this.isLoading = true;
      try {
        const settingsList = await getAllSettings();
        const settingsMap = settingsList.reduce((acc, setting) => {
            acc[setting.key] = setting.value;
            return acc;
        }, {} as Record<string, any>);

        // 使用后端返回的值填充 state
        this.logLevel = settingsMap.logLevel ?? this.logLevel;

        // 加载页面缓存设置
        this.pageCacheEnabled = settingsMap.pageCacheEnabled ?? this.pageCacheEnabled;
        this.pageCacheQuality = settingsMap.pageCacheQuality ?? this.pageCacheQuality;
        this.pageCacheMaxSizeMb = settingsMap.pageCacheMaxSizeMb ?? this.pageCacheMaxSizeMb;
        this.pageCacheStandardHeight = settingsMap.pageCacheStandardHeight ?? this.pageCacheStandardHeight;
        this.pageCacheDecisionRatio = settingsMap.pageCacheDecisionRatio ?? this.pageCacheDecisionRatio;
        this.pageCacheDecisionSizeMb = settingsMap.pageCacheDecisionSizeMb ?? this.pageCacheDecisionSizeMb;
        this.pageCacheDecisionDimension = settingsMap.pageCacheDecisionDimension ?? this.pageCacheDecisionDimension;

      } catch (error) {
        console.error('Failed to initialize settings:', error);
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * 更新单个设置项并保存到后端
     * @param key - 设置项的键
     * @param value - 设置项的新值
     */
    async updateSetting(key: keyof SettingsState, value: any) {
      if (key in this) {
        // optimistically update UI
        (this as any)[key] = value;
        try {
          await apiUpdateSetting(key, value);
          console.log(`Setting ${key} successfully updated to:`, value);
        } catch (error) {
          console.error(`Failed to save setting ${key} to backend:`, error);
          // TODO: Revert state or show error notification
        }
      }
    }
  },
});