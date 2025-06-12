# 缓存系统优化方案 V4.0

此方案旨在修复分页显示与列表内容不一致的Bug，并通过将过滤逻辑统一到后端来优化整体代码架构。

## 第一部分: 后端 API 强化 (`web/api/cache.py`)

**目标**: 改造API，使其能通过明确的布尔参数接收过滤指令，而不是依赖解析搜索字符串。

### 1. 修改 `CacheHandler` 抽象基类

-   **文件**: `web/api/cache.py`
-   **位置**: 第 `67` 行
-   **操作**: 修改 `get_entries` 的定义，使其可以接受任意数量的关键字参数，为后续扩展提供便利。
    -   **旧代码**:
        ```python
        async def get_entries(self, page: int, page_size: int, search: Optional[str] = None) -> Dict[str, Any]:
        ```
    -   **新代码**:
        ```python
        async def get_entries(self, page: int, page_size: int, search: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        ```

### 2. 修改 `get_cache_entries` API 路由

-   **文件**: `web/api/cache.py`
-   **位置**: 第 `977` 行
-   **操作**: 添加 `filter_sensitive` 和 `show_unlikely` 作为可选的布尔查询参数，并将所有过滤参数打包传递给处理器。
    -   **旧代码**:
        ```python
        @router.get("/{cache_type}/entries")
        async def get_cache_entries(
            cache_type: str,
            page: int = 1,
            page_size: int = 20,
            search: Optional[str] = None
        ):
            try:
                # ...
                handler = CacheHandlerFactory.get_handler(cache_type)
                result = await handler.get_entries(page, page_size, search)
                return result
            #...
        ```
    -   **新代码**:
        ```python
        @router.get("/{cache_type}/entries")
        async def get_cache_entries(
            cache_type: str,
            page: int = 1,
            page_size: int = 20,
            search: Optional[str] = None,
            filter_sensitive: bool = False,
            show_unlikely: bool = False
        ):
            """获取指定缓存类型的条目列表（分页、搜索和过滤）"""
            try:
                # 确保参数类型正确
                page = int(page) if isinstance(page, str) else page
                page_size = int(page_size) if isinstance(page_size, str) else page_size
        
                handler = CacheHandlerFactory.get_handler(cache_type)
                
                # 将过滤参数打包
                filter_kwargs = {
                    "filter_sensitive": filter_sensitive,
                    "show_unlikely": show_unlikely
                }
                
                result = await handler.get_entries(page, page_size, search, **filter_kwargs)
                return result
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                log.error(f"获取 {cache_type} 缓存条目失败: {e}")
                raise HTTPException(status_code=500, detail=f"获取缓存条目失败: {e}")
        ```

### 3. 重构 `TranslationCacheHandler`

-   **文件**: `web/api/cache.py`
-   **位置**: 第 `448` 行
-   **操作**: 修改 `get_entries` 方法，使用新的 `filter_sensitive` 参数，并移除旧的字符串解析逻辑。
    -   **新代码 (替换原函数)**:
        ```python
        async def get_entries(self, page: int, page_size: int, search: Optional[str] = None, **kwargs) -> Dict[str, Any]:
            """获取翻译缓存条目"""
            try:
                all_entries = self.manager.get_all_entries_for_display() if hasattr(self.manager, 'get_all_entries_for_display') else []
                filter_sensitive = kwargs.get("filter_sensitive", False)
        
                # 1. 应用敏感内容筛选
                if filter_sensitive:
                    all_entries = [entry for entry in all_entries if entry.get("is_sensitive", False)]
        
                # 2. 应用文本搜索过滤
                if search:
                    query = search.lower()
                    all_entries = [
                        entry for entry in all_entries
                        if query in str(entry.get("cache_key", "")).lower() or \
                           query in str(entry.get("original_text", "")).lower() or \
                           query in str(entry.get("translated_text", "")).lower()
                    ]
        
                # 3. 分页
                total = len(all_entries)
                start = (page - 1) * page_size
                end = start + page_size
                page_entries = all_entries[start:end]
        
                # 4. 格式化条目
                entries = [self._format_translation_entry(entry) for entry in page_entries]
        
                return {
                    "entries": entries,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
                    "filter_applied": "sensitive" if filter_sensitive else None
                }
            except Exception as e:
                self.log.error(f"获取翻译缓存条目失败: {e}")
                raise HTTPException(status_code=500, detail=f"获取翻译缓存条目失败: {e}")
        ```

