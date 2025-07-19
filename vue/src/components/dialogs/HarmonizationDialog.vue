<template>
  <el-dialog
    :model-value="visible"
    :title="title"
    width="500px"
    @update:model-value="$emit('update:visible', $event)"
  >
    <el-form label-position="top">
      <el-form-item label="原文">
        <el-input v-model="internalOriginalText" :disabled="isEditing" />
      </el-form-item>
      <el-form-item label="和谐后文本">
        <el-input v-model="internalHarmonizedText" />
      </el-form-item>
    </el-form>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="$emit('update:visible', false)">取消</el-button>
        <el-button type="primary" @click="handleConfirm">
          确认
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watchEffect } from 'vue';

const props = defineProps({
  visible: Boolean,
  title: String,
  isEditing: Boolean,
  originalText: String,
  harmonizedText: String,
});

const emit = defineEmits(['update:visible', 'confirm']);

const internalOriginalText = ref('');
const internalHarmonizedText = ref('');

watchEffect(() => {
  internalOriginalText.value = props.originalText || '';
  internalHarmonizedText.value = props.harmonizedText || '';
});

const handleConfirm = () => {
  emit('confirm', {
    originalText: internalOriginalText.value,
    harmonizedText: internalHarmonizedText.value,
  });
};
</script>