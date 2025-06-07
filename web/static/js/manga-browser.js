// 漫画浏览功能模块
window.MangaBrowserMethods = {
    // ==================== 漫画浏览功能 ====================

    async loadInitialData() {
        try {
            // 直接加载缓存中的漫画数据
            await this.loadMangaData();

            // 初始化智能预加载
            this.initSmartPreload();
        } catch (error) {
            console.error('加载初始数据失败:', error);
        }
    },

    async loadMangaData() {
        this.isLoading = true;
        try {
            // 并行加载漫画列表和标签
            const [mangaResponse, tagsResponse] = await Promise.all([
                axios.get('/api/manga/list'),
                axios.get('/api/manga/tags')
            ]);

            this.mangaList = mangaResponse.data;
            this.availableTags = tagsResponse.data;

            // 处理标签分类
            this.processTagsByCategory();

            if (this.mangaList.length > 0) {
                ElMessage.success(`加载完成，共 ${this.mangaList.length} 本漫画`);
            }

            // 初始化缩略图加载
            if (this.mangaList.length > 0) {
                this.loadThumbnail(this.mangaList[0].file_path);
            }
        } catch (error) {
            console.error('加载漫画数据失败:', error);
            ElMessage.error('加载漫画数据失败: ' + (error.response?.data?.detail || error.message));
        } finally {
            this.isLoading = false;
        }
    },

    // ==================== 标签分类处理 ====================

    processTagsByCategory() {
        const categories = {
            '作者': [],
            '组': [],
            '平台': [],
            '汉化': [],
            '会场': [],
            '其他': []
        };

        // 按分类整理标签
        for (const tag of this.availableTags) {
            if (tag.startsWith('标题:') || tag.startsWith('作品:')) {
                continue; // 跳过标题和作品标签
            }

            let category = '其他';
            let displayName = tag;

            if (tag.startsWith('作者:')) {
                category = '作者';
                displayName = tag.substring(3);
            } else if (tag.startsWith('组:')) {
                category = '组';
                displayName = tag.substring(2);
            } else if (tag.startsWith('平台:')) {
                category = '平台';
                displayName = tag.substring(3);
            } else if (tag.startsWith('汉化:')) {
                category = '汉化';
                displayName = tag.substring(3);
            } else if (tag.startsWith('会场:')) {
                category = '会场';
                displayName = tag.substring(3);
            } else if (tag.startsWith('其他:')) {
                category = '其他';
                displayName = tag.substring(3);
            }

            categories[category].push({
                full: tag,
                display: displayName
            });
        }

        // 移除空分类并按显示名称排序
        this.tagsByCategory = {};
        for (const [category, tags] of Object.entries(categories)) {
            if (tags.length > 0) {
                tags.sort((a, b) => a.display.localeCompare(b.display, 'zh-CN'));
                this.tagsByCategory[category] = tags;
                this.tagCategoryShowAll[category] = false;
            }
        }

        // 设置默认激活的分类
        const availableCategories = Object.keys(this.tagsByCategory);
        if (availableCategories.length > 0) {
            this.activeTagCategory = availableCategories.includes('作者') ? '作者' : availableCategories[0];
        }
    },

    toggleTag(tag) {
        const index = this.selectedTags.indexOf(tag);
        if (index > -1) {
            this.selectedTags.splice(index, 1);
        } else {
            this.selectedTags.push(tag);
        }
    },

    clearFilters() {
        this.searchQuery = '';
        this.selectedTags = [];
    },

    clearTagFilters() {
        this.selectedTags = [];
    },

    toggleShowAllTags(category) {
        this.tagCategoryShowAll[category] = !this.tagCategoryShowAll[category];
    },

    selectManga(manga) {
        console.log('选择漫画:', manga);

        // 保存当前浏览状态
        this.saveBrowsingState();

        // 构建查看器URL
        const encodedPath = encodeURIComponent(manga.file_path);
        const viewerUrl = `/viewer.html?path=${encodedPath}&page=0`;

        // 检测是否在桌面应用中
        if (this.checkIsDesktopApp()) {
            // 桌面应用：使用iframe方案
            this.openMangaViewer(viewerUrl);
        } else {
            // Web应用：在新标签页中打开
            window.open(viewerUrl, '_blank');
        }
    },



    // ==================== 漫画查看器iframe功能 ====================

    // 打开漫画查看器
    openMangaViewer(viewerUrl) {
        console.log('🖼️ 打开漫画查看器:', viewerUrl);

        this.currentViewerUrl = viewerUrl;
        this.showMangaViewer = true;
        document.body.style.overflow = 'hidden';
    },

    // 关闭漫画查看器
    closeMangaViewer() {
        console.log('❌ 关闭漫画查看器');

        this.showMangaViewer = false;
        this.currentViewerUrl = '';
        document.body.style.overflow = '';
    },

    // iframe加载完成事件
    onIframeLoad() {
        console.log('🎨 iframe加载完成，同步主题');
        // Removed call to syncThemeToIframe.
        // Viewer iframe theme is now independent.
    },

    // Removed syncThemeToIframe function.
    // The viewer.html iframe is now intentionally set to always use a dark theme
    // and no longer syncs with the parent page's theme.

    // 保存当前浏览状态
    saveBrowsingState() {
        const state = {
            activeMenu: this.activeMenu,
            searchQuery: this.searchQuery,
            selectedTags: [...this.selectedTags],
            activeTagCategory: this.activeTagCategory,
            tagCategoryShowAll: {...this.tagCategoryShowAll},
            sidebarCollapsed: this.sidebarCollapsed,
            timestamp: Date.now()
        };

        // 保存到sessionStorage（会话级别）和localStorage（持久化）
        sessionStorage.setItem('mangaBrowsingState', JSON.stringify(state));
        localStorage.setItem('mangaBrowsingState', JSON.stringify(state));

        console.log('🔖 浏览状态已保存:', state);
    },

    // 恢复浏览状态
    restoreBrowsingState() {
        try {
            // 优先从sessionStorage读取（更新）
            let stateStr = sessionStorage.getItem('mangaBrowsingState');
            if (!stateStr) {
                // 如果sessionStorage没有，从localStorage读取
                stateStr = localStorage.getItem('mangaBrowsingState');
            }

            if (stateStr) {
                const state = JSON.parse(stateStr);

                // 检查状态是否过期（24小时）
                if (Date.now() - state.timestamp < 24 * 60 * 60 * 1000) {
                    // 恢复状态
                    this.activeMenu = state.activeMenu || 'home';
                    this.searchQuery = state.searchQuery || '';
                    this.selectedTags = state.selectedTags || [];
                    this.activeTagCategory = state.activeTagCategory || '作者';
                    this.tagCategoryShowAll = state.tagCategoryShowAll || {};
                    this.sidebarCollapsed = state.sidebarCollapsed || false;

                    console.log('🔄 浏览状态已恢复:', state);
                    return true;
                } else {
                    console.log('⏰ 浏览状态已过期，使用默认状态');
                    this.clearBrowsingState();
                }
            }
        } catch (error) {
            console.error('❌ 恢复浏览状态失败:', error);
        }
        return false;
    },

    // 清除浏览状态
    clearBrowsingState() {
        sessionStorage.removeItem('mangaBrowsingState');
        localStorage.removeItem('mangaBrowsingState');
    },

    checkIsDesktopApp() {
        // 检测是否在桌面应用中运行
        // 简化为只检查 window.pywebview 是否存在
        const isDesktop = typeof window.pywebview !== 'undefined';
        // console.log(`[checkIsDesktopApp] Result: ${isDesktop}`); // 减少日志噪音
        return isDesktop;
    },

    viewManga(manga) {
        ElMessage.info(`查看漫画: ${manga.title}`);
    },

    translateManga(manga) {
        ElMessage.info(`开始翻译: ${manga.title}`);
        // 切换到翻译页面
        this.activeMenu = 'translation';
    },

    getFileTypeText(fileType) {
        const types = {
            'folder': '文件夹',
            'zip': '压缩包',
            'unknown': '未知'
        };
        return types[fileType] || '未知';
    },

    // ==================== 新的缩略图系统 ====================

    initThumbnailObserver() {
        // 创建Intersection Observer来监听卡片进入视口
        this.thumbnailObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const mangaPath = entry.target.dataset.mangaPath;
                    if (mangaPath && !this.thumbnailCache.has(mangaPath) && !this.loadingThumbnails.has(mangaPath)) {
                        this.loadThumbnail(mangaPath);
                    }
                }
            });
        }, {
            rootMargin: '200px', // 提前200px开始加载，增加预加载范围
            threshold: 0.1
        });

        // 创建预加载Observer，更大的预加载范围
        this.preloadObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const mangaPath = entry.target.dataset.mangaPath;
                    if (mangaPath && !this.thumbnailCache.has(mangaPath) && !this.loadingThumbnails.has(mangaPath)) {
                        // 延迟预加载，避免影响当前视口的加载
                        setTimeout(() => {
                            this.loadThumbnail(mangaPath, true);
                        }, 100);
                    }
                }
            });
        }, {
            rootMargin: '500px', // 更大的预加载范围
            threshold: 0.01
        });
    },

    async loadThumbnail(mangaPath, isPreload = false) {
        if (this.loadingThumbnails.has(mangaPath)) return;

        try {
            this.loadingThumbnails.add(mangaPath);

            // 如果是预加载，添加到预加载队列
            if (isPreload) {
                this.preloadQueue.add(mangaPath);
                // 限制并发预加载数量
                if (this.preloadQueue.size > 5) {
                    return;
                }
            }

            // 使用POST请求发送路径，避免URL编码问题
            const response = await axios.post('/api/manga/thumbnail', {
                manga_path: mangaPath,
                size: 300
            });

            if (response.data && response.data.thumbnail) {
                // 缓存缩略图
                this.thumbnailCache.set(mangaPath, response.data.thumbnail);

                // 如果是当前视口内的图片，立即更新显示
                if (!isPreload) {
                    this.$forceUpdate();
                }

                // 预加载完成后，延迟更新以避免影响性能
                if (isPreload) {
                    setTimeout(() => {
                        this.$forceUpdate();
                    }, 50);
                }
            }
        } catch (error) {
            if (!isPreload) {
                console.error('获取缩略图失败:', mangaPath, error);
            }
        } finally {
            this.loadingThumbnails.delete(mangaPath);
            if (isPreload) {
                this.preloadQueue.delete(mangaPath);
            }
        }
    },

    // 批量预加载缩略图
    async batchPreloadThumbnails(mangaPaths, batchSize = 3) {
        const batches = [];
        for (let i = 0; i < mangaPaths.length; i += batchSize) {
            batches.push(mangaPaths.slice(i, i + batchSize));
        }

        for (const batch of batches) {
            // 并行加载一批缩略图
            const promises = batch.map(mangaPath => {
                if (!this.thumbnailCache.has(mangaPath) && !this.loadingThumbnails.has(mangaPath)) {
                    return this.loadThumbnail(mangaPath, true);
                }
                return Promise.resolve();
            });

            await Promise.allSettled(promises);

            // 批次间稍作延迟，避免过度占用资源
            await new Promise(resolve => setTimeout(resolve, 100));
        }
    },

    getThumbnailUrl(mangaPath) {
        return this.thumbnailCache.get(mangaPath) || null;
    },

    isThumbnailLoading(mangaPath) {
        return this.loadingThumbnails.has(mangaPath);
    },

    observeCard(element) {
        if (element) {
            // 同时使用两个Observer
            if (this.thumbnailObserver) {
                this.thumbnailObserver.observe(element);
            }
            if (this.preloadObserver) {
                this.preloadObserver.observe(element);
            }
        }
    },

    unobserveCard(element) {
        if (element) {
            if (this.thumbnailObserver) {
                this.thumbnailObserver.unobserve(element);
            }
            if (this.preloadObserver) {
                this.preloadObserver.unobserve(element);
            }
        }
    },

    // ==================== 标签处理方法 ====================

    getTitleTag(tags) {
        if (!tags || tags.length === 0) return '';

        // 查找以"标题:"开头的标签
        const titleTag = tags.find(tag => tag && tag.startsWith && tag.startsWith('标题:'));
        if (titleTag) {
            return titleTag.substring(3).trim(); // 去掉"标题:"前缀并去除空格
        }

        // 如果没有标题标签，查找作品标签作为备选
        const workTag = tags.find(tag => tag && tag.startsWith && tag.startsWith('作品:'));
        if (workTag) {
            return workTag.substring(3).trim(); // 去掉"作品:"前缀并去除空格
        }

        // 都没有的话返回空
        return '';
    },

    getOtherTags(tags) {
        if (!tags || tags.length === 0) return [];

        const result = [];

        for (const tag of tags) {
            if (tag.startsWith('标题:')) {
                continue; // 跳过标题标签
            } else if (tag.startsWith('作者:')) {
                result.push(tag.substring(3));
            } else if (tag.startsWith('作品:')) {
                continue; // 跳过作品标签（已用作标题）
            } else if (tag.startsWith('组:')) {
                result.push(tag.substring(2));
            } else if (tag.startsWith('平台:')) {
                result.push(tag.substring(3));
            } else if (tag.startsWith('会场:')) {
                result.push(tag.substring(3));
            } else if (tag.startsWith('汉化:')) {
                result.push(tag.substring(3));
            } else if (tag.startsWith('其他:')) {
                result.push(tag.substring(3));
            } else {
                // 没有前缀的标签
                result.push(tag);
            }
        }

        return result;
    },

    // ==================== 标签点击功能 ====================

    onTagClick(tag) {
        console.log('点击标签:', tag);

        // 构建完整的标签名（需要加上分类前缀）
        let fullTag = tag;

        // 如果标签没有前缀，需要从原始标签中找到对应的完整标签
        if (!tag.includes(':')) {
            // 在所有可用标签中查找匹配的完整标签
            const matchingTag = this.availableTags.find(availableTag => {
                if (availableTag.includes(':')) {
                    const tagContent = availableTag.substring(availableTag.indexOf(':') + 1);
                    return tagContent === tag;
                }
                return availableTag === tag;
            });

            if (matchingTag) {
                fullTag = matchingTag;
            }
        }

        // 添加到过滤标签中
        if (!this.selectedTags.includes(fullTag)) {
            this.selectedTags.push(fullTag);

            // 切换到对应的标签分类
            if (fullTag.includes(':')) {
                const category = this.getCategoryFromTag(fullTag);
                if (category && this.tagsByCategory[category]) {
                    this.activeTagCategory = category;
                }
            }

            ElMessage.success(`已添加标签过滤: ${tag}`);
        } else {
            ElMessage.info(`标签已在过滤列表中: ${tag}`);
        }
    },

    onTitleClick(title) {
        // 将标题添加到搜索框
        this.searchQuery = title;
        ElMessage.success(`已搜索标题: ${title}`);
    },

    displayAllTagsModal(manga) {
        console.log('显示更多标签:', manga);

        // 获取漫画的所有标签
        const allTags = this.getOtherTags(manga.tags);
        const titleTag = this.getTitleTag(manga.tags);

        // 构建标签信息
        let message = '';
        if (titleTag) {
            message += `标题: ${titleTag}\n`;
        }
        if (allTags.length > 0) {
            message += `标签: ${allTags.join(', ')}`;
        }

        // 显示所有标签
        this.$msgbox({
            title: '所有标签',
            message: message || '无标签信息',
            showCancelButton: false,
            confirmButtonText: '关闭',
            type: 'info'
        });
    },

    getCategoryFromTag(fullTag) {
        if (fullTag.startsWith('作者:')) return '作者';
        if (fullTag.startsWith('组:')) return '组';
        if (fullTag.startsWith('平台:')) return '平台';
        if (fullTag.startsWith('汉化:')) return '汉化';
        if (fullTag.startsWith('会场:')) return '会场';
        if (fullTag.startsWith('其他:')) return '其他';
        return null;
    },

    // ==================== 桌面版功能 ====================
    async selectDirectory() {
        // 检查 Pywebview API 是否可用且包含所需方法
        if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.trigger_select_directory !== 'function') {
            console.error('window.pywebview.api.trigger_select_directory 函数未找到或无效。');
            ElMessage.error('桌面功能接口不可用，请确认应用是否正确启动。');
            return;
        }
        let loadingInstance = null;
        try {
            console.log('通过 window.pywebview.api.trigger_select_directory() 调用后端 API...');
            loadingInstance = ElLoading.service({ text: '正在打开目录选择器...' });

            // 调用通过 js_api 暴露的 Python 方法
            window.pywebview.api.trigger_select_directory()
                .then(result => {
                    console.log('Python API trigger_select_directory() 调用成功 (同步部分):', result);
                    if (!result || !result.success) {
                         loadingInstance?.close();
                         ElMessage.error(`启动目录选择失败: ${result?.message || '未知错误'}`);
                    }
                    // 加载指示器依赖事件 handleDesktopImportComplete 关闭
                })
                .catch(error => {
                    loadingInstance?.close();
                    console.error('调用 window.pywebview.api.trigger_select_directory 失败:', error);
                    ElMessage.error('与桌面后端通信失败');
                });

        } catch (error) { // 处理调用 API 前的同步错误
            loadingInstance?.close();
            console.error('调用 selectDirectory 同步出错:', error);
            ElMessage.error('打开目录选择器时发生意外错误');
        }
        // 加载指示器的关闭依赖事件 handleDesktopImportComplete
    }, // <--- 添加逗号

    async selectFile() {
        // 检查 Pywebview API 是否可用且包含所需方法 (假设新方法为 trigger_select_file)
        if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.trigger_select_file !== 'function') {
            console.error('window.pywebview.api.trigger_select_file 函数未找到或无效。');
            ElMessage.error('桌面文件选择功能接口不可用。');
            return;
        }
        let loadingInstance = null;
        try {
            console.log('通过 window.pywebview.api.trigger_select_file() 调用后端 API...');
            loadingInstance = ElLoading.service({ text: '正在打开文件选择器...' });

            // 调用新的 Python API 方法
            window.pywebview.api.trigger_select_file()
                .then(result => {
                    console.log('Python API trigger_select_file() 调用成功 (同步部分):', result);
                    if (!result || !result.success) {
                         loadingInstance?.close();
                         ElMessage.error(`启动文件选择失败: ${result?.message || '未知错误'}`);
                    }
                    // 加载指示器依赖事件 handleDesktopImportComplete 关闭
                })
                .catch(error => {
                    loadingInstance?.close();
                    console.error('调用 window.pywebview.api.trigger_select_file 失败:', error);
                    ElMessage.error('与桌面后端通信失败');
                });

        } catch (error) {
            loadingInstance?.close();
            console.error('调用 selectFile 同步出错:', error);
            ElMessage.error('打开文件选择器时发生意外错误');
        }
        // 加载指示器的关闭依赖事件 handleDesktopImportComplete
    }, // <--- 添加逗号 (如果后面还有方法)

    // 处理从后端（desktop_main.py）发送的导入完成事件
    handleDesktopImportComplete(event) {
        console.log('收到 desktopImportComplete 事件:', event.detail);
        const { success, message, added, failed } = event.detail;

        // 关闭可能存在的加载提示
        const loadingInstance = ElLoading.service();
        loadingInstance.close();

        // 使用 $notify 提供更持久的通知
        // *** 注意：这里的 added/failed 来自事件 payload，对于 set_manga_dir 可能不再准确 ***
        // *** 需要调整这里的逻辑或后端事件发送的 payload ***
        if (success) { // 简化成功判断逻辑
             this.$notify({
                title: '操作成功',
                message: message || '操作已成功启动或完成。', // 使用后端消息
                type: 'success',
                duration: 5000
            });
             // 依赖 MangaManager 信号触发的列表刷新，这里不主动调用 loadMangaData
             // this.loadMangaData();
        } else if (!success && message === '用户未选择目录') {
             console.log('用户取消选择目录或文件。');
             // ElMessage.info('未选择目录或文件。'); // 可选的轻提示
        } else { // 其他失败情况
              this.$notify({
                title: '操作失败或通知',
                message: message || '操作未能完成或遇到问题。',
                type: 'warning', // 或 'error'，取决于后端消息
                duration: 8000
            });
        }
    },


    // ==================== Web版本说明 ====================
    // Web版本不支持文件选择功能，所有文件操作功能已移除
    // 添加漫画功能在此Web版本中不可用

    // 保留空的方法以防止错误，但不执行任何操作
    async handleAddManga(command) {
        ElMessage.warning('Web版本不支持添加漫画功能。');
    },

    async onFilesSelected(event) {
        console.warn('Web版本不支持文件选择功能');
        event.target.value = '';
    },

    async onDirectorySelected(event) {
        console.warn('Web版本不支持文件选择功能');
        event.target.value = '';
    },

    // ==================== 智能预加载系统 ====================

    initSmartPreload() {
        // 滚动方向检测
        this.lastScrollTop = 0;
        this.scrollDirection = 'down';

        // 节流滚动事件
        let scrollTimeout;
        window.addEventListener('scroll', () => {
            if (scrollTimeout) {
                clearTimeout(scrollTimeout);
            }

            scrollTimeout = setTimeout(() => {
                this.handleSmartScroll();
            }, 100);
        });

        // 页面空闲时预加载
        if ('requestIdleCallback' in window) {
            this.scheduleIdlePreload();
        }
    },

    handleSmartScroll() {
        const currentScrollTop = window.pageYOffset || document.documentElement.scrollTop;

        // 检测滚动方向
        if (currentScrollTop > this.lastScrollTop) {
            this.scrollDirection = 'down';
        } else {
            this.scrollDirection = 'up';
        }

        this.lastScrollTop = currentScrollTop;

        // 根据滚动方向预加载
        this.predictivePreload();
    },

    predictivePreload() {
        // 获取当前视口中的漫画
        const visibleManga = this.getVisibleManga();
        if (visibleManga.length === 0) return;

        // 根据滚动方向预测下一批要显示的漫画
        const currentIndex = this.filteredMangaList.findIndex(
            manga => manga.file_path === visibleManga[0].file_path
        );

        if (currentIndex === -1) return;

        let preloadIndices = [];
        if (this.scrollDirection === 'down') {
            // 向下滚动，预加载后面的漫画
            for (let i = 1; i <= 6; i++) {
                const index = currentIndex + visibleManga.length + i;
                if (index < this.filteredMangaList.length) {
                    preloadIndices.push(index);
                }
            }
        } else {
            // 向上滚动，预加载前面的漫画
            for (let i = 1; i <= 6; i++) {
                const index = currentIndex - i;
                if (index >= 0) {
                    preloadIndices.push(index);
                }
            }
        }

        // 批量预加载
        const preloadPaths = preloadIndices.map(index => this.filteredMangaList[index].file_path);
        this.batchPreloadThumbnails(preloadPaths, 2);
    },

    getVisibleManga() {
        // 获取当前视口中可见的漫画
        const cards = document.querySelectorAll('.manga-card');
        const visibleCards = [];

        cards.forEach(card => {
            const rect = card.getBoundingClientRect();
            if (rect.top < window.innerHeight && rect.bottom > 0) {
                const mangaPath = card.dataset.mangaPath;
                const manga = this.filteredMangaList.find(m => m.file_path === mangaPath);
                if (manga) {
                    visibleCards.push(manga);
                }
            }
        });

        return visibleCards;
    },

    scheduleIdlePreload() {
        requestIdleCallback((deadline) => {
            // 在浏览器空闲时预加载缩略图
            if (deadline.timeRemaining() > 10) {
                this.idlePreload();
            }

            // 继续调度下一次空闲预加载
            this.scheduleIdlePreload();
        });
    },

    idlePreload() {
        // 找到还没有缓存的缩略图
        const uncachedManga = this.filteredMangaList.filter(manga =>
            !this.thumbnailCache.has(manga.file_path) &&
            !this.loadingThumbnails.has(manga.file_path)
        );

        if (uncachedManga.length > 0) {
            // 随机选择一些进行预加载，避免按顺序加载造成的偏向性
            const randomManga = uncachedManga
                .sort(() => Math.random() - 0.5)
                .slice(0, 3);

            const paths = randomManga.map(manga => manga.file_path);
            this.batchPreloadThumbnails(paths, 1);
        }
    }
};
