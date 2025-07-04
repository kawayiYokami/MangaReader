/**
 * compression_vue.js
 * 
 * 包含“漫画压缩”页面所需的Vue data和methods。
 */
(function() {
    'use strict';

    // 挂载到 window.AppData 的数据
    if (!window.AppData) {
        window.AppData = {};
    }
    Object.assign(window.AppData, {
        compressionTasks: [], // 任务列表
        compressionSettings: { // 压缩设置
            quality: 85,
        },
        isCompressing: false, // 是否正在压缩
        compressionDragOver: false, // 文件拖拽状态
    });

    // 挂载到 window.CompressionMethods 的方法
    if (!window.CompressionMethods) {
        window.CompressionMethods = {};
    }
    Object.assign(window.CompressionMethods, {
        triggerCompressionFileSelect() {
            // Vue 3 中 ref 的访问方式
            const fileInput = this.$refs.compressionFileInput;
            if(fileInput) {
                fileInput.click();
            } else {
                console.error("无法找到 ref 'compressionFileInput'");
            }
        },
        
        handleCompressionDragOver(event) {
            this.compressionDragOver = true;
        },

        handleCompressionDragLeave(event) {
            this.compressionDragOver = false;
        },

        handleCompressionDrop(event) {
            this.compressionDragOver = false;
            const files = event.dataTransfer.files;
            if (files.length > 0) {
                this.addFilesToCompressionQueue(files);
            }
        },

        handleCompressionFileSelect(event) {
            const files = event.target.files;
            if (files.length > 0) {
                this.addFilesToCompressionQueue(files);
            }
        },

        addFilesToCompressionQueue(files) {
            const newTasks = Array.from(files).map(file => ({
                id: Date.now() + Math.random(),
                file: file,
                fileName: file.name,
                status: 'pending', // pending, processing, completed, error
                progress: 0,
                currentStep: '等待上传',
                result: null, // 下载链接或错误信息
            }));
            this.compressionTasks.push(...newTasks);
        },

        async startCompression() {
            if (this.isCompressing) return;
            this.isCompressing = true;
            
            // 使用 for...of 循环确保任务按顺序执行
            for (const task of this.compressionTasks) {
                if (task.status === 'pending') {
                    try {
                        task.status = 'processing';
                        task.currentStep = '正在上传...';
                        
                        // 调用 compression.js 中的核心API方法
                        const result = await window.compressionMethods.uploadAndCompressFile(
                            task.file,
                            this.compressionSettings.quality,
                            (progress) => {
                                task.progress = progress;
                                if (progress >= 100) {
                                    task.currentStep = '服务器处理中...';
                                }
                            }
                        );
                        
                        if (result.success) {
                            task.status = 'completed';
                            task.progress = 100;
                            task.currentStep = '压缩完成';
                            task.result = result; // 保存结果以供下载
                            this.$message.success(`'${task.fileName}' 压缩成功！`);
                        } else {
                            task.status = 'error';
                            task.currentStep = result.message;
                            task.progress = 0;
                            this.$message.error(`'${task.fileName}' 压缩失败: ${result.message}`);
                        }

                    } catch (error) {
                        task.status = 'error';
                        task.progress = 0;
                        task.currentStep = error.message || '未知错误';
                        this.$message.error(`处理 '${task.fileName}' 时发生意外错误。`);
                    }
                }
            }
            this.isCompressing = false;
        },

        // 停止功能在当前即时模型下不再需要
        stopCompression() {
            console.warn("当前模式不支持停止操作。压缩过程一旦开始，将按顺序完成所有任务。");
            this.isCompressing = false; // 允许用户开始新的任务队列
        },

        clearCompressionTasks() {
            if (this.isCompressing) {
                this.$message.warning("正在压缩中，无法清空任务列表。");
                return;
            }
            this.compressionTasks = [];
        },

        removeCompressionTask(index) {
             if (this.isCompressing && this.compressionTasks[index].status !== 'pending') {
                this.$message.warning("无法移除正在处理或已完成的任务。");
                return;
            }
            this.compressionTasks.splice(index, 1);
        },

        getCompressionTaskStatusText(status) {
            const statusMap = {
                pending: '等待中',
                processing: '处理中',
                completed: '已完成',
                error: '失败'
            };
            return statusMap[status] || '未知';
        },

        // ==================== 通用接口适配 ====================

        downloadTask(task) {
            if (task.status === 'completed' && task.result && task.result.blob) {
                // 使用 File-saver.js
                saveAs(task.result.blob, task.result.fileName);
                this.$message.success('下载已开始');
            } else {
                this.$message.warning('任务未完成或无有效下载内容。');
            }
        },

        // 提供与翻译模块一致的通用方法名
        clearTasks() {
            this.clearCompressionTasks();
        },

        removeTask(index) {
            this.removeCompressionTask(index);
        },

        getTaskStatusText(status) {
            // 此方法本身已在两个模块中命名一致，但为确保接口完整性，在此保留
            return this.getCompressionTaskStatusText(status);
        }
    });
})();