## 第二部分: 前端逻辑重构 (`web/static/js/cache-management.js` & `cache-management.html`)

**目标**: 移除所有客户端过滤逻辑，将状态通过API参数传递给后端，并简化UI交互。

### 1. 在Vue data中添加状态变量

-   **文件**: 在您的Vue组件定义中 (很可能在 `viewer.html` 或主JS文件中)。
-   **操作**: 添加用于控制筛选开关的变量。
    ```javascript
    // 在 data() { return { ... } } 中添加
    showOnlySensitive: false,
    showOnlyUnlikelyManga: false,
    ```

### 2. 用`<el-switch>`替换过滤按钮

-   **文件**: `web/templates/components/pages/cache-management.html`
-   **操作**: 将“敏感内容”和“可能非漫画”的`<el-button>`替换为`<el-switch>`，并绑定到新的状态变量。
    -   **替换翻译缓存的按钮 (第 97-105 行)**:
        ```html
        <template v-if="selectedCacheType === 'translation'">
            <el-switch
                v-model="showOnlySensitive"
                @change="onFilterChange"
                active-text="仅显示敏感内容"
                style="margin-left: 1rem;">
            </el-switch>
        </template>
        ```
    -   **替换漫画列表的按钮 (第 80-86 行)**:
        ```html
        <!-- 仅保留此开关，可以移除旧的 '可能非漫画' 按钮 -->
        <el-switch
            v-model="showOnlyUnlikelyManga"
            @change="onFilterChange"
            active-text="仅显示可能非漫画"
            style="margin-left: 1rem;">
        </el-switch>
        ```

### 3. 重构核心JavaScript逻辑

-   **文件**: `web/static/js/cache-management.js`
-   **操作**:
    1.  **创建 `onFilterChange` 方法**:
        ```javascript
        // 在 CacheManagementMethods 中添加新方法
        async onFilterChange() {
            this.currentPage = 1; // 任何筛选变化都重置到第一页
            await this.loadCacheEntries();
        },
        ```
    2.  **修改搜索框HTML**:
        -   **文件**: `web/templates/components/pages/cache-management.html`
        -   **位置**: 第 `118` 行
        -   **操作**: 将 `@input` 事件改为 `@change`。
            -   **旧代码**: `@input="filterCacheEntries"`
            -   **新代码**: `@change="onFilterChange"`

    3.  **彻底重构 `loadCacheEntries`**:
        -   **文件**: `web/static/js/cache-management.js`
        -   **位置**: 第 `74` 行
        -   **操作**: 替换整个函数。
            ```javascript
            async loadCacheEntries() {
                if (!this.selectedCacheType) return;
        
                this.isLoadingEntries = true;
                try {
                    const params = {
                        page: this.currentPage,
                        page_size: this.pageSize,
                        search: this.cacheSearchQuery || null
                    };
        
                    // 根据缓存类型添加特定的过滤参数
                    if (this.selectedCacheType === 'translation') {
                        params.filter_sensitive = this.showOnlySensitive;
                    }
                    if (this.selectedCacheType === 'manga_list') {
                        params.show_unlikely = this.showOnlyUnlikelyManga; 
                    }
        
                    const response = await axios.get(`/api/cache/${this.selectedCacheType}/entries`, { params });
        
                    // 直接将后端返回的结果赋给展示列表
                    this.cacheEntries = response.data.entries || [];
                    this.filteredCacheEntries = this.cacheEntries;
                    this.totalEntries = response.data.total || 0;
        
                } catch (error) {
                    console.error('加载缓存条目失败:', error);
                    ElMessage.error('加载缓存条目失败: ' + (error.response?.data?.detail || error.message));
                    this.cacheEntries = [];
                    this.filteredCacheEntries = [];
                    this.totalEntries = 0;
                } finally {
                    this.isLoadingEntries = false;
                }
            },
            ```

    4.  **删除无用代码**:
        -   **文件**: `web/static/js/cache-management.js`
        -   **操作**:
            -   删除整个 `filterCacheEntries` 函数 (第 `104-117` 行)。
            -   删除 `filterSensitiveContent` 函数 (第 `433-442` 行)。
            -   删除 `filterUnlikelyManga` 函数 (第 `455-464` 行)。

---
完成以上V4.0方案的步骤后，您的缓存管理系统将变得更加可靠和高效。筛选逻辑将完全由后端负责，确保了数据的一致性，前端代码也得到了简化。