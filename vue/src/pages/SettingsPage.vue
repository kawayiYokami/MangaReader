<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useSettingsStore, type SettingsState } from '@/store/settings'
import { storeToRefs } from 'pinia'
import { useTheme } from '@/composables/useTheme'
import { getTranslatorConfigs, getTranslatorAgents, updateTranslatorConfigs, fetchModelsFromProvider } from '@/api/translator'
import type { APIConfig } from '@/types/translator'
import { ElMessage, ElMessageBox } from 'element-plus'

// 主题管理
const { theme } = useTheme()

// 设置状态管理
const settingsStore = useSettingsStore()
const {
  logLevel,
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

// AI 翻译器设置
const translatorConfigs = ref<APIConfig[]>([])
const translatorAgents = ref<any[]>([])

// 组件挂载时获取初始数据
onMounted(async () => {
  settingsStore.initializeSettings()
  // 获取 AI 翻译器数据
  try {
    const [configs, agents] = await Promise.all([
      getTranslatorConfigs(),
      getTranslatorAgents()
    ]);
    translatorConfigs.value = configs;
    translatorAgents.value = agents;
  } catch (error) {
    ElMessage.error('获取 AI 翻译器设置失败')
  }
})

// 统一的设置更新处理
const onSettingChange = (key: keyof SettingsState, value: any) => {
  settingsStore.updateSetting(key, value);
}

// --- AI 翻译器配置 CRUD ---
const isDialogVisible = ref(false)
const editingConfig = ref<APIConfig | null>(null)
const isNewConfig = ref(false)
const availableModels = ref<string[]>([])
const isLoadingModels = ref(false)

const emptyConfig = (): APIConfig => ({
  name: '',
  api_type: 'openai',
  api_key: '',
  model: '',
  temperature: 0.2,
  max_tokens: 4096,
  api_base_url: '',
  request_interval_ms: 1000,
})

const openEditDialog = (config: APIConfig) => {
  editingConfig.value = { ...config }
  isNewConfig.value = false
  availableModels.value = [] // 清空旧的模型列表
  isDialogVisible.value = true
}

const openNewDialog = () => {
  editingConfig.value = emptyConfig()
  isNewConfig.value = true
  availableModels.value = [] // 清空旧的模型列表
  isDialogVisible.value = true
}

const handleDelete = async (configNameToDelete: string) => {
  await ElMessageBox.confirm(
    `确定要删除配置 "${configNameToDelete}" 吗？此操作不可撤销。`,
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  )
  
  const newConfigs = translatorConfigs.value.filter(c => c.name !== configNameToDelete)
  try {
    await updateTranslatorConfigs(newConfigs)
    translatorConfigs.value = newConfigs
    ElMessage.success('配置已删除')
  } catch (error) {
    ElMessage.error('删除配置失败')
  }
}

const handleFetchModels = async () => {
  if (!editingConfig.value?.api_base_url) {
    ElMessage.warning('请先填写 API Base URL');
    return;
  }
  if (!editingConfig.value?.api_key) {
    ElMessage.warning('请先填写 API Key');
    return;
  }

  isLoadingModels.value = true;
  availableModels.value = [];

  try {
    const models = await fetchModelsFromProvider(
      editingConfig.value.api_base_url,
      editingConfig.value.api_key
    );
    availableModels.value = models;
    ElMessage.success(`成功获取到 ${models.length} 个模型`);

    // 如果当前模型不在新列表中，则清空
    if (editingConfig.value.model && !models.includes(editingConfig.value.model)) {
      editingConfig.value.model = '';
    }
    // 如果模型为空且列表不为空，则默认选中第一个
    if (!editingConfig.value.model && models.length > 0) {
      editingConfig.value.model = models[0];
    }

  } catch (error: any) {
    ElMessage.error(`获取模型失败: ${error.message}`);
  } finally {
    isLoadingModels.value = false;
  }
};

// 当对话框关闭时，重置模型列表状态
watch(isDialogVisible, (newValue) => {
  if (!newValue) {
    availableModels.value = [];
    isLoadingModels.value = false;
  }
});

const handleSave = async () => {
  if (!editingConfig.value) return

  const newConfigs = [...translatorConfigs.value]
  
  if (isNewConfig.value) {
    // 检查名称是否重复
    if (newConfigs.some(c => c.name === editingConfig.value!.name)) {
      ElMessage.error('配置名称已存在')
      return
    }
    newConfigs.push(editingConfig.value)
  } else {
    const index = newConfigs.findIndex(c => c.name === editingConfig.value!.name)
    if (index !== -1) {
      newConfigs[index] = editingConfig.value
    }
  }

  try {
    await updateTranslatorConfigs(newConfigs)
    translatorConfigs.value = newConfigs
    isDialogVisible.value = false
    ElMessage.success('配置已保存')
  } catch (error) {
    ElMessage.error('保存配置失败')
  }
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

      <!-- AI 翻译器设置 -->
      <el-card class="mt-lg">
        <template #header>
          <div class="card-header">
            <span><span class="material-symbols-rounded">translate</span> AI 翻译器设置</span>
          </div>
        </template>
        <el-form label-position="top">
          <div class="toolbar">
            <p class="setting-description">管理所有可用的 AI 服务配置 (API Key, 模型等)。</p>
            <el-button type="primary" @click="openNewDialog">新增配置</el-button>
          </div>
          <el-table :data="translatorConfigs" stripe class="mt-md">
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="api_type" label="类型" />
            <el-table-column prop="model" label="模型" />
            <el-table-column label="操作" width="120">
              <template #default="scope">
                <el-button link type="primary" size="small" @click="openEditDialog(scope.row)">编辑</el-button>
                <el-button link type="danger" size="small" @click="handleDelete(scope.row.name)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
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

    <!-- 新增/编辑配置对话框 -->
    <el-dialog v-model="isDialogVisible" :title="isNewConfig ? '新增配置' : '编辑配置'" width="500px">
      <el-form v-if="editingConfig" :model="editingConfig" label-position="top">
        <el-form-item label="配置名称">
          <el-input v-model="editingConfig.name" :disabled="!isNewConfig" />
        </el-form-item>
        <el-form-item label="API 类型">
          <el-select v-model="editingConfig.api_type" placeholder="选择 API 类型">
            <el-option label="OpenAI" value="openai"></el-option>
            <el-option label="Gemini" value="gemini"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="editingConfig.api_key" type="password" show-password />
        </el-form-item>
        <el-form-item label="模型名称">
          <el-select 
            v-model="editingConfig.model" 
            placeholder="请选择或输入模型名称"
            filterable
            allow-create
            default-first-option
            class="w-full"
          >
            <el-option
              v-for="item in availableModels"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="API Base URL (可选)">
            <div class="flex w-full">
              <el-input v-model="editingConfig.api_base_url" placeholder="例如 https://api.openai.com/v1" class="flex-grow" />
              <el-button 
                @click="handleFetchModels" 
                :loading="isLoadingModels" 
                :disabled="!editingConfig.api_base_url || !editingConfig.api_key"
                class="ml-sm"
              >
                获取模型
              </el-button>
            </div>
        </el-form-item>
        <el-form-item label="温度">
          <el-slider v-model="editingConfig.temperature" :min="0" :max="2" :step="0.1" show-input />
        </el-form-item>
        <el-form-item label="最大 Token 数">
          <el-slider v-model="editingConfig.max_tokens" :min="512" :max="16384" :step="512" show-input />
        </el-form-item>
        <el-form-item label="请求间隔 (ms)">
          <el-slider v-model="editingConfig.request_interval_ms" :min="0" :max="5000" :step="100" show-input />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="isDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSave">保存</el-button>
        </span>
      </template>
    </el-dialog>
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
.mt-md {
  margin-top: var(--spacing-md);
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.material-symbols-rounded {
  vertical-align: middle;
  margin-right: 4px;
}
.w-full {
  width: 100%;
}
.flex {
  display: flex;
}
.flex-grow {
  flex-grow: 1;
}
.ml-sm {
  margin-left: var(--spacing-sm);
}
</style>