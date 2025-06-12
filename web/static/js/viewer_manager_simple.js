/**
 * 简化的查看器管理器 - 前端组件
 * 
 * 基于翻译工厂架构的极简前端实现
 * 所有业务逻辑都由后端处理，前端只负责UI展示和API调用
 */

class ViewerManager {
    constructor() {
        this.sessionId = null;
        this.currentManga = null;
        this.currentPage = 0;
        this.totalPages = 0;
        this.displayMode = 'single';
        this.translationEnabled = false;
        
        // 事件回调
        this.onImageLoaded = null;
        this.onStatusChanged = null;
        this.onError = null;
        
        console.log('查看器管理器初始化完成');
    }
    
    /**
     * 创建新会话
     */
    async createSession() {
        try {
            const response = await fetch('/api/viewer/session/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();
            
            if (result.success) {
                this.sessionId = result.session_id;
                console.log(`会话创建成功: ${this.sessionId}`);
                return true;
            } else {
                throw new Error(result.message || '创建会话失败');
            }
        } catch (error) {
            console.error('创建会话失败:', error);
            this._handleError('创建会话失败', error);
            return false;
        }
    }
    
    /**
     * 设置当前漫画
     */
    async setCurrentManga(mangaPath, startPage = 0) {
        try {
            if (!this.sessionId) {
                await this.createSession();
            }
            
            const response = await fetch('/api/viewer/manga/set', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Session-ID': this.sessionId
                },
                body: JSON.stringify({
                    manga_path: mangaPath,
                    page: startPage
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();
            
            if (result.success) {
                this.currentManga = result.manga_info;
                this.currentPage = result.current_page;
                this.totalPages = this.currentManga.total_pages;
                
                console.log(`设置当前漫画成功: ${this.currentManga.title}`);
                this._notifyStatusChanged('manga_set', result);
                return result;
            } else {
                throw new Error(result.message || '设置漫画失败');
            }
        } catch (error) {
            console.error('设置当前漫画失败:', error);
            this._handleError('设置漫画失败', error);
            return null;
        }
    }
    
    /**
     * 获取页面图像
     */
    async getPageImages(page, displayMode = 'single', translationEnabled = false) {
        try {
            if (!this.sessionId) {
                throw new Error('会话未创建');
            }
            
            const response = await fetch('/api/viewer/page/get', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Session-ID': this.sessionId
                },
                body: JSON.stringify({
                    page: page,
                    display_mode: displayMode,
                    translation_enabled: translationEnabled
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();
            
            if (result.success) {
                this.currentPage = result.current_page;
                this.displayMode = result.display_mode;
                this.translationEnabled = result.translation_enabled;
                
                console.log(`获取页面图像成功: 页面=${page}, 模式=${displayMode}, 翻译=${translationEnabled}`);
                
                // 通知图像加载完成
                if (this.onImageLoaded) {
                    this.onImageLoaded(result.images);
                }
                
                return result.images;
            } else {
                throw new Error(result.message || '获取页面图像失败');
            }
        } catch (error) {
            console.error('获取页面图像失败:', error);
            this._handleError('获取页面图像失败', error);
            return [];
        }
    }
    
    /**
     * 切换翻译状态
     */
    async toggleTranslation(enabled) {
        try {
            if (!this.sessionId) {
                throw new Error('会话未创建');
            }
            
            const response = await fetch('/api/viewer/translation/toggle', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Session-ID': this.sessionId
                },
                body: JSON.stringify({
                    enabled: enabled
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();
            
            if (result.success) {
                this.translationEnabled = result.translation_enabled;
                console.log(`翻译状态切换: ${enabled ? '启用' : '禁用'}`);
                this._notifyStatusChanged('translation_toggled', result);
                return true;
            } else {
                throw new Error(result.message || '切换翻译状态失败');
            }
        } catch (error) {
            console.error('切换翻译状态失败:', error);
            this._handleError('切换翻译状态失败', error);
            return false;
        }
    }
    
    /**
     * 获取翻译服务状态
     */
    async getTranslationStatus() {
        try {
            if (!this.sessionId) {
                return null;
            }
            
            const response = await fetch('/api/viewer/translation/status', {
                headers: {
                    'X-Session-ID': this.sessionId
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();
            
            if (result.success) {
                return {
                    serviceRunning: result.service_running,
                    sessionTranslationEnabled: result.session_translation_enabled,
                    currentTranslator: result.current_translator
                };
            }
        } catch (error) {
            console.error('获取翻译状态失败:', error);
        }
        
        return null;
    }
    
    /**
     * 销毁会话
     */
    async destroySession() {
        try {
            if (!this.sessionId) {
                return true;
            }
            
            const response = await fetch(`/api/viewer/session/${this.sessionId}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();
            
            if (result.success) {
                console.log(`会话销毁成功: ${this.sessionId}`);
                this.sessionId = null;
                return true;
            }
        } catch (error) {
            console.error('销毁会话失败:', error);
        }
        
        return false;
    }
    
    /**
     * 通知状态变化
     */
    _notifyStatusChanged(eventType, data) {
        if (this.onStatusChanged) {
            this.onStatusChanged(eventType, data);
        }
    }
    
    /**
     * 处理错误
     */
    _handleError(message, error) {
        if (this.onError) {
            this.onError(message, error);
        }
    }
    
    /**
     * 获取当前状态
     */
    getCurrentState() {
        return {
            sessionId: this.sessionId,
            currentManga: this.currentManga,
            currentPage: this.currentPage,
            totalPages: this.totalPages,
            displayMode: this.displayMode,
            translationEnabled: this.translationEnabled
        };
    }
}

// 导出全局实例
window.ViewerManager = ViewerManager;
