# Web UI 架构框架

## 🏗️ 整体架构

### 单页面应用 (SPA) 结构
- **文件**: `web/templates/index.html`
- **框架**: Vue 3 + Element Plus
- **路由**: 基于 `activeMenu` 状态的条件渲染
- **主题**: 支持浅色/深色/自动切换

## 📱 4个主要页面

### 1. 首页 (`activeMenu === 'home'`)
```html
<div v-if="activeMenu === 'home'">
```
- **功能**: 欢迎页面，功能介绍
- **特性**: 
  - 远程访问安全提示
  - 功能卡片展示
  - 快速导航按钮

### 2. 漫画浏览 (`activeMenu === 'manga-browser'`)
```html
<div v-else-if="activeMenu === 'manga-browser'">
```
- **功能**: 漫画库管理和浏览
- **特性**:
  - 搜索和标签过滤
  - 缩略图网格显示
  - 添加漫画功能 (仅本地)
  - 标签分类管理

### 3. 漫画翻译 (`activeMenu === 'translation'`)
```html
<div v-else-if="activeMenu === 'translation'">
```
- **功能**: 漫画翻译处理
- **特性**:
  - 文件上传选择
  - 翻译引擎配置
  - 批量处理任务
  - 进度监控

### 4. 缓存管理 (`activeMenu === 'cache'`) - 仅本地访问
```html
<div v-else-if="activeMenu === 'cache'">
```
- **功能**: 各种缓存数据管理
- **特性**:
  - 翻译缓存
  - 和谐词缓存
  - 缓存统计
  - 条目编辑

### 5. 设置页面 (`activeMenu === 'settings'`)
```html
<div v-else-if="activeMenu === 'settings'">
```
- **功能**: 应用配置
- **特性**:
  - 主题切换
  - 外观设置

## 🧭 导航结构

### 侧边栏导航
```html
<div class="sidebar" :class="{ 'collapsed': sidebarCollapsed }">
```

#### 主导航菜单
- 🏠 **首页** (`home`)
- 📚 **漫画浏览** (`manga-browser`)
- 🔤 **漫画翻译** (`translation`)
- 💾 **缓存管理** (`cache`) - 仅本地访问

#### 底部设置
- ⚙️ **设置** (`settings`)

### 汉堡包菜单
- 支持侧边栏折叠/展开
- 折叠时只显示图标

## 🔐 权限控制

### 本地访问 (`isLocalAccess = true`)
- 完整功能访问
- 可添加漫画到库
- 可访问缓存管理
- 支持文件替换操作

### 远程访问 (`isLocalAccess = false`)
- 只读漫画浏览
- 文件上传处理模式
- 隐藏缓存管理
- 安全模式提示

## 🎨 UI设计原则

### 现代扁平设计
- 无阴影，纯色块
- 清晰边界
- 简洁图标 (中文字符)

### 响应式布局
- 网格系统
- 弹性容器
- 移动端适配

### 主题系统
- CSS变量驱动
- 实时切换
- 本地存储

## 📂 文件结构

```
web/
├── templates/
│   └── index.html          # 主SPA文件
├── static/
│   ├── css/
│   │   └── modern-theme.css # 主题样式
│   └── js/
│       └── theme-manager.js # 主题管理
├── api/                    # 后端API
└── app.py                  # FastAPI应用
```

## 🔄 状态管理

### Vue Data 属性
```javascript
data() {
    return {
        activeMenu: 'home',           // 当前页面
        sidebarCollapsed: false,      // 侧边栏状态
        isLocalAccess: true,          // 访问权限
        currentTheme: 'auto',         // 主题设置
        // ... 各页面特定数据
    }
}
```

### 页面切换
```javascript
handleMenuSelect(menu) {
    this.activeMenu = menu;
    // 页面特定初始化逻辑
}
```

## 🚀 扩展指南

### 添加新页面
1. 在导航菜单中添加新项目
2. 添加对应的 `v-else-if` 条件块
3. 实现页面特定的数据和方法
4. 添加必要的API调用

### 修改现有页面
1. 找到对应的条件块
2. 修改HTML结构和Vue逻辑
3. 更新相关的数据属性和方法
4. 测试功能完整性

## 🔧 开发注意事项

### 前端文件处理原则
- 所有文件处理应在前端进行
- 使用 File API、JSZip、Canvas 等
- 减少服务器负担
- 提供实时进度反馈

### API设计原则
- 后端只提供AI服务 (OCR、翻译)
- 避免文件传输
- 使用JSON数据交换
- 支持批量处理

### 用户体验原则
- 极简设计，减少选择
- 自动化常用操作
- 清晰的状态反馈
- 优雅的错误处理
