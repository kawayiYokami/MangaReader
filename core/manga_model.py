import os
import re
import io
from zipfile import ZipFile
from PIL import Image
from utils import manga_logger as log

class MangaInfo:
    def __init__(self, file_path):
        self.file_path = file_path
        self.title = os.path.basename(file_path)
        self.tags = set()
        self.current_page = 0
        self.total_pages = 0
        self.is_valid = False
        self._parse_metadata()
    
    def _parse_metadata(self):
        # 保存原始文件名
        original_title = os.path.splitext(self.title)[0]  # 移除扩展名
        
        # 解析杂志/平台信息 (Fantia) 等
        platform_match = re.match(r'[\(（](.*?)[\)）](.*)', original_title)
        if platform_match:
            platform = platform_match.group(1)
            # 排除版本号和包含数字的括号内容
            if not re.search(r'\d', platform):
                self.tags.add(f'平台:{platform}')
                original_title = platform_match.group(2).strip()
        
        # 解析作者和团队 [团队 (作者)]
        group_author_match = re.search(r'\[(.*?) \((.*?)\)\]', original_title)
        if group_author_match:
            self.tags.add(f'组:{group_author_match.group(1)}')
            self.tags.add(f'作者:{group_author_match.group(2)}')
            original_title = original_title.replace(group_author_match.group(0), '', 1).strip()
        else:
            # 解析单独的作者 [作者]
            author_match = re.search(r'\[(.*?)\]', original_title)
            if author_match and '汉化' not in author_match.group(1):
                self.tags.add(f'作者:{author_match.group(1)}')
                original_title = original_title.replace(author_match.group(0), '', 1).strip()
        
        # 解析会场信息 (C97) 等
        event_match = re.match(r'\(([Cc][0-9]+)\)(.*)', original_title)
        if event_match:
            self.tags.add(f'会场:{event_match.group(1)}')
            original_title = event_match.group(2).strip()
        
        # 解析作品名 (作品名)
        # 解析作品名，修改正则表达式以支持中文括号并排除包含数字的括号内容
        series_match = re.search(r'[\(（]([^()（）\d]*?)[\)）](?![^[]*\])', original_title)
        if series_match and series_match.group(1).strip():
            self.tags.add(f'作品:{series_match.group(1)}')
            # 移除作品名部分，保留主标题
            original_title = original_title[:original_title.rfind(series_match.group(0))].strip()
        
        # 处理其他方括号标签
        while True:
            bracket_match = re.search(r'\[(.*?)\]', original_title)
            if not bracket_match:
                break
            tag_content = bracket_match.group(1)
            
            # 改进汉化标签识别
            if any(keyword in tag_content for keyword in ['汉化', '漢化', '翻訳', '翻译', '翻譯']):
                self.tags.add(f'汉化:{tag_content}')
            elif any(keyword in tag_content for keyword in ['中国翻訳', '中国翻译', '中國翻譯', '中國翻訳']):
                self.tags.add('汉化:中国翻译')
            elif any(keyword in tag_content for keyword in ['無修正', '无修正', '無修']):
                self.tags.add('其他:无修正')
            else:
                # 未知类型的标签
                self.tags.add(f'其他:{tag_content}')
            
            # 从标题中移除这个标签
            original_title = original_title.replace(f'[{tag_content}]', '', 1).strip()
        
        # 剩下的就是真正的标题
        clean_title = original_title.strip()
        if clean_title:
            self.tags.add(f'标题:{clean_title}')
        
        # 验证：必须有作者和标题标签才是有效的漫画
        has_author = any(tag.startswith('作者:') for tag in self.tags)
        has_title = any(tag.startswith('标题:') for tag in self.tags)
        self.is_valid = has_author and has_title

