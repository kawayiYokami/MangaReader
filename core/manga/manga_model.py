import os
import re
import io
from zipfile import ZipFile
import cv2
import numpy as np
from utils import manga_logger as log

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

        # 页面尺寸分析相关属性
        self.page_dimensions = []  # 存储每页的尺寸 [(width, height), ...]
        self.dimension_variance = None  # 尺寸方差分数 (0-1, 越小越一致)
        self.is_likely_manga = None  # 基于尺寸分析的漫画可能性判断

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

    def analyze_page_dimensions(self):
        """分析页面尺寸一致性，计算方差分数"""
        if not self.page_dimensions or len(self.page_dimensions) < 2:
            self.dimension_variance = 0.0
            self.is_likely_manga = True
            return

        try:
            import numpy as np

            # 转换为numpy数组便于计算
            dimensions = np.array(self.page_dimensions)
            widths = dimensions[:, 0]
            heights = dimensions[:, 1]

            # 计算宽高比
            aspect_ratios = widths / heights

            # 计算面积
            areas = widths * heights

            # 使用变异系数 (CV = std/mean) 来衡量一致性
            # 变异系数对尺寸大小不敏感，更适合评估相对变化

            # 宽度变异系数
            width_cv = np.std(widths) / np.mean(widths) if np.mean(widths) > 0 else 0

            # 高度变异系数
            height_cv = np.std(heights) / np.mean(heights) if np.mean(heights) > 0 else 0

            # 宽高比变异系数
            ratio_cv = np.std(aspect_ratios) / np.mean(aspect_ratios) if np.mean(aspect_ratios) > 0 else 0

            # 面积变异系数
            area_cv = np.std(areas) / np.mean(areas) if np.mean(areas) > 0 else 0

            # 综合方差分数：取各项变异系数的加权平均
            # 宽高比权重最高，因为漫画页面宽高比通常很一致
            # 面积权重次之，宽高权重较低
            variance_score = (
                ratio_cv * 0.4 +      # 宽高比权重40%
                area_cv * 0.3 +       # 面积权重30%
                width_cv * 0.15 +     # 宽度权重15%
                height_cv * 0.15      # 高度权重15%
            )

            # 限制分数在0-1范围内
            self.dimension_variance = min(variance_score, 1.0)

            # 判断是否可能是漫画
            # 使用配置中的阈值
            from core.config import config
            manga_threshold = config.dimension_variance_threshold.value
            self.is_likely_manga = self.dimension_variance < manga_threshold

            log.debug(f"尺寸分析完成 {self.file_path}: "
                     f"方差分数={self.dimension_variance:.3f}, "
                     f"可能是漫画={self.is_likely_manga}, "
                     f"页数={len(self.page_dimensions)}")

        except Exception as e:
            log.warning(f"页面尺寸分析失败 {self.file_path}: {e}")
            # 分析失败时保守处理
            self.dimension_variance = 0.0
            self.is_likely_manga = True


