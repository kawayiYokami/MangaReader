# 统一应用样式层级计划

**目标：** 解决漫画浏览页面主题色未正确应用的问题，并通过建立一个涵盖颜色、排版、间距、圆角、边框等属性的统一样式层级，提升应用整体的视觉一致性和可维护性。

**背景：**
在漫画浏览页面，部分元素（如搜索框、标签）在深色主题下显示不协调。初步分析表明，这可能是由于 Element Plus 组件默认样式未完全适配主题，以及现有 CSS 样式定义可能缺乏统一的层级和变量使用。

**计划步骤：**

1.  **分析现有样式变量和值：**
    *   仔细审查 [`web\static\css\modern-theme.css`](web/static/css/modern-theme.css) 和 [`web\static\css\viewer.css`](web/static/css/viewer.css) 中定义的所有 CSS 变量以及硬编码的样式值。
    *   识别出所有与颜色、字体大小、字重、间距、圆角、边框等相关的样式定义，理解它们当前的用途和命名约定。

2.  **设计统一的样式层级和变量命名方案：**
    *   提出一个全面、结构化且语义化的 CSS 变量命名方案，涵盖以下方面：
        *   **颜色：** 定义背景色、文字颜色、边框颜色、强调色等不同层级的颜色变量，并为浅色和深色模式分别设置值（例如：`--color-bg-default`, `--color-text-primary`, `--color-border-base`, `--color-accent`）。
        *   **排版：** 定义基础字体大小、不同层级的标题字号、辅助文本字号等，以及不同的字重变量（例如：`--font-size-base`, `--font-size-lg`, `--font-weight-bold`）。
        *   **间距：** 定义一系列用于内外边距的间距变量，形成一个比例系统（例如：`--spacing-xs`, `--spacing-sm`, `--spacing-md`, `--spacing-lg`）。
        *   **圆角：** 定义不同大小的圆角变量（例如：`--border-radius-sm`, `--border-radius-md`）。
        *   **边框：** 定义基础边框样式和颜色变量（例如：`--border-width`, `--border-style`, `--border-color-base`）。
    *   确保变量命名清晰、一致，易于理解和使用。

3.  **重构主题 CSS 文件：**
    *   修改 [`web\static\css\modern-theme.css`](web/static/css/modern-theme.css)，用新的统一样式变量替换现有的硬编码值和旧的变量。
    *   确保浅色和深色模式都使用这套新的变量体系。

4.  **应用统一样式到漫画浏览页面：**
    *   更新漫画浏览页面相关的 CSS 规则（主要在 [`web\static\css\modern-theme.css`](web/static/css/modern-theme.css) 中，也可能涉及其他相关 CSS 文件），确保页面中的自定义元素和 Element Plus 组件（如 `el-input`, `el-tag`, `el-card`, `el-tabs` 等）都使用新的统一样式变量来定义其外观。
    *   这将解决截图中的主题色不一致问题，并提升整体视觉一致性。

5.  **应用统一样式到漫画查看页面（可选但强烈推荐）：**
    *   为了保持整个应用的设计一致性，将新的统一样式变量应用到漫画查看页面的 CSS 文件 [`web\static\css\viewer.css`](web/static/css/viewer.css) 中。

6.  **验证修改：**
    *   在浏览器中全面测试漫画浏览页面和查看页面，检查所有样式属性在浅色和深色模式下是否正确、一致地应用。

**实施：**
在您批准计划并确认写入 Markdown 文件后，将切换到 Code 模式进行具体的代码修改。