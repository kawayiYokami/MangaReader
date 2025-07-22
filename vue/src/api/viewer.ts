import { ElMessage } from 'element-plus';
import { API_BASE_URL } from './base';

// ==================== 会话管理 ====================

class SessionManager {
    private sessionId: string | null = null;

    async getSessionId(): Promise<string> {
        if (!this.sessionId) {
            this.sessionId = await this.createSession();
        }
        return this.sessionId!;
    }

    async createSession(): Promise<string> {
        try {
            const response = await fetch(`${API_BASE_URL}/api/viewer/session/create`, { method: 'POST' });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            if (data.success && data.session_id) {
                this.sessionId = data.session_id;
                // console.log(`会话创建成功: ${this.sessionId}`);
                return data.session_id;
            } else {
                throw new Error(data.message || '创建会话失败');
            }
        } catch (error) {
            console.error('创建会话时出错:', error);
            ElMessage.error('无法与服务器建立查看会话');
            throw error;
        }
    }

    async destroySession(): Promise<void> {
        if (!this.sessionId) return;
        try {
            await fetch(`${API_BASE_URL}/api/viewer/session/${this.sessionId}`, { method: 'DELETE' });
            // console.log(`会话已销毁: ${this.sessionId}`);
            this.sessionId = null;
        } catch (error) {
            console.error('销毁会话时出错:', error);
            // ElMessage.error('销毁会话失败');
        }
    }
}

const sessionManager = new SessionManager();

// ==================== API 封装 ====================

async function fetchWithSession(url: string, options: RequestInit = {}): Promise<any> {
    const sessionId = await sessionManager.getSessionId();
    const headers = new Headers(options.headers || {});
    headers.set('X-Session-Id', sessionId);
    headers.set('Content-Type', 'application/json');

    const fullUrl = `${API_BASE_URL}${url}`;
    const response = await fetch(fullUrl, { ...options, headers });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: '未知错误' }));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }
    
    const responseData = await response.json();
    if (responseData.success === false) { // 检查明确的 false
        throw new Error(responseData.message || 'API 请求未成功');
    }
    // 新架构下，我们只关心返回的数据本身
    return responseData;
}

export const viewerApi = {
    // 会话管理
    createSession: () => sessionManager.createSession(),
    destroySession: () => sessionManager.destroySession(),

    // 漫画操作
    setCurrentManga: async (mangaPath: string, page: number = 0) => {
        return fetchWithSession('/api/viewer/manga/set', {
            method: 'POST',
            body: JSON.stringify({ manga_path: mangaPath, page }),
        });
    },

    // 页面元数据获取
    getPageMetadata: async (page: number, displayMode: 'single' | 'double') => {
        const data = await fetchWithSession('/api/viewer/page/get', {
            method: 'POST',
            body: JSON.stringify({ page, display_mode: displayMode }),
        });
        return data; // 后端直接返回 { success: true, images: [...] }
    },
};