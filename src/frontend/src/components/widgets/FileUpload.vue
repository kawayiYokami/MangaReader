<script setup lang="ts">
import { ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'

const emit = defineEmits(['files-selected'])

const fileInput = ref<HTMLInputElement | null>(null)
const dragOver = ref(false)

const triggerFileSelect = () => {
  fileInput.value?.click()
}

const handleFileSelect = (event: Event) => {
  const files = (event.target as HTMLInputElement).files
  if (files) {
    emit('files-selected', Array.from(files))
  }
}

const handleDrop = (event: DragEvent) => {
  dragOver.value = false
  const files = event.dataTransfer?.files
  if (files) {
    emit('files-selected', Array.from(files))
  }
}
</script>

<template>
  <div class="file-selection">
    <div
      class="upload-area upload-area-themed"
      :class="{ dragover: dragOver }"
      @click="triggerFileSelect"
      @dragover.prevent="dragOver = true"
      @dragleave.prevent="dragOver = false"
      @drop.prevent="handleDrop"
    >
      <el-icon size="48">
        <upload-filled />
      </el-icon>
      <h3>拖拽文件到此处，或点击选择文件</h3>
      <p>支持 ZIP、CBZ 格式的漫画文件</p>
      <input
        ref="fileInput"
        type="file"
        multiple
        accept=".zip,.cbz"
        style="display: none;"
        @change="handleFileSelect"
      />
    </div>
  </div>
</template>

<style scoped>
.upload-area {
  border: 2px dashed var(--color-border-default);
  border-radius: var(--border-radius);
  padding: var(--spacing-xl);
  text-align: center;
  cursor: pointer;
  transition: background-color var(--transition);
}
.upload-area.dragover {
  background-color: var(--color-bg-elevated);
  border-color: var(--color-accent-default);
}
.upload-area h3 {
  margin: var(--spacing-md) 0 var(--spacing-sm);
}
.upload-area p {
  color: var(--color-text-secondary);
  margin: 0;
}
</style>