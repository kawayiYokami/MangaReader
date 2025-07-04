# core/manga/data_source.py
"""
定义了数据源策略，用于从不同类型的漫画源（如文件夹、ZIP文件）中统一提取物理属性。
"""
import os
import abc
from zipfile import ZipFile
from typing import List, Dict, Any, Type, Tuple, Optional
from utils import manga_logger as log
from PIL import Image
import io

def _natural_sort_key(s):
    """
    为字符串提供自然排序的键。
    """
    import re
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def _get_image_dimensions_fast(image_data: bytes) -> Optional[Tuple[int, int]]:
    """
    使用Pillow从内存中的图像数据快速获取尺寸，避免完全解压。
    """
    if not image_data:
        return None
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            return img.size  # (width, height)
    except Exception as e:
        log.warning(f"使用Pillow快速获取图像尺寸失败: {e}")
        return None

class DataSource(abc.ABC):
    """数据源策略的抽象基类 (ABC)"""

    def __init__(self, path: str):
        self.path = path

    @abc.abstractmethod
    def get_properties(self) -> Dict[str, Any]:
        """
        获取漫画源的物理属性。

        Returns:
            Dict[str, Any]: 一个包含以下键的字典:
                'file_size': int,
                'last_modified': float (timestamp),
                'total_pages': int,
                'pages': List[str],
                'file_type': str
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_page_image_data(self, page_index: int) -> bytes | None:
        """获取指定页面的原始图像数据"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_all_page_dimensions(self) -> List[Tuple[int, int]]:
        """
        获取漫画源中所有页面的尺寸列表。

        Returns:
            List[Tuple[int, int]]: 一个包含 (宽度, 高度) 元组的列表。
                                   如果某页无法分析，则可能包含 (0, 0) 或 None。
        """
        raise NotImplementedError

class FolderDataSource(DataSource):
    """处理文件夹作为漫画源"""

    def _get_image_files(self) -> List[str]:
        """辅助方法：获取并排序文件夹内的图片文件"""
        image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".webp")
        image_files = [
            os.path.join(self.path, item)
            for item in os.listdir(self.path)
            if os.path.isfile(os.path.join(self.path, item)) and item.lower().endswith(image_extensions)
        ]
        image_files.sort(key=_natural_sort_key)
        return image_files

    def get_properties(self) -> Dict[str, Any]:
        log.debug(f"正在从文件夹处理属性: {self.path}")
        try:
            image_files = self._get_image_files()
            latest_mtime = 0.0
            
            if image_files:
                # 只获取最新的修改时间，不再计算每个文件的尺寸
                try:
                    latest_mtime = max(os.path.getmtime(p) for p in image_files)
                except Exception:
                    # 如果获取文件时间失败，则回退到目录时间
                    latest_mtime = os.path.getmtime(self.path)
            else:
                log.warning(f"文件夹中未找到图片: {self.path}")
                latest_mtime = os.path.getmtime(self.path)

            props = {
                'file_size': 0, # 文件夹大小计算成本高，此处简化
                'last_modified': latest_mtime,
                'total_pages': len(image_files),
                'pages': image_files,
                'file_type': 'folder'
            }
            log.info(f"[数据源-文件夹] '{self.path}' 的属性: last_modified={props['last_modified']}")
            return props
        except Exception as e:
            log.error(f"处理文件夹数据源时出错 {self.path}: {e}")
            return None
    
    def get_page_image_data(self, page_index: int) -> bytes | None:
        try:
            image_files = self._get_image_files()
            if 0 <= page_index < len(image_files):
                image_path = image_files[page_index]
                with open(image_path, 'rb') as f:
                    return f.read()
            else:
                log.warning(f"页面索引越界: {page_index}, 总页数: {len(image_files)}")
                return None
        except Exception as e:
            log.error(f"从文件夹读取页面图像失败 {self.path} - page {page_index}: {e}")
            return None

    def get_all_page_dimensions(self) -> List[Tuple[int, int]]:
        dimensions = []
        try:
            image_files = self._get_image_files()
            for image_path in image_files:
                with open(image_path, 'rb') as f:
                    image_data = f.read()
                dim = _get_image_dimensions_fast(image_data)
                dimensions.append(dim if dim else (0, 0))
            return dimensions
        except Exception as e:
            log.error(f"从文件夹获取所有页面尺寸失败 {self.path}: {e}")
            # 根据错误策略，可以返回空列表或部分结果
            return dimensions


class ZipDataSource(DataSource):
    """处理ZIP文件作为漫画源"""

    def _get_image_files(self) -> List[str]:
        """辅助方法：获取并排序ZIP内的图片文件"""
        with ZipFile(self.path, "r") as zip_file:
            image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".webp")
            image_files = [
                f.filename for f in zip_file.infolist()
                if not f.is_dir() and f.filename.lower().endswith(image_extensions)
            ]
            image_files.sort(key=_natural_sort_key)
            return image_files

    def get_properties(self) -> Dict[str, Any]:
        log.debug(f"正在从ZIP文件处理属性: {self.path}")
        try:
            with ZipFile(self.path, "r") as zip_file:
                image_files = self._get_image_files()
                if not image_files:
                    log.warning(f"ZIP文件中未找到图片: {self.path}")
                    return None

            props = {
                'file_size': os.path.getsize(self.path),
                'last_modified': os.path.getmtime(self.path),
                'total_pages': len(image_files),
                'pages': image_files,
                'file_type': 'zip'
            }
            log.info(f"[数据源-ZIP] '{self.path}' 的属性: last_modified={props['last_modified']}")
            return props
        except Exception as e:
            log.error(f"处理ZIP数据源时出错 {self.path}: {e}")
            return None

    def get_page_image_data(self, page_index: int) -> bytes | None:
        try:
            with ZipFile(self.path, "r") as zip_file:
                image_files = self._get_image_files()
                if 0 <= page_index < len(image_files):
                    file_name = image_files[page_index]
                    return zip_file.read(file_name)
                else:
                    log.warning(f"页面索引越界: {page_index}, 总页数: {len(image_files)}")
                    return None
        except Exception as e:
            log.error(f"从ZIP读取页面图像失败 {self.path} - page {page_index}: {e}")
            return None

    def get_all_page_dimensions(self) -> List[Tuple[int, int]]:
        dimensions = []
        try:
            with ZipFile(self.path, "r") as zip_file:
                image_files = self._get_image_files()
                for file_name in image_files:
                    image_data = zip_file.read(file_name)
                    dim = _get_image_dimensions_fast(image_data)
                    dimensions.append(dim if dim else (0, 0))
            return dimensions
        except Exception as e:
            log.error(f"从ZIP获取所有页面尺寸失败 {self.path}: {e}")
            return dimensions


class DataSourceFactory:
    """数据源工厂，根据路径返回合适的DataSource实例"""

    _strategies: Dict[str, Type[DataSource]] = {
        'folder': FolderDataSource,
        'zip': ZipDataSource
    }

    @staticmethod
    def create(path: str) -> DataSource:
        """
        根据文件路径创建并返回一个具体的数据源实例。

        Args:
            path (str): 漫画文件或文件夹的路径。

        Returns:
            DataSource: 一个具体的DataSource实例，如果类型不支持则返回None。
        """
        if not os.path.exists(path):
            log.error(f"路径不存在，无法创建数据源: {path}")
            return None

        if os.path.isdir(path):
            return DataSourceFactory._strategies['folder'](path)
        
        file_ext = os.path.splitext(path)[1].lower()
        if file_ext == '.zip':
            return DataSourceFactory._strategies['zip'](path)
            
        log.warning(f"不支持的数据源类型: {path}")
        return None