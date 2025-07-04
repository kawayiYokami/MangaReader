/**
 * compression.js
 * 
 * 负责与后端“上传-压缩-下载”API交互的前端逻辑。
 * 此文件将通过 window.compressionMethods 暴露方法给Vue组件。
 */
(function() {
    'use strict';

    /**
     * 上传、压缩并下载单个文件。
     * @param {File} file - 用户选择的文件对象
     * @param {number} quality - WebP 压缩质量 (50-100)
     * @param {function} onProgress - 进度回调函数，接收一个参数 (0-100)
     * @returns {Promise<object>} - 返回一个包含 success 和 message 的对象
     */
    async function uploadAndCompressFile(file, quality, onProgress) {
        console.log(`开始处理文件: ${file.name}, 质量: ${quality}`);
        const endpoint = '/api/manga/compress-file-and-download';

        const formData = new FormData();
        formData.append('file', file);
        formData.append('webp_quality', quality);

        try {
            const response = await new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                xhr.open('POST', endpoint, true);

                // 进度事件监听
                xhr.upload.onprogress = (event) => {
                    if (event.lengthComputable && onProgress) {
                        const percentComplete = Math.round((event.loaded / event.total) * 100);
                        onProgress(percentComplete);
                    }
                };

                xhr.onload = () => {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        resolve(xhr);
                    } else {
                        reject({ status: xhr.status, statusText: xhr.statusText, response: xhr.response });
                    }
                };

                xhr.onerror = () => {
                    reject({ status: xhr.status, statusText: xhr.statusText, response: xhr.response });
                };

                xhr.responseType = 'blob'; // 期望服务器返回文件数据
                xhr.send(formData);
            });
            
            // 服务器返回的是压缩后的文件blob
            const blob = response.response;
            
            // 直接使用上传时的原始文件名来构建下载文件名，这是最可靠的方式。
            const downloadFilename = `${file.name.replace(/\.[^/.]+$/, "")}_compressed.zip`;
            
            // 创建一个下载链接并模拟点击
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = downloadFilename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            console.log(`文件 ${downloadFilename} 已成功下载。`);
            return { success: true, message: '压缩并下载成功！' };

        } catch (error) {
            console.error('上传或压缩文件时出错:', error);
            let errorMessage = '请求失败。';
            try {
                // 尝试解析错误响应
                const errorText = await new Response(error.response).text();
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.detail || errorMessage;
            } catch (e) {
                // 解析失败，使用通用错误
                errorMessage = error.statusText || '网络错误或服务器无响应。';
            }
            return { success: false, message: `压缩失败: ${errorMessage}` };
        }
    }
    
    // 将方法暴露到全局 window 对象
    window.compressionMethods = {
        uploadAndCompressFile,
    };

})();