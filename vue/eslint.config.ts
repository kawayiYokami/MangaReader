import tseslint from 'typescript-eslint'
import eslintPluginVue from 'eslint-plugin-vue'
import vueParser from 'vue-eslint-parser'
import eslintConfigPrettier from 'eslint-config-prettier'

/**
 * This configuration file is manually crafted to avoid issues with the
 * helper functions (`tseslint.config`, `defineConfigWithVueTs`) which have
 * proven to have incompatible or broken type definitions in this project's
 * dependency environment.
 *
 * This is a standard ESLint Flat Config array.
 */
export default [
  // 1. Global Ignores - MUST be the first element
  {
    ignores: ['**/dist/**', '**/dist-ssr/**', '**/coverage/**'],
  },

  // 2. Vue Recommended Rules
  ...eslintPluginVue.configs['flat/recommended'],

  // 3. TypeScript Recommended Rules
  ...tseslint.configs.recommended,

  // 4. Custom override for Vue files to ensure the TS parser is used correctly
  {
    files: ['**/*.vue'],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: tseslint.parser,
        sourceType: 'module',
      },
    },
  },

  // 5. Prettier config to disable formatting rules
  eslintConfigPrettier,
]
