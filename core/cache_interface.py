# core/cache_interface.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class CacheInterface(ABC):
    """
    统一缓存接口定义
    """

    @abstractmethod
    def generate_key(self, *args, **kwargs) -> str:
        """
        根据特定缓存类型所需的信息生成唯一的键。
        """
        pass

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        根据键获取缓存数据。
        如果键不存在或缓存无效，则返回 None。
        """
        pass

    @abstractmethod
    def set(self, key: str, data: Any, **kwargs) -> None:
        """
        根据键设置缓存数据。
        kwargs 可以用于传递特定缓存类型需要的额外参数，例如有效期等。
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """
        删除指定键的缓存。
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """
        清空所有缓存。
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        关闭缓存资源，例如数据库连接。
        """
        pass