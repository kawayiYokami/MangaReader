<script setup lang="ts">
import { ref, reactive, watch } from 'vue';
import type { PropType } from 'vue';
import { ElMessage } from 'element-plus';
import { useTaskStore } from '@/store/task';
import type { BatchCompressOptions } from '@/api/manga';
import { startBatchCompression } from '@/api/manga';
import { useCacheStore } from '@/store/cache';

const props = defineProps<{
  visible: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
}>();

const taskStore = useTaskStore();
const cacheStore = useCacheStore();
const isLoading = ref(false);
const isProcessing = ref(false);
const results = ref<any | null>(null);

const options = reactive<BatchCompressOptions>({
  webp_quality: 85,
  min_compression_ratio: 0.25,
  preserve_original_names: true,
});

const resetDialog = () => {
  isLoading.value = false;
  isProcessing.value = false;
  results.value = null;
};

watch(() => props.visible, (newValue) => {
  if (newValue) {
    resetDialog();
  }
});

const handleStartCompression = async () => {
  isLoading.value = true;
  isProcessing.value = true;
  results.value = null;

  try {
    const response = await startBatchCompression(options);
    taskStore.startTask(response.task_id, '批量压缩');
    ElMessage.success('批量压缩任务已启动，请稍后查看结果。');
    emit('update:visible', false);
    // You might want a global task monitor UI to see the progress
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
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="批量压缩漫画缓存"
    width="500px"
    @update:model-value="$emit('update:visible', $event)"
    :before-close="handleClose"
    @closed="resetDialog"
    destroy-on-close
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
      </el-form>
    </div>

    <template #footer>
      <span class="dialog-footer">
        <el-button @click="handleClose" :disabled="isProcessing">取消</el-button>
        <el-button type="primary" @click="handleStartCompression" :loading="isLoading">
          启动压缩
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