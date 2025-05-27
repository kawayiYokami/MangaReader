import os
import re
import io
from zipfile import ZipFile
import cv2
import numpy as np
from utils import manga_logger as log
import threading
from collections import OrderedDict
from PIL import Image


class MangaInfo:
    def __init__(self, file_path):
        self.file_path = file_path
        self.title = os.path.basename(file_path)
        self.tags = set()
        self.current_page = 0
        self.total_pages = 0
        self.is_valid = False
        self.pages = []  # 存储页面路径
        self.last_modified = os.path.getmtime(file_path) if os.path.exists(file_path) else 0  # 获取文件最后修改时间
        self._parse_metadata()

    def get_page_path(self, page_index):
        """获取指定页码的图像路径（兼容方法）
        注意：此方法仅返回页面在ZIP文件中的路径，不是实际文件系统路径
        实际显示应使用MangaLoader.get_page_image方法
        """
        if 0 <= page_index < len(self.pages):
            return self.pages[page_index]
        return None

    def _parse_metadata(self):
        # 保存原始文件名
        original_title = os.path.splitext(self.title)[0]  # 移除扩展名

        # 解析杂志/平台信息 (Fantia) 等
        platform_match = re.match(r"[\(（](.*?)[\)）](.*)", original_title)
        if platform_match:
            platform = platform_match.group(1)
            # 排除版本号和包含数字的括号内容
            if not re.search(r"\d", platform):
                self.tags.add(f"平台:{platform}")
                original_title = platform_match.group(2).strip()

        # 解析作者和团队 [团队 (作者)]
        group_author_match = re.search(r"\[(.*?) \((.*?)\)\]", original_title)
        if group_author_match:
            self.tags.add(f"组:{group_author_match.group(1)}")
            self.tags.add(f"作者:{group_author_match.group(2)}")
            original_title = original_title.replace(
                group_author_match.group(0), "", 1
            ).strip()
        else:
            # 解析单独的作者 [作者]
            author_match = re.search(r"\[(.*?)\]", original_title)
            if author_match and "汉化" not in author_match.group(1):
                self.tags.add(f"作者:{author_match.group(1)}")
                original_title = original_title.replace(
                    author_match.group(0), "", 1
                ).strip()

        # 解析会场信息 (C97) 等
        event_match = re.match(r"\(([Cc][0-9]+)\)(.*)", original_title)
        if event_match:
            self.tags.add(f"会场:{event_match.group(1)}")
            original_title = event_match.group(2).strip()

        # 解析作品名 (作品名)
        # 解析作品名，修改正则表达式以支持中文括号并排除包含数字的括号内容
        series_match = re.search(
            r"[\(（]([^()（）\d]*?)[\)）](?![^[]*\])", original_title
        )
        if series_match and series_match.group(1).strip():
            self.tags.add(f"作品:{series_match.group(1)}")
            # 移除作品名部分，保留主标题
            original_title = original_title[
                : original_title.rfind(series_match.group(0))
            ].strip()

        # 处理其他方括号标签
        while True:
            bracket_match = re.search(r"\[(.*?)\]", original_title)
            if not bracket_match:
                break
            tag_content = bracket_match.group(1)

            # 改进汉化标签识别
            if any(
                keyword in tag_content
                for keyword in ["中国翻訳", "中国翻译", "中國翻譯", "中國翻訳"]
            ):
                self.tags.add("汉化:中国翻译")
            elif any(
                keyword in tag_content
                for keyword in ["汉化", "漢化", "翻訳", "翻译", "翻譯"]
            ):
                self.tags.add(f"汉化:{tag_content}")
            elif any(
                keyword in tag_content for keyword in ["無修正", "无修正", "無修"]
            ):
                self.tags.add("其他:无修正")
            else:
                # 未知类型的标签
                self.tags.add(f"其他:{tag_content}")

            # 从标题中移除这个标签
            original_title = original_title.replace(f"[{tag_content}]", "", 1).strip()

        # 剩下的就是真正的标题
        clean_title = original_title.strip()
        if clean_title:
            self.tags.add(f"标题:{clean_title}")

        # 验证：必须有作者和标题标签才是有效的漫画
        has_author = any(tag.startswith("作者:") for tag in self.tags)
        has_title = any(tag.startswith("标题:") for tag in self.tags)
        self.is_valid = has_author and has_title


