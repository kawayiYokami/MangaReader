// 压缩功能模块
window.CompressionMethods = {
    // ==================== 压缩功能 ====================

    triggerCompressionFileSelect() {
        this.$refs.compressionFileInput.click();
    },

    handleCompressionFileSelect(event) {
        const files = Array.from(event.target.files);
        this.processCompressionFiles(files);
        // 清空文件选择器
        event.target.value = '';
    },

    handleCompressionDragOver(event) {
        event.preventDefault();
        this.isCompressionDragOver = true;
    },

    handleCompressionDragLeave(event) {
        event.preventDefault();
        this.isCompressionDragOver = false;
    },

    handleCompressionDrop(event) {
        event.preventDefault();
        this.isCompressionDragOver = false;
        
        const files = Array.from(event.dataTransfer.files);
        this.processCompressionFiles(files);
    },

    processCompressionFiles(files) {
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

        // 为每个文件创建压缩任务
        supportedFiles.forEach(file => {
            const task = {
                id: Date.now() + Math.random(),
                fileName: file.name,
                file: file,
                status: 'pending', // pending, processing, completed, error
                progress: 0,
                currentStep: '等待开始',
                error: null,
                result: null,
                originalSize: file.size,
                compressedSize: 0
            };

            this.compressionTasks.push(task);
        });

        ElMessage.success(`已添加 ${supportedFiles.length} 个压缩任务`);
    },

    async startCompression() {
        if (this.compressionTasks.length === 0) {
            ElMessage.warning('请先选择要压缩的文件');
            return;
        }

        this.isCompressing = true;
        this.compressionStopped = false;

        try {
            // 逐个处理压缩任务
            for (const task of this.compressionTasks) {
                if (this.compressionStopped) break;
                
                if (task.status === 'pending') {
                    await this.processCompressionFile(task);
                }
            }
        } catch (error) {
            console.error('压缩过程出错:', error);
            ElMessage.error('压缩过程出错: ' + error.message);
        } finally {
            this.isCompressing = false;
        }
    },

    stopCompression() {
        this.compressionStopped = true;
        this.isCompressing = false;
        ElMessage.info('压缩已停止');
    },

    async processCompressionFile(task) {
        try {
            task.status = 'processing';
            task.progress = 0;
            task.currentStep = '读取文件...';

            // 读取ZIP文件
            const zip = new JSZip();
            const zipContent = await zip.loadAsync(task.file);

            // 获取所有图片文件
            const imageFiles = [];
            zipContent.forEach((relativePath, file) => {
                if (!file.dir && this.isImageFile(relativePath)) {
                    imageFiles.push({ path: relativePath, file: file });
                }
            });

            if (imageFiles.length === 0) {
                throw new Error('ZIP文件中没有找到图片文件');
            }

            task.currentStep = `找到 ${imageFiles.length} 个图片文件`;
            task.progress = 10;

            // 预检测：压缩第一张图片检查压缩率
            if (imageFiles.length > 0) {
                task.currentStep = '检测压缩效果...';
                const firstImage = imageFiles[0];
                const originalData = await firstImage.file.async('blob');
                const compressedData = await this.compressImage(originalData, this.compressionSettings);
                
                const compressionRatio = compressedData.size / originalData.size;
                if (compressionRatio > 0.75) {
                    // 如果压缩率小于25%，询问是否继续
                    const shouldContinue = confirm(
                        `检测到压缩效果不明显（压缩率仅 ${(100 - compressionRatio * 100).toFixed(1)}%），是否继续压缩？`
                    );
                    if (!shouldContinue) {
                        task.status = 'error';
                        task.error = '用户取消了压缩';
                        return;
                    }
                }
            }

            task.progress = 20;

            // 创建结果ZIP
            const resultZip = new JSZip();

            // 逐个压缩图片
            for (let i = 0; i < imageFiles.length; i++) {
                if (this.compressionStopped) {
                    task.status = 'error';
                    task.error = '用户停止了压缩';
                    return;
                }

                const imageFile = imageFiles[i];
                task.currentStep = `压缩第 ${i + 1}/${imageFiles.length} 张图片`;
                task.progress = 20 + Math.round((i / imageFiles.length) * 70);

                try {
                    // 读取图片数据
                    const originalData = await imageFile.file.async('blob');
                    
                    // 压缩图片
                    const compressedData = await this.compressImage(originalData, this.compressionSettings);
                    
                    // 生成新的文件名（WebP格式）
                    const originalPath = imageFile.path;
                    const pathWithoutExt = originalPath.substring(0, originalPath.lastIndexOf('.'));
                    const newPath = pathWithoutExt + '.webp';
                    
                    // 将压缩后的图片添加到结果ZIP
                    resultZip.file(newPath, compressedData);
                    
                } catch (error) {
                    console.error(`压缩第 ${i + 1} 张图片失败:`, error);
                    // 如果压缩失败，添加原图片
                    const originalData = await imageFile.file.async('blob');
                    resultZip.file(imageFile.path, originalData);
                }
            }

            task.currentStep = '生成压缩包...';
            task.progress = 90;

            // 生成最终的ZIP文件
            const resultBlob = await resultZip.generateAsync({ 
                type: 'blob',
                compression: 'DEFLATE',
                compressionOptions: { level: 6 }
            });
            
            task.status = 'completed';
            task.progress = 100;
            task.result = resultBlob;
            task.compressedSize = resultBlob.size;
            task.currentStep = '压缩完成';
            
            const compressionRatio = ((task.originalSize - task.compressedSize) / task.originalSize * 100).toFixed(1);
            ElMessage.success(`${task.fileName} 压缩完成，减少了 ${compressionRatio}%`);

        } catch (error) {
            console.error('压缩文件失败:', error);
            task.status = 'error';
            task.error = error.message;
            ElMessage.error(`${task.fileName} 压缩失败: ${error.message}`);
        }
    },

    async compressImage(imageBlob, settings) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');

            img.onload = () => {
                canvas.width = img.width;
                canvas.height = img.height;
                ctx.drawImage(img, 0, 0);

                // 根据设置选择压缩方式
                if (settings.lossless) {
                    // 无损压缩
                    canvas.toBlob(resolve, 'image/webp', 1.0);
                } else {
                    // 有损压缩
                    const quality = settings.quality / 100;
                    canvas.toBlob(resolve, 'image/webp', quality);
                }
            };

            img.onerror = reject;
            img.src = URL.createObjectURL(imageBlob);
        });
    },

    downloadCompressionTask(task) {
        if (task.status !== 'completed' || !task.result) {
            ElMessage.warning('任务未完成或结果不可用');
            return;
        }

        try {
            // 生成下载文件名
            const originalName = task.fileName;
            const nameWithoutExt = originalName.substring(0, originalName.lastIndexOf('.'));
            const downloadName = `${nameWithoutExt}_compressed.zip`;

            // 下载文件
            saveAs(task.result, downloadName);
            ElMessage.success('下载开始');
        } catch (error) {
            console.error('下载失败:', error);
            ElMessage.error('下载失败: ' + error.message);
        }
    },

    removeCompressionTask(index) {
        if (index >= 0 && index < this.compressionTasks.length) {
            const task = this.compressionTasks[index];
            this.compressionTasks.splice(index, 1);
            ElMessage.success(`已移除任务: ${task.fileName}`);
        }
    },

    clearCompressionTasks() {
        if (this.compressionTasks.length === 0) {
            ElMessage.info('任务列表已经是空的');
            return;
        }

        this.compressionTasks = [];
        ElMessage.success('已清空所有压缩任务');
    },

    getCompressionTaskStatusText(status) {
        const statusMap = {
            'pending': '等待中',
            'processing': '处理中',
            'completed': '已完成',
            'error': '失败'
        };
        return statusMap[status] || '未知';
    }
};
