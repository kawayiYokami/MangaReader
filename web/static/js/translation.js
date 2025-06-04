// 翻译功能模块
window.TranslationMethods = {
    // ==================== 翻译功能 ====================

    triggerTranslationFileSelect() {
        this.$refs.translationFileInput.click();
    },

    handleTranslationFileSelect(event) {
        const files = Array.from(event.target.files);
        this.processSelectedFiles(files);
        // 清空文件选择器
        event.target.value = '';
    },

    handleTranslationDragOver(event) {
        event.preventDefault();
        this.isTranslationDragOver = true;
    },

    handleTranslationDragLeave(event) {
        event.preventDefault();
        this.isTranslationDragOver = false;
    },

    handleTranslationDrop(event) {
        event.preventDefault();
        this.isTranslationDragOver = false;

        const files = Array.from(event.dataTransfer.files);
        this.processSelectedFiles(files);
    },

    processSelectedFiles(files) {
        if (files.length === 0) return;

        // 过滤支持的文件类型
        const supportedFiles = files.filter(file => {
            const extension = file.name.toLowerCase().split('.').pop();
            return ['zip', 'cbz', 'cbr'].includes(extension);
        });

        if (supportedFiles.length === 0) {
            ElMessage.warning('请选择ZIP、CBZ或CBR格式的漫画文件');
            return;
        }

        if (supportedFiles.length !== files.length) {
            ElMessage.warning(`已过滤掉 ${files.length - supportedFiles.length} 个不支持的文件`);
        }

        // 为每个文件创建翻译任务
        supportedFiles.forEach(file => {
            const task = {
                id: Date.now() + Math.random(),
                fileName: file.name,
                file: file,
                status: 'pending', // pending, processing, completed, error
                progress: 0,
                currentPage: 0,
                totalPages: 0,
                error: null,
                result: null
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

        if (this.isProcessing) {
            ElMessage.warning('翻译正在进行中，请先停止当前翻译');
            return;
        }

        this.isProcessing = true;
        this.translationStopped = false;

        console.log('🚀 开始翻译任务');

        try {
            // 逐个处理翻译任务
            for (const task of this.translationTasks) {
                if (this.translationStopped) {
                    console.log('🛑 翻译已停止，跳出循环');
                    break;
                }

                if (task.status === 'pending') {
                    await this.processTranslationFileAsync(task);
                }
            }
        } catch (error) {
            console.error('翻译过程出错:', error);
            ElMessage.error('翻译过程出错: ' + error.message);
        } finally {
            this.isProcessing = false;
            console.log('🏁 翻译任务结束');
        }
    },

    async stopTranslation() {
        console.log('🛑 用户点击停止翻译按钮');

        // 立即设置停止标志和显示提示
        this.translationStopped = true;
        ElMessage.success('正在停止翻译...');

        // 使用setTimeout确保UI立即响应
        setTimeout(async () => {
            try {
                // 调用后端API杀掉翻译进程
                console.log('🛑 调用后端杀掉翻译进程');
                const response = await axios.post('/api/translation/cancel-translation');

                if (response.data.success) {
                    console.log('🛑 翻译进程已终止:', response.data.message);
                    ElMessage.success(response.data.message);
                } else {
                    console.log('🛑 终止翻译进程失败:', response.data.message);
                    ElMessage.warning(response.data.message);
                }
            } catch (error) {
                console.error('🛑 终止翻译进程API调用失败:', error);
                ElMessage.error('终止翻译失败: ' + (error.response?.data?.detail || error.message));
            }

            // 确保状态重置
            this.isProcessing = false;
        }, 100); // 100ms后执行，确保UI先响应
    },

    async processTranslationFileAsync(task) {
        try {
            console.log(`🚀 开始异步翻译: ${task.fileName}`);

            // 检查是否已停止
            if (this.translationStopped) {
                console.log('🛑 翻译已停止，跳过任务:', task.fileName);
                return;
            }

            task.status = 'processing';
            task.progress = 0;

            // 启动异步翻译任务
            const taskId = await this.startAsyncTranslationTask(task);

            if (!taskId) {
                throw new Error('启动翻译任务失败');
            }

            // 轮询检查翻译状态
            await this.pollAsyncTranslationStatus(task, taskId);

        } catch (error) {
            console.error('异步翻译文件失败:', error);
            task.status = 'error';
            task.error = error.message;
            ElMessage.error(`${task.fileName} 翻译失败: ${error.message}`);
        }
    },

    async startAsyncTranslationTask(task) {
        try {
            // 调用后端异步翻译API
            const formData = new FormData();
            formData.append('file', task.file);
            formData.append('source_lang', this.translationSettings.sourceLang);
            formData.append('target_lang', this.translationSettings.targetLang);
            formData.append('translator_engine', this.translationSettings.engine);
            formData.append('webp_quality', this.translationSettings.webpQuality);

            const response = await axios.post('/api/translation/translate-manga-async', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            if (response.data.success) {
                console.log(`✅ 翻译任务已启动: ${response.data.task_id}`);
                return response.data.task_id;
            } else {
                throw new Error(response.data.message || '启动翻译任务失败');
            }
        } catch (error) {
            console.error('启动异步翻译任务失败:', error);
            throw error;
        }
    },

    async pollAsyncTranslationStatus(task, taskId) {
        const maxAttempts = 300; // 最多轮询5分钟
        let attempts = 0;

        while (attempts < maxAttempts) {
            // 检查是否已停止
            if (this.translationStopped) {
                console.log('🛑 翻译已停止，取消任务:', taskId);

                // 调用取消API
                try {
                    await axios.post(`/api/translation/cancel-task/${taskId}`);
                    console.log('✅ 任务已取消');
                } catch (error) {
                    console.error('取消任务失败:', error);
                }

                task.status = 'error';
                task.error = '翻译已取消';
                return;
            }

            try {
                const response = await axios.get(`/api/translation/task-status/${taskId}`);

                if (response.data.success) {
                    const status = response.data.status;
                    task.progress = response.data.progress || 0;

                    if (status === 'completed') {
                        task.status = 'completed';
                        task.result = response.data.output_files;
                        ElMessage.success(`${task.fileName} 翻译完成`);
                        return;
                    } else if (status === 'error') {
                        task.status = 'error';
                        task.error = response.data.error || '翻译失败';
                        ElMessage.error(`${task.fileName} 翻译失败: ${task.error}`);
                        return;
                    } else if (status === 'cancelled') {
                        task.status = 'error';
                        task.error = '翻译已取消';
                        return;
                    }
                    // status === 'processing' 继续轮询
                }
            } catch (error) {
                console.error('轮询翻译状态失败:', error);
            }

            // 等待1秒后继续轮询
            await new Promise(resolve => setTimeout(resolve, 1000));
            attempts++;
        }

        // 超时
        task.status = 'error';
        task.error = '翻译超时';
        ElMessage.error(`${task.fileName} 翻译超时`);
    },

    async processTranslationFile(task) {
        try {
            // 检查是否已停止
            if (this.translationStopped) {
                console.log('🛑 翻译已停止，跳过任务:', task.fileName);
                return;
            }

            task.status = 'processing';
            task.progress = 0;

            // 调用后端翻译API
            const formData = new FormData();
            formData.append('file', task.file);
            formData.append('source_lang', this.translationSettings.sourceLang);
            formData.append('target_lang', this.translationSettings.targetLang);
            formData.append('translator_engine', this.translationSettings.engine);
            formData.append('webp_quality', this.translationSettings.webpQuality);

            task.progress = 10;

            // 发送翻译请求（支持取消）
            const response = await axios.post('/api/translation/translate-manga', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                },
                signal: this.abortController ? this.abortController.signal : undefined,
                onUploadProgress: (progressEvent) => {
                    // 上传进度 (0-30%)
                    const uploadProgress = Math.round((progressEvent.loaded / progressEvent.total) * 30);
                    task.progress = uploadProgress;
                }
            });

            if (!response.data.success) {
                throw new Error(response.data.message || '翻译失败');
            }

            // 再次检查是否已停止
            if (this.translationStopped) {
                console.log('🛑 翻译已停止，跳过下载:', task.fileName);
                task.status = 'error';
                task.error = '翻译已取消';
                return;
            }

            task.progress = 80;

            // 下载翻译结果（支持取消）
            const downloadResponse = await axios.post('/api/translation/download-task', {
                task_name: task.fileName,
                output_files: response.data.output_files
            }, {
                responseType: 'blob',
                signal: this.abortController ? this.abortController.signal : undefined
            });

            task.progress = 100;
            task.status = 'completed';
            task.result = downloadResponse.data;

            ElMessage.success(`${task.fileName} 翻译完成`);

        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('🛑 翻译请求被取消:', task.fileName);
                task.status = 'error';
                task.error = '翻译已取消';
                // 不显示错误消息，因为这是用户主动取消
            } else {
                console.error('翻译文件失败:', error);
                task.status = 'error';
                task.error = error.response?.data?.detail || error.message;
                ElMessage.error(`${task.fileName} 翻译失败: ${task.error}`);
            }
        }
    },

    isImageFile(filename) {
        const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'];
        const extension = filename.toLowerCase().substring(filename.lastIndexOf('.'));
        return imageExtensions.includes(extension);
    },

    downloadTask(task) {
        if (task.status !== 'completed' || !task.result) {
            ElMessage.warning('任务未完成或结果不可用');
            return;
        }

        try {
            // 生成下载文件名
            const originalName = task.fileName;
            const nameWithoutExt = originalName.substring(0, originalName.lastIndexOf('.'));
            const downloadName = `${nameWithoutExt}_translated.zip`;

            // 下载文件
            saveAs(task.result, downloadName);
            ElMessage.success('下载开始');
        } catch (error) {
            console.error('下载失败:', error);
            ElMessage.error('下载失败: ' + error.message);
        }
    },

    removeTask(index) {
        if (index >= 0 && index < this.translationTasks.length) {
            const task = this.translationTasks[index];
            this.translationTasks.splice(index, 1);
            ElMessage.success(`已移除任务: ${task.fileName}`);
        }
    },

    clearTranslationTasks() {
        if (this.translationTasks.length === 0) {
            ElMessage.info('任务列表已经是空的');
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
