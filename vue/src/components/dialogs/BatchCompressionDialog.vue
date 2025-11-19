<script setup lang="ts">
import { ref, reactive, watch } from 'vue';
import { ElMessage } from 'element-plus';
import type { BatchCompressOptions } from '@/api/manga';
import { startBatchCompression, getBatchCompressionStatus } from '@/api/manga';
import type { BatchCompressionTask } from '@/types/batchCompression';

const props = defineProps<{
  visible: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
}>();

const isLoading = ref(false);
const isProcessing = ref(false);
const currentTaskId = ref<string | null>(null);
const pollingInterval = ref<number | null>(null);

// 添加进度相关状态
const taskProgress = ref(0);
const taskStatus = ref<string>('idle');
const currentFile = ref<string>('');
const totalFiles = ref(0);
const processedFiles = ref(0);
const successfulFiles = ref(0);
const failedFiles = ref(0);

const options = reactive<BatchCompressOptions>({
  webp_quality: 85,
  min_compression_ratio: 0.25,
  preserve_original_names: true,
  delete_source_on_success: false,
});

const resetDialog = () => {
  isLoading.value = false;
  isProcessing.value = false;
  currentTaskId.value = null;
  taskProgress.value = 0;
  taskStatus.value = 'idle';
  currentFile.value = '';
  totalFiles.value = 0;
  processedFiles.value = 0;
  successfulFiles.value = 0;
  failedFiles.value = 0;

  // 清理轮询
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value);
    pollingInterval.value = null;
  }
};

const updateProgress = (status: {
  progress?: number;
  status?: string;
  current_file?: string;
  total_files?: number;
  processed_files?: number;
  successful_files?: number;
  failed_files?: number;
}) => {
  taskProgress.value = status.progress || 0;
  taskStatus.value = status.status || 'idle';
  currentFile.value = status.current_file || '';
  totalFiles.value = status.total_files || 0;
  processedFiles.value = status.processed_files || 0;
  successfulFiles.value = status.successful_files || 0;
  failedFiles.value = status.failed_files || 0;
};

const startPolling = (taskId: string) => {
  // 清理现有轮询
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value);
  }

  // 开始新的轮询
  pollingInterval.value = window.setInterval(async () => {
    try {
      const status = await getBatchCompressionStatus(taskId);
      updateProgress(status);

      // 如果任务完成，停止轮询
      if (status.status === 'completed' || status.status === 'cancelled' || status.status === 'failed') {
        stopPolling();
        isProcessing.value = false;
      }
    } catch (error) {
      console.error(`轮询任务 ${taskId} 状态失败:`, error);
      stopPolling();
      isProcessing.value = false;
    }
  }, 2000); // 每2秒更新一次
};

const stopPolling = () => {
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value);
    pollingInterval.value = null;
  }
};

const handleStartCompression = async () => {
  isLoading.value = true;
  isProcessing.value = true;

  try {
    const response = await startBatchCompression(options);
    currentTaskId.value = response.task_id;

    // 启动轮询
    startPolling(response.task_id);

    ElMessage.success('批量压缩任务已启动。');
  } catch (error) {
    ElMessage.error('启动批量压缩任务失败。');
    console.error(error);
    isProcessing.value = false;
  } finally {
    isLoading.value = false;
  }
};

const handleClose = () => {
  if (isProcessing.value) {
    ElMessage.warning('任务正在进行中，无法关闭对话框。');
    return;
  }
  emit('update:visible', false);
};

// 组件卸载时清理轮询
watch(() => props.visible, (newValue) => {
  if (!newValue) {
    stopPolling();
  }
});

// 映射任务状态到 Element Plus 进度条状态
const getProgressStatus = (status: string) => {
  switch (status) {
    case 'completed':
      return 'success';
    case 'failed':
      return 'exception';
    case 'running':
      return 'warning';
    default:
      return 'success';
  }
};
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="批量压缩漫画缓存"
    width="500px"
    :before-close="handleClose"
    destroy-on-close
    @update:model-value="$emit('update:visible', $event)"
    @closed="resetDialog"
  >
    <div v-loading="isLoading">
      <el-form :model="options" label-position="top">
        <el-form-item label="WebP 压缩质量">
          <el-slider v-model="options.webp_quality" :min="10" :max="100" show-input />
          <div class="el-form-item__description">
            推荐值在 75-90 之间。质量越高，文件越大。
          </div>
        </el-form-item>
        <el-form-item label="最小压缩率">
          <el-slider v-model="options.min_compression_ratio" :min="0.05" :max="0.95" :step="0.05" show-input />
           <div class="el-form-item__description">
            如果压缩后的文件大小与原文件大小的比率低于此值，则不进行压缩以节省时间。例如，0.25 表示至少要节省 25% 的空间。
          </div>
        </el-form-item>
        <el-form-item label="保留原始文件名">
          <el-switch v-model="options.preserve_original_names" />
           <div class="el-form-item__description">
            开启后，压缩后的文件将保留原始文件名（仅扩展名变为 .webp）。关闭则会使用新的命名规则。
          </div>
        </el-form-item>
        <el-form-item label="压缩后删除源文件">
          <el-switch v-model="options.delete_source_on_success" />
           <div class="el-form-item__description">
            开启后，压缩成功并验证通过后将自动删除原始文件以节省磁盘空间。此操作不可逆，请谨慎使用。
          </div>
        </el-form-item>
      </el-form>

      <!-- 进度显示 -->
      <div v-if="isProcessing && currentTaskId" class="progress-section" style="margin-top: 20px;">
        <el-progress
          :percentage="taskProgress"
          :status="getProgressStatus(taskStatus)"
          :show-text="true"
        />

        <div class="progress-details" style="margin-top: 10px;">
          <p><strong>当前文件:</strong> {{ currentFile || '准备中...' }}</p>
          <p><strong>进度:</strong> {{ processedFiles }}/{{ totalFiles }}</p>
          <p><strong>成功:</strong> {{ successfulFiles }} | <strong>失败:</strong> {{ failedFiles }}</p>
        </div>
      </div>
    </div>

    <template #footer>
      <span class="dialog-footer">
        <el-button :disabled="isProcessing" @click="handleClose">取消</el-button>
        <el-button
          type="primary"
          :loading="isLoading"
          :disabled="isProcessing"
          @click="handleStartCompression"
        >
          {{ isProcessing ? '压缩中...' : '启动压缩' }}
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<style scoped>
.el-form-item__description {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
  margin-top: 4px;
}
</style>
