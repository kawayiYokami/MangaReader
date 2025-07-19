<script setup lang="ts">
import { useTranslationStore } from '@/store/translation'
import { storeToRefs } from 'pinia'
import FileUpload from '@/components/widgets/FileUpload.vue'
import TaskList from '@/components/widgets/TaskList.vue'
import OperationCard from '@/components/widgets/OperationCard.vue'

const translationStore = useTranslationStore()
const { tasks, isProcessing, settings } = storeToRefs(translationStore)

const handleFilesSelected = (files: File[]) => {
  files.forEach(file => translationStore.addTask(file))
}
</script>

<template>
  <div class="translation-interface">
    <div class="translation-layout">
      <!-- Left Panel -->
      <div class="translation-control">
        <el-card>
          <template #header><span>文件选择</span></template>
          <FileUpload @files-selected="handleFilesSelected" />
        </el-card>

        <el-card style="margin-top: 16px;">
          <template #header><span>翻译设置</span></template>
          <el-form label-width="80px">
            <el-form-item label="目标语言">
              <el-select v-model="settings.targetLang" style="width: 100%">
                <el-option label="简体中文" value="zh-CN"></el-option>
              </el-select>
            </el-form-item>
          </el-form>
        </el-card>

        <OperationCard
          title="开始翻译"
          :loading="isProcessing"
          :disabled="tasks.length === 0 || isProcessing"
          @start="translationStore.startTranslation"
          @clear="translationStore.clearTasks"
          style="margin-top: 16px;"
        />
      </div>

      <!-- Right Panel -->
      <div class="translation-tasks">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span>翻译任务</span>
              <span>{{ tasks.length }} 个任务</span>
            </div>
          </template>
          <TaskList :tasks="tasks" :is-processing="isProcessing" @remove-task="translationStore.removeTask" />
        </el-card>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Layout styles are now handled globally in page-layouts.css */
</style>