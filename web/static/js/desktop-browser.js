// 桌面端漫画浏览功能模块
window.MangaBrowserDesktopMethods = {
    // ==================== 漫画选择 ====================
    selectManga(manga) {
        console.log('selectManga (Desktop): 点击了漫画', manga);
        this.saveBrowsingState();
        const encodedPath = encodeURIComponent(manga.file_path);
        
        const viewerUrl = `/viewer.html?path=${encodedPath}&page=0`;

        // 根据环境决定打开方式
        // IS_PYWEBVIEW 在 index.html 中定义
        if (window.IS_PYWEBVIEW) {
            // PyWebView环境: 使用iframe在应用内打开
            this.openMangaViewer(viewerUrl);
        } else {
            // 普通桌面浏览器: 在新标签页打开
            window.open(viewerUrl, '_blank');
        }
    }
};