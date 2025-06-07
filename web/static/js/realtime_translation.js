/**
 * 实时翻译功能模块
 */

class RealtimeTranslationManager {
    constructor() {
        this.isServiceRunning = false;
        this.currentManga = null;
        this.currentPage = 0;
        this.translatedPages = new Map(); // 缓存翻译结果
        this.statusCheckInterval = null;
        this.autoTranslateEnabled = false;
        
        // 事件回调
        this.onTranslationCompleted = null;
        this.onStatusChanged = null;
        
        console.log('实时翻译管理器初始化完成');
    }
    
    /**
     * 启动翻译服务
     */
    async startService(translatorType = '智谱', apiKey = null, model = null) {
        try {
            const requestData = {
                translator_type: translatorType
            };
            
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
            ElMessage.error(`启动翻译服务失败: ${error.message}`);
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
            ElMessage.error(`停止翻译服务失败: ${error.message}`);
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
     * 请求翻译指定页面
     */
    async requestTranslation(mangaPath, pageIndices, priority = 10) {
        try {
            if (!this.isServiceRunning) {
                console.warn('翻译服务未启动，无法请求翻译');
                return false;
            }
            
            const response = await fetch('/api/realtime-translation/request-translation', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    manga_path: mangaPath,
                    page_indices: Array.isArray(pageIndices) ? pageIndices : [pageIndices],
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
     * 获取翻译后的页面
     */
    async getTranslatedPage(mangaPath, pageIndex) {
        try {
            // 先检查本地缓存
            const cacheKey = `${mangaPath}:${pageIndex}`;
            if (this.translatedPages.has(cacheKey)) {
                return this.translatedPages.get(cacheKey);
            }
            
            const response = await fetch(`/api/realtime-translation/translated-page/${encodeURIComponent(mangaPath)}/${pageIndex}`);
            const result = await response.json();
            
            if (result.is_translated && result.image_data) {
                // 缓存翻译结果
                this.translatedPages.set(cacheKey, result.image_data);
                
                if (this.onTranslationCompleted) {
                    this.onTranslationCompleted(mangaPath, pageIndex, result.image_data);
                }
                
                return result.image_data;
            }
            
            return null;
            
        } catch (error) {
            console.error('获取翻译页面失败:', error);
            return null;
        }
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
        }, 2000); // 每2秒检查一次状态
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
     * 销毁管理器
     */
    destroy() {
        this._stopStatusMonitoring();
        this.translatedPages.clear();
        this.isServiceRunning = false;
    }
}

// 全局实例
window.realtimeTranslationManager = new RealtimeTranslationManager();

// 导出到全局作用域
if (typeof module !== 'undefined' && module.exports) {
    module.exports = RealtimeTranslationManager;
}
