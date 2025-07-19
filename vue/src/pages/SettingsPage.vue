<script setup lang="ts">
import { onMounted } from 'vue'
import { useSettingsStore, type SettingsState } from '@/store/settings'
import { storeToRefs } from 'pinia'
import { useTheme } from '@/composables/useTheme'

// 主题管理
const { theme } = useTheme()

// 设置状态管理
const settingsStore = useSettingsStore()
const {
  availableTranslators,
  isLoadingTranslators,
  openaiModels,
  isLoadingOpenAIModels,
  geminiModels,
  isLoadingGeminiModels,
  translator_type,
  openai_api_key,
  openai_api_base_url,
  openai_model,
  gemini_api_key,
  gemini_model,
  zhipu_api_key,
  zhipu_model,
  font_name,
  logLevel,
  availableFonts,
  isLoading,
  // 页面缓存
  pageCacheEnabled,
  pageCacheQuality,
  pageCacheMaxSizeMb,
  pageCacheStandardHeight,
  pageCacheDecisionRatio,
  pageCacheDecisionSizeMb,
  pageCacheDecisionDimension
} = storeToRefs(settingsStore)

// 组件挂载时获取初始数据
onMounted(() => {
  settingsStore.initializeSettings()
})

// 当API Key或Base URL变化时，触发模型列表获取
const handleApiKeyChange = (provider: 'openai' | 'gemini') => {
  // 保存新值到后端
  if (provider === 'openai') {
    settingsStore.updateSetting('openai_api_key', openai_api_key.value);
    settingsStore.updateSetting('openai_api_base_url', openai_api_base_url.value);
  } else {
    settingsStore.updateSetting('gemini_api_key', gemini_api_key.value);
  }
  // 触发模型列表刷新
  settingsStore.fetchModelsForProvider(provider)
}

// 统一的设置更新处理
const onSettingChange = (key: keyof SettingsState, value: any) => {
  settingsStore.updateSetting(key, value);
}

</script>

