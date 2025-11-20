"""
漫画管理 API

提供漫画浏览、文件管理等功能的RESTful接口。
通过统一接口层与core模块交互。
"""

from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from typing import List, Optional
from pydantic import BaseModel
from math import ceil
import os
from pathlib import Path
from functools import wraps
import shutil
import tempfile
from datetime import datetime
from urllib.parse import unquote

# 导入统一接口层
from starlette.background import BackgroundTask

from src.backend.core.image.image_compressor import get_image_compressor
from src.backend.web.dependencies import get_interface
from src.backend.web.core_interface import (
    CoreInterface,
    CoreInterfaceError
)
import logging

# 权限控制函数
def is_local_request(request: Request) -> bool:
    """检查是否为本地访问"""
    client_ip = request.client.host
    local_ips = ['127.0.0.1', '::1', 'localhost']
    return client_ip in local_ips

def local_only(func):
    """装饰器：仅允许本地访问"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # 从参数中找到Request对象
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break

        if request and not is_local_request(request):
            raise HTTPException(status_code=403, detail="此功能仅限本地访问")

        return await func(*args, **kwargs)
    return wrapper

router = APIRouter()

# 数据模型
class MangaInfoResponse(BaseModel):
    """漫画信息响应模型"""
    file_path: str
    title: str
    tags: List[str]
    total_pages: int
    is_valid: bool
    last_modified: str
    file_type: str
    file_size: Optional[int] = None
    # 缓存信息
    dimension_variance: Optional[float] = None
    is_likely_manga: Optional[bool] = None
    page_dimensions: Optional[List[List[int]]] = None

class DirectoryRequest(BaseModel):
    """目录请求模型"""
    directory_path: str

class TagFilterRequest(BaseModel):
    """标签过滤请求模型"""
    tags: List[str]

class ScanRequest(BaseModel):
    """扫描请求模型"""
    force_rescan: bool = False

class AddMangaRequest(BaseModel):
    """添加漫画请求模型"""
    paths: List[str]

class ScanDirectoryRequest(BaseModel):
    """扫描目录请求模型"""
    directory_path: str

class SetCurrentMangaRequest(BaseModel):
    """设置当前漫画请求模型"""
    manga_path: str
    page: int = 0

class PaginatedMangaResponse(BaseModel):
    """分页漫画列表响应模型"""
    items: List[MangaInfoResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

# 依赖注入函数已从 api_server 导入

@router.get("/health")
async def manga_health():
    """漫画模块健康检查"""
    return {"status": "healthy", "module": "manga"}

@router.get("/directory")
async def get_current_directory(interface: CoreInterface = Depends(get_interface)):
    """获取当前漫画目录"""
    try:
        dir_info = await interface.get_current_directory()
        return {
            "current_directory": dir_info.path,
            "exists": dir_info.exists,
            "is_directory": dir_info.is_directory,
            "manga_count": dir_info.manga_count
        }
    except CoreInterfaceError as e:
        logging.error(f"获取当前目录失败: {e}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        logging.error(f"获取当前目录失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/directory")
@local_only
async def set_directory(
    request: DirectoryRequest,
    http_request: Request,
    interface: CoreInterface = Depends(get_interface)
):
    """设置漫画目录并扫描文件"""
    try:
        scan_result = await interface.set_directory(request.directory_path)

        return {
            "success": scan_result.success,
            "message": scan_result.message,
            "directory": request.directory_path,
            "manga_count": scan_result.manga_count,
            "tags_count": scan_result.tags_count,
            "scan_time": scan_result.scan_time,
            "errors": scan_result.errors
        }

    except CoreInterfaceError as e:
        logging.error(f"设置目录失败: {e}")
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        logging.error(f"设置目录失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list", response_model=PaginatedMangaResponse)
async def get_manga_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    sort_by: Optional[str] = "last_modified DESC",
    tag_filters: Optional[str] = None, # 接收逗号分隔的字符串
    query: Optional[str] = None, # 新增搜索查询参数
    interface: CoreInterface = Depends(get_interface)
):
    """
    获取漫画列表，支持分页、排序、标签过滤和标题搜索。
    - page: 页码
    - page_size: 每页数量
    - sort_by: 排序字段和顺序, e.g., "title ASC", "last_modified DESC"
    - tag_filters: 逗号分隔的标签字符串, e.g., "tag1,tag2"
    - query: 搜索查询字符串 (匹配标题)
    """
    try:
        filters = tag_filters.split(',') if tag_filters and tag_filters.strip() else None

        # 调用核心接口，现在期望它返回一个包含 'items' 和 'total' 的字典
        result = await interface.get_manga_list_paginated(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            tag_filters=filters,
            query=query
        )

        manga_list = result['items']
        total_items = result['total']

        # 将 WebMangaInfo 转换为 MangaInfoResponse
        response_items = [MangaInfoResponse(**m.__dict__) for m in manga_list]

        return PaginatedMangaResponse(
            items=response_items,
            total=total_items,
            page=page,
            page_size=page_size,
            total_pages=ceil(total_items / page_size) if total_items > 0 else 0
        )

    except CoreInterfaceError as e:
        logging.error(f"获取漫画列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        logging.error(f"获取漫画列表时发生未知错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")

@router.get("/tags")
async def get_all_tags(interface: CoreInterface = Depends(get_interface)) -> List[str]:
    """获取所有标签"""
    try:
        return await interface.get_all_tags()
    except CoreInterfaceError as e:
        logging.error(f"获取标签失败: {e}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        logging.error(f"获取标签失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# /filter 端点已被移除，其功能已合并到 /list 端点中

@router.get("/current")
async def get_current_manga(interface: CoreInterface = Depends(get_interface)):
    """获取当前选中的漫画（功能未实现）"""
    raise HTTPException(status_code=501, detail="此功能尚未实现")

@router.post("/scan")
async def scan_manga_files(interface: CoreInterface = Depends(get_interface)):
    """重新扫描当前设置的漫画目录以发现新文件"""
    try:
        # 获取当前配置的目录
        dir_info = await interface.get_current_directory()
        if not dir_info.path or not dir_info.exists:
            raise CoreInterfaceError("漫画目录未设置或不存在，无法扫描。")

        # 调用新的统一接口进行扫描（本质是添加）
        # 注意：force_rescan 的逻辑已移至 set_directory, 此处为增量扫描
        scan_result = await interface.add_mangas_from_paths([dir_info.path])

        # add_mangas_from_paths 返回的是一个 Pydantic 模型，可以直接返回
        return scan_result

    except CoreInterfaceError as e:
        logging.error(f"扫描文件失败: {e}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        logging.error(f"扫描文件时发生未知错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")

@router.post("/add")
@local_only
async def add_manga_files(
    request: AddMangaRequest,
    http_request: Request,
    interface: CoreInterface = Depends(get_interface)
):
    """添加多个漫画文件或文件夹到缓存"""
    try:
        result = await interface.add_mangas_from_paths(request.paths)
        return result
    except CoreInterfaceError as e:
        logging.error(f"添加漫画失败: {e}")
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        logging.error(f"添加漫画时发生未知错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Web版本不支持文件对话框功能，该功能已移除
# 文件选择功能在此Web版本中不可用

@router.post("/scan-directory")
@local_only
async def scan_directory(
    request: ScanDirectoryRequest,
    http_request: Request,
    interface: CoreInterface = Depends(get_interface)
):
    """
    接收一个目录路径，并异步触发后台扫描。
    这是一个 'fire-and-forget' 接口，它会立即返回，扫描在后台进行。
    """
    try:
        import asyncio
        # 使用 add_mangas_from_paths，因为它似乎是核心入口点
        logging.info(f"后台扫描任务已启动: {request.directory_path}")
        asyncio.create_task(interface.add_mangas_from_paths([request.directory_path]))
        return {"status": "success", "message": f"Scan for path '{request.directory_path}' started in background."}
    except Exception as e:
        logging.error(f"启动目录 '{request.directory_path}' 的后台扫描失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start background scan.")

@router.delete("/clear")
@local_only
async def clear_all_data(
    http_request: Request,
    interface: CoreInterface = Depends(get_interface)
):
    """清空所有漫画数据，并触发刷新事件"""
    try:
        success = await interface.clear_all_data()

        if success:
            # 手动触发一个更新事件，通知所有客户端刷新列表
            logging.info("数据已清空，正在触发 manga_list_updated 事件...")
            interface.manga_manager._emit_event("manga_list_updated")

        return {
            "success": success,
            "message": "所有数据已清空"
        }

    except CoreInterfaceError as e:
        logging.error(f"清空数据失败: {e}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        logging.error(f"清空数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/thumbnail")
async def get_manga_thumbnail(
    manga_path: str = Query(..., description="漫画文件的绝对路径"),
    interface: CoreInterface = Depends(get_interface)
):
    """
    获取漫画缩略图（GET方式）。
    此接口为获取缩略图的唯一推荐方式。
    它返回文件本身，以利用浏览器缓存。
    """
    try:
        if not manga_path:
            raise HTTPException(status_code=400, detail="缺少manga_path参数")

        # 调用新的核心接口方法获取缩略图文件路径
        thumbnail_path = interface.get_manga_thumbnail_path(manga_path)

        if thumbnail_path:
            # 直接返回文件，让浏览器缓存
            return FileResponse(
                thumbnail_path,
                media_type="image/webp",
                headers={
                    "Cache-Control": "public, max-age=86400",  # 缓存1天
                    "ETag": f'"{os.path.getmtime(thumbnail_path)}"'
                }
            )
        else:
            # 如果核心层无法提供路径（例如，原始文件不存在），则返回404
            raise HTTPException(status_code=404, detail="无法获取或生成漫画缩略图")

    except CoreInterfaceError as e:
        logging.error(f"获取缩略图时发生核心层错误: {e}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        logging.error(f"获取缩略图时发生未知错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")


# ==================== 漫画查看器 API ====================

@router.post("/current")
async def set_current_manga(
    request: SetCurrentMangaRequest,
    interface: CoreInterface = Depends(get_interface)
):
    """设置当前查看的漫画（功能未实现）"""
    raise HTTPException(status_code=501, detail="此功能尚未实现")

@router.post("/viewer/info", response_model=MangaInfoResponse)
async def get_manga_info(
    request: dict,
    interface: CoreInterface = Depends(get_interface)
):
    """获取漫画详细信息（用于查看器）"""
    try:
        manga_path = request.get("manga_path")
        if not manga_path:
            raise HTTPException(status_code=400, detail="缺少manga_path参数")

        logging.info(f"通过路径查找漫画信息: {manga_path}")

        # 调用接口层的封装方法
        manga_info = await interface.get_manga_by_path(manga_path)

        if not manga_info:
            logging.warning(f"漫画未找到: {manga_path}")
            raise HTTPException(status_code=404, detail="漫画未找到")

        # MangaInfo -> MangaInfoResponse
        return MangaInfoResponse(
            file_path=manga_info.file_path,
            title=manga_info.title,
            tags=list(manga_info.tags),
            total_pages=manga_info.total_pages,
            is_valid=manga_info.is_valid,
            last_modified=datetime.fromtimestamp(manga_info.last_modified).isoformat() if manga_info.last_modified else "",
            file_type=manga_info.file_type,
            file_size=manga_info.file_size,
            dimension_variance=getattr(manga_info, 'dimension_variance', None),
            is_likely_manga=getattr(manga_info, 'is_likely_manga', None),
            page_dimensions=getattr(manga_info, 'page_dimensions', None)
        )

    except CoreInterfaceError as e:
        logging.error(f"获取漫画信息失败: {e}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        logging.error(f"获取漫画信息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/viewer/page")
async def get_manga_page(
    request: dict,
    interface: CoreInterface = Depends(get_interface)
):
    """获取漫画指定页面的图片"""
    try:
        manga_path = request.get("manga_path")
        page_num = request.get("page_num")

        if not manga_path:
            raise HTTPException(status_code=400, detail="缺少manga_path参数")
        if page_num is None:
            raise HTTPException(status_code=400, detail="缺少page_num参数")

        logging.info(f"获取漫画页面: {manga_path}, 页码: {page_num}")

        # 调用核心接口获取页面图片
        image_data, _, _ = await interface.get_manga_page(manga_path, page_num)

        if image_data:
            return {"image": image_data}
        else:
            raise HTTPException(status_code=404, detail="页面图片未找到")

    except CoreInterfaceError as e:
        logging.error(f"获取漫画页面失败: {e}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        logging.error(f"获取漫画页面失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 单文件压缩功能 (重构后) ====================

@router.post("/compress-file-and-download")
@local_only
async def compress_file_and_download(
    request: Request,
    file: UploadFile = File(...),
    webp_quality: int = Form(85)
):
    """
    接收单个上传的漫画文件，使用新的 ImageCompressor 进行压缩，
    并以文件流的形式返回压缩后的文件供下载。
    """
    temp_upload_path = None
    try:
        # 将上传的文件保存到临时位置
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_upload_file:
            shutil.copyfileobj(file.file, temp_upload_file)
            temp_upload_path = temp_upload_file.name

        # 调用新的压缩模块
        compressor = get_image_compressor()
        compressor.reset_cancel_flag()  # 确保每次调用都是干净的状态

        compressed_temp_path = compressor.compress_manga_file(
            file_path=temp_upload_path,
            webp_quality=webp_quality,
            preserve_original_names=True
        )

        if compressed_temp_path and os.path.exists(compressed_temp_path):
            # 浏览器上传时可能已对文件名进行URL编码，此处进行解码以还原
            unquoted_filename = unquote(file.filename)
            original_name_without_ext = Path(unquoted_filename).stem
            download_filename = f"{original_name_without_ext}_compressed.zip"

            return FileResponse(
                path=compressed_temp_path,
                filename=download_filename,
                media_type='application/zip',
                background=BackgroundTask(os.remove, compressed_temp_path)
            )
        else:
            logging.error(f"文件 {file.filename} 压缩失败，未返回有效的压缩包路径。")
            raise HTTPException(status_code=500, detail="文件压缩失败或未返回有效的压缩包路径。")

    except Exception as e:
        logging.error(f"处理压缩请求 {file.filename} 时发生错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器处理压缩时出错: {str(e)}")
    finally:
        # 确保上传的临时文件总能被清理
        if temp_upload_path and os.path.exists(temp_upload_path):
            os.remove(temp_upload_path)


# ==================== 随机阅读 API ====================

class RandomSessionRequest(BaseModel):
    limit: int = 50

@router.post("/random-session")
async def start_random_session(
    request: RandomSessionRequest,
    interface: CoreInterface = Depends(get_interface)
):
    """启动一个新的随机漫画会话"""
    try:
        session_id, first_page_manga = await interface.start_random_session(limit=request.limit)
        if session_id:
            return {
                "success": True,
                "session_id": session_id,
                "manga_list": first_page_manga
            }
        else:
            return {"success": False, "message": "无法启动随机播放会话，因为漫画库为空。"}
    except CoreInterfaceError as e:
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        logging.error(f"启动随机播放会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")

@router.get("/random-session/{session_id}")
async def get_random_session_page(
    session_id: str,
    page: int = 1,
    limit: int = 50,
    interface: CoreInterface = Depends(get_interface)
):
    """获取随机漫画会话的特定页面"""
    try:
        manga_page = await interface.get_random_session_page(session_id, page, limit)
        return {
            "success": True,
            "session_id": session_id,
            "manga_list": manga_page,
            "page": page
        }
    except CoreInterfaceError as e:
        raise HTTPException(status_code=404, detail=e.message) # 404 for session not found
    except Exception as e:
        logging.error(f"获取随机播放会话页面失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")


# ==================== 缓存管理功能 ====================

@router.get("/cache/stats")
async def get_cache_stats(interface: CoreInterface = Depends(get_interface)):
    """获取缓存统计信息"""
    try:
        stats = interface.get_cache_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        logging.error(f"获取缓存统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cache/cleanup")
async def cleanup_cache(
    request: dict = None,
    interface: CoreInterface = Depends(get_interface)
):
    """清理过期的缓存文件"""
    try:
        max_age_days = request.get("max_age_days", 7) if request else 7

        cleanup_result = interface.cleanup_cache(max_age_days=max_age_days)

        return {
            "success": True,
            "message": "缓存清理完成",
            "stats": cleanup_result
        }
    except Exception as e:
        logging.error(f"清理缓存失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")

@router.post("/cache/clear")
async def clear_cache(interface: CoreInterface = Depends(get_interface)):
    """清空所有缓存"""
    try:
        interface.clear_cache()
        return {"success": True, "message": "缓存已清空"}
    except Exception as e:
        logging.error(f"清空缓存失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 批量压缩功能 ====================

class BatchCompressRequest(BaseModel):
    """批量压缩请求模型"""
    webp_quality: int = 85
    min_compression_ratio: float = 0.05
    preserve_original_names: bool = True
    delete_source_on_success: bool = False

@router.post("/batch-compress")
async def start_batch_compression(
    request: BatchCompressRequest,
    interface: CoreInterface = Depends(get_interface)
):
    """
    启动批量压缩任务
    """
    try:
        # 调用核心接口的批量压缩方法
        result = await interface.batch_compress_manga(
            webp_quality=request.webp_quality,
            min_compression_ratio=request.min_compression_ratio,
            preserve_original_names=request.preserve_original_names,
            delete_source_on_success=request.delete_source_on_success
        )

        return {
            "success": result["success"],
            "message": result["message"],
            "task_id": result.get("task_id")
        }

    except CoreInterfaceError as e:
        logging.error(f"启动批量压缩失败: {e}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        logging.error(f"启动批量压缩时发生未知错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")

@router.get("/batch-compress/status/{task_id}")
async def get_batch_compression_status(
    task_id: str,
    interface: CoreInterface = Depends(get_interface)
):
    """
    获取批量压缩任务状态
    """
    try:
        status = interface.get_batch_compression_status(task_id)
        return status
    except CoreInterfaceError as e:
        logging.error(f"获取批量压缩状态失败: {e}")
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        logging.error(f"获取批量压缩状态时发生未知错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")

@router.post("/batch-compress/cancel/{task_id}")
async def cancel_batch_compression(
    task_id: str,
    interface: CoreInterface = Depends(get_interface)
):
    """
    取消批量压缩任务
    """
    try:
        success = interface.cancel_batch_compression(task_id)
        return {"success": success, "message": "任务已取消" if success else "任务取消失败"}
    except CoreInterfaceError as e:
        logging.error(f"取消批量压缩失败: {e}")
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        logging.error(f"取消批量压缩时发生未知错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")
