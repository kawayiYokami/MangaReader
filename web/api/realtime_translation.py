"""
实时翻译功能 API

提供实时翻译服务的RESTful接口。
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import os
import base64
import io
import cv2
import numpy as np

from core.realtime_translator import get_realtime_translator, TranslationStatus
from core.config import config
from utils import manga_logger as log

router = APIRouter()

# 数据模型
class StartTranslationServiceRequest(BaseModel):
    """启动翻译服务请求模型"""
    translator_type: str = "智谱"
    api_key: Optional[str] = None
    model: Optional[str] = None

class SetCurrentMangaRequest(BaseModel):
    """设置当前漫画请求模型"""
    manga_path: str
    current_page: int = 0

class RequestTranslationRequest(BaseModel):
    """请求翻译页面模型"""
    manga_path: str
    page_indices: List[int]  # 支持批量请求
    priority: int = 10

class TranslationStatusResponse(BaseModel):
    """翻译状态响应模型"""
    is_running: bool
    current_manga: Optional[str]
    current_page: int
    queue_size: int
    completed_count: int
    current_task: Optional[Dict[str, Any]]

class TranslatedPageResponse(BaseModel):
    """翻译页面响应模型"""
    manga_path: str
    page_index: int
    is_translated: bool
    image_data: Optional[str] = None  # base64编码的图像数据
    error_message: Optional[str] = None

@router.get("/health")
async def realtime_translation_health():
    """实时翻译模块健康检查"""
    return {"status": "healthy", "module": "realtime_translation"}

@router.post("/start-service")
async def start_translation_service(request: StartTranslationServiceRequest):
    """启动实时翻译服务"""
    try:
        translator = get_realtime_translator()
        
        # 配置翻译器
        translator_kwargs = {}
        if request.api_key:
            translator_kwargs["api_key"] = request.api_key
        if request.model:
            translator_kwargs["model"] = request.model
        
        translator.set_translator_config(
            translator_type=request.translator_type,
            **translator_kwargs
        )
        
        # 启动服务
        translator.start_translation_service()
        
        return {
            "success": True,
            "message": f"实时翻译服务已启动，使用翻译器: {request.translator_type}"
        }
        
    except Exception as e:
        log.error(f"启动实时翻译服务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop-service")
async def stop_translation_service():
    """停止实时翻译服务"""
    try:
        translator = get_realtime_translator()
        translator.stop_translation_service()
        
        return {
            "success": True,
            "message": "实时翻译服务已停止"
        }
        
    except Exception as e:
        log.error(f"停止实时翻译服务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/set-current-manga")
async def set_current_manga(request: SetCurrentMangaRequest):
    """设置当前漫画和页面"""
    try:
        # 验证文件路径
        if not os.path.exists(request.manga_path):
            raise HTTPException(status_code=404, detail=f"漫画文件不存在: {request.manga_path}")
        
        translator = get_realtime_translator()
        translator.set_current_manga(request.manga_path, request.current_page)
        
        # 自动请求翻译当前页面及附近页面
        await _auto_request_nearby_pages(request.manga_path, request.current_page)
        
        return {
            "success": True,
            "message": f"已设置当前漫画: {os.path.basename(request.manga_path)}, 页面: {request.current_page}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"设置当前漫画失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/request-translation")
async def request_translation(request: RequestTranslationRequest):
    """请求翻译指定页面"""
    try:
        translator = get_realtime_translator()
        
        if not translator.is_running:
            raise HTTPException(status_code=400, detail="翻译服务未启动")
        
        # 验证文件路径
        if not os.path.exists(request.manga_path):
            raise HTTPException(status_code=404, detail=f"漫画文件不存在: {request.manga_path}")
        
        # 批量请求翻译
        for page_index in request.page_indices:
            translator.request_translation(
                manga_path=request.manga_path,
                page_index=page_index,
                priority=request.priority
            )
        
        return {
            "success": True,
            "message": f"已请求翻译 {len(request.page_indices)} 个页面",
            "requested_pages": request.page_indices
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"请求翻译失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_translation_status() -> TranslationStatusResponse:
    """获取翻译状态"""
    try:
        translator = get_realtime_translator()
        status = translator.get_translation_status()
        
        return TranslationStatusResponse(
            is_running=status["is_running"],
            current_manga=status["current_manga"],
            current_page=status["current_page"],
            queue_size=status["queue_size"],
            completed_count=status["completed_count"],
            current_task=status["current_task"]
        )
        
    except Exception as e:
        log.error(f"获取翻译状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/translated-page/{manga_path:path}/{page_index}")
async def get_translated_page(manga_path: str, page_index: int) -> TranslatedPageResponse:
    """获取翻译后的页面"""
    try:
        translator = get_realtime_translator()
        
        # 检查是否已翻译
        is_translated = translator.is_page_translated(manga_path, page_index)
        
        response = TranslatedPageResponse(
            manga_path=manga_path,
            page_index=page_index,
            is_translated=is_translated
        )
        
        if is_translated:
            # 获取翻译后的图像
            translated_image = translator.get_translated_page(manga_path, page_index)
            
            if translated_image is not None:
                # 将图像转换为base64编码
                image_data = _encode_image_to_base64(translated_image)
                response.image_data = image_data
            else:
                response.error_message = "翻译图像数据为空"
        
        return response
        
    except Exception as e:
        log.error(f"获取翻译页面失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/check-pages-translated/{manga_path:path}")
async def check_pages_translated(manga_path: str, page_indices: str):
    """批量检查页面是否已翻译"""
    try:
        # 解析页面索引
        try:
            page_list = [int(x.strip()) for x in page_indices.split(',') if x.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="页面索引格式错误")
        
        translator = get_realtime_translator()
        
        results = {}
        for page_index in page_list:
            results[str(page_index)] = translator.is_page_translated(manga_path, page_index)
        
        return {
            "success": True,
            "manga_path": manga_path,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"批量检查翻译状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auto-translate-current")
async def auto_translate_current():
    """自动翻译当前漫画的当前页面及附近页面"""
    try:
        translator = get_realtime_translator()
        status = translator.get_translation_status()
        
        if not status["is_running"]:
            raise HTTPException(status_code=400, detail="翻译服务未启动")
        
        if not status["current_manga"]:
            raise HTTPException(status_code=400, detail="未设置当前漫画")
        
        manga_path = status["current_manga"]
        current_page = status["current_page"]
        
        # 自动请求翻译附近页面
        await _auto_request_nearby_pages(manga_path, current_page)
        
        return {
            "success": True,
            "message": f"已自动请求翻译当前页面及附近页面",
            "manga_path": manga_path,
            "current_page": current_page
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"自动翻译失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 辅助函数
async def _auto_request_nearby_pages(manga_path: str, current_page: int, range_size: int = 5):
    """自动请求翻译附近页面"""
    try:
        from core.manga_model import MangaLoader
        
        # 加载漫画获取总页数
        manga = MangaLoader.load_manga(manga_path)
        if not manga:
            log.warning(f"无法加载漫画: {manga_path}")
            return
        
        translator = get_realtime_translator()
        
        # 计算要翻译的页面范围
        start_page = max(0, current_page - range_size)
        end_page = min(manga.total_pages - 1, current_page + range_size)
        
        # 按距离当前页面的远近设置优先级
        for page_index in range(start_page, end_page + 1):
            distance = abs(page_index - current_page)
            priority = distance  # 距离越近优先级越高（数字越小）
            
            translator.request_translation(
                manga_path=manga_path,
                page_index=page_index,
                priority=priority
            )
        
        log.info(f"自动请求翻译页面范围: {start_page}-{end_page}, 当前页面: {current_page}")
        
    except Exception as e:
        log.error(f"自动请求翻译附近页面失败: {e}")

def _encode_image_to_base64(image: np.ndarray) -> str:
    """将图像编码为base64字符串"""
    try:
        # 确保图像是RGB格式
        if len(image.shape) == 3 and image.shape[2] == 3:
            # 转换为BGR格式（OpenCV默认）
            image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        else:
            image_bgr = image
        
        # 编码为JPEG格式
        _, buffer = cv2.imencode('.jpg', image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
        
        # 转换为base64
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return f"data:image/jpeg;base64,{image_base64}"
        
    except Exception as e:
        log.error(f"图像编码失败: {e}")
        raise
