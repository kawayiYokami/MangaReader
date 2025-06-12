# 缓存系统优化方案 V4.1

此方案为 V4.0 的追加修复，旨在修正 `MangaListCacheHandler`，使其能正确响应前端的 `show_unlikely` 过滤开关。

## 目标

- 改造 `MangaListCacheHandler` 的 `get_entries` 方法。
- 使用从 `**kwargs` 传入的布尔参数 `show_unlikely` 进行过滤。
- 移除旧的、基于搜索字符串解析的过滤逻辑，以统一和简化代码。

## 执行步骤

### 1. 修改 `MangaListCacheHandler.get_entries`

-   **文件**: `web/api/cache.py`
-   **位置**: 第 `130` 行左右
-   **操作**: 完整替换 `get_entries` 方法。

    -   **旧代码 (问题所在)**:
        ```python
        async def get_entries(self, page: int, page_size: int, search: Optional[str] = None, **kwargs) -> Dict[str, Any]:
            """获取漫画列表缓存条目"""
            try:
                # ... 获取 all_manga ...
                
                # 检查是否有分类筛选请求 (旧逻辑)
                filter_category = None
                actual_search = search

                if search:
                    if search.startswith("category:likely_manga"):
                        # ...
                    elif search.startswith("category:unlikely_manga"): # <--- 问题点
                        filter_category = "unlikely_manga"
                        actual_search = search[23:].strip() if len(search) > 23 else ""
                    # ...

                # 应用分类筛选 (旧逻辑)
                if filter_category:
                    # ...
                    elif filter_category == "unlikely_manga": # <--- 问题点
                        all_manga = [
                            manga for manga in all_manga
                            if manga.get("is_likely_manga", False) == False and manga.get("dimension_variance") is not None
                        ]
                    # ...
                
                # ... 后续的文本搜索和分页 ...
        ```

    -   **新代码 (修复方案)**:
        ```python
        async def get_entries(self, page: int, page_size: int, search: Optional[str] = None, **kwargs) -> Dict[str, Any]:
            """获取漫画列表缓存条目"""
            try:
                # 获取所有漫画条目
                all_manga = []
                cached_dirs = self.manager.get_all_entries_for_display()
                
                for dir_entry in cached_dirs:
                    directory_path = dir_entry.get("directory_path")
                    if directory_path:
                        manga_list = self.manager.get(directory_path)
                        if manga_list:
                            all_manga.extend(manga_list)

                # 1. 应用新的布尔筛选
                show_unlikely = kwargs.get("show_unlikely", False)
                if show_unlikely:
                    all_manga = [
                        manga for manga in all_manga
                        if manga.get("is_likely_manga") is False and manga.get("dimension_variance") is not None
                    ]

                # 2. 应用文本搜索过滤
                if search:
                    query = search.lower()
                    # 避免在已有 unlikely 筛选时重复过滤
                    if not show_unlikely: 
                        if "category:unlikely_manga" in query:
                            # 提示用户使用开关，但仍执行一次
                            self.log.info("检测到旧的过滤语法，请使用'仅显示可能非漫画'开关。")
                            all_manga = [
                                manga for manga in all_manga
                                if manga.get("is_likely_manga") is False and manga.get("dimension_variance") is not None
                            ]
                            # 移除分类指令，只留下搜索词
                            query = query.replace("category:unlikely_manga", "").strip()

                    if query: # 如果移除指令后还有搜索词
                        filtered_manga = []
                        for manga in all_manga:
                            title = str(manga.get("title", "")).lower()
                            file_path = str(manga.get("file_path", "")).lower()
                            tags = str(manga.get("tags", [])).lower()
                            if query in title or query in file_path or query in tags:
                                filtered_manga.append(manga)
                        all_manga = filtered_manga
                
                # 3. 分页
                total = len(all_manga)
                start = (page - 1) * page_size
                end = start + page_size
                page_manga = all_manga[start:end]
                
                # 4. 格式化条目
                entries = [self._format_manga_entry(manga) for manga in page_manga]
                
                return {
                    "entries": entries,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
                    "filter_applied": "unlikely" if show_unlikely else None
                }
            except Exception as e:
                self.log.error(f"获取漫画列表缓存条目失败: {e}")
                raise HTTPException(status_code=500, detail=f"获取漫画列表缓存条目失败: {e}")
        ```

### 总结

完成以上修改后，`MangaListCacheHandler` 将完全采用新的过滤机制，与 `TranslationCacheHandler` 的行为保持一致，从而修复前端开关无效的 Bug。