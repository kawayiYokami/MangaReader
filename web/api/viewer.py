"""
漫画查看器 API 路由层

基于翻译工厂架构的新查看器API，提供：
- 会话管理
- 页面获取
- 翻译状态管理
- 预载策略
"""

from fastapi import APIRouter, HTTPException, Header, Request
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import uuid

from web.manga_viewer_manager import get_viewer_manager, cleanup_session, get_active_sessions
from core.translation.translation_factory import get_translation_factory
from core.config import config
from utils import manga_logger as log

router = APIRouter()

# ==================== 数据模型 ====================

class SetMangaRequest(BaseModel):
    """设置漫画请求模型"""
    manga_path: str
    page: int = 0

class GetPageRequest(BaseModel):
    """获取页面请求模型"""
    page: int
    display_mode: str = "single"  # single, double
    translation_enabled: bool = False

class SessionInfoResponse(BaseModel):
    """会话信息响应模型"""
    session_id: str
    current_manga_path: Optional[str]
    current_page: int
    total_pages: int
    display_mode: str
    translation_enabled: bool
    cache_stats: Dict[str, Any]

# ==================== 辅助函数 ====================

def get_session_id_from_header(x_session_id: Optional[str] = Header(None)) -> str:
    """从请求头获取或生成会话ID"""
    if x_session_id:
        return x_session_id
    return str(uuid.uuid4())

# ==================== API 端点 ====================

@router.get("/health")
async def viewer_health():
    """查看器模块健康检查"""
    translation_factory = get_translation_factory()
    return {
        "status": "healthy",
        "module": "viewer",
        "translation_service_running": translation_factory.is_service_running(),
        "active_sessions": len(get_active_sessions())
    }

@router.post("/session/create")
async def create_session():
    """创建新的查看器会话"""
    try:
        session_id = str(uuid.uuid4())
        manager = get_viewer_manager(session_id)
        
        log.info(f"创建新查看器会话: {session_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "message": "会话创建成功"
        }
    except Exception as e:
        log.error(f"创建会话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """删除查看器会话"""
    try:
        cleanup_session(session_id)
        return {
            "success": True,
            "message": f"会话 {session_id} 已删除"
        }
    except Exception as e:
        log.error(f"删除会话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session/list")
async def list_sessions():
    """获取活跃会话列表"""
    try:
        sessions = get_active_sessions()
        return {
            "success": True,
            "sessions": sessions,
            "count": len(sessions)
        }
    except Exception as e:
        log.error(f"获取会话列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/manga/set")
async def set_current_manga(
    request: SetMangaRequest,
    x_session_id: Optional[str] = Header(None)
):
    """设置当前查看的漫画"""
    try:
        session_id = get_session_id_from_header(x_session_id)
        manager = get_viewer_manager(session_id)
        
        result = manager.set_current_manga(request.manga_path, request.page)
        
        if result["success"]:
            result["session_id"] = session_id
            log.info(f"会话 {session_id}: 设置漫画成功 {request.manga_path}")
        else:
            log.warning(f"会话 {session_id}: 设置漫画失败 {result['message']}")
        
        return result
        
    except Exception as e:
        log.error(f"设置当前漫画失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/page/get")
async def get_page_images(
    request: GetPageRequest,
    x_session_id: Optional[str] = Header(None)
):
    """获取页面图像"""
    try:
        session_id = get_session_id_from_header(x_session_id)
        manager = get_viewer_manager(session_id)
        
        result = manager.get_page_images(
            page=request.page,
            display_mode=request.display_mode,
            translation_enabled=request.translation_enabled
        )
        
        if result["success"]:
            result["session_id"] = session_id
            log.debug(f"会话 {session_id}: 获取页面图像成功 页面={request.page}")
        else:
            log.warning(f"会话 {session_id}: 获取页面图像失败 {result['message']}")
        
        return result
        
    except Exception as e:
        log.error(f"获取页面图像失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session/info")
async def get_session_info(x_session_id: Optional[str] = Header(None)):
    """获取会话信息"""
    try:
        session_id = get_session_id_from_header(x_session_id)
        manager = get_viewer_manager(session_id)
        
        info = manager.get_session_info()
        
        return {
            "success": True,
            "session_info": info
        }
        
    except Exception as e:
        log.error(f"获取会话信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/translation/toggle")
async def toggle_translation(
    request: Dict[str, Any],
    x_session_id: Optional[str] = Header(None)
):
    """切换翻译状态"""
    try:
        session_id = get_session_id_from_header(x_session_id)
        manager = get_viewer_manager(session_id)
        
        enabled = request.get("enabled", False)
        
        # 更新翻译状态
        manager.translation_enabled = enabled
        
        # 如果禁用翻译，清空翻译缓存
        if not enabled:
            with manager.cache_lock:
                manager.translated_cache.clear()
            log.info(f"会话 {session_id}: 翻译已禁用，清空翻译缓存")
        
        return {
            "success": True,
            "translation_enabled": enabled,
            "message": f"翻译状态已{'启用' if enabled else '禁用'}"
        }
        
    except Exception as e:
        log.error(f"切换翻译状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/translation/status")
async def get_translation_status(x_session_id: Optional[str] = Header(None)):
    """获取翻译服务状态"""
    try:
        session_id = get_session_id_from_header(x_session_id)
        manager = get_viewer_manager(session_id)
        translation_factory = get_translation_factory()
        
        return {
            "success": True,
            "service_running": translation_factory.is_service_running(),
            "session_translation_enabled": manager.translation_enabled,
            "current_translator": config.translator_type.value,
            "session_id": session_id
        }
        
    except Exception as e:
        log.error(f"获取翻译状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/preload")
async def preload_pages(
    request: Dict[str, Any],
    x_session_id: Optional[str] = Header(None)
):
    """手动预载页面"""
    try:
        session_id = get_session_id_from_header(x_session_id)
        manager = get_viewer_manager(session_id)
        
        page_indices = request.get("page_indices", [])
        use_translation = request.get("translation_enabled", False)
        
        if not page_indices:
            return {"success": False, "message": "未指定要预载的页面"}
        
        # 异步预载
        manager._preload_pages_async(page_indices, use_translation)
        
        return {
            "success": True,
            "message": f"已开始预载 {len(page_indices)} 个页面",
            "page_indices": page_indices
        }
        
    except Exception as e:
        log.error(f"预载页面失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cache/stats")
async def get_cache_stats(x_session_id: Optional[str] = Header(None)):
    """获取缓存统计信息"""
    try:
        session_id = get_session_id_from_header(x_session_id)
        manager = get_viewer_manager(session_id)
        
        with manager.cache_lock:
            stats = {
                "session_id": session_id,
                "original_cache_size": len(manager.original_cache),
                "translated_cache_size": len(manager.translated_cache),
                "loaded_pages": list(manager.loaded_pages),
                "preloaded_pages": list(manager.preloaded_pages),
                "current_manga": manager.current_manga_path,
                "current_page": manager.current_page
            }
        
        return {
            "success": True,
            "cache_stats": stats
        }
        
    except Exception as e:
        log.error(f"获取缓存统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cache/clear")
async def clear_cache(x_session_id: Optional[str] = Header(None)):
    """清空会话缓存"""
    try:
        session_id = get_session_id_from_header(x_session_id)
        manager = get_viewer_manager(session_id)
        
        manager._clear_caches()
        
        return {
            "success": True,
            "message": "会话缓存已清空"
        }
        
    except Exception as e:
        log.error(f"清空缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
