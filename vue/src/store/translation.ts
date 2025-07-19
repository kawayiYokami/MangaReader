import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { translateFile } from '@/api/translation'

export interface TranslationTask {
  id: string;
  file: File;
  fileName: string;
  status: 'pending' | 'processing' | 'completed' | 'error';
  progress: number;
  error?: string;
  result?: Blob;
}

export const useTranslationStore = defineStore('translation', () => {
  // State
  const tasks = ref<TranslationTask[]>([])
  const isProcessing = ref(false)
  const settings = reactive({
    targetLang: 'zh-CN',
  })

  // Actions
  function addTask(file: File) {
    const newTask: TranslationTask = {
      id: `${file.name}-${Date.now()}`,
      file,
      fileName: file.name,
      status: 'pending',
      progress: 0,
    };
    tasks.value.push(newTask);
  }

  function removeTask(taskId: string) {
    tasks.value = tasks.value.filter(task => task.id !== taskId);
  }

  function clearTasks() {
    if (!isProcessing.value) {
      tasks.value = [];
    }
  }

  async function startTranslation() {
    if (isProcessing.value) return;
    isProcessing.value = true;

    for (const task of tasks.value) {
      if (task.status === 'pending') {
        try {
          task.status = 'processing';
          task.progress = 50; // Simulate progress
          const resultBlob = await translateFile(task.file, { targetLang: settings.targetLang });
          task.progress = 100;
          task.status = 'completed';
          task.result = resultBlob;
        } catch (e) {
          task.status = 'error';
          task.error = e instanceof Error ? e.message : 'Unknown error';
        }
      }
    }

    isProcessing.value = false;
  }

  return {
    tasks,
    isProcessing,
    settings,
    addTask,
    removeTask,
    clearTasks,
    startTranslation,
  }
})