class MangaLoader:
    def __init__(self):
        self._cache_lock = threading.Lock()
        self._image_cache = OrderedDict()  # 保持访问顺序
        self._cache_size_limit = 1024 * 1024 * 1024  # 1GB限制
        self._current_cache_size = 0
        self._caching_thread = None
        self._stop_caching = True
        self._last_file_path = None  # 记录最后加载的文件路径
        self._screen_width = 1920  # 默认屏幕宽度
        self._screen_height = 1080  # 默认屏幕高度
        cv2.ocl.setUseOpenCL(True)

    @staticmethod
    def find_manga_files(directory):
        """递归遍历目录查找漫画文件"""
        manga_files = []
        try:
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith(".zip"):
                        full_path = os.path.join(root, file)
                        manga_files.append(full_path)
        except Exception as e:
            log.error(f"遍历目录时发生错误: {str(e)}")
        return manga_files

    @staticmethod
    def load_manga(file_path):
        if not os.path.exists(file_path) or not file_path.lower().endswith(".zip"):
            log.warning(f"文件不存在或不是ZIP文件: {file_path}")
            return None

        manga = MangaInfo(file_path)  # MangaInfo 的 __init__ 方法已经设置了 file_path

        try:
            with ZipFile(file_path, "r") as zip_file:
                all_files = zip_file.namelist()
                image_files = [
                    f
                    for f in all_files
                    if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
                ]

                if not image_files and all_files:
                    log.warning(f"未找到图片文件: {file_path}")
                    return None

                image_files.sort()
                manga.total_pages = len(image_files)
                manga.pages = image_files  # 保存页面列表

                if not manga.is_valid:
                    # 如果验证不通过，但包含图片，则设置默认标题和添加未知标签
                    if image_files:
                        title_from_filename = os.path.splitext(
                            os.path.basename(file_path)
                        )[0]
                        manga.tags.add(f"标题:{title_from_filename}")
                        manga.tags.add("其他:未知")
                        manga.is_valid = True  # 标记为有效

        except Exception as e:
            log.error(f"加载漫画时发生错误: {str(e)}")
            return None

        return manga

    def _get_image_size(self, image):
        """估算图像内存占用"""
        if isinstance(image, np.ndarray):
            return image.nbytes
        return image.width * image.height * len(image.mode)

    def _add_to_cache(self, page_index, image):
        """线程安全地添加图像到缓存"""
        with self._cache_lock:
            if page_index in self._image_cache:
                return False

            img_size = self._get_image_size(image)

            # 释放空间直到足够
            while (
                self._current_cache_size + img_size > self._cache_size_limit
                and self._image_cache
            ):
                oldest_key, oldest_img = self._image_cache.popitem(last=False)
                self._current_cache_size -= self._get_image_size(oldest_img)

            # 添加新图像
            self._image_cache[page_index] = image
            self._current_cache_size += img_size
            return True

    def start_precaching(self, manga):
        """启动后台预缓存线程"""
        self._stop_caching = False
        self._caching_thread = threading.Thread(
            target=self._cache_entire_manga, args=(manga,), daemon=True
        )
        self._caching_thread.start()

    def clear_cache(self):
        """清空所有缓存"""
        with self._cache_lock:
            self._stop_caching = True
            self._image_cache.clear()
            self._current_cache_size = 0
            self._last_file_path = None  # 新增这行，清空最后加载的文件路径记录

    def get_page_image(self, manga, page_index):
        """获取指定页面的漫画图像(优先从缓存读取)"""
        # 先检查是否需要清空缓存（不加锁）
        if hasattr(self, "_last_file_path") and self._last_file_path != manga.file_path:
            log.info(f"切换漫画，清空缓存: {self._last_file_path} -> {manga.file_path}")
            self.clear_cache()  # 清空缓存
            self._last_file_path = manga.file_path  # 更新文件路径

        # 加锁检查缓存
        with self._cache_lock:
            if page_index in self._image_cache:
                return self._image_cache[page_index]

        # 获取当前屏幕分辨率
        try:
            import screeninfo

            monitors = screeninfo.get_monitors()
            if monitors:
                self._screen_width = monitors[0].width
                self._screen_height = monitors[0].height
        except Exception as e:
            log.warning(f"获取屏幕分辨率失败: {str(e)}")

        # 缓存未命中则从ZIP读取并缓存整本漫画
        if manga.total_pages > 0 and self._stop_caching:
            # 启动后台线程缓存整本漫画
            self.start_precaching(manga)

        # 返回当前请求的页面
        image = MangaLoader._get_page_image_from_zip(manga, page_index)
        if image is not None and (isinstance(image, np.ndarray) and np.any(image)):
            self._add_to_cache(page_index, image)
        return image

    def _cache_entire_manga(self, manga):
        """后台线程缓存整本漫画，按2倍屏幕尺寸缩放图像"""
        if not manga or not manga.file_path:
            self._is_caching = False
            return

        log.info(f"开始缓存漫画: {manga.file_path}")
        cached_pages = 0

        # 获取屏幕分辨率（使用类属性存储的值）
        screen_width = self._screen_width
        screen_height = self._screen_height

        # 计算缓存尺寸上限（屏幕尺寸的2倍）
        target_width_limit = screen_width * 1 if screen_width > 0 else 1
        target_height_limit = screen_height * 1 if screen_height > 0 else 1

        for i in range(manga.total_pages):
            # 检查是否应该停止缓存（漫画已切换或收到停止信号）
            if self._stop_caching or (
                hasattr(self, "_last_file_path")
                and self._last_file_path != manga.file_path
            ):
                log.info(f"停止缓存: 漫画已切换或收到停止信号")
                self.clear_cache()  # 清空缓存
                self._stop_caching = True
                break

            if i in self._image_cache:
                continue

            # 获取原始图像数据
            image = MangaLoader._get_page_image_from_zip(manga, i)
            if not isinstance(image, np.ndarray) or not np.any(image):
                log.warning(f"页面 {i+1}: 获取无效图像")
                continue

            # 获取图像原始尺寸
            height, width = image.shape[:2]

            # 判断是否需要缩放
            if width > target_width_limit or height > target_height_limit:
                # 计算缩放比例
                scale_factor = 1.0 / max(
                    width / target_width_limit,
                    height / target_height_limit
                )
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)

                # 使用三次插值算法缩放图像
                image = cv2.resize(
                    image,
                    (new_width, new_height),
                    interpolation=cv2.INTER_AREA
                )

            # 尝试添加到缓存
            if self._add_to_cache(i, image):
                cached_pages += 1

        # 更新缓存状态并记录结果
        with self._cache_lock:
            log.info(f"缓存完成: {cached_pages}/{manga.total_pages}页")
            log.info(
                f"占用内存: {self._current_cache_size / (self._cache_size_limit):.2f}GB"
            )
            self._stop_caching = True

    @staticmethod
    def _get_page_image_from_zip(manga, page_index):
        """从ZIP文件读取图像数据(原get_page_image的逻辑)
        优化版本：使用高质量图像读取设置
        """
        # 参数验证
        if not manga or not os.path.exists(manga.file_path):
            log.warning(
                f"无效的漫画对象或文件不存在: {getattr(manga, 'file_path', None)}"
            )
            return None

        try:
            with ZipFile(manga.file_path, "r") as zip_file:
                # 获取并过滤图像文件
                image_files = [
                    f
                    for f in zip_file.namelist()
                    if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
                ]

                if not image_files:
                    log.debug(f"ZIP中未找到图片文件: {manga.file_path}")
                    return None

                image_files.sort()

                # 页码验证
                if page_index < 0 or page_index >= len(image_files):
                    log.warning(f"无效页码: {page_index} (总数: {len(image_files)})")
                    return None

                # 读取图像数据
                file_name = image_files[page_index]
                try:
                    image_data = zip_file.read(file_name)
                    if not image_data:
                        log.error(f"空图像数据: {file_name}")
                        return None

                    # 首先尝试使用OpenCV解码
                    nparr = np.frombuffer(image_data, np.uint8)
                    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    if image is None:
                        log.warning(f"OpenCV无法解码图像，尝试使用Pillow: {file_name}")
                        try:
                            # 使用Pillow尝试解码
                            image_io = io.BytesIO(image_data)
                            pil_image = Image.open(image_io)
                            
                            # 确保图像被完全加载
                            pil_image.load()
                            
                            # 转换为RGB模式
                            if pil_image.mode != 'RGB':
                                pil_image = pil_image.convert('RGB')
                            
                            # 转换为OpenCV格式
                            image = np.array(pil_image)
                            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                        except Exception as e:
                            log.error(f"Pillow也无法解码图像({file_name}): {str(e)}")
                            return None
                    
                    # 转换为RGB格式
                    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                    return image

                except Exception as e:
                    log.error(f"处理图像时出错({file_name}): {str(e)}")
                    return None

        except Exception as e:
            log.error(f"处理ZIP文件时出错({manga.file_path}): {str(e)}")
            return None
