const { dialog, shell } = require('electron');
const fs = require('fs').promises;
const path = require('path');

/**
 * 文件系统API
 * 提供统一的文件操作接口
 */
class FileSystemAPI {
    constructor() {
        console.log('📁 FileSystemAPI initialized');
    }

    /**
     * 选择单个文件
     */
    async selectFile(options = {}) {
        try {
            const defaultOptions = {
                properties: ['openFile'],
                filters: [
                    { name: '所有文件', extensions: ['*'] }
                ]
            };

            const mergedOptions = { ...defaultOptions, ...options };
            const result = await dialog.showOpenDialog(mergedOptions);

            if (result.canceled || result.filePaths.length === 0) {
                return null;
            }

            const filePath = result.filePaths[0];
            console.log('📁 选择文件:', filePath);
            
            return {
                path: filePath,
                name: path.basename(filePath),
                size: await this.getFileSize(filePath),
                extension: path.extname(filePath)
            };

        } catch (error) {
            console.error('❌ 选择文件失败:', error);
            throw error;
        }
    }

    /**
     * 选择文件夹
     */
    async selectDirectory(options = {}) {
        try {
            const defaultOptions = {
                properties: ['openDirectory']
            };

            const mergedOptions = { ...defaultOptions, ...options };
            const result = await dialog.showOpenDialog(mergedOptions);

            if (result.canceled || result.filePaths.length === 0) {
                return null;
            }

            const dirPath = result.filePaths[0];
            console.log('📁 选择文件夹:', dirPath);
            
            return {
                path: dirPath,
                name: path.basename(dirPath)
            };

        } catch (error) {
            console.error('❌ 选择文件夹失败:', error);
            throw error;
        }
    }

    /**
     * 选择多个文件
     */
    async selectMultipleFiles(options = {}) {
        try {
            const defaultOptions = {
                properties: ['openFile', 'multiSelections'],
                filters: [
                    { name: '漫画文件', extensions: ['zip', 'rar', 'cbz', 'cbr'] },
                    { name: '所有文件', extensions: ['*'] }
                ]
            };

            const mergedOptions = { ...defaultOptions, ...options };
            const result = await dialog.showOpenDialog(mergedOptions);

            if (result.canceled || result.filePaths.length === 0) {
                return [];
            }

            console.log('📁 选择多个文件:', result.filePaths.length, '个文件');
            
            const files = await Promise.all(
                result.filePaths.map(async (filePath) => ({
                    path: filePath,
                    name: path.basename(filePath),
                    size: await this.getFileSize(filePath),
                    extension: path.extname(filePath)
                }))
            );

            return files;

        } catch (error) {
            console.error('❌ 选择多个文件失败:', error);
            throw error;
        }
    }

    /**
     * 保存文件对话框
     */
    async saveFile(options = {}) {
        try {
            const defaultOptions = {
                filters: [
                    { name: '所有文件', extensions: ['*'] }
                ]
            };

            const mergedOptions = { ...defaultOptions, ...options };
            const result = await dialog.showSaveDialog(mergedOptions);

            if (result.canceled || !result.filePath) {
                return null;
            }

            console.log('📁 保存文件路径:', result.filePath);
            return result.filePath;

        } catch (error) {
            console.error('❌ 保存文件对话框失败:', error);
            throw error;
        }
    }

    /**
     * 在文件管理器中显示文件
     */
    async showItemInFolder(filePath) {
        try {
            const exists = await this.fileExists(filePath);
            if (!exists) {
                throw new Error(`文件不存在: ${filePath}`);
            }

            shell.showItemInFolder(filePath);
            console.log('📁 在文件管理器中显示:', filePath);
            return true;

        } catch (error) {
            console.error('❌ 在文件管理器中显示文件失败:', error);
            throw error;
        }
    }

    /**
     * 打开文件或文件夹
     */
    async openPath(filePath) {
        try {
            const exists = await this.fileExists(filePath);
            if (!exists) {
                throw new Error(`路径不存在: ${filePath}`);
            }

            const result = await shell.openPath(filePath);
            if (result) {
                throw new Error(`打开失败: ${result}`);
            }

            console.log('📁 打开路径:', filePath);
            return true;

        } catch (error) {
            console.error('❌ 打开路径失败:', error);
            throw error;
        }
    }

