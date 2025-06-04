/**
 * 文件API适配器
 * 提供统一的文件操作接口，自动适配Electron和Web环境
 */
class FileAPIAdapter {
    constructor() {
        this.isElectron = EnvironmentDetector.isElectron();
        this.implementation = this.isElectron ? new ElectronFileAPI() : new WebFileAPI();
        
        console.log(`📁 FileAPIAdapter initialized for ${this.isElectron ? 'Electron' : 'Web'} environment`);
    }

    /**
     * 选择单个文件
     */
    async selectFile(options = {}) {
        return await this.implementation.selectFile(options);
    }

    /**
     * 选择文件夹
     */
    async selectDirectory(options = {}) {
        return await this.implementation.selectDirectory(options);
    }

    /**
     * 选择多个文件
     */
    async selectMultipleFiles(options = {}) {
        return await this.implementation.selectMultipleFiles(options);
    }

    /**
     * 保存文件
     */
    async saveFile(data, options = {}) {
        return await this.implementation.saveFile(data, options);
    }

    /**
     * 显示文件在文件管理器中
     */
    async showItemInFolder(filePath) {
        return await this.implementation.showItemInFolder(filePath);
    }

    /**
     * 打开文件或文件夹
     */
    async openPath(filePath) {
        return await this.implementation.openPath(filePath);
    }

    /**
     * 获取当前实现类型
     */
    getImplementationType() {
        return this.isElectron ? 'electron' : 'web';
    }
}

/**
 * 文件API接口基类
 */
class IFileAPI {
    async selectFile(options) {
        throw new Error('selectFile method not implemented');
    }

    async selectDirectory(options) {
        throw new Error('selectDirectory method not implemented');
    }

    async selectMultipleFiles(options) {
        throw new Error('selectMultipleFiles method not implemented');
    }

    async saveFile(data, options) {
        throw new Error('saveFile method not implemented');
    }

    async showItemInFolder(filePath) {
        throw new Error('showItemInFolder method not implemented');
    }

    async openPath(filePath) {
        throw new Error('openPath method not implemented');
    }
}

/**
 * Electron环境的文件API实现
 */
class ElectronFileAPI extends IFileAPI {
    async selectFile(options = {}) {
        try {
            const result = await window.electronAPI.file.selectFile(options);
            console.log('📁 Electron选择文件:', result);
            return result;
        } catch (error) {
            console.error('❌ Electron选择文件失败:', error);
            throw error;
        }
    }

    async selectDirectory(options = {}) {
        try {
            const result = await window.electronAPI.file.selectDirectory(options);
            console.log('📁 Electron选择文件夹:', result);
            return result;
        } catch (error) {
            console.error('❌ Electron选择文件夹失败:', error);
            throw error;
        }
    }

    async selectMultipleFiles(options = {}) {
        try {
            const result = await window.electronAPI.file.selectMultipleFiles(options);
            console.log('📁 Electron选择多个文件:', result?.length || 0, '个文件');
            return result;
        } catch (error) {
            console.error('❌ Electron选择多个文件失败:', error);
            throw error;
        }
    }

    async saveFile(data, options = {}) {
        try {
            const filePath = await window.electronAPI.file.saveFile(options);
            if (filePath) {
                // 在Electron中，我们需要通过后端API保存文件
                // 这里返回文件路径，实际保存由调用方处理
                console.log('📁 Electron保存文件路径:', filePath);
                return filePath;
            }
            return null;
        } catch (error) {
            console.error('❌ Electron保存文件失败:', error);
            throw error;
        }
    }

    async showItemInFolder(filePath) {
        try {
            await window.electronAPI.file.showItemInFolder(filePath);
            console.log('📁 Electron在文件管理器中显示:', filePath);
            return true;
        } catch (error) {
            console.error('❌ Electron显示文件失败:', error);
            throw error;
        }
    }

    async openPath(filePath) {
        try {
            await window.electronAPI.file.openPath(filePath);
            console.log('📁 Electron打开路径:', filePath);
            return true;
        } catch (error) {
            console.error('❌ Electron打开路径失败:', error);
            throw error;
        }
    }
}

/**
 * Web环境的文件API实现
 */
class WebFileAPI extends IFileAPI {
    async selectFile(options = {}) {
        return new Promise((resolve, reject) => {
            try {
                const input = document.createElement('input');
                input.type = 'file';
                input.accept = options.accept || '*/*';
                
                input.onchange = (event) => {
                    const file = event.target.files[0];
                    if (file) {
                        const result = {
                            file: file,
                            name: file.name,
                            size: file.size,
                            type: file.type,
                            lastModified: file.lastModified
                        };
                        console.log('📁 Web选择文件:', result);
                        resolve(result);
                    } else {
                        resolve(null);
                    }
                };
                
                input.oncancel = () => resolve(null);
                input.click();
                
            } catch (error) {
                console.error('❌ Web选择文件失败:', error);
                reject(error);
            }
        });
    }

    async selectDirectory(options = {}) {
        // Web环境不支持文件夹选择
        console.warn('⚠️ Web环境不支持文件夹选择');
        throw new Error('Web环境不支持文件夹选择，请使用文件上传');
    }

    async selectMultipleFiles(options = {}) {
        return new Promise((resolve, reject) => {
            try {
                const input = document.createElement('input');
                input.type = 'file';
                input.multiple = true;
                input.accept = options.accept || '*/*';
                
                input.onchange = (event) => {
                    const files = Array.from(event.target.files);
                    const results = files.map(file => ({
                        file: file,
                        name: file.name,
                        size: file.size,
                        type: file.type,
                        lastModified: file.lastModified
                    }));
                    
                    console.log('📁 Web选择多个文件:', results.length, '个文件');
                    resolve(results);
                };
                
                input.oncancel = () => resolve([]);
                input.click();
                
            } catch (error) {
                console.error('❌ Web选择多个文件失败:', error);
                reject(error);
            }
        });
    }

    async saveFile(data, options = {}) {
        try {
            const blob = new Blob([data], { type: options.type || 'application/octet-stream' });
            const url = URL.createObjectURL(blob);
            
            const a = document.createElement('a');
            a.href = url;
            a.download = options.defaultName || 'download';
            a.style.display = 'none';
            
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            
            // 清理URL对象
            setTimeout(() => URL.revokeObjectURL(url), 1000);
            
            console.log('📁 Web保存文件:', options.defaultName);
            return true;
            
        } catch (error) {
            console.error('❌ Web保存文件失败:', error);
            throw error;
        }
    }

    async showItemInFolder(filePath) {
        // Web环境不支持在文件管理器中显示
        console.warn('⚠️ Web环境不支持在文件管理器中显示文件');
        throw new Error('Web环境不支持在文件管理器中显示文件');
    }

    async openPath(filePath) {
        // Web环境不支持打开本地路径
        console.warn('⚠️ Web环境不支持打开本地路径');
        throw new Error('Web环境不支持打开本地路径');
    }
}

// 导出到全局作用域
if (typeof window !== 'undefined') {
    window.FileAPIAdapter = FileAPIAdapter;
    window.IFileAPI = IFileAPI;
    window.ElectronFileAPI = ElectronFileAPI;
    window.WebFileAPI = WebFileAPI;
}

// 支持模块化导入
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { FileAPIAdapter, IFileAPI, ElectronFileAPI, WebFileAPI };
}