<template>
  <div class="settings-page">
    <!-- 加载遮罩 -->
    <el-skeleton :rows="15" animated v-if="isLoading" />

    <template v-else>
      <!-- 外观设置 -->
      <el-card>
        <template #header>
          <div class="card-header">
            <span><span class="material-symbols-rounded">palette</span> 外观设置</span>
          </div>
        </template>
        <el-form label-position="top">
          <el-form-item>
            <template #label>
              <div>
                <span>应用主题</span>
                <p class="setting-description">选择应用的外观主题。</p>
              </div>
            </template>
            <el-radio-group v-model="theme">
              <el-radio value="light">浅色</el-radio>
              <el-radio value="dark">深色</el-radio>
            </el-radio-group>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 翻译与文本设置 -->
      <el-card class="mt-lg">
        <template #header>
          <div class="card-header">
            <span><span class="material-symbols-rounded">language</span> 翻译与文本设置</span>
          </div>
        </template>
        <el-form label-position="top">
          <el-form-item label="翻译接口">
            <el-select v-model="translator_type" placeholder="选择翻译引擎" :loading="isLoadingTranslators" @change="onSettingChange('translator_type', $event)">
              <el-option
                v-for="translator in availableTranslators"
                :key="translator.value"
                :label="translator.label"
                :value="translator.value"
              />
            </el-select>
          </el-form-item>
          
          <!-- 智谱AI -->
          <div v-if="translator_type === '智谱'">
            <el-form-item label="智谱AI API密钥">
              <el-input v-model="zhipu_api_key" @change="onSettingChange('zhipu_api_key', $event)"/>
            </el-form-item>
            <el-form-item label="智谱AI模型">
               <el-select v-model="zhipu_model" @change="onSettingChange('zhipu_model', $event)">
                  <el-option label="glm-4-flash" value="glm-4-flash"></el-option>
                  <el-option label="glm-4" value="glm-4"></el-option>
                  <el-option label="glm-3-turbo" value="glm-3-turbo"></el-option>
                  <el-option label="glm-4-flash-250414" value="glm-4-flash-250414"></el-option>
               </el-select>
            </el-form-item>
          </div>

          <!-- OpenAI -->
          <div v-if="translator_type === 'OpenAI'">
            <el-form-item label="OpenAI API密钥">
              <el-input v-model="openai_api_key" @change="handleApiKeyChange('openai')" />
            </el-form-item>
            <el-form-item label="API Base URL (可选)">
              <el-input v-model="openai_api_base_url" placeholder="例如: https://api.openai.com/v1" @change="handleApiKeyChange('openai')" />
            </el-form-item>
            <el-form-item label="OpenAI 模型">
              <el-select v-model="openai_model" placeholder="输入API Key后自动加载" :loading="isLoadingOpenAIModels" filterable allow-create default-first-option @change="onSettingChange('openai_model', $event)">
                <el-option v-for="model in openaiModels" :key="model" :label="model" :value="model" />
              </el-select>
            </el-form-item>
          </div>

          <!-- Gemini -->
          <div v-if="translator_type === 'Gemini'">
            <el-form-item label="Gemini API密钥">
              <el-input v-model="gemini_api_key" @change="handleApiKeyChange('gemini')" />
            </el-form-item>
            <el-form-item label="Gemini 模型">
              <el-select v-model="gemini_model" placeholder="输入API Key后自动加载" :loading="isLoadingGeminiModels" filterable allow-create default-first-option @change="onSettingChange('gemini_model', $event)">
                <el-option v-for="model in geminiModels" :key="model" :label="model" :value="model" />
              </el-select>
            </el-form-item>
          </div>

          <!-- 文本替换字体 -->
          <el-form-item label="文本替换字体">
            <el-select v-model="font_name" placeholder="选择字体" @change="onSettingChange('font_name', $event)">
              <el-option
                v-for="font in availableFonts"
                :key="font.file_name"
                :label="font.display_name"
                :value="font.file_name"
              />
            </el-select>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 页面缓存设置 -->
      <el-card class="mt-lg">
        <template #header>
          <div class="card-header">
            <span><span class="material-symbols-rounded">photo_library</span> 页面缓存设置</span>
          </div>
        </template>
        <el-form label-position="top">
          <el-form-item>
            <template #label>
              <div>
                <span>启用页面缓存</span>
                <p class="setting-description">开启后，应用会将处理过的漫画页面保存到本地，加快二次加载速度。</p>
              </div>
            </template>
            <el-switch v-model="pageCacheEnabled" @change="onSettingChange('pageCacheEnabled', $event)" />
          </el-form-item>

          <el-form-item>
             <template #label>
              <div>
                <span>缓存图像质量</span>
                <p class="setting-description">设置缓存图像的质量，值越高，图像越清晰，但文件也越大。(范围: 10-100)</p>
              </div>
            </template>
            <el-slider v-model="pageCacheQuality" :min="10" :max="100" show-input @change="onSettingChange('pageCacheQuality', $event)" />
          </el-form-item>

          <el-form-item>
            <template #label>
              <div>
                <span>最大缓存体积 (MB)</span>
                <p class="setting-description">设置页面缓存可以占用的最大磁盘空间。(范围: 100-20480 MB)</p>
              </div>
            </template>
            <el-slider v-model="pageCacheMaxSizeMb" :min="100" :max="20480" show-input @change="onSettingChange('pageCacheMaxSizeMb', $event)" />
          </el-form-item>

          <el-form-item>
            <template #label>
              <div>
                <span>缓存标准高度 (px)</span>
                <p class="setting-description">缓存时，所有页面的高度将被统一调整到此值，以优化阅读体验。(范围: 720-4000 px)</p>
              </div>
            </template>
            <el-slider v-model="pageCacheStandardHeight" :min="720" :max="4000" show-input @change="onSettingChange('pageCacheStandardHeight', $event)" />
          </el-form-item>

          <el-divider>缓存决策阈值</el-divider>
          
          <el-form-item>
            <template #label>
              <div>
                <span>压缩率阈值</span>
                <p class="setting-description">当（原图大小 / 缓存图大小）的比率超过此值时，倾向于进行缓存。(范围: 0.05-1.0)</p>
              </div>
            </template>
            <el-slider v-model="pageCacheDecisionRatio" :min="0.05" :max="1.0" :step="0.01" show-input @change="onSettingChange('pageCacheDecisionRatio', $event)" />
          </el-form-item>

          <el-form-item>
            <template #label>
              <div>
                <span>文件大小阈值 (MB)</span>
                <p class="setting-description">当原图文件大小超过此值时，倾向于进行缓存。(范围: 0.5-10.0 MB)</p>
              </div>
            </template>
            <el-slider v-model="pageCacheDecisionSizeMb" :min="0.5" :max="10.0" :step="0.1" show-input @change="onSettingChange('pageCacheDecisionSizeMb', $event)" />
          </el-form-item>

          <el-form-item>
            <template #label>
              <div>
                <span>图像尺寸阈值 (px)</span>
                <p class="setting-description">当原图的最长边超过此像素值时，倾向于进行缓存。(范围: 1000-8000 px)</p>
              </div>
            </template>
            <el-slider v-model="pageCacheDecisionDimension" :min="1000" :max="8000" show-input @change="onSettingChange('pageCacheDecisionDimension', $event)" />
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 系统设置 -->
      <el-card class="mt-lg">
          <template #header>
              <div class="card-header">
                  <span><span class="material-symbols-rounded">settings</span> 系统设置</span>
              </div>
          </template>
          <el-form label-position="top">
              <el-form-item label="日志等级">
                  <el-select v-model="logLevel" placeholder="选择日志等级" @change="onSettingChange('logLevel', $event)">
                      <el-option label="调试 (DEBUG)" value="DEBUG"></el-option>
                      <el-option label="信息 (INFO)" value="INFO"></el-option>
                      <el-option label="警告 (WARNING)" value="WARNING"></el-option>
                      <el-option label="错误 (ERROR)" value="ERROR"></el-option>
                      <el-option label="严重 (CRITICAL)" value="CRITICAL"></el-option>
                  </el-select>
              </el-form-item>
          </el-form>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 800px;
  margin: 0 auto;
}
.setting-description {
    color: var(--color-text-secondary);
    font-size: 12px;
    margin-top: 4px;
    line-height: 1.4;
}
.mt-lg {
  margin-top: var(--spacing-lg);
}
.material-symbols-rounded {
  vertical-align: middle; 
  margin-right: 4px;
}
</style>