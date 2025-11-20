<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps({
  // Type controls the button's appearance
  type: {
    type: String as () => 'primary' | 'text',
    default: 'primary'
  },
  // Loading state shows a spinner and disables the button
  loading: {
    type: Boolean,
    default: false
  },
  // Disabled state prevents interaction
  disabled: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['click'])

const isButtonDisabled = computed(() => props.disabled || props.loading)

const handleClick = (event: MouseEvent) => {
  if (isButtonDisabled.value) {
    event.preventDefault()
    return
  }
  emit('click', event)
}
</script>

<template>
  <button
    :class="['app-button', `app-button--${type}`]"
    :disabled="isButtonDisabled"
    @click="handleClick"
  >
    <span v-if="loading" class="material-symbols-rounded loading-icon">progress_activity</span>
    <span class="button-text">
      <slot />
    </span>
  </button>
</template>

<style scoped>
.app-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease;
  white-space: nowrap;
  user-select: none;
}

/* Primary Button Styles */
.app-button--primary {
  color: #ffffff;
  background-color: var(--color-accent-default);
  border-color: var(--color-accent-default);
}

.app-button--primary:hover {
  background-color: var(--color-accent-hover);
  border-color: var(--color-accent-hover);
}

.app-button--primary:active {
  background-color: var(--color-accent-active);
  border-color: var(--color-accent-active);
}

/* Text Button Styles */
.app-button--text {
  color: var(--color-text-secondary);
  background-color: transparent;
  border-color: transparent;
}

.app-button--text:hover {
  color: var(--color-text-default);
  background-color: rgba(var(--color-text-default-rgb), 0.08);
}

/* Disabled State */
.app-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Loading State */
.loading-icon {
  margin-right: 8px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>