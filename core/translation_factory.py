"""
翻译工厂 - 核心翻译服务组件

实现全局单例的翻译工厂，提供统一的翻译接口。
集成现有的翻译队列管理器和防重复翻译逻辑。
"""

import threading
import time
from typing import Optional, Dict, Any, Tuple
from enum import Enum

from core.cache_key_generator import get_cache_key_generator
from core.realtime_translator import get_realtime_translator
from core.manga_model import MangaLoader
from core.persistent_translation_cache import get_persistent_translation_cache
from core.config import config
from utils import manga_logger as log


class PageStatus(Enum):
    """页面翻译状态枚举"""
    UNKNOWN = "unknown"          # 未知状态
    QUEUED = "queued"           # 已排队
    TRANSLATING = "translating"  # 翻译中
    TRANSLATED = "translated"    # 已翻译
    FAILED = "failed"           # 翻译失败





class TranslationFactory:
    """翻译工厂 - 全局单例服务"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True

        # 使用现有的持久化翻译缓存
        self.persistent_cache = get_persistent_translation_cache()
        self.key_generator = get_cache_key_generator()

        # 页面状态跟踪器
        self.page_status: Dict[str, PageStatus] = {}
        self.status_lock = threading.RLock()

        # 翻译器和漫画加载器
        self.translator = get_realtime_translator()
        self.manga_loader = MangaLoader()

        # 初始化翻译器配置
        self._init_translator_config()

        log.info("翻译工厂初始化完成 - 全局单例服务")
    
    def _init_translator_config(self):
        """初始化翻译器配置"""
        try:
            translator_type = config.translator_type.value

            # 根据翻译器类型设置参数
            if translator_type == "智谱":
                success = self.translator.set_translator_config(
                    translator_type=translator_type,
                    api_key=config.zhipu_api_key.value,
                    model=config.zhipu_model.value
                )
            elif translator_type == "Google":
                success = self.translator.set_translator_config(
                    translator_type=translator_type,
                    api_key=config.google_api_key.value
                )
            else:
                # 默认使用Google翻译器
                success = self.translator.set_translator_config(translator_type="Google")

            if success:
                log.info(f"翻译工厂: 翻译器配置成功 - {translator_type}")
            else:
                log.warning(f"翻译工厂: 翻译器配置失败 - {translator_type}")

        except Exception as e:
            log.error(f"翻译工厂: 翻译器配置异常: {e}")
    
    def get_translated_page(self, manga_path: str, page_index: int, translator_id: str) -> Optional[bytes]:
        """
        获取翻译页面 - 唯一对外接口
        
        Args:
            manga_path: 漫画路径
            page_index: 页面索引
            translator_id: 翻译引擎ID
            
        Returns:
            翻译后的图像数据（WebP格式）或None
        """
        try:
            status_key = self.key_generator.generate_translation_key(manga_path, page_index, translator_id)
            
            # 1. 检查持久化缓存
            cached_data = self.persistent_cache.get_cached_translation(manga_path, page_index, "zh", translator_id)
            if cached_data is not None:
                with self.status_lock:
                    self.page_status[status_key] = PageStatus.TRANSLATED
                return cached_data
            
            # 2. 检查当前状态
            with self.status_lock:
                current_status = self.page_status.get(status_key, PageStatus.UNKNOWN)
            
            if current_status == PageStatus.TRANSLATING:
                log.info(f"翻译工厂: 页面正在翻译中，等待完成 {manga_path}:{page_index}")
                return self._wait_for_translation(manga_path, page_index, translator_id)
            elif current_status == PageStatus.QUEUED:
                log.info(f"翻译工厂: 页面已在队列中，等待完成 {manga_path}:{page_index}")
                return self._wait_for_translation(manga_path, page_index, translator_id)
            elif current_status == PageStatus.FAILED:
                log.info(f"翻译工厂: 页面翻译失败，重新翻译 {manga_path}:{page_index}")
                # 重置状态
                with self.status_lock:
                    if status_key in self.page_status:
                        del self.page_status[status_key]

            # 3. 启动翻译并等待完成
            if self._start_translation(manga_path, page_index, translator_id):
                with self.status_lock:
                    self.page_status[status_key] = PageStatus.QUEUED
                log.info(f"翻译工厂: 已添加到翻译队列，等待完成 {manga_path}:{page_index}")
                return self._wait_for_translation(manga_path, page_index, translator_id)
            else:
                with self.status_lock:
                    self.page_status[status_key] = PageStatus.FAILED
                log.error(f"翻译工厂: 添加到翻译队列失败 {manga_path}:{page_index}")
                return None
            
        except Exception as e:
            log.error(f"翻译工厂: 获取翻译页面失败: {e}")
            return None
    
    def _wait_for_translation(self, manga_path: str, page_index: int, translator_id: str, timeout: int = 60) -> Optional[bytes]:
        """等待翻译完成"""
        status_key = self.key_generator.generate_translation_key(manga_path, page_index, translator_id)
        start_time = time.time()

        log.info(f"翻译工厂: 等待翻译完成 {manga_path}:{page_index} (超时: {timeout}秒)")

        while time.time() - start_time < timeout:
            # 检查是否已完成
            with self.status_lock:
                current_status = self.page_status.get(status_key, PageStatus.UNKNOWN)

            if current_status == PageStatus.TRANSLATED:
                # 翻译完成，从缓存获取结果
                cached_data = self.persistent_cache.get_cached_translation(manga_path, page_index, "zh", translator_id)
                if cached_data is not None:
                    log.info(f"翻译工厂: 翻译等待完成 {manga_path}:{page_index}")
                    return cached_data
                else:
                    log.warning(f"翻译工厂: 翻译完成但缓存为空 {manga_path}:{page_index}")
                    return None
            elif current_status == PageStatus.FAILED:
                log.warning(f"翻译工厂: 翻译失败 {manga_path}:{page_index}")
                return None

            # 等待一小段时间再检查
            time.sleep(0.5)

        # 超时
        log.warning(f"翻译工厂: 翻译等待超时 {manga_path}:{page_index}")
        return None

    def _start_translation(self, manga_path: str, page_index: int, translator_id: str) -> bool:
        """启动翻译任务"""
        try:
            if not self.translator.is_ready():
                log.error("翻译工厂: 翻译器未准备就绪")
                return False

            # 在后台线程中执行翻译
            def translate_task():
                self._execute_translation(manga_path, page_index, translator_id)

            thread = threading.Thread(target=translate_task, daemon=True)
            thread.start()

            return True

        except Exception as e:
            log.error(f"启动翻译任务失败: {e}")
            return False

    def _execute_translation(self, manga_path: str, page_index: int, translator_id: str):
        """执行翻译任务"""
        status_key = self.key_generator.generate_translation_key(manga_path, page_index, translator_id)

        try:
            # 更新状态为翻译中
            with self.status_lock:
                self.page_status[status_key] = PageStatus.TRANSLATING

            log.info(f"翻译工厂: 开始翻译 {manga_path}:{page_index}")

            # 加载漫画和图像
            manga = self.manga_loader.load_manga(manga_path)
            if not manga:
                raise Exception(f"无法加载漫画: {manga_path}")

            image = self.manga_loader.get_page_image(manga, page_index)
            if image is None:
                raise Exception(f"无法获取页面图像: {page_index}")

            # 执行翻译
            translation_result = self.translator.translate_image_with_cache_data(
                image=image,
                target_language="zh",
                file_path_for_cache=manga_path,
                page_num_for_cache=page_index
            )

            if translation_result and translation_result.get("translated_image") is not None:
                translated_image = translation_result["translated_image"]

                # 保存到持久化WebP缓存
                if self.persistent_cache.save_translated_image(manga_path, page_index, translated_image, "zh", translator_id):
                    # 更新状态为已翻译
                    with self.status_lock:
                        self.page_status[status_key] = PageStatus.TRANSLATED
                    log.info(f"翻译工厂: 翻译完成并保存 {manga_path}:{page_index}")
                else:
                    raise Exception("保存翻译结果失败")
            else:
                raise Exception("翻译返回空结果")

        except Exception as e:
            # 更新状态为失败
            with self.status_lock:
                self.page_status[status_key] = PageStatus.FAILED
            log.error(f"翻译工厂: 翻译失败 {manga_path}:{page_index} - {e}")
    
    def get_page_status(self, manga_path: str, page_index: int, translator_id: str) -> PageStatus:
        """获取页面翻译状态"""
        status_key = self.key_generator.generate_translation_key(manga_path, page_index, translator_id)
        
        with self.status_lock:
            return self.page_status.get(status_key, PageStatus.UNKNOWN)
    
    def is_service_running(self) -> bool:
        """检查翻译服务是否运行"""
        return self.translator is not None and self.translator.is_ready()




# 全局实例获取函数
_translation_factory = None

def get_translation_factory() -> TranslationFactory:
    """获取全局翻译工厂实例"""
    global _translation_factory
    if _translation_factory is None:
        _translation_factory = TranslationFactory()
    return _translation_factory
