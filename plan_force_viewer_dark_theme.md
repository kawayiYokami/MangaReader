# 计划：强制漫画查看器 (iframe) 使用固定深色主题并与父页面解耦

**目标:** 使漫画查看器 (`viewer.html`，在 iframe 中加载) 始终以深色主题显示，不受父页面主题设置的影响，并且初始加载时即为深色。

**涉及文件:**

1.  `web/templates/viewer.html` (iframe 内容)
2.  `web/static/js/manga-browser.js` (父页面，控制 iframe 加载和交互)
3.  `web/static/css/modern-theme.css` (提供深色主题的 CSS 变量，此文件本身无需修改)

**步骤:**

## 第一部分: 修改 `viewer.html` (iframe 端)

**目标:** 使 `viewer.html` 初始加载为深色，并移除其接收和应用父页面主题同步的逻辑。

1.  **设置 HTML 标签为深色模式:**
    *   打开文件: `web/templates/viewer.html`
    *   修改第 2 行的 `<html>` 标签，从：
        ```html
        <html lang="zh-CN">
        ```
        修改为：
        ```html
        <html lang="zh-CN" class="theme-dark" data-theme="dark">
        ```
    *   **理由:** 这将使得 `viewer.html` 在 CSS 解析时立即应用 `modern-theme.css` 中为 `html.theme-dark` 定义的深色主题变量。

2.  **移除主题同步相关的 JavaScript 代码:**
    *   在 `web/templates/viewer.html` 的 `<script>` 部分 (Vue app 定义内):
        *   **删除 `initThemeMessageListener` 函数定义:** 找到并删除整个 `function initThemeMessageListener() { ... }` 代码块 (原大致在第 230-238 行)。
        *   **删除 `applyCSSVars` 函数定义:** 找到并删除整个 `function applyCSSVars(vars) { ... }` 代码块 (原大致在第 240-247 行)。
        *   **删除 `onMounted` 钩子中对监听器的调用:** 在 `onMounted` 函数内部，找到并删除 `initThemeMessageListener();` 这一行代码 (原大致在第 251 行)。
    *   **理由:** 这些函数用于接收和应用父页面通过 `postMessage` 发送的主题变量。删除它们可以确保 `viewer.html` 不再响应父页面的主题同步尝试。
    *   **(推荐) 添加代码注释:** 在删除上述 JavaScript 代码的位置，添加注释说明修改原因，例如：
        ```javascript
        // Removed theme message listener (initThemeMessageListener) and applyCSSVars function.
        // This viewer is intentionally set to always use a dark theme (via <html class="theme-dark">)
        // and does not sync with or inherit theme from the parent page.
        ```

## 第二部分: 修改 `manga-browser.js` (父页面端)

**目标:** 移除父页面向 `viewer.html` iframe 推送主题变量的行为。

1.  **移除 `syncThemeToIframe` 函数及其调用:**
    *   打开文件: `web/static/js/manga-browser.js`
    *   **删除 `syncThemeToIframe` 函数定义:** 找到并删除整个 `syncThemeToIframe() { ... }` 函数代码块 (原大致在第 183-217 行)。
    *   **删除对 `syncThemeToIframe` 函数的调用:** 找到并删除以下代码块 (原大致在第 177-179 行):
        ```javascript
        // setTimeout(() => {
        //     this.syncThemeToIframe();
        // }, 200);
        ```
    *   **理由:** 此函数及其调用负责从父页面收集当前主题变量并通过 `postMessage` 发送给 `viewer.html` iframe。删除它们可以彻底阻止父页面尝试同步主题到查看器。
    *   **(推荐) 添加代码注释:** 在删除上述 JavaScript 代码的位置，添加注释说明修改原因，例如：
        ```javascript
        // Where syncThemeToIframe function definition was:
        // Removed syncThemeToIframe function.
        // The viewer.html iframe is now intentionally set to always use a dark theme
        // and no longer syncs with the parent page's theme.

        // Where the call to syncThemeToIframe was:
        // Removed call to syncThemeToIframe.
        // Viewer iframe theme is now independent.
        ```

**预期结果:**

*   漫画查看器 (`viewer.html`) 在加载时将立即显示为深色主题。
*   漫画查看器的主题将固定为深色，不会随父页面主题的切换而改变。
*   父页面的主题切换功能将保持正常，不受此修改影响。
*   代码更加解耦，`viewer.html` 的外观独立于父页面。

**潜在风险与缓解:**

*   **极低风险**: 如果 `web/static/css/viewer.css` 中有样式依赖于某些只能通过原 `postMessage` 机制传递的、非标准的、动态计算的 CSS 变量，则这部分特定样式可能显示不正确。但从分析来看，传递的都是标准核心主题变量，`modern-theme.css` 已提供这些变量的深色版本。
*   **维护**: 清晰的代码注释和（如果项目有）更新相关文档，有助于未来开发者理解此设计决策。