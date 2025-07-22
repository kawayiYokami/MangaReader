<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useEnvironment } from '@/composables/useEnvironment'

const { isPyWebView } = useEnvironment()
const sidebarCollapsed = ref(true)
const router = useRouter()
const route = useRoute()

// The active menu is now a computed property based on the current route
const activeMenu = computed(() => route.name)

// Map menu keys to route names
const menuRoutes: { [key: string]: string } = {
  'manga-browser': 'browser',
  'compression': 'compression',
  'cache': 'cache',
  'settings': 'settings', // Placeholder for future route
  // Add other mappings here
}

const handleMenuSelect = (menuKey: string) => {
  const routeName = menuRoutes[menuKey]
  if (routeName) {
    router.push({ name: routeName })
  }
}
</script>

<template>
  <!-- 侧边栏组件 -->
  <div class="sidebar" :class="{ 'collapsed': sidebarCollapsed }">

    <!-- 导航菜单 -->
    <nav class="nav-menu">

      <div class="nav-item" :class="{ active: activeMenu === 'browser' }" @click="handleMenuSelect('manga-browser')">
        <div class="nav-icon"><span class="material-symbols-rounded">menu_book</span></div>
        <span class="nav-text">漫画浏览</span>
      </div>

      <div class="nav-item" :class="{ active: activeMenu === 'compression' }" @click="handleMenuSelect('compression')">
        <div class="nav-icon"><span class="material-symbols-rounded">compress</span></div>
        <span class="nav-text">漫画压缩</span>
      </div>

      <div v-if="isPyWebView" class="nav-item" :class="{ active: activeMenu === 'cache' }" @click="handleMenuSelect('cache')">
        <div class="nav-icon"><span class="material-symbols-rounded">database</span></div>
        <span class="nav-text">缓存管理</span>
      </div>
    </nav>

    <!-- 底部设置 -->
    <div class="nav-footer">
      <div class="nav-item" :class="{ active: activeMenu === 'settings' }" @click="handleMenuSelect('settings')">
        <div class="nav-icon"><span class="material-symbols-rounded">settings</span></div>
        <span class="nav-text">设置</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 
  All styles are currently handled by the global layout.css.
  Scoped styles can be added here if needed for component-specific adjustments.
*/
.material-symbols-rounded {
  font-family: 'Material Symbols Rounded';
  font-weight: normal;
  font-style: normal;
  font-size: 24px;
  line-height: 1;
  letter-spacing: normal;
  text-transform: none;
  display: inline-block;
  white-space: nowrap;
  word-wrap: normal;
  direction: ltr;
  -webkit-font-feature-settings: 'liga';
  font-feature-settings: 'liga';
  -webkit-font-smoothing: antialiased;
}
</style>