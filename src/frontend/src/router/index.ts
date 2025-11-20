import { createRouter, createWebHashHistory } from 'vue-router'

// Layouts
import AppContainer from '@/components/layout/AppContainer.vue'
import ViewerLayout from '@/components/layout/ViewerLayout.vue'

// Pages
import HomeView from '../pages/HomeView.vue'
import MangaBrowserPage from '../pages/MangaBrowserPage.vue'
import SettingsPage from '../pages/SettingsPage.vue'

import CompressionPage from '../pages/CompressionPage.vue'
import CacheManagementPage from '../pages/CacheManagementPage.vue'
import MangaViewerPage from '../pages/MangaViewerPage.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    // Main application layout
    {
      path: '/',
      component: AppContainer,
      children: [
        { path: '', redirect: '/browser' }, // Redirect root to browser
        {
          path: 'browser',
          name: 'browser',
          component: MangaBrowserPage
        },
        {
          path: 'settings',
          name: 'settings',
          component: SettingsPage
        },
        {
          path: 'compression',
          name: 'compression',
          component: CompressionPage
        },
        {
          path: 'cache',
          name: 'cache',
          component: CacheManagementPage
        },
        {
          path: 'home',
          name: 'home',
          component: HomeView
        }
      ]
    },
    // Viewer layout
    {
      path: '/viewer',
      component: ViewerLayout,
      children: [
        {
          path: '',
          name: 'viewer',
          component: MangaViewerPage
        }
      ]
    }
  ]
})

export default router
