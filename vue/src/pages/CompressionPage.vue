<script setup lang="ts">
import { useCompressionStore } from '@/store/compression'
import { storeToRefs } from 'pinia'
import FileUpload from '@/components/widgets/FileUpload.vue'
import TaskList from '@/components/widgets/TaskList.vue'
import OperationCard from '@/components/widgets/OperationCard.vue'

const compressionStore = useCompressionStore()
const { tasks, isProcessing, settings } = storeToRefs(compressionStore)

const handleFilesSelected = (files: File[]) => {
  files.forEach(file => compressionStore.addTask(file))
}
</script>

<template>
  <div class="compression-interface">
    <div class="processing-layout">
      <!-- Left Panel -->
      <div class="processing-controls">
        <el-card>
          <template #header><span>文件选择</span></template>
          <FileUpload @files-selected="handleFilesSelected" />
        </el-card>

        <el-card style="margin-top: 16px;">
          <template #header><span>压缩设置</span></template>
          <el-form label-width="80px">
            <el-form-item label="WebP质量">
              <el-slider v-model="settings.quality" :min="50" :max="100" :step="5" show-input />
            </el-form-item>
          </el-form>
        </el-card>

        <OperationCard
          title="开始压缩"
          :loading="isProcessing"
          :disabled="tasks.length === 0 || isProcessing"
          style="margin-top: 16px;"
          @start="compressionStore.startCompression"
          @clear="compressionStore.clearTasks"
        />
      </div>

      <!-- Right Panel -->
      <div class="processing-tasks">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span>压缩任务</span>
              <span>{{ tasks.length }} 个任务</span>
            </div>
          </template>
          <TaskList :tasks="tasks" :is-processing="isProcessing" task-type="compressed" @remove-task="compressionStore.removeTask" />
        </el-card>
      </div>
    </div>
  </div>
</template>

<style scoped>
.processing-layout {
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 16px;
  padding: 16px;
}

.processing-controls {
  display: flex;
  flex-direction: column;
}

.processing-tasks {
  min-width: 0;
}
</style>