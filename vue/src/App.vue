<script setup lang="ts">
import { useTheme } from '@/composables/useTheme'

// Initialize the theme management globally
useTheme()
</script>

<template>
  <router-view v-slot="{ Component }">
    <transition name="fade" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
</template>

<style>
/* Base styles are imported in main.ts. This style block can be removed or used for truly global, app-level styles if needed. */

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
