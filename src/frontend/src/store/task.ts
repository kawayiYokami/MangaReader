// vue/src/store/task.ts
import { defineStore } from 'pinia';
import { ref, readonly } from 'vue';

export type TaskStatus = 'idle' | 'processing' | 'success' | 'error';

export interface Task {
  id: string;
  status: TaskStatus;
  progress: number;
  message: string;
  startTime: number;
  endTime?: number;
}

export const useTaskStore = defineStore('task', () => {
  const tasks = ref<Record<string, Task>>({});

  function startTask(id: string, message: string = '任务已开始...'): void {
    tasks.value[id] = {
      id,
      status: 'processing',
      progress: 0,
      message,
      startTime: Date.now(),
    };
  }

  function updateTaskProgress(id: string, progress: number, message?: string): void {
    if (tasks.value[id]) {
      tasks.value[id].progress = progress;
      if (message) {
        tasks.value[id].message = message;
      }
    }
  }

  function completeTask(id: string, message: string = '任务已完成'): void {
    if (tasks.value[id]) {
      tasks.value[id].status = 'success';
      tasks.value[id].progress = 100;
      tasks.value[id].message = message;
      tasks.value[id].endTime = Date.now();
    }
  }

  function failTask(id: string, message: string = '任务失败'): void {
    if (tasks.value[id]) {
      tasks.value[id].status = 'error';
      tasks.value[id].message = message;
      tasks.value[id].endTime = Date.now();
    }
  }

  function removeTask(id: string): void {
    delete tasks.value[id];
  }

  return {
    tasks: readonly(tasks),
    startTask,
    updateTaskProgress,
    completeTask,
    failTask,
    removeTask,
  };
});