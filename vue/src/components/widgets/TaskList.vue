<script setup lang="ts">
import type { TranslationTask } from '@/store/translation';

defineProps({
  tasks: {
    type: Array as () => TranslationTask[],
    required: true
  },
  isProcessing: {
    type: Boolean,
    required: true
  }
})

const emit = defineEmits(['remove-task', 'download-task'])

const getTaskStatusText = (status: TranslationTask['status']) => {
  switch (status) {
    case 'pending': return '等待中';
    case 'processing': return '处理中';
    case 'completed': return '已完成';
    case 'error': return '失败';
  }
}

const downloadTask = (task: TranslationTask) => {
  if (task.result) {
    const url = URL.createObjectURL(task.result);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${task.fileName.replace(/\.[^/.]+$/, "")}_translated.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
}
</script>

<template>
  <div>
    <el-empty v-if="tasks.length === 0" description="暂无翻译任务" />
    <div v-else class="task-list">
      <div
        v-for="task in tasks"
        :key="task.id"
        class="task-item"
        :class="{
          'task-processing': task.status === 'processing',
          'task-completed': task.status === 'completed',
          'task-error': task.status === 'error'
        }"
      >
        <div class="task-info">
          <div class="task-name" :title="task.fileName">{{ task.fileName }}</div>
        </div>
        <div class="task-progress" v-if="task.status === 'processing'">
          <el-progress :percentage="task.progress" :show-text="false" />
        </div>
        <div class="task-actions">
          <el-tag v-if="task.status === 'completed'" type="success">完成</el-tag>
          <el-tag v-else-if="task.status === 'error'" type="danger" :title="task.error">失败</el-tag>
          <el-tag v-else-if="task.status === 'processing'" type="warning">处理中</el-tag>
          <el-tag v-else type="info">等待中</el-tag>
          <el-button v-if="task.status === 'completed'" size="small" type="primary" @click="downloadTask(task)">下载</el-button>
          <el-button size="small" type="danger" @click="emit('remove-task', task.id)" :disabled="isProcessing && task.status !== 'pending'">移除</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-list {
  max-height: 600px;
  overflow-y: auto;
}
.task-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-sm);
  border-bottom: 1px solid var(--color-border-subtle);
}
.task-item:last-child {
  border-bottom: none;
}
.task-info {
  flex: 1;
  overflow: hidden;
}
.task-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.task-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}
</style>