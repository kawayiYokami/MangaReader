<script setup lang="ts">
import AppButton from './AppButton.vue';

defineProps({
  title: {
    type: String,
    required: true
  },
  loading: {
    type: Boolean,
    default: false
  },
  disabled: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['start', 'clear'])
</script>

<template>
  <el-card>
    <template #header><span>操作</span></template>
    <div class="button-group">
      <AppButton
        type="primary"
        :disabled="disabled"
        :loading="loading"
        @click="emit('start')"
      >
        {{ title }}
      </AppButton>
      <AppButton
        type="text"
        :disabled="disabled"
        @click="emit('clear')"
      >
        清空任务
      </AppButton>
    </div>
  </el-card>
</template>

<style scoped>
.button-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>