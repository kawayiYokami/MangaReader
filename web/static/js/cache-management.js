// 缓存管理功能模块
window.CacheManagementMethods = {
    // ==================== 缓存管理功能 ====================

    async initCacheManagement() {
        // 初始化新的 harmonizationDialog 数据结构 (如果尚未存在)
        if (!this.harmonizationDialog) {
             this.harmonizationDialog = {
                visible: false,
                title: '',
                isEditing: false,
                originalText: '',
                harmonizedText: '',
                currentKey: null // 用于存储正在编辑的条目的原始 key
            };
        }

        try {
            await this.loadCacheStats();
        } catch (error) {
            console.error('初始化缓存管理失败:', error);
        }
    },

    async loadCacheStats() {
        try {
            // 加载常规缓存统计
            const response = await axios.get('/api/cache/stats');
            // 确保 this.cacheStats 被正确初始化
            if (!this.cacheStats) this.cacheStats = {};
            // 更新统计数据，Vue 会自动响应变化
            for (const key in response.data.stats) {
                this.cacheStats[key] = response.data.stats[key];
            }



            // 如果响应中没有某个 key，确保它存在且为 0
             this.cacheTypes.forEach(type => {
                if (!this.cacheStats[type.key]) {
                    this.cacheStats[type.key] = { entries: 0, size: 0 };
                }
            });

        } catch (error) {
            console.error('加载缓存统计失败:', error);
            ElMessage.error('加载缓存统计失败');
        }
    },

    getCacheTypeStats(cacheType) {
        const stats = (this.cacheStats && this.cacheStats[cacheType]) ? this.cacheStats[cacheType] : {};
        return {
            entries: stats.entries || 0,
            size: this.formatFileSize(stats.size || 0)
        };
    },

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    async selectCacheType(cacheType) {
        this.selectedCacheType = cacheType;
        this.currentPage = 1;
        this.cacheSearchQuery = '';
        await this.loadCacheEntries();
    },

async onFilterChange() {
        this.currentPage = 1; // 任何筛选变化都重置到第一页
        await this.loadCacheEntries();
    },
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
                // 假设 showOnlyUnlikelyManga 控制 "unlikely_manga" 的显示
                params.show_unlikely = this.showOnlyUnlikelyManga; 
            }

            const response = await axios.get(`/api/cache/${this.selectedCacheType}/entries`, { params });

            // 直接将后端返回的结果赋给 filteredCacheEntries
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

    

    async onPageChange(page) {
        this.currentPage = page;
        await this.loadCacheEntries();
    },

    getSelectedCacheName() {
        const cacheType = this.cacheTypes.find(type => type.key === this.selectedCacheType);
        return cacheType ? cacheType.name : '';
    },

    getTableColspan() {
        // 计算表格列数
        let baseColumns = 3; // 键、内容、操作
        if (this.selectedCacheType === 'manga_list') {
            baseColumns += 5; // 方差值、可能是漫画、页数、文件大小、标签数
        } else if (this.selectedCacheType === 'translation') {
            baseColumns += 1; // 敏感内容
        } else if (this.selectedCacheType === 'realtime_translation') {
            baseColumns += 5; // 翻译引擎、缓存页数、页面范围、缓存来源、操作
        }
        return baseColumns;
    },

    getDisplayKey(key) {
        // 对于文件路径，只显示文件名
        if (this.selectedCacheType === 'manga_list' && key) {
            const parts = key.split(/[/\\]/);
            return parts[parts.length - 1] || key;
        }
        return key;
    },

    getVarianceClass(variance) {
        // 根据方差值返回CSS类名
        if (typeof variance !== 'number') return '';

        if (variance < 0.1) {
            return 'variance-low'; // 绿色，很可能是漫画
        } else if (variance < 0.3) {
            return 'variance-medium'; // 黄色，可能是漫画
        } else {
            return 'variance-high'; // 红色，不太可能是漫画
        }
    },

    formatFileSize(bytes) {
        // 格式化文件大小
        if (!bytes || bytes === 0) return '未知';

        if (bytes >= 1024 * 1024) {
            return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
        } else if (bytes >= 1024) {
            return `${(bytes / 1024).toFixed(1)} KB`;
        } else {
            return `${bytes} B`;
        }
    },

    // --- 编辑/添加条目 (旧对话框逻辑，保留用于非和谐映射类型) ---
    editCacheEntry(entry) {
        if (this.selectedCacheType === 'harmonization_map') {
            // --- 使用新的 Material Design 对话框编辑和谐映射 ---
             // 确保 harmonizationDialog 存在
            if (!this.harmonizationDialog) {
                 this.harmonizationDialog = { visible: false, title: '', isEditing: false, originalText: '', harmonizedText: '', currentKey: null };
            }
            this.harmonizationDialog.visible = true;
            this.harmonizationDialog.isEditing = true;
            this.harmonizationDialog.title = '编辑和谐映射';
            this.harmonizationDialog.originalText = entry.key; // 原文是 key
            this.harmonizationDialog.harmonizedText = entry.value || ''; // 和谐后是 value
            this.harmonizationDialog.currentKey = entry.key; // 存储原始 key 用于更新/删除
        } else if (this.selectedCacheType === 'persistent_translation') {
            // --- 持久化翻译缓存是只读的，不可编辑 ---
            ElMessage.info('持久化翻译缓存条目为只读，不可编辑。');
            return;
        } else {
            // --- 使用旧的 Element Plus 对话框编辑其他类型 ---
            this.editDialog.visible = true;
            this.editDialog.type = this.selectedCacheType;
            this.editDialog.isEditing = true;
            this.editDialog.key = entry.key;
            this.editDialog.content = entry.value || '';
            this.editDialog.currentEntry = entry; // 保留对原始条目的引用

            const cacheTypeName = this.getSelectedCacheName();
            this.editDialog.title = `编辑${cacheTypeName}条目`;

            if (this.selectedCacheType === 'translation') {
                this.editDialog.isSensitive = entry.is_sensitive || false;
            }
            // 移除旧的和谐映射处理逻辑
            // else if (this.selectedCacheType === 'harmonization_map') { ... }
        }
    },



    async saveEdit() { // 保存旧对话框的逻辑 (非和谐映射)
        try {
            let data = {};
            const cacheType = this.editDialog.type; // 使用 editDialog 中的 type

            // 移除和谐映射的保存逻辑，因为它现在由 saveHarmonizationEdit 处理
            // if (cacheType === 'harmonization_map') { ... }
            if (cacheType === 'translation') {
                data = {
                    key: this.editDialog.key,
                    content: this.editDialog.content,
                    is_sensitive: this.editDialog.isSensitive
                };
            } else if (cacheType) { // 处理其他可能的类型
                data = {
                    key: this.editDialog.key,
                    content: this.editDialog.content
                };
            } else {
                console.error('无法确定编辑类型');
                ElMessage.error('保存失败：未知的编辑类型');
                return;
            }

            // 检查 key 是否为空 (所有类型都需要 key)
             if (!data.key || (typeof data.key === 'string' && !data.key.trim())) {
                 ElMessage.warning('Key 不能为空');
                 return;
             }


            // URL 仍然基于 editDialog 的状态
            const url = this.editDialog.isEditing
                ? `/api/cache/${cacheType}/update`
                : `/api/cache/${cacheType}/add`; // 添加操作可能需要调整

            const response = await axios.post(url, data);

            if (response.data.success) {
                ElMessage.success(this.editDialog.isEditing ? '修改成功' : '添加成功');
                this.cancelEdit(); // 关闭旧对话框
                await this.loadCacheEntries();
                await this.loadCacheStats();
            } else {
                ElMessage.error(response.data.message || '操作失败');
            }
        } catch (error) {
            console.error('保存失败:', error);
            ElMessage.error('保存失败: ' + (error.response?.data?.detail || error.message));
        }
    },

    cancelEdit() { // 关闭旧对话框的逻辑
        this.editDialog.visible = false;
        // 重置旧对话框状态 (移除和谐映射字段)
        this.editDialog.type = '';
        this.editDialog.title = '';
        this.editDialog.isEditing = false;
        this.editDialog.key = '';
        this.editDialog.content = '';
        // this.editDialog.originalText = ''; // 移除
        // this.editDialog.harmonizedText = ''; // 移除
        this.editDialog.isSensitive = false;
        this.editDialog.currentEntry = null;
    },

    async deleteCurrentEntry() { // 删除旧对话框对应条目的逻辑
        if (!this.editDialog.currentEntry || !this.editDialog.type) return;

        try {
             // 使用 $confirm 可能仍依赖 Element Plus，如果完全移除需要替代方案
             // 暂时保留
            await this.$confirm('确定要删除这个条目吗？', '确认删除', {
                confirmButtonText: '删除',
                cancelButtonText: '取消',
                type: 'warning'
            });

            const response = await axios.post(`/api/cache/${this.editDialog.type}/delete`, {
                key: this.editDialog.currentEntry.key
            });

            if (response.data.success) {
                ElMessage.success('删除成功');
                this.cancelEdit(); // 关闭旧对话框
                await this.loadCacheEntries();
                await this.loadCacheStats();
            } else {
                ElMessage.error(response.data.message || '删除失败');
            }
        } catch (error) {
            // 检查是否是用户取消操作
            if (error !== 'cancel' && error !== 'close' && error?.message !== 'cancel') {
                console.error('删除失败:', error);
                ElMessage.error('删除失败: ' + (error.response?.data?.detail || error.message));
            }
        }
    },
    // --- End of Old Dialog Logic ---


    // --- 新增: Material Design 和谐映射对话框方法 ---
    showAddHarmonizationDialog() {
        // 确保 harmonizationDialog 存在
        if (!this.harmonizationDialog) {
             this.harmonizationDialog = { visible: false, title: '', isEditing: false, originalText: '', harmonizedText: '', currentKey: null };
        }
        this.harmonizationDialog.visible = true;
        this.harmonizationDialog.isEditing = false;
        this.harmonizationDialog.title = '添加和谐映射';
        this.harmonizationDialog.originalText = '';
        this.harmonizationDialog.harmonizedText = '';
        this.harmonizationDialog.currentKey = null;
    },

    cancelHarmonizationEdit() {
        try {
            if (this.harmonizationDialog) {
                this.harmonizationDialog.visible = false;
                // 可选：重置数据
                // this.harmonizationDialog.originalText = '';
                // this.harmonizationDialog.harmonizedText = '';
                // this.harmonizationDialog.currentKey = null;
                // this.harmonizationDialog.isEditing = false;
            }
        } catch (error) {
            // 忽略取消操作的错误
            console.debug('对话框取消操作:', error);
        }
    },

    async saveHarmonizationEdit() {
         if (!this.harmonizationDialog) return;

        try {
            const originalText = this.harmonizationDialog.originalText.trim();
            const harmonizedText = this.harmonizationDialog.harmonizedText.trim(); // 允许为空

            if (!originalText) {
                ElMessage.warning('原文不能为空');
                return;
            }

            let url = '';
            let data = {};

            if (this.harmonizationDialog.isEditing) {
                // 更新操作
                url = `/api/cache/harmonization_map/update`;
                data = {
                    // API 可能需要原始 key 来定位条目
                    original_text: this.harmonizationDialog.currentKey,
                    // 以及新的和谐后文本
                    new_harmonized_text: harmonizedText
                };
                 // 如果 API 设计为用新原文替换旧原文，则发送新原文
                 // data = { original_text: originalText, harmonized_text: harmonizedText };
                 // *** 确认 API `update` 的确切参数 ***
                 // 假设 API 需要原始 key 和新的 value
            } else {
                // 添加操作
                url = `/api/cache/harmonization_map/add`;
                data = {
                    original_text: originalText,
                    harmonized_text: harmonizedText
                };
            }

            const response = await axios.post(url, data);

            if (response.data.success) {
                ElMessage.success(this.harmonizationDialog.isEditing ? '修改成功' : '添加成功');
                this.cancelHarmonizationEdit(); // 关闭新对话框
                // 确保在正确的缓存类型下刷新
                if (this.selectedCacheType === 'harmonization_map') {
                    await this.loadCacheEntries();
                }
                await this.loadCacheStats(); // 刷新统计数据
            } else {
                ElMessage.error(response.data.message || '操作失败');
            }
        } catch (error) {
            console.error('保存和谐映射失败:', error);
            ElMessage.error('保存和谐映射失败: ' + (error.response?.data?.detail || error.message));
        }
    },

    async deleteHarmonizationEntry() {
        if (!this.harmonizationDialog || !this.harmonizationDialog.isEditing || !this.harmonizationDialog.currentKey) return;

        try {
            // 假设 Material Dialog 不需要 $confirm, 直接执行
            // 如果需要确认，需要实现 Material Design 的确认对话框

            const response = await axios.post(`/api/cache/harmonization_map/delete`, {
                key: this.harmonizationDialog.currentKey
            });

            if (response.data.success) {
                ElMessage.success('删除成功');
                this.cancelHarmonizationEdit(); // 关闭新对话框
                if (this.selectedCacheType === 'harmonization_map') {
                    await this.loadCacheEntries();
                }
                await this.loadCacheStats();
            } else {
                ElMessage.error(response.data.message || '删除失败');
            }
        } catch (error) {
             console.error('删除和谐映射失败:', error);
             ElMessage.error('删除和谐映射失败: ' + (error.response?.data?.detail || error.message));
        }
    },
    // --- End of New Dialog Methods ---

    

    // --- 持久化翻译缓存删除方法 ---
    async deleteCacheEntry(entry) {
        if (!entry || !entry.key) {
            ElMessage.error('无效的缓存条目，无法删除。');
            return;
        }

        try {
            await this.$confirm(`此操作将删除漫画 "${entry.value_preview || entry.key}" 的所有持久化翻译缓存。确定吗？`, '确认删除', {
                confirmButtonText: '删除',
                cancelButtonText: '取消',
                type: 'warning'
            });

            // 调用后端的通用删除接口。URL中的key需要编码以处理特殊字符。
            const response = await axios.delete(`/api/cache/persistent_translation/entries/${encodeURIComponent(entry.key)}`);

            ElMessage.success('漫画的持久化翻译缓存已删除');
            await this.loadCacheEntries(); // 重新加载条目
            await this.loadCacheStats();   // 更新统计信息
        } catch (error) {
            // 忽略用户取消操作
            if (error !== 'cancel' && error !== 'close' && error?.message !== 'cancel') {
                console.error('删除缓存失败:', error);
                ElMessage.error('删除失败: ' + (error.response?.data?.detail || error.message));
            }
        }
    },





    formatDateTime(dateTimeStr) {
        if (!dateTimeStr) return '未知';

        try {
            const date = new Date(dateTimeStr);
            const now = new Date();
            const diffMs = now - date;
            const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

            if (diffDays === 0) {
                return '今天 ' + date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
            } else if (diffDays === 1) {
                return '昨天 ' + date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
            } else if (diffDays < 7) {
                return `${diffDays}天前`;
            } else {
                return date.toLocaleDateString('zh-CN');
            }
        } catch (error) {
            return '格式错误';
        }
    },
    // --- End of 实时翻译缓存特殊方法 ---

    // --- 清空缓存 (保持不变) ---
    async clearSingleCache(cacheType) {
        try {
            // 假设 $confirm 仍然可用
            await this.$confirm(`确定要清空 ${this.cacheTypes.find(t => t.key === cacheType)?.name} 缓存吗？`, '确认清空', {
                confirmButtonText: '清空',
                cancelButtonText: '取消',
                type: 'warning'
            });

            // 确保 loadingStates 被初始化
             if (!this.loadingStates) this.loadingStates = {};
             if (!this.loadingStates[cacheType]) this.loadingStates[cacheType] = { clearing: false };
            this.loadingStates[cacheType].clearing = true;

            let response;

            // 所有缓存类型使用统一的API
            response = await axios.post(`/api/cache/${cacheType}/clear`);

            if (response.data.success) {
                ElMessage.success(`${this.cacheTypes.find(t => t.key === cacheType)?.name} 缓存已清空`);
                if (this.selectedCacheType === cacheType) {
                    await this.loadCacheEntries();
                }
                await this.loadCacheStats();
            } else {
                ElMessage.error(response.data.message || '清空失败');
            }
        } catch (error) {
            // 检查是否是用户取消操作
            if (error !== 'cancel' && error !== 'close' && error?.message !== 'cancel') {
                console.error('清空缓存失败:', error);
                ElMessage.error('清空缓存失败: ' + (error.response?.data?.detail || error.message));
            }
        } finally {
             if (this.loadingStates && this.loadingStates[cacheType]) {
                 this.loadingStates[cacheType].clearing = false;
            }
        }
    },

     // generateHarmonizationFromCurrent 方法需要更新以使用新对话框
    async generateHarmonizationFromCurrent() {
         // 这个方法似乎是从旧的“翻译”编辑对话框中调用的
         // 如果翻译对话框也需要 M3 风格，需要另外处理
         // 假设现在只处理缓存管理页面的和谐映射
         // 这个方法在当前上下文中可能不再直接相关或需要重构
         console.warn('generateHarmonizationFromCurrent 需要审查其上下文和目的');

         // 临时的简单实现：如果当前在编辑翻译，并且想生成映射
         if (this.editDialog.visible && this.editDialog.type === 'translation' && this.editDialog.content.trim()) {
             const originalText = this.editDialog.content.trim();
             // 先关闭旧的翻译对话框
             this.cancelEdit();
             // 打开新的和谐映射对话框
             this.showAddHarmonizationDialog(); // 打开添加模式
             this.harmonizationDialog.originalText = originalText; // 预填原文
             this.harmonizationDialog.title = '生成和谐映射';
             ElMessage.info('请输入和谐后的文本');
         } else {
             ElMessage.warning('无法从当前状态生成和谐映射');
         }
    },

    // ==================== 批量压缩功能 ====================

    showBatchCompressionDialog() {
        // 检查是否需要显示警告
        const dontShowWarning = localStorage.getItem('compressionWarningDismissed') === 'true';

        if (!dontShowWarning) {
            // 显示警告对话框
            this.compressionWarningDialog.visible = true;
            this.compressionWarningDialog.dontShowAgain = false;
        } else {
            // 直接显示压缩对话框
            this.openBatchCompressionDialog();
        }
    },

    openBatchCompressionDialog() {
        // 初始化批量压缩对话框数据
        if (!this.batchCompressionDialog) {
            this.batchCompressionDialog = {
                visible: false,
                webpQuality: 85,
                minCompressionRatio: 0.25,
                preserveOriginalNames: true,  // 默认保留原始文件名
                isProcessing: false,
                progress: 0,
                status: '',
                progressText: '',
                results: null
            };
        }

        // 重置状态
        this.batchCompressionDialog.visible = true;
        this.batchCompressionDialog.isProcessing = false;
        this.batchCompressionDialog.results = null;
    },

    // 警告对话框相关方法
    cancelCompressionWarning() {
        this.compressionWarningDialog.visible = false;
    },

    proceedWithCompression() {
        // 保存用户选择
        if (this.compressionWarningDialog.dontShowAgain) {
            localStorage.setItem('compressionWarningDismissed', 'true');
        }

        // 关闭警告对话框，打开压缩对话框
        this.compressionWarningDialog.visible = false;
        this.openBatchCompressionDialog();
    },

    openAutoFilterFirst() {
        // 关闭警告对话框，打开自动过滤对话框
        this.compressionWarningDialog.visible = false;
        this.showAutoFilterDialog();
    },

    cancelBatchCompression() {
        this.batchCompressionDialog.visible = false;
    },



    formatQualityTooltip(value) {
        return `${value}%`;
    },

    formatCompressionTooltip(value) {
        return `${(value * 100).toFixed(0)}%`;
    },

    // ==================== 自动过滤功能 ====================

    showAutoFilterDialog() {
        // 重置状态
        this.autoFilterDialog.visible = true;
        this.autoFilterDialog.currentStep = 0;
        this.autoFilterDialog.filterMethod = '';
        this.autoFilterDialog.forceReanalyze = false;
        this.autoFilterDialog.previewResults = null;
        this.autoFilterDialog.filterResults = null;
        this.autoFilterDialog.isProcessing = false;
        this.autoFilterDialog.isPreviewing = false;
    },

    // 过滤方法数据
    getFilterMethods() {
        return [
            {
                value: 'dimension_analysis',
                title: '尺寸分析',
                description: '基于页面尺寸一致性判断是否为漫画',
                icon: 'straighten',
                features: ['检测页面尺寸变化', '识别非标准比例', '适合混合内容库']
            },
            {
                value: 'tag_based',
                title: '标签检查',
                description: '检查是否包含必要的作者和标题标签',
                icon: 'label',
                features: ['验证元数据完整性', '检查标签格式', '适合规范化库']
            },
            {
                value: 'hybrid',
                title: '混合方法',
                description: '同时使用尺寸分析和标签检查',
                icon: 'tune',
                features: ['双重验证机制', '最高准确率', '推荐使用']
            }
        ];
    },

    // 步骤控制方法
    selectFilterMethod(method) {
        this.autoFilterDialog.filterMethod = method;
    },

    nextStep() {
        if (this.autoFilterDialog.currentStep === 0) {
            // 从方法选择到预览结果
            this.autoFilterDialog.currentStep = 1;
            this.previewFilterResults();
        } else if (this.autoFilterDialog.currentStep === 1) {
            // 从预览结果到应用过滤
            this.autoFilterDialog.currentStep = 2;
            this.applyAutoFilter();
        }
    },

    previousStep() {
        if (this.autoFilterDialog.currentStep > 0) {
            this.autoFilterDialog.currentStep--;
        }
    },

    cancelAutoFilter() {
        this.autoFilterDialog.visible = false;
    },

    formatThresholdTooltip(value) {
        return `${value.toFixed(2)}`;
    },

    // ==================== 文件列表对话框功能 ====================

    showFilteredFilesList(type) {
        if (!this.autoFilterDialog.previewResults) return;

        const results = this.autoFilterDialog.previewResults;
        let files = [];
        let title = '';

        if (type === 'keep') {
            files = results.filtered_manga || [];
            title = `保留的文件 (${files.length} 个)`;
        } else if (type === 'remove') {
            files = results.removed_manga || [];
            title = `将被移除的文件 (${files.length} 个)`;
        }

        this.filterFilesListDialog.visible = true;
        this.filterFilesListDialog.title = title;
        this.filterFilesListDialog.type = type;
        this.filterFilesListDialog.files = files;
        this.filterFilesListDialog.searchQuery = '';
        this.filterFilesListDialog.currentPage = 1;
    },

    closeFilterFilesListDialog() {
        this.filterFilesListDialog.visible = false;
    },

    getFileName(filePath) {
        if (!filePath) return '';
        return filePath.split(/[/\\]/).pop();
    },

    async copyFilePath(filePath) {
        try {
            await navigator.clipboard.writeText(filePath);
            ElMessage.success('文件路径已复制到剪贴板');
        } catch (error) {
            console.error('复制失败:', error);
            ElMessage.error('复制失败');
        }
    },

    exportFilesList() {
        if (!this.filterFilesListDialog.files.length) {
            ElMessage.warning('没有文件可导出');
            return;
        }

        const files = this.filteredFilesList;
        const type = this.filterFilesListDialog.type;

        // 创建CSV内容
        let csvContent = 'Title,File Path';
        if (type === 'remove') {
            csvContent += ',Reason';
        }
        csvContent += '\n';

        files.forEach(file => {
            const title = (file.title || '').replace(/"/g, '""');
            const path = (file.file_path || '').replace(/"/g, '""');
            let row = `"${title}","${path}"`;

            if (type === 'remove' && file.reason) {
                const reason = file.reason.replace(/"/g, '""');
                row += `,"${reason}"`;
            }

            csvContent += row + '\n';
        });

        // 下载文件
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', `${type === 'keep' ? '保留' : '移除'}_文件列表.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        ElMessage.success('文件列表已导出');
    },

    // ==================== 批量压缩异步方法 ====================

    async startBatchCompression() {
        // 检查是否有漫画文件
        if (!this.totalMangaCount || this.totalMangaCount === 0) {
            ElMessage.warning('没有可压缩的漫画文件');
            return;
        }

        this.batchCompressionDialog.isProcessing = true;
        this.batchCompressionDialog.progress = 0;
        this.batchCompressionDialog.status = '';
        this.batchCompressionDialog.progressText = '准备开始批量压缩...';

        try {
            this.batchCompressionDialog.progressText = '正在执行批量压缩...';
            this.batchCompressionDialog.progress = 20;

            const response = await axios.post('/api/manga/batch-compress', {
                webp_quality: this.batchCompressionDialog.webpQuality,
                min_compression_ratio: this.batchCompressionDialog.minCompressionRatio,
                preserve_original_names: this.batchCompressionDialog.preserveOriginalNames
            });

            this.batchCompressionDialog.progress = 100;
            this.batchCompressionDialog.status = 'success';
            this.batchCompressionDialog.progressText = '批量压缩完成！';
            this.batchCompressionDialog.results = response.data;

            const successCount = response.data.successful_compressions;
            const skippedCount = response.data.skipped_files || 0;
            const failedCount = response.data.failed_files ? response.data.failed_files.length : 0;

            ElMessage.success(`批量压缩完成！成功处理 ${successCount} 个文件，跳过 ${skippedCount} 个，失败 ${failedCount} 个`);

            // 刷新漫画列表（因为文件可能已被替换）
            if (this.loadInitialData) {
                await this.loadInitialData();
            }

        } catch (error) {
            console.error('批量压缩失败:', error);
            this.batchCompressionDialog.progress = 100;
            this.batchCompressionDialog.status = 'exception';
            this.batchCompressionDialog.progressText = '批量压缩失败';
            ElMessage.error('批量压缩失败: ' + (error.response?.data?.detail || error.message));
        } finally {
            this.batchCompressionDialog.isProcessing = false;
        }
    },



    // ==================== 自动过滤异步方法 ====================

    async previewFilterResults() {
        this.autoFilterDialog.isPreviewing = true;

        try {
            const response = await axios.post('/api/manga/auto-filter-preview', {
                filter_method: this.autoFilterDialog.filterMethod,
                threshold: this.autoFilterDialog.threshold,
                force_reanalyze: this.autoFilterDialog.forceReanalyze
            });

            this.autoFilterDialog.previewResults = response.data;
            ElMessage.success('预览完成');

        } catch (error) {
            console.error('预览失败:', error);
            ElMessage.error('预览失败: ' + (error.response?.data?.detail || error.message));
        } finally {
            this.autoFilterDialog.isPreviewing = false;
        }
    },

    async applyAutoFilter() {
        if (!this.autoFilterDialog.previewResults) {
            ElMessage.warning('请先预览过滤结果');
            return;
        }

        this.autoFilterDialog.isProcessing = true;
        this.autoFilterDialog.progress = 0;
        this.autoFilterDialog.progressText = '正在应用过滤结果...';

        try {
            const response = await axios.post('/api/manga/apply-auto-filter', {
                filter_results: this.autoFilterDialog.previewResults
            });

            this.autoFilterDialog.progress = 100;
            this.autoFilterDialog.status = 'success';
            this.autoFilterDialog.progressText = '过滤应用完成！';
            this.autoFilterDialog.filterResults = response.data;

            ElMessage.success(`过滤应用完成！已移除 ${this.autoFilterDialog.previewResults.removed_count} 个文件`);

            // 刷新缓存数据
            await this.loadCacheStats();
            if (this.selectedCacheType === 'manga_list') {
                await this.loadCacheEntries();
            }

        } catch (error) {
            console.error('应用过滤失败:', error);
            this.autoFilterDialog.progress = 100;
            this.autoFilterDialog.status = 'exception';
            this.autoFilterDialog.progressText = '应用过滤失败';
            ElMessage.error('应用过滤失败: ' + (error.response?.data?.detail || error.message));
        } finally {
            this.autoFilterDialog.isProcessing = false;
        }
    },

    // ==================== 辅助方法 ====================

    formatFileSize(bytes) {
        if (!bytes) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },



    /**
     * 格式化日期时间
     */
    formatDateTime(dateTimeString) {
        if (!dateTimeString) return '未知';
        try {
            const date = new Date(dateTimeString);
            return date.toLocaleString('zh-CN');
        } catch (error) {
            return dateTimeString;
        }
    }
};


