/**
 * 实时翻译功能模块
 */

class RealtimeTranslationManager {
    constructor() {
        this.isServiceRunning = false;
        this.currentManga = null;
        this.currentPage = 0;

        // 双重缓存机制
        this.translatedPages = new Map(); // 翻译后页面缓存
        this.originalPages = new Map();   // 原始页面缓存
        this.cacheMetadata = new Map();   // 缓存元数据（时间戳、哈希等）

        // 缓存配置（优化版本）
        this.cacheConfig = {
            maxTranslatedPages: 15,  // 进一步减少翻译页面缓存数
            maxOriginalPages: 25,    // 进一步减少原始页面缓存数
            cacheExpireTime: 10 * 60 * 1000, // 10分钟过期
            enablePersistence: false, // 完全禁用localStorage持久化
            preferBackendCache: true  // 优先使用后端缓存
        };

        this.statusCheckInterval = null;
        this.autoTranslateEnabled = false;

        // 事件回调
        this.onTranslationCompleted = null;
        this.onStatusChanged = null;

        // 初始化缓存系统
        this._initializeCacheSystem();

        console.log('实时翻译管理器初始化完成 (增强缓存版本)');
    }

    /**
     * 初始化缓存系统
     */
    _initializeCacheSystem() {
        // 从localStorage恢复缓存（如果启用持久化）
        if (this.cacheConfig.enablePersistence) {
            this._loadCacheFromStorage();
        }

        // 定期清理过期缓存
        setInterval(() => {
            this._cleanupExpiredCache();
        }, 5 * 60 * 1000); // 每5分钟清理一次
    }

    /**
     * 从localStorage加载缓存
     */
    _loadCacheFromStorage() {
        try {
            const translatedCache = localStorage.getItem('rt_translated_cache');
            const originalCache = localStorage.getItem('rt_original_cache');
            const metadataCache = localStorage.getItem('rt_metadata_cache');

            if (translatedCache) {
                const data = JSON.parse(translatedCache);
                this.translatedPages = new Map(data);
                console.log(`从存储恢复翻译缓存: ${this.translatedPages.size} 项`);
            }

            if (originalCache) {
                const data = JSON.parse(originalCache);
                this.originalPages = new Map(data);
                console.log(`从存储恢复原始缓存: ${this.originalPages.size} 项`);
            }

            if (metadataCache) {
                const data = JSON.parse(metadataCache);
                this.cacheMetadata = new Map(data);
            }
        } catch (error) {
            console.warn('加载缓存失败:', error);
        }
    }

    /**
     * 保存缓存到localStorage（增强版本，支持配额检查和错误处理）
     */
    _saveCacheToStorage() {
        if (!this.cacheConfig.enablePersistence) {
            console.log('💾 localStorage持久化已禁用，跳过localStorage保存');
            return;
        }

        const timestamp = new Date().toLocaleTimeString();

        try {
            // 检查存储配额
            if (this.cacheConfig.enableStorageCheck && !this._checkStorageQuota()) {
                console.warn(`⚠️ [${timestamp}] localStorage配额不足，跳过保存`);
                return;
            }

            // 准备要保存的数据
            const translatedData = [...this.translatedPages];
            const originalData = [...this.originalPages];
            const metadataData = [...this.cacheMetadata];

            // 计算数据大小
            const estimatedSize = this._estimateDataSize(translatedData, originalData, metadataData);

            if (estimatedSize > this.cacheConfig.maxStorageSize) {
                console.warn(`⚠️ [${timestamp}] 缓存数据过大 (${(estimatedSize / 1024 / 1024).toFixed(2)}MB)，执行清理`);
                this._cleanupForStorage();
                return; // 清理后不再尝试保存，避免递归
            }

            // 分别保存，捕获每个操作的错误
            this._saveToLocalStorageWithFallback('rt_translated_cache', translatedData, '翻译缓存');
            this._saveToLocalStorageWithFallback('rt_original_cache', originalData, '原始缓存');
            this._saveToLocalStorageWithFallback('rt_metadata_cache', metadataData, '元数据缓存');

            console.log(`✅ [${timestamp}] 缓存保存成功 (大小: ${(estimatedSize / 1024).toFixed(1)}KB)`);

        } catch (error) {
            console.error(`❌ [${timestamp}] 保存缓存失败:`, error);

            // 如果是配额错误，清理缓存并禁用持久化
            if (error.name === 'QuotaExceededError') {
                console.warn(`⚠️ [${timestamp}] 检测到配额超限，禁用持久化缓存`);
                this.cacheConfig.enablePersistence = false;
                this._clearAllLocalStorage();
            }
        }
    }

