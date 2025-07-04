// 移动端漫画浏览功能模块
window.MangaBrowserMobileMethods = {
    // ==================== 漫画选择 ====================
    selectManga(manga) {
        console.log('selectManga (Mobile): 点击了漫画', manga);
        this.saveBrowsingState();
        const encodedPath = encodeURIComponent(manga.file_path);

        // 移动端在新标签页中打开 viewer_mobile.html
        const viewerUrl = `/viewer_mobile.html?path=${encodedPath}&page=0`;
        window.open(viewerUrl, '_blank');
    }
};