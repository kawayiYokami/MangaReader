# 漫画翻译工具 - Electron桌面版

基于现有Web版本开发的Electron桌面应用，提供本地文件系统访问和更好的用户体验。

## 🎯 项目特点

- **高代码复用率**: 前端代码100%复用，后端代码95%复用
- **本地文件系统权限**: 直接文件选择、原地替换、批量处理
- **组件化架构**: 低耦合、高内聚的模块化设计
- **跨平台支持**: Windows、macOS、Linux

## 📁 项目结构

```
electron-app/
├── src/main/                  # 主进程
│   ├── main.js               # 应用入口
│   ├── preload.js            # 预加载脚本
│   └── components/           # 主进程组件
│       ├── PythonServiceManager.js
│       ├── FileSystemAPI.js
│       ├── WindowManager.js
│       └── IPCHandler.js
├── renderer/                 # 渲染进程
│   ├── index.html           # 测试页面
│   └── js/adapters/         # 适配器层
│       ├── EnvironmentDetector.js
│       ├── FileAPIAdapter.js
│       ├── ElectronBridge.js
│       └── AdapterManager.js
├── design/                   # 设计文档
│   └── component-architecture.md
├── package.json             # 项目配置
├── test-electron.js         # 简化测试启动脚本
└── README.md               # 本文件
```

## 🛠️ 环境要求

### 必需环境
- **Node.js**: >= 16.0.0
- **npm**: >= 8.0.0
- **Python**: >= 3.8 (用于后端服务)
- **uv**: Python包管理器

### 开发工具
- **Electron**: ^22.0.0
- **electron-builder**: ^23.0.0 (用于打包)

## 🚀 快速开始

### 1. 安装Node.js
从 [Node.js官网](https://nodejs.org/) 下载并安装Node.js 16+

### 2. 安装依赖
```bash
cd electron-app
npm install
```

### 3. 测试基础功能（不含Python服务）
```bash
# 使用简化测试脚本
npm run test

# 或者直接运行
node test-electron.js
```

### 4. 完整功能测试（含Python服务）
```bash
# 确保Python后端可用
cd ../
python web_main.py --port 8080

# 在另一个终端启动Electron
cd electron-app
npm start
```

## 🧩 架构设计

### 主进程组件
- **PythonServiceManager**: 管理Python后端服务生命周期
- **FileSystemAPI**: 提供文件系统操作接口
- **WindowManager**: 管理应用窗口和菜单
- **IPCHandler**: 处理进程间通信

### 渲染进程适配层
- **EnvironmentDetector**: 检测运行环境（Electron/Web）
- **FileAPIAdapter**: 统一文件操作接口
- **ElectronBridge**: Electron功能桥接
- **AdapterManager**: 统一管理所有适配器

### 通信机制
- 主进程 ↔ 渲染进程: IPC通信
- 渲染进程 ↔ Python后端: HTTP API
- 安全隔离: contextIsolation + preload script

## 📋 开发脚本

```bash
# 开发模式启动
npm run dev

# 生产模式启动
npm start

# 简化测试（无Python服务）
npm run test

# 构建应用
npm run build

# 跨平台构建
npm run build-win    # Windows
npm run build-mac    # macOS
npm run build-linux  # Linux
```

## 🔧 配置说明

### package.json关键配置
- **main**: `src/main/main.js` - 主进程入口
- **scripts**: 开发和构建脚本
- **build**: electron-builder配置

### 安全配置
- **nodeIntegration**: false
- **contextIsolation**: true
- **enableRemoteModule**: false
- **preload**: 安全的API暴露

## 🧪 测试功能

### 基础功能测试
1. 环境检测
2. 适配器初始化
3. 文件选择API
4. 系统通知
5. 进度条显示

### 完整功能测试
1. Python服务集成
2. 漫画翻译功能
3. 文件压缩功能
4. 缓存管理
5. 原地文件替换

## 🚨 故障排除

### 常见问题

#### 1. Node.js未安装
```bash
# 检查Node.js版本
node --version
npm --version

# 如果未安装，请从官网下载安装
```

#### 2. Python服务启动失败
```bash
# 检查Python环境
python --version
uv --version

# 确保在正确目录启动
cd ../
python web_main.py --port 8080
```

#### 3. Electron应用无法启动
```bash
# 重新安装依赖
rm -rf node_modules package-lock.json
npm install

# 检查preload脚本路径
# 确保src/main/preload.js存在
```

#### 4. 文件选择功能不工作
- 检查是否在Electron环境中运行
- 查看开发者工具控制台错误信息
- 确认IPC通信正常

## 📝 开发注意事项

### 代码复用策略
1. **前端组件**: 直接复制Web版本的Vue组件
2. **API适配**: 通过适配器层统一接口
3. **环境检测**: 自动适配Electron/Web环境

### 安全考虑
1. **禁用Node集成**: 防止安全漏洞
2. **上下文隔离**: 隔离主世界和隔离世界
3. **预加载脚本**: 安全地暴露API

### 性能优化
1. **懒加载**: 按需加载组件
2. **进程分离**: 主进程专注系统集成
3. **异步操作**: 避免阻塞UI线程

## 🔄 下一步计划

1. **复制Web UI资源**: 将现有Vue组件集成到Electron
2. **API适配**: 修改前端代码以使用适配器
3. **功能测试**: 验证所有功能正常工作
4. **性能优化**: 优化启动速度和内存使用
5. **打包发布**: 配置跨平台构建和分发

## 📞 支持

如果遇到问题，请检查：
1. 控制台错误信息
2. Python服务日志
3. Electron开发者工具
4. 本README的故障排除部分

---

**开发状态**: 基础架构完成，等待Node.js环境安装后进行测试