class MangaLoader:
    def __init__(self):
        cv2.ocl.setUseOpenCL(True)

    @staticmethod
    def find_manga_files(directory):
        """递归遍历目录查找漫画文件和图片文件夹"""
        manga_files = []
        image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".webp")
        try:
            # 首先检查传入的directory本身是否是一个漫画文件夹
            if os.path.isdir(directory):
                has_images_in_root = False
                for item in os.listdir(directory):
                    item_path = os.path.join(directory, item)
                    if os.path.isfile(item_path) and item.lower().endswith(image_extensions):
                        has_images_in_root = True
                        break
                if has_images_in_root:
                    manga_files.append(directory)

            for root, dirs, files in os.walk(directory):
                # 检查ZIP文件
                for file in files:
                    if file.lower().endswith(".zip"):
                        full_path = os.path.join(root, file)
                        manga_files.append(full_path)

                # 检查图片文件夹 (不包含子目录)
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    # 检查目录是否包含图片文件 (不递归检查子目录)
                    has_images = False
                    for item in os.listdir(dir_path):
                        item_path = os.path.join(dir_path, item)
                        if os.path.isfile(item_path) and item.lower().endswith(image_extensions):
                            has_images = True
                            break # 找到图片文件即可

                    if has_images:
                        manga_files.append(dir_path)
        except Exception as e:
            log.error(f"遍历目录时发生错误: {str(e)}")
        return manga_files

    @staticmethod
    def load_manga(file_path, analyze_dimensions=True):
        if not os.path.exists(file_path):
            log.warning(f"文件或目录不存在: {file_path}")
            return None

        manga = MangaInfo(file_path)

        if os.path.isdir(file_path):
            # 处理文件夹作为漫画
            image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".webp")
            try:
                all_files = os.listdir(file_path)
                image_files = [
                    os.path.join(file_path, f)
                    for f in all_files
                    if os.path.isfile(os.path.join(file_path, f)) and f.lower().endswith(image_extensions)
                ]
                image_files.sort()

                if not image_files:
                    log.warning(f"文件夹中未找到图片文件: {file_path}")
                    return None

                manga.total_pages = len(image_files)
                manga.pages = image_files  # 存储实际文件路径

                if not manga.is_valid:
                    title_from_filename = os.path.basename(file_path)
                    manga.tags.add(f"标题:{title_from_filename}")
                    manga.tags.add("其他:文件夹漫画")
                    manga.is_valid = True

            except Exception as e:
                log.error(f"加载文件夹漫画时发生错误: {str(e)}")
                return None
        elif file_path.lower().endswith(".zip"):
            # 处理ZIP文件作为漫画
            try:
                with ZipFile(file_path, "r") as zip_file:
                    all_files = zip_file.namelist()
                    image_files = [
                        f
                        for f in all_files
                        if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
                    ]

                    if not image_files and all_files:
                        log.warning(f"ZIP中未找到图片文件: {file_path}")
                        return None

                    image_files.sort()
                    manga.total_pages = len(image_files)
                    manga.pages = image_files  # 保存页面在ZIP文件中的路径

                    if not manga.is_valid:
                        title_from_filename = os.path.splitext(
                            os.path.basename(file_path)
                        )[0]
                        manga.tags.add(f"标题:{title_from_filename}")
                        manga.tags.add("其他:未知")
                        manga.is_valid = True

            except Exception as e:
                log.error(f"加载ZIP漫画时发生错误: {str(e)}")
                return None
        else:
            log.warning(f"不支持的文件类型: {file_path}")
            return None

        return manga

    @staticmethod
    def _analyze_manga_dimensions(manga):
        """分析漫画页面尺寸，提取尺寸信息（仅对ZIP文件进行分析）"""
        if not manga or not manga.pages:
            return

        # 只对ZIP文件进行尺寸分析，文件夹结构的漫画不需要过滤
        if os.path.isdir(manga.file_path):
            log.debug(f"跳过文件夹漫画的尺寸分析: {manga.file_path}")
            # 文件夹漫画默认认为是有效漫画
            manga.dimension_variance = None  # 设置为None表示不需要分析
            manga.is_likely_manga = True
            return

        try:
            log.info(f"开始分析ZIP漫画页面尺寸: {manga.file_path}")

            # 采样策略：对于页数较多的漫画，采样分析以提高性能
            total_pages = len(manga.pages)
            if total_pages <= 10:
                # 少于10页，全部分析
                sample_indices = list(range(total_pages))
            elif total_pages <= 50:
                # 10-50页，采样70%
                sample_size = max(7, int(total_pages * 0.7))
                sample_indices = np.random.choice(total_pages, sample_size, replace=False)
            else:
                # 超过50页，采样30页
                sample_indices = np.random.choice(total_pages, 30, replace=False)

            dimensions = []

            for i in sample_indices:
                try:
                    # 获取页面尺寸信息
                    if os.path.isdir(manga.file_path):
                        width, height = MangaLoader._get_page_dimensions_from_folder(manga, i)
                    else:
                        width, height = MangaLoader._get_page_dimensions_from_zip(manga, i)

                    if width and height:
                        dimensions.append((width, height))

                except Exception as e:
                    log.debug(f"获取页面 {i} 尺寸失败: {e}")
                    continue

            # 更新漫画对象的尺寸信息
            manga.page_dimensions = dimensions

            # 执行尺寸分析
            manga.analyze_page_dimensions()

            log.info(f"尺寸分析完成: {manga.file_path}, "
                    f"采样页数={len(dimensions)}/{total_pages}, "
                    f"方差分数={manga.dimension_variance:.3f}, "
                    f"可能是漫画={manga.is_likely_manga}")

        except Exception as e:
            log.error(f"分析漫画尺寸失败 {manga.file_path}: {e}")
            # 分析失败时设置默认值
            manga.page_dimensions = []
            manga.dimension_variance = 0.0
            manga.is_likely_manga = True

    @staticmethod
    def _get_page_dimensions_from_zip(manga, page_index):
        """从ZIP文件获取页面尺寸（不加载完整图像）"""
        try:
            with ZipFile(manga.file_path, "r") as zip_file:
                image_files = [
                    f for f in zip_file.namelist()
                    if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
                ]

                if page_index >= len(image_files):
                    return None, None

                image_files.sort()
                file_name = image_files[page_index]

                # 读取图像数据
                image_data = zip_file.read(file_name)

                # 使用PIL快速获取尺寸（不加载完整图像）
                image_io = io.BytesIO(image_data)
                with Image.open(image_io) as pil_image:
                    return pil_image.size  # 返回 (width, height)

        except Exception as e:
            log.debug(f"获取ZIP页面尺寸失败 {file_name}: {e}")
            return None, None

    @staticmethod
    def _get_page_dimensions_from_folder(manga, page_index):
        """从文件夹获取页面尺寸（不加载完整图像）"""
        try:
            image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".webp")
            image_files = [
                f for f in os.listdir(manga.file_path)
                if f.lower().endswith(image_extensions)
            ]

            if page_index >= len(image_files):
                return None, None

            image_files.sort()
            image_path = os.path.join(manga.file_path, image_files[page_index])

            # 使用PIL快速获取尺寸
            with Image.open(image_path) as pil_image:
                return pil_image.size  # 返回 (width, height)

        except Exception as e:
            log.debug(f"获取文件夹页面尺寸失败 {image_path}: {e}")
            return None, None



    def get_page_image(self, manga, page_index):
        """获取指定页面的漫画图像"""
        # 根据漫画类型调用不同的图像获取方法
        if os.path.isdir(manga.file_path):
            image = MangaLoader._get_page_image_from_folder(manga, page_index)
        else: # 默认为ZIP文件
            image = MangaLoader._get_page_image_from_zip(manga, page_index)

        return image



    @staticmethod
    def _get_page_image_from_zip(manga, page_index):
        """从ZIP文件读取图像数据"""
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

    @staticmethod
    def _get_page_image_from_folder(manga, page_index):
        """从文件夹读取图像数据"""
        if not manga or not os.path.exists(manga.file_path) or not os.path.isdir(manga.file_path):
            log.warning(f"无效的漫画对象或目录不存在: {getattr(manga, 'file_path', None)}")
            return None

        try:
            # manga.pages 已经存储了完整的图片路径
            if page_index < 0 or page_index >= len(manga.pages):
                log.warning(f"无效页码: {page_index} (总数: {len(manga.pages)})")
                return None

            image_path = manga.pages[page_index]
            if not os.path.exists(image_path):
                log.error(f"图片文件不存在: {image_path}")
                return None

            try:
                # 首先尝试使用OpenCV解码
                image = cv2.imread(image_path, cv2.IMREAD_COLOR)

                if image is None:
                    log.warning(f"OpenCV无法解码图像，尝试使用Pillow: {image_path}")
                    try:
                        # 使用Pillow尝试解码
                        pil_image = Image.open(image_path)
                        
                        # 确保图像被完全加载
                        pil_image.load()
                        
                        # 转换为RGB模式
                        if pil_image.mode != 'RGB':
                            pil_image = pil_image.convert('RGB')
                        
                        # 转换为OpenCV格式
                        image = np.array(pil_image)
                        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                    except Exception as e:
                        log.error(f"Pillow也无法解码图像({image_path}): {str(e)}")
                        return None
                
                # 转换为RGB格式
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                return image

            except Exception as e:
                log.error(f"处理图像时出错({image_path}): {str(e)}")
                return None

        except Exception as e:
            log.error(f"处理文件夹漫画时出错({manga.file_path}): {str(e)}")
            return None
