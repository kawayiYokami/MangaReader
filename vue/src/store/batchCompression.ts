import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getBatchCompressionStatus, cancelBatchCompression } from '@/api/manga'
import type { BatchCompressionTask } from '@/types/batchCompression'

export const useBatchCompressionStore = defineStore('batchCompression', () => {
  const tasks = ref<Record<string, BatchCompressionTask>>({})
  const activeTaskIds = ref<string[]>([])
  const pollingIntervals = ref<Record<string, number>>({})

  // Actions
  function addTask(taskId: string, initialTask: Omit<BatchCompressionTask, 'task_id'>) {
    tasks.value[taskId] = {
      ...initialTask,
      task_id: taskId
    }
    activeTaskIds.value.push(taskId)
  }

  function updateTask(taskId: string, statusData: any) {
    if (tasks.value[taskId]) {
      tasks.value[taskId] = {
        ...tasks.value[taskId],
        ...statusData
      }
    }
  }

  function removeTask(taskId: string) {
    delete tasks.value[taskId]
    activeTaskIds.value = activeTaskIds.value.filter(id => id !== taskId)
    stopPolling(taskId)
  }

  function stopPolling(taskId: string) {
    if (pollingIntervals.value[taskId]) {
      clearInterval(pollingIntervals.value[taskId])
      delete pollingIntervals.value[taskId]
    }
  }

  function startPolling(taskId: string) {
    // 停止已有轮询
    stopPolling(taskId)

    // 开始新的轮询
    pollingIntervals.value[taskId] = window.setInterval(async () => {
      try {
        const status = await getBatchCompressionStatus(taskId)
        updateTask(taskId, status)

        // 如果任务完成，停止轮询
        if (status.status === 'completed' || status.status === 'cancelled' || status.status === 'failed') {
          stopPolling(taskId)
        }
      } catch (error) {
        console.error(`轮询任务 ${taskId} 状态失败:`, error)
        stopPolling(taskId)
      }
    }, 2000) // 每2秒更新一次
  }

  async function cancelTask(taskId: string) {
    try {
      await cancelBatchCompression(taskId)
      // 服务器会更新状态，轮询会自动获取到新状态
      return true
    } catch (error) {
      console.error(`取消任务 ${taskId} 失败:`, error)
      return false
    }
  }

  // Computed
  const getTask = computed(() => (taskId: string) => tasks.value[taskId])

  const getActiveTasks = computed(() => () => {
    return activeTaskIds.value.map(id => tasks.value[id]).filter(Boolean)
  })

  return {
    tasks,
    activeTaskIds,
    addTask,
    updateTask,
    removeTask,
    startPolling,
    stopPolling,
    cancelTask,
    getTask,
    getActiveTasks
  }
})
