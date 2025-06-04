// 漫画浏览功能模块
window.MangaBrowserMethods = {
    // ==================== 漫画浏览功能 ====================

    async loadInitialData() {
        try {
            // 直接加载缓存中的漫画数据
            await this.loadMangaData();
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

            // 测试加载第一个漫画的缩略图
            if (this.mangaList.length > 0) {
                console.log('开始测试缩略图加载...');
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
                this.showAllTags[category] = false;
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
        this.showAllTags[category] = !this.showAllTags[category];
    },

    selectManga(manga) {
        console.log('选择漫画:', manga);

        // 跳转到漫画查看器
        const encodedPath = encodeURIComponent(manga.file_path);
        const viewerUrl = `/viewer.html?path=${encodedPath}&page=0`;
        window.open(viewerUrl, '_blank');
    },

    viewManga(manga) {
        console.log('查看漫画:', manga);
        ElMessage.info(`查看漫画: ${manga.title}`);
    },

    translateManga(manga) {
        console.log('翻译漫画:', manga);
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
            rootMargin: '50px', // 提前50px开始加载
            threshold: 0.1
        });
    },

    async loadThumbnail(mangaPath) {
        if (this.loadingThumbnails.has(mangaPath)) return;

        try {
            this.loadingThumbnails.add(mangaPath);

            // 使用POST请求发送路径，避免URL编码问题
            const response = await axios.post('/api/manga/thumbnail', {
                manga_path: mangaPath,
                size: 300
            });

            if (response.data && response.data.thumbnail) {
                // 缓存缩略图
                this.thumbnailCache.set(mangaPath, response.data.thumbnail);

                // 强制更新Vue响应式数据
                this.$forceUpdate();
                console.log('缩略图加载成功:', mangaPath);
            }
        } catch (error) {
            console.error('获取缩略图失败:', mangaPath, error);
        } finally {
            this.loadingThumbnails.delete(mangaPath);
        }
    },

    getThumbnailUrl(mangaPath) {
        return this.thumbnailCache.get(mangaPath) || null;
    },

    isThumbnailLoading(mangaPath) {
        return this.loadingThumbnails.has(mangaPath);
    },

    observeCard(element) {
        if (this.thumbnailObserver && element) {
            this.thumbnailObserver.observe(element);
        }
    },

    unobserveCard(element) {
        if (this.thumbnailObserver && element) {
            this.thumbnailObserver.unobserve(element);
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
        console.log('点击标题:', title);

        // 将标题添加到搜索框
        this.searchQuery = title;
        ElMessage.success(`已搜索标题: ${title}`);
    },

    showAllTags(manga) {
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

    // ==================== Web版本说明 ====================
    // Web版本不支持文件选择功能，所有文件操作功能已移除
    // 如需添加漫画功能，请使用Electron版本

    // 保留空的方法以防止错误，但不执行任何操作
    async handleAddManga(command) {
        ElMessage.warning('Web版本不支持添加漫画功能，请使用Electron版本');
    },

    async onFilesSelected(event) {
        console.warn('Web版本不支持文件选择功能');
        event.target.value = '';
    },

    async onDirectorySelected(event) {
        console.warn('Web版本不支持文件选择功能');
        event.target.value = '';
    }
};
