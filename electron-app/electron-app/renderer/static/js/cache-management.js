// 缓存管理功能模块
window.CacheManagementMethods = {
    // ==================== 缓存管理功能 ====================

    async initCacheManagement() {
        try {
            await this.loadCacheStats();
        } catch (error) {
            console.error('初始化缓存管理失败:', error);
        }
    },

    async loadCacheStats() {
        try {
            const response = await axios.get('/api/cache/stats');
            this.cacheStats = response.data;
        } catch (error) {
            console.error('加载缓存统计失败:', error);
            ElMessage.error('加载缓存统计失败');
        }
    },

    getCacheTypeStats(cacheType) {
        const stats = this.cacheStats[cacheType] || {};
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

    async loadCacheEntries() {
        if (!this.selectedCacheType) return;

        this.isLoadingEntries = true;
        try {
            const response = await axios.get(`/api/cache/${this.selectedCacheType}/entries`, {
                params: {
                    page: this.currentPage,
                    page_size: this.pageSize,
                    search: this.cacheSearchQuery
                }
            });

            this.cacheEntries = response.data.entries || [];
            this.totalEntries = response.data.total || 0;
            this.filteredCacheEntries = this.cacheEntries;
        } catch (error) {
            console.error('加载缓存条目失败:', error);
            ElMessage.error('加载缓存条目失败');
            this.cacheEntries = [];
            this.filteredCacheEntries = [];
            this.totalEntries = 0;
        } finally {
            this.isLoadingEntries = false;
        }
    },

    filterCacheEntries() {
        // 实时搜索过滤
        if (!this.cacheSearchQuery) {
            this.filteredCacheEntries = this.cacheEntries;
        } else {
            const query = this.cacheSearchQuery.toLowerCase();
            this.filteredCacheEntries = this.cacheEntries.filter(entry =>
                entry.key.toLowerCase().includes(query) ||
                entry.value_preview.toLowerCase().includes(query)
            );
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

    editCacheEntry(entry) {
        this.editDialog.visible = true;
        this.editDialog.type = this.selectedCacheType;
        this.editDialog.isEditing = true;
        this.editDialog.key = entry.key;
        this.editDialog.content = entry.value || '';
        this.editDialog.currentEntry = entry;

        // 设置对话框标题
        const cacheTypeName = this.getSelectedCacheName();
        this.editDialog.title = `编辑${cacheTypeName}条目`;

        // 特殊处理不同类型的缓存
        if (this.selectedCacheType === 'translation') {
            this.editDialog.isSensitive = entry.is_sensitive || false;
        } else if (this.selectedCacheType === 'harmonization_map') {
            // 和谐映射的特殊处理
            this.editDialog.originalText = entry.key;
            this.editDialog.harmonizedText = entry.value || '';
        }
    },

    async saveEdit() {
        try {
            let data = {};

            if (this.editDialog.type === 'harmonization_map') {
                // 和谐映射的保存
                if (!this.editDialog.originalText.trim()) {
                    ElMessage.warning('原文不能为空');
                    return;
                }

                data = {
                    original_text: this.editDialog.originalText.trim(),
                    harmonized_text: this.editDialog.harmonizedText.trim()
                };
            } else if (this.editDialog.type === 'translation') {
                // 翻译缓存的保存
                data = {
                    key: this.editDialog.key,
                    content: this.editDialog.content,
                    is_sensitive: this.editDialog.isSensitive
                };
            } else {
                // 其他类型的保存
                data = {
                    key: this.editDialog.key,
                    content: this.editDialog.content
                };
            }

            const url = this.editDialog.isEditing
                ? `/api/cache/${this.editDialog.type}/update`
                : `/api/cache/${this.editDialog.type}/add`;

            const response = await axios.post(url, data);

            if (response.data.success) {
                ElMessage.success(this.editDialog.isEditing ? '修改成功' : '添加成功');
                this.cancelEdit();
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

    cancelEdit() {
        this.editDialog.visible = false;
        this.editDialog.type = '';
        this.editDialog.title = '';
        this.editDialog.isEditing = false;
        this.editDialog.key = '';
        this.editDialog.content = '';
        this.editDialog.originalText = '';
        this.editDialog.harmonizedText = '';
        this.editDialog.isSensitive = false;
        this.editDialog.currentEntry = null;
    },

    async deleteCurrentEntry() {
        if (!this.editDialog.currentEntry) return;

        try {
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
                this.cancelEdit();
                await this.loadCacheEntries();
                await this.loadCacheStats();
            } else {
                ElMessage.error(response.data.message || '删除失败');
            }
        } catch (error) {
            if (error !== 'cancel') {
                console.error('删除失败:', error);
                ElMessage.error('删除失败: ' + (error.response?.data?.detail || error.message));
            }
        }
    },

    async clearSingleCache(cacheType) {
        try {
            await this.$confirm(`确定要清空 ${this.cacheTypes.find(t => t.key === cacheType)?.name} 缓存吗？`, '确认清空', {
                confirmButtonText: '清空',
                cancelButtonText: '取消',
                type: 'warning'
            });

            this.loadingStates[cacheType].clearing = true;

            const response = await axios.post(`/api/cache/${cacheType}/clear`);

            if (response.data.success) {
                ElMessage.success(`${this.cacheTypes.find(t => t.key === cacheType)?.name} 缓存已清空`);
                
                // 如果当前选择的就是被清空的缓存类型，重新加载
                if (this.selectedCacheType === cacheType) {
                    await this.loadCacheEntries();
                }
                
                await this.loadCacheStats();
            } else {
                ElMessage.error(response.data.message || '清空失败');
            }
        } catch (error) {
            if (error !== 'cancel') {
                console.error('清空缓存失败:', error);
                ElMessage.error('清空缓存失败: ' + (error.response?.data?.detail || error.message));
            }
        } finally {
            this.loadingStates[cacheType].clearing = false;
        }
    },

    showAddHarmonizationDialog() {
        this.editDialog.visible = true;
        this.editDialog.type = 'harmonization_map';
        this.editDialog.isEditing = false;
        this.editDialog.title = '添加和谐映射';
        this.editDialog.originalText = '';
        this.editDialog.harmonizedText = '';
    },

    async generateHarmonizationFromCurrent() {
        if (!this.editDialog.content.trim()) {
            ElMessage.warning('请先输入翻译内容');
            return;
        }

        // 将当前翻译内容作为原文，打开和谐映射对话框
        const originalText = this.editDialog.content.trim();
        
        // 先保存当前的翻译编辑
        await this.saveEdit();
        
        // 然后打开和谐映射对话框
        this.editDialog.visible = true;
        this.editDialog.type = 'harmonization_map';
        this.editDialog.isEditing = false;
        this.editDialog.title = '生成和谐映射';
        this.editDialog.originalText = originalText;
        this.editDialog.harmonizedText = '';
        
        ElMessage.info('请输入和谐后的文本');
    }
};
