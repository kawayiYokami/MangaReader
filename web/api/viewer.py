"""
漫画查看器 API 路由层

基于翻译工厂架构的新查看器API，提供：
- 会话管理
- 页面获取
- 预载策略
"""

from fastapi import APIRouter, HTTPException, Header, Request, Response
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import uuid
import time
import json
import io

from web.manga_viewer_manager import get_viewer_manager, cleanup_session, get_active_sessions, PageLoadStrategy, DisplayMode
from core.config import config
import logging

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

class SessionInfoResponse(BaseModel):
    """会话信息响应模型"""
    session_id: str
    current_manga_path: Optional[str]
    current_page: int
    total_pages: int
    display_mode: str
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
    return {
        "status": "healthy",
        "module": "viewer",
        "active_sessions": len(get_active_sessions())
    }

@router.post("/session/create")
async def create_session():
    """创建新的查看器会话"""
    try:
        session_id = str(uuid.uuid4())
        manager = get_viewer_manager(session_id)
        
        logging.info(f"创建新查看器会话: {session_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "message": "会话创建成功"
        }
    except Exception as e:
        logging.error(f"创建会话失败: {e}", exc_info=True)
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
        logging.error(f"删除会话失败: {e}", exc_info=True)
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
        logging.error(f"获取会话列表失败: {e}", exc_info=True)
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
        
        result = await manager.set_current_manga(request.manga_path, request.page)
        
        if result["success"]:
            result["session_id"] = session_id
            logging.info(f"会话 {session_id}: 设置漫画成功 {request.manga_path}")
        else:
            logging.warning(f"会话 {session_id}: 设置漫画失败 {result['message']}")
        
        return result
        
    except Exception as e:
        logging.error(f"设置当前漫画失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/page/get")
async def get_page_metadata(
    request_data: GetPageRequest,
    x_session_id: Optional[str] = Header(None)
):
    """获取页面元数据，返回图片URL而不是数据"""
    try:
        session_id = get_session_id_from_header(x_session_id)
        manager = get_viewer_manager(session_id)

        if not manager.current_manga_path:
            return {"success": False, "message": "未设置当前漫画"}

        # 更新状态
        manager.current_page = max(0, min(request_data.page, manager.total_pages - 1))
        display_mode_enum = DisplayMode.SINGLE if request_data.display_mode == "single" else DisplayMode.DOUBLE
        
        # 计算需要加载的页面
        current_pages, _ = PageLoadStrategy.get_pages_to_load(
            manager.current_page, display_mode_enum, manager.total_pages
        )

        # 构建图片 URL
        image_urls = [
            {
                "pageIndex": page_idx,
                # 在URL中包含 session_id 以便后续请求能找到正确的会话
                "url": f"/api/viewer/image/{page_idx}?session_id={session_id}"
            }
            for page_idx in current_pages
        ]

        return {
            "success": True,
            "images": image_urls,
            "current_page": manager.current_page,
        }

    except Exception as e:
        logging.error(f"获取页面元数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/image/{page_index}")
async def get_image_data(
    page_index: int,
    session_id: str
):
    """获取单个页面的原始图像字节流"""
    try:
        manager = get_viewer_manager(session_id)
        if not manager:
            raise HTTPException(status_code=404, detail="会话不存在")

        image_data = await manager.get_page_image_bytes(page_index)
        
        if image_data is None:
            raise HTTPException(status_code=404, detail=f"找不到页面 {page_index} 的图像")
            
        image_bytes, mime_type = image_data
        
        return Response(content=image_bytes, media_type=mime_type)

    except Exception as e:
        logging.error(f"获取图像数据失败 (页面 {page_index}): {e}", exc_info=True)
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
        logging.error(f"获取会话信息失败: {e}", exc_info=True)
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
        
        if not page_indices:
            return {"success": False, "message": "未指定要预载的页面"}
        
        # 异步预载
        manager._preload_pages_async(page_indices)
        
        return {
            "success": True,
            "message": f"已开始预载 {len(page_indices)} 个页面",
            "page_indices": page_indices
        }
        
    except Exception as e:
        logging.error(f"预载页面失败: {e}", exc_info=True)
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
        logging.error(f"获取缓存统计失败: {e}", exc_info=True)
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
        logging.error(f"清空缓存失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
