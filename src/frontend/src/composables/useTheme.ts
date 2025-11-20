import { useStorage } from '@vueuse/core'
import { watch } from 'vue'

export type Theme = 'light' | 'dark'

export function useTheme() {
  // 默认主题设置为 'light'
  const theme = useStorage<Theme>('app-theme', 'light')

  const applyTheme = (newTheme: Theme) => {
    const isDark = newTheme === 'dark'
    document.documentElement.classList.toggle('theme-dark', isDark)
    document.documentElement.classList.toggle('theme-light', !isDark)
  }

  // 初始加载时应用一次主题
  applyTheme(theme.value)

  // 监听 theme 的变化并应用
  watch(theme, (newTheme) => {
    applyTheme(newTheme)
  })

  return {
    theme
  }
}