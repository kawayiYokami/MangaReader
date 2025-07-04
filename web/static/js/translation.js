// 翻译功能模块 (重构为同步阻塞模式)
window.TranslationMethods = {
    // ==================== UI交互 ====================

    triggerTranslationFileSelect() {
        this.$refs.translationFileInput.click();
    },

    handleTranslationFileSelect(event) {
        const files = Array.from(event.target.files);
        this.processSelectedFiles(files);
        event.target.value = '';
    },

    handleTranslationDragOver(event) {
        event.preventDefault();
        this.translationDragOver = true;
    },

    handleTranslationDragLeave(event) {
        event.preventDefault();
        this.translationDragOver = false;
    },

    handleTranslationDrop(event) {
        event.preventDefault();
        this.translationDragOver = false;
        const files = Array.from(event.dataTransfer.files);
        this.processSelectedFiles(files);
    },

    // ==================== 任务管理 ====================

    processSelectedFiles(files) {
        if (files.length === 0) return;

        const supportedFiles = files.filter(file => {
            const extension = file.name.toLowerCase().split('.').pop();
            return ['zip', 'cbz'].includes(extension); // .cbr is not a zip archive
        });

        if (supportedFiles.length === 0) {
            ElMessage.warning('请选择ZIP或CBZ格式的漫画文件');
            return;
        }

        if (supportedFiles.length !== files.length) {
            ElMessage.warning(`已过滤掉 ${files.length - supportedFiles.length} 个不支持的文件`);
        }

        supportedFiles.forEach(file => {
            if (this.translationTasks.some(t => t.fileName === file.name)) {
                ElMessage.warning(`任务 "${file.name}" 已存在于列表中。`);
                return;
            }

            const task = {
                fileName: file.name,
                file: file,
                status: 'pending', // pending, processing, completed, error
                progress: 0,
                error: null,
            };
            this.translationTasks.push(task);
        });

        ElMessage.success(`已添加 ${supportedFiles.length} 个翻译任务`);
    },

    async startTranslation() {
        if (this.translationTasks.length === 0) {
            ElMessage.warning('请先选择要翻译的文件');
            return;
        }

        if (this.taskIsProcessing) {
            ElMessage.warning('已有任务在进行中，请稍候');
            return;
        }

        this.taskIsProcessing = true;
        console.log('🚀 开始翻译任务');

        try {
            for (const task of this.translationTasks) {
                if (task.status === 'pending') {
                    await this.processAndDownloadTranslation(task);
                }
            }
        } catch (error) {
            console.error('翻译过程出错:', error);
            ElMessage.error('翻译过程出错: ' + error.message);
        } finally {
            this.taskIsProcessing = false;
            console.log('🏁 所有翻译任务已处理完毕');
        }
    },

    async processAndDownloadTranslation(task) {
        console.log(`🚀 开始处理翻译: ${task.fileName}`);
        task.status = 'processing';
        task.progress = 0;
        task.error = null;

        const endpoint = '/api/translation/translate-file-and-download';
        const formData = new FormData();
        formData.append('file', task.file);
        formData.append('target_lang', this.translationSettings.targetLang);

        try {
            const response = await new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                xhr.open('POST', endpoint, true);

                xhr.upload.onprogress = (event) => {
                    if (event.lengthComputable) {
                        // We give 50% progress to upload, and 50% to backend processing
                        const uploadProgress = Math.round((event.loaded / event.total) * 50);
                        task.progress = uploadProgress;
                    }
                };
                
                // Show backend processing after upload completes
                xhr.upload.onload = () => {
                    task.progress = 55; // Indicate backend is working
                };

                xhr.onload = () => {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        resolve(xhr);
                    } else {
                        reject({ status: xhr.status, response: xhr.response });
                    }
                };

                xhr.onerror = () => {
                    reject({ status: xhr.status, response: xhr.response });
                };

                xhr.responseType = 'blob';
                xhr.send(formData);
            });
            
            task.progress = 100;
            const blob = response.response;
            const downloadFilename = `${task.fileName.replace(/\.[^/.]+$/, "")}_translated.zip`;
            
            // Use FileSaver.js `saveAs` if available, otherwise fallback
            if (typeof saveAs === 'function') {
                saveAs(blob, downloadFilename);
            } else {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = downloadFilename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
            }
            
            task.status = 'completed';
            ElMessage.success(`${task.fileName} 翻译并下载成功！`);

        } catch (error) {
            console.error(`翻译失败 for ${task.fileName}:`, error);
            let errorMessage = '请求失败。';
            try {
                // Try to parse error response from backend
                const errorText = await new Response(error.response).text();
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.detail || errorMessage;
            } catch (e) {
                errorMessage = '网络错误或服务器无响应。';
            }
            task.status = 'error';
            task.error = errorMessage;
            ElMessage.error(`${task.fileName} 翻译失败: ${errorMessage}`);
        }
    },
    
    // This is now a simple UI action, no download logic here
    downloadTask(task) {
        ElMessage.info('翻译完成后文件会自动下载。如果下载失败，请重新翻译。');
    },
    
    removeTask(index) {
        if (index >= 0 && index < this.translationTasks.length) {
            if (this.translationTasks[index].status === 'processing') {
                ElMessage.warning('不能移除正在处理中的任务。');
                return;
            }
            const task = this.translationTasks[index];
            this.translationTasks.splice(index, 1);
            ElMessage.success(`已移除任务: ${task.fileName}`);
        }
    },
    
    clearTasks() {
        if (this.translationTasks.some(t => t.status === 'processing')) {
            ElMessage.warning('有任务正在处理中，无法清空列表。');
            return;
        }
        this.translationTasks = [];
        ElMessage.success('已清空所有翻译任务');
    },
    
    getTaskStatusText(status) {
        const statusMap = {
            'pending': '等待中',
            'processing': '处理中',
            'completed': '已完成',
            'error': '失败'
        };
        return statusMap[status] || '未知';
    }
};
