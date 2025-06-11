#!/usr/bin/env python3
"""
统一实时翻译服务

这是实时翻译功能的统一服务层，负责：
1. 翻译服务的生命周期管理
2. 缓存策略协调
3. 翻译请求处理
4. 状态监控和报告

遵循严格的分层架构：
- 对外提供统一的服务接口
- 内部协调各个核心组件
- 不包含具体的实现细节
"""

import threading
from typing import Dict, Any, Optional, List
from pathlib import Path

from core.realtime_translator import RealtimeTranslator
from core.cache_coordinator import get_cache_coordinator
from core.config import config
from utils import manga_logger as log


class TranslationStatusManager:
    """翻译状态管理器"""
    
    def __init__(self):
        self._status = {
            "is_running": False,
            "current_manga": None,
            "current_page": 0,
            "reading_direction": "ltr",
            "service_type": "unified_realtime_translation"
        }
        self._lock = threading.RLock()
    
    def update_status(self, **kwargs):
        """更新状态"""
        with self._lock:
            self._status.update(kwargs)
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        with self._lock:
            return self._status.copy()


class RealtimeTranslationService:
    """统一实时翻译服务"""
    
    def __init__(self):
        # 核心组件
        self.translator = RealtimeTranslator()
        self.cache_coordinator = get_cache_coordinator()
        self.status_manager = TranslationStatusManager()
        
        # 服务状态
        self._lock = threading.RLock()
        
        log.info("统一实时翻译服务初始化完成")
    
    # ==================== 服务生命周期管理 ====================
    
    def start_service(self, translator_type: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        启动翻译服务
        
        Args:
            translator_type: 翻译器类型
            **kwargs: 翻译器配置参数
        
        Returns:
            启动结果
        """
        with self._lock:
            try:
                # 检查服务状态
                if self.status_manager.get_status()["is_running"]:
                    return {
                        "success": True,
                        "message": "翻译服务已在运行",
                        "was_running": True
                    }
                
                # 配置翻译器
                translator_type = translator_type or config.translator_type.value
                translator_config = self._prepare_translator_config(translator_type, **kwargs)
                
                log.info(f"统一翻译服务: 配置翻译器 {translator_type}")
                self.translator.set_translator_config(
                    translator_type=translator_type,
                    **translator_config
                )
                
                # 验证翻译器状态
                if not self.translator.image_translator:
                    raise Exception("翻译器配置失败，无法创建图片翻译器实例")
                
                if not self.translator.image_translator.is_ready():
                    log.warning("翻译器未完全准备就绪，但将尝试启动服务")
                
                # 启动翻译服务
                self.translator.start_translation_service()
                
                # 更新状态
                self.status_manager.update_status(
                    is_running=True,
                    translator_type=translator_type
                )
                
                log.info(f"统一翻译服务启动成功: {translator_type}")
                return {
                    "success": True,
                    "message": f"统一翻译服务已启动，使用翻译器: {translator_type}",
                    "translator_type": translator_type
                }
                
            except Exception as e:
                log.error(f"启动统一翻译服务失败: {e}")
                self.status_manager.update_status(is_running=False)
                return {
                    "success": False,
                    "message": f"启动统一翻译服务失败: {str(e)}"
                }
    
    def stop_service(self) -> Dict[str, Any]:
        """停止翻译服务"""
        with self._lock:
            try:
                # 停止翻译器
                self.translator.stop_translation_service()
                
                # 更新状态
                self.status_manager.update_status(
                    is_running=False,
                    current_manga=None,
                    current_page=0
                )
                
                log.info("统一翻译服务已停止")
                return {
                    "success": True,
                    "message": "统一翻译服务已停止"
                }
                
            except Exception as e:
                log.error(f"停止统一翻译服务失败: {e}")
                return {
                    "success": False,
                    "message": f"停止统一翻译服务失败: {str(e)}"
                }
    
    def get_service_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        try:
            # 获取基础状态
            base_status = self.status_manager.get_status()
            
            # 获取翻译器状态
            if base_status["is_running"]:
                translator_status = self.translator.get_translation_status()
                base_status.update(translator_status)
            
            # 获取缓存统计
            cache_stats = self.cache_coordinator.get_cache_statistics()
            base_status["cache_statistics"] = cache_stats
            
            return base_status
            
        except Exception as e:
            log.error(f"获取服务状态失败: {e}")
            return {
                "is_running": False,
                "error": str(e)
            }
    
    # ==================== 翻译管理 ====================
    
    def set_current_manga(self, manga_path: str, current_page: int) -> Dict[str, Any]:
        """设置当前漫画"""
        try:
            # 验证文件路径
            if not Path(manga_path).exists():
                return {
                    "success": False,
                    "message": f"漫画文件不存在: {manga_path}"
                }
            
            # 设置翻译器当前漫画
            success = self.translator.set_current_manga(manga_path, current_page)
            
            if success:
                # 更新状态
                self.status_manager.update_status(
                    current_manga=manga_path,
                    current_page=current_page
                )
                
                # 自动请求翻译附近页面
                self._auto_request_nearby_pages(manga_path, current_page)
                
                return {
                    "success": True,
                    "message": f"已设置当前漫画: {Path(manga_path).name}, 页面: {current_page + 1}"
                }
            else:
                return {
                    "success": False,
                    "message": "设置当前漫画失败"
                }
                
        except Exception as e:
            log.error(f"设置当前漫画失败: {e}")
            return {
                "success": False,
                "message": f"设置当前漫画失败: {str(e)}"
            }
    
    def request_translation(self, manga_path: str, page_indices: List[int], priority: int = 10) -> Dict[str, Any]:
        """请求翻译"""
        try:
            # 检查服务状态
            if not self.status_manager.get_status()["is_running"]:
                return {
                    "success": False,
                    "message": "翻译服务未启动"
                }
            
            # 验证文件路径
            if not Path(manga_path).exists():
                return {
                    "success": False,
                    "message": f"漫画文件不存在: {manga_path}"
                }
            
            # 批量请求翻译
            requested_pages = []
            for page_index in page_indices:
                task_id = self.translator.request_translation(
                    manga_path=manga_path,
                    page_index=page_index,
                    priority=priority
                )
                if task_id:
                    requested_pages.append(page_index)
            
            log.info(f"统一翻译服务: 已请求翻译 {len(requested_pages)}/{len(page_indices)} 个页面")
            return {
                "success": True,
                "message": f"已请求翻译 {len(requested_pages)} 个页面",
                "requested_pages": requested_pages,
                "total_requested": len(page_indices)
            }
            
        except Exception as e:
            log.error(f"请求翻译失败: {e}")
            return {
                "success": False,
                "message": f"请求翻译失败: {str(e)}"
            }
    
    # ==================== 缓存管理 ====================
    
    def get_translated_page(self, manga_path: str, page_index: int, target_language: str = "zh") -> Dict[str, Any]:
        """获取翻译后的页面（统一接口）"""
        try:
            # 首先检查页面是否存在
            from core.manga_model import MangaLoader
            manga = MangaLoader.load_manga(manga_path)
            if manga and page_index >= manga.total_pages:
                return {
                    "is_translated": False,
                    "image_data": None,
                    "manga_path": manga_path,
                    "page_index": page_index,
                    "source": "none",
                    "cache_source": "none",
                    "error": f"页面索引超出范围: {page_index} >= {manga.total_pages}"
                }

            # 通过缓存协调器获取翻译页面和缓存来源
            image_data = self.cache_coordinator.get_translated_page(manga_path, page_index, target_language)
            has_cache, cache_source = self.cache_coordinator.has_cached_translation(manga_path, page_index, target_language)

            # 验证图像数据有效性
            is_valid_data = (image_data is not None and
                           isinstance(image_data, str) and
                           len(image_data) > 0)

            if is_valid_data:
                return {
                    "is_translated": True,
                    "image_data": image_data,
                    "manga_path": manga_path,
                    "page_index": page_index,
                    "source": "cache_coordinator",
                    "cache_source": cache_source
                }
            else:
                return {
                    "is_translated": False,
                    "image_data": None,
                    "manga_path": manga_path,
                    "page_index": page_index,
                    "source": "none",
                    "cache_source": cache_source if has_cache else "none"
                }

        except Exception as e:
            log.error(f"统一翻译服务: 获取翻译页面失败 {manga_path}:{page_index}: {e}")
            return {
                "is_translated": False,
                "image_data": None,
                "manga_path": manga_path,
                "page_index": page_index,
                "source": "error",
                "cache_source": "unknown",
                "error": str(e)
            }
    
    def check_cache_status(self, manga_path: str, page_index: int, target_language: str = "zh") -> Dict[str, Any]:
        """检查缓存状态"""
        try:
            has_cache, cache_source = self.cache_coordinator.has_cached_translation(manga_path, page_index, target_language)
            
            return {
                "success": True,
                "manga_path": manga_path,
                "page_index": page_index,
                "has_cache": has_cache,
                "cache_source": cache_source
            }
            
        except Exception as e:
            log.error(f"检查缓存状态失败: {e}")
            return {
                "success": False,
                "manga_path": manga_path,
                "page_index": page_index,
                "has_cache": False,
                "error": str(e)
            }
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            return self.cache_coordinator.get_cache_statistics()
        except Exception as e:
            log.error(f"获取缓存统计失败: {e}")
            return {"error": str(e)}
    
    def clear_cache(self, manga_path: Optional[str] = None) -> Dict[str, Any]:
        """清空缓存"""
        try:
            cleared_counts = self.cache_coordinator.clear_cache(manga_path)
            
            # 同时清空翻译器内存缓存
            if manga_path:
                keys_to_remove = [k for k in self.translator.completed_translations.keys() 
                                if k.startswith(f"{manga_path}:")]
                for key in keys_to_remove:
                    del self.translator.completed_translations[key]
                cleared_counts["translator_memory"] = len(keys_to_remove)
            else:
                cleared_counts["translator_memory"] = len(self.translator.completed_translations)
                self.translator.completed_translations.clear()
            
            return {
                "success": True,
                "message": "缓存清理完成",
                "cleared_counts": cleared_counts
            }
            
        except Exception as e:
            log.error(f"清空缓存失败: {e}")
            return {
                "success": False,
                "message": f"清空缓存失败: {str(e)}"
            }
    
    # ==================== 私有方法 ====================
    
    def _prepare_translator_config(self, translator_type: str, **kwargs) -> Dict[str, Any]:
        """准备翻译器配置"""
        translator_config = {}
        
        if translator_type == "智谱":
            translator_config["api_key"] = kwargs.get("api_key") or config.zhipu_api_key.value
            translator_config["model"] = kwargs.get("model") or config.zhipu_model.value
        elif translator_type == "Google":
            translator_config["api_key"] = kwargs.get("api_key") or config.google_api_key.value
        
        return translator_config
    
    def _auto_request_nearby_pages(self, manga_path: str, current_page: int, range_size: int = 5):
        """自动请求翻译附近页面"""
        try:
            from core.manga_model import MangaLoader
            
            # 加载漫画获取总页数
            manga = MangaLoader.load_manga(manga_path)
            if not manga:
                log.warning(f"无法加载漫画: {manga_path}")
                return
            
            # 计算要翻译的页面范围
            start_page = max(0, current_page - range_size)
            end_page = min(manga.total_pages - 1, current_page + range_size)
            
            # 按距离当前页面的远近设置优先级
            page_indices = []
            for page_index in range(start_page, end_page + 1):
                distance = abs(page_index - current_page)
                page_indices.append(page_index)
            
            # 请求翻译
            if page_indices:
                self.request_translation(manga_path, page_indices, priority=5)
                log.info(f"统一翻译服务: 自动请求翻译页面范围 {start_page}-{end_page}, 当前页面: {current_page}")
            
        except Exception as e:
            log.error(f"自动请求翻译附近页面失败: {e}")


# 全局实例
_translation_service_instance: Optional[RealtimeTranslationService] = None


def get_realtime_translation_service() -> RealtimeTranslationService:
    """获取统一实时翻译服务全局实例"""
    global _translation_service_instance
    if _translation_service_instance is None:
        _translation_service_instance = RealtimeTranslationService()
    return _translation_service_instance