class MangaLoader:
    @staticmethod
    def find_manga_files(directory):
        """递归遍历目录查找漫画文件"""
        manga_files = []
        try:
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith('.zip'):
                        full_path = os.path.join(root, file)
                        manga_files.append(full_path)
        except Exception as e:
            log.error(f"遍历目录时发生错误: {str(e)}")
        return manga_files

    @staticmethod
    def load_manga(file_path):
        if not os.path.exists(file_path) or not file_path.lower().endswith('.zip'):
            log.warning(f"文件不存在或不是ZIP文件: {file_path}")
            return None
        
        manga = MangaInfo(file_path)
        manga.file_path = file_path
        
        try:
            with ZipFile(file_path, 'r') as zip_file:
                all_files = zip_file.namelist()
                image_files = [f for f in all_files 
                              if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))]
                
                if not image_files and all_files:
                    log.warning(f"未找到图片文件: {file_path}")
                    return None
                
                image_files.sort()
                manga.total_pages = len(image_files)
                
                if not manga.is_valid:
                    log.warning(f"无效的漫画文件（缺少作者或标题）: {file_path}")
                    return None
                    
        except Exception as e:
            log.error(f"加载漫画时发生错误: {str(e)}")
            return None
        
        return manga
    
    @staticmethod
    def get_page_image(manga, page_index):
        if not manga or not os.path.exists(manga.file_path):
            log.warning(f"无法加载图像: 漫画对象为空或文件不存在 {manga.file_path if manga else 'None'}")
            return None
        
        try:
            with ZipFile(manga.file_path, 'r') as zip_file:
                # 获取所有文件
                all_files = zip_file.namelist()
                # log.debug(f"ZIP文件中包含 {len(all_files)} 个文件")
                
                # 获取所有图片文件，包括子目录中的图片
                image_files = [f for f in all_files 
                              if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))]
                
                # 如果没有找到图片，尝试列出所有文件名以便调试
                if not image_files:
                    if all_files:
                        log.debug(f"ZIP文件中未找到图片文件，内容: {', '.join(all_files[:10])}{'...' if len(all_files) > 10 else ''}")
                    else:
                        log.debug("ZIP文件为空或无法读取内容")
                    return None
                
                image_files.sort()
                
                if 0 <= page_index < len(image_files):
                    file_name = image_files[page_index]
                    # log.debug(f"尝试读取图像文件: {file_name}")
                    try:
                        image_data = zip_file.read(file_name)
                        # log.debug(f"成功读取图像数据，大小: {len(image_data)} 字节")
                    except Exception as zip_error:
                        log.error(f"从ZIP文件读取图像数据时发生错误: {str(zip_error)}")
                        return None
                    
                    # 使用PIL打开图像数据
                    try:
                        # 检查图像数据是否有效
                        if not image_data or len(image_data) == 0:
                            log.error(f"图像数据为空: {file_name}")
                            return None
                            
                        # log.debug(f"创建BytesIO对象，数据大小: {len(image_data)} 字节")
                        image_buffer = io.BytesIO(image_data)
                        
                        # 尝试打开图像
                        # log.debug(f"尝试使用PIL打开图像: {file_name}")
                        image = Image.open(image_buffer)
                        
                        # 立即加载图像数据，确保图像有效
                        image.load()
                        
                        # 验证图像属性
                        if not hasattr(image, 'width') or not hasattr(image, 'height') or not hasattr(image, 'mode'):
                            log.error(f"图像缺少必要属性: {file_name}")
                            return None
                            
                        # log.debug(f"成功加载图像: {file_name}, 大小: {image.width}x{image.height}, 模式: {image.mode}")
                        return image
                    except Exception as img_error:
                        log.error(f"无法解析图像数据: {str(img_error)}, 文件: {file_name}")
                        return None
                else:
                    log.warning(f"页码超出范围: {page_index + 1}, 总页数: {len(image_files)}")
        except Exception as e:
            log.error(f"加载图像时发生错误: {str(e)}")
        
        log.warning("返回空图像")
        return None