    /**
     * 安全保存到localStorage，带降级处理
     */
    _saveToLocalStorageWithFallback(key, data, description) {
        try {
            const jsonString = JSON.stringify(data);
            localStorage.setItem(key, jsonString);
            console.log(`💾 ${description}保存成功 (${(jsonString.length / 1024).toFixed(1)}KB)`);
        } catch (error) {
            if (error.name === 'QuotaExceededError') {
                console.warn(`⚠️ ${description}保存失败：配额超限`);
                // 尝试清理其他缓存后重试
                this._clearOtherLocalStorageData();
                try {
                    localStorage.setItem(key, JSON.stringify(data));
                    console.log(`💾 ${description}重试保存成功`);
                } catch (retryError) {
                    console.error(`❌ ${description}重试保存仍然失败:`, retryError);
                    throw retryError;
                }
            } else {
                console.error(`❌ ${description}保存失败:`, error);
                throw error;
            }
        }
    }

    /**
     * 检查localStorage配额
     */
    _checkStorageQuota() {
        try {
            // 尝试写入测试数据
            const testKey = 'rt_quota_test';
            const testData = 'x'.repeat(1024); // 1KB测试数据
            localStorage.setItem(testKey, testData);
            localStorage.removeItem(testKey);
            return true;
        } catch (error) {
            if (error.name === 'QuotaExceededError') {
                return false;
            }
            return true; // 其他错误不影响配额检查
        }
    }

    /**
     * 估算数据大小
     */
    _estimateDataSize(translatedData, originalData, metadataData) {
        try {
            const translatedSize = JSON.stringify(translatedData).length;
            const originalSize = JSON.stringify(originalData).length;
            const metadataSize = JSON.stringify(metadataData).length;
            return translatedSize + originalSize + metadataSize;
        } catch (error) {
            console.warn('估算数据大小失败:', error);
            return 0;
        }
    }

    /**
     * 为存储清理缓存
     */
    _cleanupForStorage() {
        const timestamp = new Date().toLocaleTimeString();
        console.log(`🧹 [${timestamp}] 开始清理缓存以释放存储空间`);

        // 清理最旧的翻译缓存
        const translatedEntries = [...this.cacheMetadata.entries()]
            .filter(([key, metadata]) => metadata.type === 'translated')
            .sort(([,a], [,b]) => a.lastAccess - b.lastAccess);

        const toRemove = Math.ceil(translatedEntries.length * 0.5); // 清理50%
        for (let i = 0; i < toRemove && i < translatedEntries.length; i++) {
            const [key] = translatedEntries[i];
            this.translatedPages.delete(key);
            this.cacheMetadata.delete(key);
        }

        console.log(`🧹 [${timestamp}] 清理完成，移除${toRemove}个翻译缓存项`);
    }

    /**
     * 清理其他localStorage数据
     */
    _clearOtherLocalStorageData() {
        try {
            // 清理可能的旧缓存数据
            const keysToRemove = [];
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key && (key.startsWith('rt_') || key.startsWith('manga_') || key.startsWith('cache_'))) {
                    keysToRemove.push(key);
                }
            }

            keysToRemove.forEach(key => {
                try {
                    localStorage.removeItem(key);
                } catch (error) {
                    console.warn(`清理localStorage键失败: ${key}`, error);
                }
            });

