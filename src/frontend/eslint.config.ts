import eslint from '@eslint/js'
import tseslint from 'typescript-eslint'
import pluginVue from 'eslint-plugin-vue'
import eslintConfigPrettier from 'eslint-config-prettier'
import globals from 'globals'

export default [
  {
    ignores: ['dist/**', '**/dist-ssr/**', '**/coverage/**', '**/node_modules/**']
  },
  
  eslint.configs.recommended,
  
  ...tseslint.configs.recommended,
  
  ...pluginVue.configs['flat/recommended'],
  
  {
    files: ['**/*.vue', '**/*.ts'],
    languageOptions: {
      parserOptions: {
        parser: tseslint.parser,
        ecmaVersion: 'latest',
        sourceType: 'module'
      },
      globals: {
        ...globals.browser,
        ...globals.node
      }
    },
    rules: {
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': 'error',
      'no-unused-vars': 'off',
      'no-undef': 'off',
      'vue/multi-word-component-names': 'off'
    }
  },
  
  eslintConfigPrettier
]