    /**
     * 读取文件
     */
    async readFile(filePath, encoding = 'utf8') {
        try {
            const content = await fs.readFile(filePath, encoding);
            console.log('📁 读取文件:', filePath);
            return content;

        } catch (error) {
            console.error('❌ 读取文件失败:', error);
            throw error;
        }
    }

    /**
     * 写入文件
     */
    async writeFile(filePath, data, encoding = 'utf8') {
        try {
            await fs.writeFile(filePath, data, encoding);
            console.log('📁 写入文件:', filePath);
            return true;

        } catch (error) {
            console.error('❌ 写入文件失败:', error);
            throw error;
        }
    }

    /**
     * 复制文件
     */
    async copyFile(srcPath, destPath) {
        try {
            await fs.copyFile(srcPath, destPath);
            console.log('📁 复制文件:', srcPath, '->', destPath);
            return true;

        } catch (error) {
            console.error('❌ 复制文件失败:', error);
            throw error;
        }
    }

    /**
     * 移动文件
     */
    async moveFile(srcPath, destPath) {
        try {
            await fs.rename(srcPath, destPath);
            console.log('📁 移动文件:', srcPath, '->', destPath);
            return true;

        } catch (error) {
            console.error('❌ 移动文件失败:', error);
            throw error;
        }
    }

    /**
     * 删除文件
     */
    async deleteFile(filePath) {
        try {
            await fs.unlink(filePath);
            console.log('📁 删除文件:', filePath);
            return true;

        } catch (error) {
            console.error('❌ 删除文件失败:', error);
            throw error;
        }
    }

    /**
     * 创建目录
     */
    async createDirectory(dirPath) {
        try {
            await fs.mkdir(dirPath, { recursive: true });
            console.log('📁 创建目录:', dirPath);
            return true;

        } catch (error) {
            console.error('❌ 创建目录失败:', error);
            throw error;
        }
    }

    /**
     * 检查文件是否存在
     */
    async fileExists(filePath) {
        try {
            await fs.access(filePath);
            return true;
        } catch {
            return false;
        }
    }

    /**
     * 获取文件大小
     */
    async getFileSize(filePath) {
        try {
            const stats = await fs.stat(filePath);
            return stats.size;
        } catch {
            return 0;
        }
    }

    /**
     * 获取文件信息
     */
    async getFileInfo(filePath) {
        try {
            const stats = await fs.stat(filePath);
            return {
                path: filePath,
                name: path.basename(filePath),
                size: stats.size,
                extension: path.extname(filePath),
                isFile: stats.isFile(),
                isDirectory: stats.isDirectory(),
                created: stats.birthtime,
                modified: stats.mtime,
                accessed: stats.atime
            };

        } catch (error) {
            console.error('❌ 获取文件信息失败:', error);
            throw error;
        }
    }

    /**
     * 扫描目录中的文件
     */
    async scanDirectory(dirPath, options = {}) {
        try {
            const {
                recursive = false,
                extensions = null,
                maxDepth = 10
            } = options;

            const files = [];
            await this._scanDirectoryRecursive(dirPath, files, extensions, recursive, 0, maxDepth);
            
            console.log('📁 扫描目录:', dirPath, '找到', files.length, '个文件');
            return files;

        } catch (error) {
            console.error('❌ 扫描目录失败:', error);
            throw error;
        }
    }

    /**
     * 递归扫描目录
     */
    async _scanDirectoryRecursive(dirPath, files, extensions, recursive, currentDepth, maxDepth) {
        if (currentDepth >= maxDepth) {
            return;
        }

        const entries = await fs.readdir(dirPath, { withFileTypes: true });

        for (const entry of entries) {
            const fullPath = path.join(dirPath, entry.name);

            if (entry.isFile()) {
                if (!extensions || extensions.includes(path.extname(entry.name).toLowerCase())) {
                    const fileInfo = await this.getFileInfo(fullPath);
                    files.push(fileInfo);
                }
            } else if (entry.isDirectory() && recursive) {
                await this._scanDirectoryRecursive(fullPath, files, extensions, recursive, currentDepth + 1, maxDepth);
            }
        }
    }
}

module.exports = FileSystemAPI;
