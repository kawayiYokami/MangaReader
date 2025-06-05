# Web 版翻译设置集成计划

**目标**：在 Web 版设置页面中添加翻译设置，包括翻译接口选择、API 密钥配置、模型选择和字体选择，并考虑权限控制。

**步骤**：

1.  **更新 `web/templates/components/pages/settings.html`**：
    *   在现有主题设置卡片下方，添加一个新的 `el-card` 用于“翻译与文本设置”。
    *   在该卡片中，使用 `el-form` 和 `el-form-item` 来构建以下设置项：
        *   **翻译接口**：使用 `el-select` 组件，绑定 `translationSettings.engine`，选项为 "Google" 和 "智谱"。
        *   **服务特定设置**：
            *   根据 `translationSettings.engine` 的值，使用 `v-if` 条件渲染来显示智谱 AI 或 Google 的 API 密钥输入框和模型选择。
            *   智谱 AI：`el-input` 绑定 `translationSettings.zhipuApiKey` (密码类型)，`el-select` 绑定 `translationSettings.zhipuModel`。
            *   Google：`el-input` 绑定 `translationSettings.googleApiKey` (密码类型)。
        *   **文本替换字体**：使用 `el-select` 绑定 `translationSettings.fontName`。选项需要通过后端 API 获取。
    *   **权限控制**：对于所有翻译设置相关的表单项，添加 `v-if="isLocalAccess"` 或 `:disabled="!isLocalAccess"` 属性，确保只有在本地访问时才能进行更改或显示。

2.  **更新 `web/static/js/app-data.js`**：
    *   扩展 `window.AppData.translationSettings` 对象，添加以下属性：
        *   `zhipuApiKey: ''`
        *   `zhipuModel: 'glm-4-flash'` (或根据 `views/settings_interface.py` 中的默认值)
        *   `googleApiKey: ''`
        *   `fontName: ''`
        *   `availableFonts: []` (用于存储字体列表)
    *   移除 `translateTitle`、`simplifyChinese` 和 `webpQuality` 属性。
    *   `isLocalAccess` 变量已经存在，可以直接使用。

3.  **更新 `web/static/js/utils.js`**：
    *   在 `window.UtilsMethods` 中添加一个新的方法 `fetchAvailableFonts()`，用于调用后端 API 获取可用字体列表，并更新 `AppData.availableFonts` 和 `AppData.translationSettings.fontName`。
    *   移除 `clearTranslationCache()` 方法。
    *   添加方法来处理设置项的更改事件（例如 `onTranslatorChange`, `onApiKeyChange`, `onFontChange`），这些方法将调用后端 `/api/settings/{key}` PUT 接口来更新 `config`。

4.  **更新 `web/api/settings.py`**：
    *   添加一个新的 API 接口 `/api/settings/available-fonts` (GET)，用于返回 `font` 目录下所有可用字体的列表，包括它们的显示名称和文件路径，类似于 `TranslationSettingsCard` 中的 `_load_available_fonts` 方法。
    *   移除清空翻译缓存的 API 接口 (如果之前有计划添加的话)。
    *   确保现有的 `/api/settings/{key}` PUT 接口可以正确处理 `translatorType`, `zhipuApiKey`, `zhipuModel`, `googleApiKey`, `fontName` 的更新。
    *   移除 `translateTitle`, `simplifyChinese`, `webpQuality` 相关设置项的获取和更新逻辑。