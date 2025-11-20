import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { compressFile } from '@/api/compression'
import type { ProcessingTask as CompressionTask } from '@/types/tasks.d'

export const useCompressionStore = defineStore('compression', () => {
  // State
  const tasks = ref<CompressionTask[]>([])
  const isProcessing = ref(false)
  const settings = reactive({
    quality: 85,
  })

  // Actions
  function addTask(file: File) {
    const newTask: CompressionTask = {
      id: `${file.name}-${Date.now()}`,
      file,
      fileName: file.name,
      status: 'pending',
      progress: 0,
    };
    tasks.value.push(newTask);
  }

  function removeTask(taskId: string | number) {
    tasks.value = tasks.value.filter(task => task.id !== taskId);
  }

  function clearTasks() {
    if (!isProcessing.value) {
      tasks.value = [];
    }
  }

  async function startCompression() {
    if (isProcessing.value) return;
    isProcessing.value = true;

    for (const task of tasks.value) {
      if (task.status === 'pending') {
        try {
          task.status = 'processing';
          task.progress = 50; // Simulate progress
          const resultBlob = await compressFile(task.file, { quality: settings.quality });
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
    startCompression,
  }
})