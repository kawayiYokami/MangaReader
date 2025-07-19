import { defineStore } from 'pinia';
import {
  getAllSettings,
  updateSetting as apiUpdateSetting,
  getTranslatorOptions,
  fetchProviderModels,
  getAvailableFonts,
  type TranslatorOption,
  type FontOption,
  type SettingItem
} from '@/api/settings';

// 定义 State 的类型
export interface SettingsState {
  // 翻译服务商
  availableTranslators: TranslatorOption[];
  isLoadingTranslators: boolean;

  // OpenAI 模型
  openaiModels: string[];
  isLoadingOpenAIModels: boolean;
  
  // Gemini 模型
  geminiModels: string[];
  isLoadingGeminiModels: boolean;

  // 当前设置值
  translator_type: string;
  openai_api_key: string;
  openai_api_base_url: string;
  openai_model: string;
  gemini_api_key: string;
  gemini_model: string;
  zhipu_api_key: string;
  zhipu_model: string;
  font_name: string;
  logLevel: string;
  
  // 字体
  availableFonts: FontOption[];
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
    availableTranslators: [],
    isLoadingTranslators: false,
    openaiModels: [],
    isLoadingOpenAIModels: false,
    geminiModels: [],
    isLoadingGeminiModels: false,
    
    // 初始化为空值，等待从后端加载
    translator_type: '',
    openai_api_key: '',
    openai_api_base_url: '',
    openai_model: '',
    gemini_api_key: '',
    gemini_model: '',
    zhipu_api_key: '',
    zhipu_model: '',
    font_name: '',
    logLevel: '',
    availableFonts: [],
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
        this.translator_type = settingsMap.translator_type ?? this.translator_type;
        this.openai_api_key = settingsMap.openai_api_key ?? this.openai_api_key;
        this.openai_api_base_url = settingsMap.openai_api_base_url ?? this.openai_api_base_url;
        this.openai_model = settingsMap.openai_model ?? this.openai_model;
        this.gemini_api_key = settingsMap.gemini_api_key ?? this.gemini_api_key;
        this.gemini_model = settingsMap.gemini_model ?? this.gemini_model;
        this.zhipu_api_key = settingsMap.zhipu_api_key ?? this.zhipu_api_key;
        this.zhipu_model = settingsMap.zhipu_model ?? this.zhipu_model;
        this.font_name = settingsMap.font_name ?? this.font_name;
        this.logLevel = settingsMap.logLevel ?? this.logLevel;

        // 加载页面缓存设置
        this.pageCacheEnabled = settingsMap.pageCacheEnabled ?? this.pageCacheEnabled;
        this.pageCacheQuality = settingsMap.pageCacheQuality ?? this.pageCacheQuality;
        this.pageCacheMaxSizeMb = settingsMap.pageCacheMaxSizeMb ?? this.pageCacheMaxSizeMb;
        this.pageCacheStandardHeight = settingsMap.pageCacheStandardHeight ?? this.pageCacheStandardHeight;
        this.pageCacheDecisionRatio = settingsMap.pageCacheDecisionRatio ?? this.pageCacheDecisionRatio;
        this.pageCacheDecisionSizeMb = settingsMap.pageCacheDecisionSizeMb ?? this.pageCacheDecisionSizeMb;
        this.pageCacheDecisionDimension = settingsMap.pageCacheDecisionDimension ?? this.pageCacheDecisionDimension;
        
        // 并行获取下拉列表选项
        await Promise.all([
          this.fetchTranslatorOptions(),
          this.fetchAvailableFonts()
        ]);

      } catch (error) {
        console.error('Failed to initialize settings:', error);
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * 获取可用的翻译服务商列表
     */
    async fetchTranslatorOptions() {
      this.isLoadingTranslators = true;
      try {
        this.availableTranslators = await getTranslatorOptions();
      } catch (error) {
        console.error('Failed to fetch translator options in store:', error);
      } finally {
        this.isLoadingTranslators = false;
      }
    },

    /**
     * 根据服务商名称获取模型列表
     * @param provider - 'openai' 或 'gemini'
     */
    async fetchModelsForProvider(provider: 'openai' | 'gemini') {
      let apiKey = '';
      let baseUrl: string | undefined = undefined;

      if (provider === 'openai') {
        this.isLoadingOpenAIModels = true;
        apiKey = this.openai_api_key;
        baseUrl = this.openai_api_base_url;
      } else if (provider === 'gemini') {
        this.isLoadingGeminiModels = true;
        apiKey = this.gemini_api_key;
      }

      if (!apiKey) {
        if (provider === 'openai') this.isLoadingOpenAIModels = false;
        if (provider === 'gemini') this.isLoadingGeminiModels = false;
        return;
      }

      try {
        const models = await fetchProviderModels(provider, apiKey, baseUrl);
        if (provider === 'openai') {
          this.openaiModels = models;
        } else if (provider === 'gemini') {
          this.geminiModels = models;
        }
      } catch (error) {
        console.error(`Failed to fetch models for ${provider} in store:`, error);
      } finally {
        if (provider === 'openai') this.isLoadingOpenAIModels = false;
        if (provider === 'gemini') this.isLoadingGeminiModels = false;
      }
    },

    /**
     * 获取可用的字体列表
     */
    async fetchAvailableFonts() {
      try {
        this.availableFonts = await getAvailableFonts();
      } catch (error) {
        console.error('Failed to fetch available fonts in store:', error);
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