            console.log(`🧹 清理了${keysToRemove.length}个localStorage项`);
        } catch (error) {
            console.warn('清理其他localStorage数据失败:', error);
        }
    }

    /**
     * 清理所有localStorage缓存
     */
    _clearAllLocalStorage() {
        try {
            localStorage.removeItem('rt_translated_cache');
            localStorage.removeItem('rt_original_cache');
            localStorage.removeItem('rt_metadata_cache');
            console.log('🧹 已清理所有实时翻译localStorage缓存');
        } catch (error) {
            console.warn('清理localStorage失败:', error);
        }
    }

    /**
     * 清理过期缓存
     */
    _cleanupExpiredCache() {
        const now = Date.now();
        let cleanedCount = 0;

        // 清理翻译缓存
        for (const [key, metadata] of this.cacheMetadata.entries()) {
            if (now - metadata.timestamp > this.cacheConfig.cacheExpireTime) {
                this.translatedPages.delete(key);
                this.originalPages.delete(key);
                this.cacheMetadata.delete(key);
                cleanedCount++;
            }
        }

        // 限制缓存大小
        this._limitCacheSize();

        if (cleanedCount > 0) {
            console.log(`清理过期缓存: ${cleanedCount} 项`);
            this._saveCacheToStorage();
        }
    }

    /**
     * 限制缓存大小
     */
    _limitCacheSize() {
        // 限制翻译缓存大小
        if (this.translatedPages.size > this.cacheConfig.maxTranslatedPages) {
            const entries = [...this.translatedPages.entries()];
            const toRemove = entries.slice(0, entries.length - this.cacheConfig.maxTranslatedPages);

            for (const [key] of toRemove) {
                this.translatedPages.delete(key);
                this.cacheMetadata.delete(key);
            }
        }

        // 限制原始缓存大小
        if (this.originalPages.size > this.cacheConfig.maxOriginalPages) {
            const entries = [...this.originalPages.entries()];
            const toRemove = entries.slice(0, entries.length - this.cacheConfig.maxOriginalPages);

            for (const [key] of toRemove) {
                this.originalPages.delete(key);
            }
        }
    }

    /**
     * 获取页面（优化版本，实现缓存优先级策略）
     */
    async getPageWithCachePriority(mangaPath, pageIndex, preferTranslated = true) {
        const cacheKey = `${mangaPath}:${pageIndex}`;

        // 缓存优先级策略
        if (preferTranslated) {
            // 1. 前端翻译页面缓存
            if (this.translatedPages.has(cacheKey)) {
                console.log(`前端翻译缓存命中: ${cacheKey}`);
                this._updateCacheAccess(cacheKey);
                return {
                    type: 'translated',
                    data: this.translatedPages.get(cacheKey),
                    source: 'frontend_translated_cache'
                };
            }

            // 2. 后端翻译结果缓存
            const translatedPage = await this.getTranslatedPage(mangaPath, pageIndex);
            if (translatedPage) {
                console.log(`后端翻译缓存命中: ${cacheKey}`);
                return {
                    type: 'translated',
                    data: translatedPage,
                    source: 'backend_translated_cache'
                };
            }
        }

        // 3. 前端原始页面缓存
        if (this.originalPages.has(cacheKey)) {
            console.log(`前端原始缓存命中: ${cacheKey}`);
            this._updateCacheAccess(cacheKey);
            return {
                type: 'original',
                data: this.originalPages.get(cacheKey),
                source: 'frontend_original_cache'
            };
        }

        // 4. 发起新的翻译请求（如果需要翻译）
        if (preferTranslated && this.isServiceRunning) {
            console.log(`缓存未命中，发起翻译请求: ${cacheKey}`);
            await this.requestTranslation(mangaPath, pageIndex);
        }

        return null;
    }

    /**
     * 更新缓存访问时间
     */
    _updateCacheAccess(cacheKey) {
        const metadata = this.cacheMetadata.get(cacheKey) || {};
        metadata.lastAccess = Date.now();
        metadata.accessCount = (metadata.accessCount || 0) + 1;
        this.cacheMetadata.set(cacheKey, metadata);
    }

    /**
     * 缓存原始页面
     */
    cacheOriginalPage(mangaPath, pageIndex, imageData) {
        const cacheKey = `${mangaPath}:${pageIndex}`;
        this.originalPages.set(cacheKey, imageData);

        const metadata = this.cacheMetadata.get(cacheKey) || {};
        metadata.timestamp = Date.now();
        metadata.type = 'original';
        this.cacheMetadata.set(cacheKey, metadata);

        this._limitCacheSize();
        this._saveCacheToStorage();

        console.log(`缓存原始页面: ${cacheKey}`);
    }

    /**
     * 启动翻译服务
     */
    async startService(translatorType = null, apiKey = null, model = null) {
        try {
            const requestData = {};

            // 如果没有指定翻译器类型，则不传递，让后端使用配置文件中的设置
            if (translatorType) {
                requestData.translator_type = translatorType;
            }
            
            if (apiKey) {
                requestData.api_key = apiKey;
            }
            if (model) {
                requestData.model = model;
            }
            
            const response = await fetch('/api/realtime-translation/start-service', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.isServiceRunning = true;
                this._startStatusMonitoring();
                console.log('实时翻译服务启动成功:', result.message);
                
                if (this.onStatusChanged) {
                    this.onStatusChanged('service_started', result);
                }
                
                return true;
            } else {
                throw new Error(result.message || '启动服务失败');
            }
            
        } catch (error) {
            console.error('启动实时翻译服务失败:', error);
            // 检查是否有ElMessage可用
            if (typeof ElMessage !== 'undefined') {
                ElMessage.error(`启动翻译服务失败: ${error.message}`);
            }
            return false;
        }
    }
    
    /**
     * 停止翻译服务
     */
    async stopService() {
        try {
            const response = await fetch('/api/realtime-translation/stop-service', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.isServiceRunning = false;
                this._stopStatusMonitoring();
                this.translatedPages.clear();
                console.log('实时翻译服务停止成功');
                
                if (this.onStatusChanged) {
                    this.onStatusChanged('service_stopped', result);
                }
                
                return true;
            } else {
                throw new Error(result.message || '停止服务失败');
            }
            
        } catch (error) {
            console.error('停止实时翻译服务失败:', error);
            // 检查是否有ElMessage可用
            if (typeof ElMessage !== 'undefined') {
                ElMessage.error(`停止翻译服务失败: ${error.message}`);
            }
            return false;
        }
    }
    
    /**
     * 设置当前漫画
     */
    async setCurrentManga(mangaPath, currentPage = 0) {
        try {
            if (!this.isServiceRunning) {
                console.warn('翻译服务未启动，无法设置当前漫画');
                return false;
            }
            
            const response = await fetch('/api/realtime-translation/set-current-manga', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    manga_path: mangaPath,
                    current_page: currentPage
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                // 如果切换了漫画，清空缓存
                if (this.currentManga !== mangaPath) {
                    this.translatedPages.clear();
                }
                
                this.currentManga = mangaPath;
                this.currentPage = currentPage;
                
                console.log('设置当前漫画成功:', result.message);
                
                if (this.onStatusChanged) {
                    this.onStatusChanged('manga_changed', {
                        manga_path: mangaPath,
                        current_page: currentPage
                    });
                }
                
                return true;
            } else {
                throw new Error(result.message || '设置当前漫画失败');
            }
            
        } catch (error) {
            console.error('设置当前漫画失败:', error);
            ElMessage.error(`设置当前漫画失败: ${error.message}`);
            return false;
        }
    }
    
    /**
     * 请求翻译指定页面（优化版本，减少重复请求）
     */
    async requestTranslation(mangaPath, pageIndices, priority = 10) {
        try {
            if (!this.isServiceRunning) {
                console.warn('翻译服务未启动，无法请求翻译');
                return false;
            }

            const indices = Array.isArray(pageIndices) ? pageIndices : [pageIndices];

            // 过滤已缓存的页面，减少重复请求（修复版本）
            const uncachedIndices = [];
            const timestamp = new Date().toLocaleTimeString();

            for (const pageIndex of indices) {
                const translationCacheKey = `TRANS_${mangaPath}:${pageIndex}`;
                const timestamp_inner = new Date().toLocaleTimeString();

                // 1. 检查前端翻译页面缓存（内存base64）
                if (this.translatedPages.has(translationCacheKey)) {
                    console.log(`💾 [${timestamp_inner}] 页面${pageIndex + 1}前端翻译缓存命中（内存base64），跳过请求 (键: ${translationCacheKey})`);
                    continue;
                }

                // 2. 检查后端持久化WebP缓存（磁盘文件）
                const hasBackendWebPCache = await this._quickCheckPersistentWebPCache(mangaPath, pageIndex);
                if (hasBackendWebPCache) {
                    console.log(`🗄️ [${timestamp_inner}] 页面${pageIndex + 1}后端持久化WebP缓存命中（磁盘文件），跳过请求`);
                    continue;
                }

                // 3. 检查后端实时翻译工具缓存（内存数组）
                const hasBackendTranslationToolCache = await this._quickCheckBackendTranslationToolCache(mangaPath, pageIndex);
                if (hasBackendTranslationToolCache) {
                    console.log(`🧠 [${timestamp_inner}] 页面${pageIndex + 1}后端翻译工具缓存命中（内存数组），跳过请求`);
                    continue;
                }

                // 4. 页面需要翻译，加入请求队列
                uncachedIndices.push(pageIndex);
                console.log(`🔄 [${timestamp_inner}] 页面${pageIndex + 1}需要翻译，加入请求队列`);
            }

            if (uncachedIndices.length === 0) {
                console.log(`✅ [${timestamp}] 所有${indices.length}个页面都已有翻译缓存，跳过翻译请求`);
                return true;
            }

            console.log(`请求翻译 ${uncachedIndices.length}/${indices.length} 个页面:`, uncachedIndices);

            const response = await fetch('/api/realtime-translation/request-translation', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    manga_path: mangaPath,
                    page_indices: uncachedIndices,
                    priority: priority
                })
            });

            const result = await response.json();

            if (result.success) {
                console.log('请求翻译成功:', result.message);
                return true;
            } else {
                throw new Error(result.message || '请求翻译失败');
            }

        } catch (error) {
            console.error('请求翻译失败:', error);
            return false;
        }
    }

    /**
     * 快速检查后端持久化WebP缓存（磁盘文件）
     */
    async _quickCheckPersistentWebPCache(mangaPath, pageIndex) {
        try {
            const response = await fetch(`/api/realtime-translation/check-cache/${encodeURIComponent(mangaPath)}/${pageIndex}`);
            const result = await response.json();

            if (result.success) {
                const hasCache = result.has_cache === true;
                const cacheSource = result.cache_source;
                if (hasCache && (cacheSource === 'persistent_webp' || cacheSource === 'memory')) {
                    console.log(`🗄️ 后端持久化WebP缓存检查: 页面${pageIndex + 1} -> 命中 (来源: ${cacheSource})`);
                    return true;
                }
            }

            return false;
        } catch (error) {
            console.debug('检查后端持久化WebP缓存失败:', error);
            return false;
        }
    }

    /**
     * 快速检查后端实时翻译工具缓存（内存数组）
     */
    async _quickCheckBackendTranslationToolCache(mangaPath, pageIndex) {
        try {
            const response = await fetch(`/api/realtime-translation/check-cache/${encodeURIComponent(mangaPath)}/${pageIndex}`);
            const result = await response.json();

            if (result.success) {
                const hasCache = result.has_cache === true;
                const cacheSource = result.cache_source;
                if (hasCache && (cacheSource === 'memory' || cacheSource === 'translation_tool')) {
                    console.log(`🧠 后端翻译工具缓存检查: 页面${pageIndex + 1} -> 命中 (来源: ${cacheSource})`);
                    return true;
                }
            }

            return false;
        } catch (error) {
            console.debug('检查后端翻译工具缓存失败:', error);
            return false;
        }
    }

    /**
     * 快速检查后端缓存（传统方式，保留作为降级选项）
     */
    async _quickCheckBackendCache(mangaPath, pageIndex) {
        try {
            const response = await fetch(`/api/realtime-translation/check-pages-translated/${encodeURIComponent(mangaPath)}?page_indices=${pageIndex}`);
            const result = await response.json();

            if (result.success && result.results) {
                return result.results[pageIndex] === true;
            }

            return false;
        } catch (error) {
            console.debug('快速检查传统磁盘缓存失败:', error);
            return false;
        }
    }
    
    /**
     * 获取翻译后的页面（四层缓存架构版本）
     */
    async getTranslatedPage(mangaPath, pageIndex) {
        const timestamp = new Date().toLocaleTimeString();
        const translationCacheKey = `TRANS_${mangaPath}:${pageIndex}`;

        try {
            console.log(`🔍 [${timestamp}] 四层缓存架构: 获取翻译页面 ${pageIndex + 1}`);

            // 1. 检查前端翻译页面缓存（内存base64）
            if (this.translatedPages.has(translationCacheKey)) {
                console.log(`💾 [${timestamp}] 页面${pageIndex + 1}前端翻译缓存命中（内存base64） (键: ${translationCacheKey})`);
                this._updateCacheAccess(translationCacheKey);
                return this.translatedPages.get(translationCacheKey);
            }

            console.log(`🔍 [${timestamp}] 检查后端三层缓存: 页面${pageIndex + 1}`);

            // 2. 通过API检查后端三层缓存（持久化WebP + 翻译工具 + 原始漫画）
            const response = await fetch(`/api/realtime-translation/translated-page/${encodeURIComponent(mangaPath)}/${pageIndex}`);
            const result = await response.json();

            // 增强数据验证：检查翻译状态和数据有效性
            const hasValidData = result.image_data &&
                                 typeof result.image_data === 'string' &&
                                 result.image_data.length > 0;

            if (result.is_translated && hasValidData) {
                // 根据缓存来源显示详细日志
                let cacheSource = '未知缓存';
                if (result.cache_source === 'persistent_webp') {
                    cacheSource = '后端持久化WebP缓存（磁盘文件）';
                } else if (result.cache_source === 'memory') {
                    cacheSource = '后端内存缓存（快速访问）';
                } else if (result.cache_source === 'sqlite') {
                    cacheSource = '后端SQLite缓存（完整数据）';
                } else if (result.cache_source === 'legacy') {
                    cacheSource = '后端传统缓存（兼容性）';
                }

                console.log(`🗄️ [${timestamp}] 页面${pageIndex + 1}${cacheSource}命中 (数据长度: ${result.image_data.length}字符)`);

                // 检查是否是新的翻译结果
                const isNewTranslation = !this.translatedPages.has(translationCacheKey);

                // 缓存翻译结果到前端翻译缓存（使用正确的键）
                this._cacheTranslatedPageWithType(mangaPath, pageIndex, result.image_data, 'translated');

                // 只有新的翻译结果才触发回调
                if (isNewTranslation && this.onTranslationCompleted) {
                    console.log(`🔔 [${timestamp}] 触发翻译完成回调: 页面${pageIndex + 1}`);
                    this.onTranslationCompleted(mangaPath, pageIndex, result.image_data);
                }

                return result.image_data;
            } else {
                // 详细的错误信息，帮助调试
                const debugInfo = {
                    is_translated: result.is_translated,
                    has_image_data: !!result.image_data,
                    data_type: typeof result.image_data,
                    data_length: result.image_data ? result.image_data.length : 0,
                    cache_source: result.cache_source || 'unknown',
                    error: result.error || 'no_error'
                };

                // 如果是页面不存在错误，使用debug级别避免日志污染
                if (result.error && result.error.includes('页面索引超出范围')) {
                    console.debug(`📄 [${timestamp}] 页面${pageIndex + 1}不存在:`, debugInfo);
                } else {
                    console.log(`❌ [${timestamp}] 页面${pageIndex + 1}数据验证失败:`, debugInfo);
                }

                // 对于明确的错误（如页面不存在），标记为已处理，避免重复检查
                if (result.error) {
                    const errorCacheKey = `ERROR_${mangaPath}:${pageIndex}`;
                    this.translatedPages.set(errorCacheKey, null);
                }
            }

            return null;

        } catch (error) {
            console.error(`❌ [${timestamp}] 四层缓存架构: 获取翻译页面失败 ${pageIndex + 1}:`, error);
            return null;
        }
    }

    /**
     * 缓存翻译页面（四层缓存架构版本）
     */
    _cacheTranslatedPage(mangaPath, pageIndex, imageData) {
        // 使用新的带类型标记的缓存方法
        this._cacheTranslatedPageWithType(mangaPath, pageIndex, imageData, 'translated');
    }

    /**
     * 带类型标记的缓存页面方法
     */
    _cacheTranslatedPageWithType(mangaPath, pageIndex, imageData, cacheType) {
        const timestamp = new Date().toLocaleTimeString();
        const cacheKey = cacheType === 'translated' ? `TRANS_${mangaPath}:${pageIndex}` : `ORIG_${mangaPath}:${pageIndex}`;
        const targetCache = cacheType === 'translated' ? this.translatedPages : this.originalPages;

        // 检查是否已存在
        const wasExisting = targetCache.has(cacheKey);

        // 验证缓存内容类型
        if (cacheType === 'translated' && imageData) {
            // 简单验证：翻译图像通常包含特定的base64前缀或格式
            console.log(`🔍 [${timestamp}] 验证翻译图像数据: 页面${pageIndex + 1}, 数据长度: ${imageData.length}字符`);
        }

        targetCache.set(cacheKey, imageData);

        const metadata = this.cacheMetadata.get(cacheKey) || {};
        metadata.timestamp = Date.now();
        metadata.type = cacheType;
        metadata.lastAccess = Date.now();
        metadata.accessCount = (metadata.accessCount || 0) + 1;
        metadata.dataSize = imageData ? imageData.length : 0;
        this.cacheMetadata.set(cacheKey, metadata);

        this._limitCacheSize();
        this._saveCacheToStorage();

        const action = wasExisting ? '更新' : '新增';
        const cacheTypeName = cacheType === 'translated' ? '前端翻译缓存（内存base64）' : '前端原始缓存（内存base64）';
        console.log(`💾 [${timestamp}] ${action}${cacheTypeName}: 页面${pageIndex + 1} (键: ${cacheKey}, 大小: ${targetCache.size})`);
    }
    
    /**
     * 检查页面是否已翻译
     */
    async checkPagesTranslated(mangaPath, pageIndices) {
        try {
            const pageIndicesStr = Array.isArray(pageIndices) ? pageIndices.join(',') : pageIndices.toString();
            
            const response = await fetch(`/api/realtime-translation/check-pages-translated/${encodeURIComponent(mangaPath)}?page_indices=${pageIndicesStr}`);
            const result = await response.json();
            
            if (result.success) {
                return result.results;
            }
            
            return {};
            
        } catch (error) {
            console.error('检查翻译状态失败:', error);
            return {};
        }
    }
    
    /**
     * 获取翻译状态
     */
    async getStatus() {
        try {
            const response = await fetch('/api/realtime-translation/status');
            const status = await response.json();
            return status;
            
        } catch (error) {
            console.error('获取翻译状态失败:', error);
            return null;
        }
    }
    
    /**
     * 自动翻译当前页面及附近页面
     */
    async autoTranslateCurrent() {
        try {
            if (!this.isServiceRunning) {
                return false;
            }
            
            const response = await fetch('/api/realtime-translation/auto-translate-current', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                console.log('自动翻译请求成功:', result.message);
                return true;
            }
            
            return false;
            
        } catch (error) {
            console.error('自动翻译失败:', error);
            return false;
        }
    }
    
    /**
     * 启用/禁用自动翻译
     */
    setAutoTranslate(enabled) {
        this.autoTranslateEnabled = enabled;
        console.log('自动翻译设置:', enabled ? '启用' : '禁用');
    }
    
    /**
     * 页面切换时的处理
     */
    async onPageChanged(mangaPath, newPageIndex) {
        if (this.currentManga === mangaPath) {
            this.currentPage = newPageIndex;
            
            // 如果启用了自动翻译，自动请求翻译
            if (this.autoTranslateEnabled && this.isServiceRunning) {
                await this.setCurrentManga(mangaPath, newPageIndex);
            }
        }
    }
    
    /**
     * 开始状态监控
     */
    _startStatusMonitoring() {
        if (this.statusCheckInterval) {
            clearInterval(this.statusCheckInterval);
        }
        
        this.statusCheckInterval = setInterval(async () => {
            const status = await this.getStatus();
            if (status && this.onStatusChanged) {
                this.onStatusChanged('status_update', status);
            }

            // 检查当前页面是否有新的翻译结果（降低频率，避免过度请求）
            if (this.currentManga && status && status.is_running) {
                // 只在状态检查的每第3次才检查翻译状态
                this._statusCheckCount = (this._statusCheckCount || 0) + 1;
                if (this._statusCheckCount % 3 === 0) {
                    await this._checkCurrentPageTranslation();
                }
            }
        }, 3000); // 每3秒检查一次状态（从2秒改为3秒）
    }
    
    /**
     * 检查当前页面翻译状态
     */
    async _checkCurrentPageTranslation() {
        if (!this.currentManga) return;

        try {
            // 获取漫画总页数，避免检查不存在的页面
            let totalPages = 999; // 默认值
            try {
                const response = await fetch(`/api/manga/info/${encodeURIComponent(this.currentManga)}`);
                if (response.ok) {
                    const mangaInfo = await response.json();
                    totalPages = mangaInfo.total_pages || 999;
                }
            } catch (e) {
                console.debug('获取漫画信息失败，使用默认页数限制:', e);
            }

            // 检查当前页面和相邻页面的翻译状态（限制在有效范围内）
            const pagesToCheck = [];
            const startPage = Math.max(0, this.currentPage - 1);
            const endPage = Math.min(this.currentPage + 1, totalPages - 1);

            for (let i = startPage; i <= endPage; i++) {
                pagesToCheck.push(i);
            }

            // 限制检查频率，避免过度请求
            const now = Date.now();
            if (this._lastCheckTime && (now - this._lastCheckTime) < 5000) {
                return; // 5秒内不重复检查
            }
            this._lastCheckTime = now;

            for (const pageIndex of pagesToCheck) {
                const translationCacheKey = `TRANS_${this.currentManga}:${pageIndex}`;

                // 如果本地缓存中没有，检查服务器
                if (!this.translatedPages.has(translationCacheKey)) {
                    const result = await this.getTranslatedPage(this.currentManga, pageIndex);

                    // 如果返回错误（如页面不存在），停止检查后续页面
                    if (result === null) {
                        console.debug(`页面${pageIndex + 1}检查失败，停止后续检查`);
                        break;
                    }
                }
            }
        } catch (error) {
            // 静默处理错误，避免干扰正常使用
            console.debug('检查翻译状态失败:', error);
        }
    }

    /**
     * 停止状态监控
     */
    _stopStatusMonitoring() {
        if (this.statusCheckInterval) {
            clearInterval(this.statusCheckInterval);
            this.statusCheckInterval = null;
        }
    }
    
    /**
     * 获取缓存统计信息
     */
    getCacheStatistics() {
        const stats = {
            translatedPages: this.translatedPages.size,
            originalPages: this.originalPages.size,
            totalCacheSize: this.translatedPages.size + this.originalPages.size,
            maxTranslatedPages: this.cacheConfig.maxTranslatedPages,
            maxOriginalPages: this.cacheConfig.maxOriginalPages,
            cacheHitRate: 0,
            recentAccess: []
        };

        // 计算缓存命中率（基于访问次数）
        let totalAccess = 0;
        let cacheHits = 0;

        for (const [key, metadata] of this.cacheMetadata.entries()) {
            if (metadata.accessCount) {
                totalAccess += metadata.accessCount;
                cacheHits += metadata.accessCount;
            }
        }

        if (totalAccess > 0) {
            stats.cacheHitRate = (cacheHits / totalAccess * 100).toFixed(2);
        }

        // 最近访问的页面
        const recentEntries = [...this.cacheMetadata.entries()]
            .filter(([key, metadata]) => metadata.lastAccess)
            .sort(([, a], [, b]) => b.lastAccess - a.lastAccess)
            .slice(0, 10);

        stats.recentAccess = recentEntries.map(([key, metadata]) => ({
            key,
            lastAccess: new Date(metadata.lastAccess).toLocaleString(),
            accessCount: metadata.accessCount || 0,
            type: metadata.type || 'unknown'
        }));

        return stats;
    }

    /**
     * 清空缓存
     */
    clearCache(type = 'all') {
        let clearedCount = 0;

        switch (type) {
            case 'translated':
                clearedCount = this.translatedPages.size;
                this.translatedPages.clear();
                // 清理相关元数据
                for (const [key, metadata] of this.cacheMetadata.entries()) {
                    if (metadata.type === 'translated') {
                        this.cacheMetadata.delete(key);
                    }
                }
                break;

            case 'original':
                clearedCount = this.originalPages.size;
                this.originalPages.clear();
                // 清理相关元数据
                for (const [key, metadata] of this.cacheMetadata.entries()) {
                    if (metadata.type === 'original') {
                        this.cacheMetadata.delete(key);
                    }
                }
                break;

            case 'all':
            default:
                clearedCount = this.translatedPages.size + this.originalPages.size;
                this.translatedPages.clear();
                this.originalPages.clear();
                this.cacheMetadata.clear();
                break;
        }

        this._saveCacheToStorage();
        console.log(`清空${type}缓存: ${clearedCount} 项`);

        return clearedCount;
    }

    /**
     * 智能预加载页面缓存（与前端预加载策略协调）
     */
    async preloadPages(mangaPath, currentPage, mode = 'single') {
        const timestamp = new Date().toLocaleTimeString();

        // 预加载配置（与前端保持一致）
        const preloadConfig = {
            immediate: { single: 1, double: 2 },
            progressive: { single: 3, double: 4 }
        };

        const immediateRange = preloadConfig.immediate[mode];
        const progressiveRange = preloadConfig.progressive[mode];

        console.log(`🔄 [${timestamp}] 实时翻译模块: 智能预加载开始 (模式: ${mode})`);

        try {
            // 第一阶段：立即预加载相邻页面的翻译
            const immediatePages = [];
            for (let i = 1; i <= immediateRange; i++) {
                const nextPage = currentPage + i;
                if (nextPage < 1000) { // 假设最大页数限制
                    immediatePages.push(nextPage);
                }
            }

            if (immediatePages.length > 0) {
                console.log(`⚡ [${timestamp}] 实时翻译模块: 立即预加载 ${immediatePages.map(p => p + 1).join(', ')}`);
                await this.requestTranslation(mangaPath, immediatePages, 6); // 中高优先级
            }

            // 第二阶段：延迟预加载扩展范围
            setTimeout(async () => {
                const progressivePages = [];

                // 向前
                for (let i = 1; i <= progressiveRange; i++) {
                    const prevPage = currentPage - i;
                    if (prevPage >= 0) {
                        progressivePages.push(prevPage);
                    }
                }

                // 向后（跳过立即范围）
                for (let i = immediateRange + 1; i <= progressiveRange; i++) {
                    const nextPage = currentPage + i;
                    if (nextPage < 1000) {
                        progressivePages.push(nextPage);
                    }
                }

                if (progressivePages.length > 0) {
                    console.log(`🔮 [${timestamp}] 实时翻译模块: 渐进式预加载 ${progressivePages.map(p => p + 1).join(', ')}`);
                    await this.requestTranslation(mangaPath, progressivePages, 2); // 低优先级
                }
            }, 2000); // 延迟2秒

        } catch (error) {
            console.warn(`⚠️ [${timestamp}] 实时翻译模块: 预加载失败:`, error);
        }
    }

    /**
     * 销毁管理器
     */
    destroy() {
        this._stopStatusMonitoring();

        // 保存缓存到存储
        this._saveCacheToStorage();

        // 清空内存缓存
        this.translatedPages.clear();
        this.originalPages.clear();
        this.cacheMetadata.clear();

        this.isServiceRunning = false;

        console.log('实时翻译管理器已销毁');
    }
}

// 为了向后兼容，同时导出两个名称
window.RealtimeTranslation = RealtimeTranslationManager;
window.RealtimeTranslationManager = RealtimeTranslationManager;

// 全局实例
window.realtimeTranslationManager = new RealtimeTranslationManager();

// 导出到全局作用域
if (typeof module !== 'undefined' && module.exports) {
    module.exports = RealtimeTranslationManager;
}
