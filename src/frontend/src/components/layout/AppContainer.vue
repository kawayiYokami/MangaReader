<script setup lang="ts">
import Sidebar from './Sidebar.vue'
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="app-container">
    <!-- 主要内容区域 -->
    <div class="main-content">
      <!-- 侧边栏 -->
      <Sidebar />

      <!-- 内容区域 (由路由控制) -->
      <div class="content-area">
        <RouterView />
      </div>
    </div>

    <!-- 
      漫画查看器将在后续步骤中实现
      <div v-if="showMangaViewer" class="manga-viewer-overlay">
        ...
      </div> 
    -->
  </div>
</template>

<style scoped>
/* Styles are handled by global layout.css */
</style>