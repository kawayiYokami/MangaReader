"""
漫画管理 API

提供漫画浏览、文件管理等功能的RESTful接口。
通过统一接口层与core模块交互。
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import Response
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import os
import base64
from pathlib import Path
from functools import wraps

# 导入统一接口层
from web.core_interface import (
    get_core_interface,
    CoreInterface,
    WebMangaInfo,
    WebDirectoryInfo,
    WebScanResult,
    CoreInterfaceError
)
from utils import manga_logger as log

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

# 依赖注入：获取Core接口实例
def get_interface() -> CoreInterface:
    """获取Core接口实例"""
    return get_core_interface()

@router.get("/health")
async def manga_health():
    """漫画模块健康检查"""
    return {"status": "healthy", "module": "manga"}

@router.get("/directory")
async def get_current_directory(interface: CoreInterface = Depends(get_interface)):
    """获取当前漫画目录"""
    try:
        dir_info = interface.get_current_directory()
        return {
            "current_directory": dir_info.path,
            "exists": dir_info.exists,
            "is_directory": dir_info.is_directory,
            "manga_count": dir_info.manga_count
        }
    except CoreInterfaceError as e:
        log.error(f"获取当前目录失败: {e}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        log.error(f"获取当前目录失败: {e}")
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
        scan_result = interface.set_directory(request.directory_path)

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
        log.error(f"设置目录失败: {e}")
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        log.error(f"设置目录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
async def get_manga_list(interface: CoreInterface = Depends(get_interface)) -> List[MangaInfoResponse]:
    """获取漫画列表"""
    try:
        web_manga_list = interface.get_manga_list()

        manga_list = []
        for web_manga in web_manga_list:
            manga_list.append(MangaInfoResponse(
                file_path=web_manga.file_path,
                title=web_manga.title,
                tags=web_manga.tags,
                total_pages=web_manga.total_pages,
                is_valid=web_manga.is_valid,
                last_modified=web_manga.last_modified,
                file_type=web_manga.file_type,
                file_size=web_manga.file_size
            ))

        return manga_list

    except CoreInterfaceError as e:
        log.error(f"获取漫画列表失败: {e}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        log.error(f"获取漫画列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tags")
async def get_all_tags(interface: CoreInterface = Depends(get_interface)) -> List[str]:
    """获取所有标签"""
    try:
        return interface.get_all_tags()
    except CoreInterfaceError as e:
        log.error(f"获取标签失败: {e}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        log.error(f"获取标签失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/filter")
async def filter_by_tags(
    request: TagFilterRequest,
    interface: CoreInterface = Depends(get_interface)
) -> List[MangaInfoResponse]:
    """根据标签过滤漫画"""
    try:
        web_manga_list = interface.filter_manga_by_tags(request.tags)

        manga_list = []
        for web_manga in web_manga_list:
            manga_list.append(MangaInfoResponse(
                file_path=web_manga.file_path,
                title=web_manga.title,
                tags=web_manga.tags,
                total_pages=web_manga.total_pages,
                is_valid=web_manga.is_valid,
                last_modified=web_manga.last_modified,
                file_type=web_manga.file_type,
                file_size=web_manga.file_size
            ))

        return manga_list

    except CoreInterfaceError as e:
        log.error(f"标签过滤失败: {e}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        log.error(f"标签过滤失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/current")
async def get_current_manga(interface: CoreInterface = Depends(get_interface)):
    """获取当前选中的漫画"""
    try:
        # 注意：这个功能需要在接口层实现
        # 暂时返回空，后续可以扩展
        return {"current_manga": None, "current_page": 0}

    except Exception as e:
        log.error(f"获取当前漫画失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scan")
async def scan_manga_files(
    request: ScanRequest,
    interface: CoreInterface = Depends(get_interface)
):
    """扫描漫画文件"""
    try:
        scan_result = interface.scan_manga_files(force_rescan=request.force_rescan)

        return {
            "success": scan_result.success,
            "message": scan_result.message,
            "manga_count": scan_result.manga_count,
            "tags_count": scan_result.tags_count,
            "scan_time": scan_result.scan_time,
            "errors": scan_result.errors
        }

    except CoreInterfaceError as e:
        log.error(f"扫描文件失败: {e}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        log.error(f"扫描文件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add")
@local_only
async def add_manga_files(
    request: AddMangaRequest,
    http_request: Request,
    interface: CoreInterface = Depends(get_interface)
):
    """添加漫画文件或文件夹到缓存"""
    try:
        import os

        added_count = 0
        failed_paths = []

        for path in request.paths:
            try:
                # 检查路径是否存在
                if not os.path.exists(path):
                    failed_paths.append(f"{path} (路径不存在)")
                    continue

                # 检查是否为支持的类型
                if os.path.isdir(path):
                    # 文件夹
                    result = interface.add_manga_from_path(path)
                    if result.success:
                        added_count += result.manga_count
                    else:
                        failed_paths.append(f"{path} ({result.message})")
                elif path.lower().endswith('.zip'):
                    # ZIP文件
                    result = interface.add_manga_from_path(path)
                    if result.success:
                        added_count += result.manga_count
                    else:
                        failed_paths.append(f"{path} ({result.message})")
                else:
                    failed_paths.append(f"{path} (不支持的文件类型)")

            except Exception as e:
                failed_paths.append(f"{path} (处理失败: {str(e)})")

        # 构建响应消息
        message_parts = []
        if added_count > 0:
            message_parts.append(f"成功添加 {added_count} 本漫画")
        if failed_paths:
            message_parts.append(f"失败 {len(failed_paths)} 个路径")

        message = "，".join(message_parts) if message_parts else "没有添加任何漫画"

        return {
            "success": added_count > 0,
            "message": message,
            "added_count": added_count,
            "failed_paths": failed_paths
        }

    except CoreInterfaceError as e:
        log.error(f"添加漫画失败: {e}")
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        log.error(f"添加漫画失败: {e}")
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
    """扫描指定目录中的所有漫画"""
    try:
        import os

        directory_path = request.directory_path

        # 检查目录是否存在
        if not os.path.exists(directory_path):
            return {
                "success": False,
                "message": f"目录不存在: {directory_path}",
                "added_count": 0,
                "failed_paths": [f"{directory_path} (目录不存在)"]
            }

        if not os.path.isdir(directory_path):
            return {
                "success": False,
                "message": f"路径不是目录: {directory_path}",
                "added_count": 0,
                "failed_paths": [f"{directory_path} (不是目录)"]
            }

        # 调用核心接口扫描目录
        result = interface.scan_directory_for_manga(directory_path)

        return {
            "success": result.success,
            "message": result.message,
            "added_count": result.manga_count,
            "scan_time": result.scan_time,
            "errors": result.errors
        }

    except CoreInterfaceError as e:
        log.error(f"扫描目录失败: {e}")
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        log.error(f"扫描目录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/clear")
@local_only
async def clear_all_data(
    http_request: Request,
    interface: CoreInterface = Depends(get_interface)
):
    """清空所有漫画数据"""
    try:
        success = interface.clear_all_data()

        return {
            "success": success,
            "message": "所有数据已清空"
        }

    except CoreInterfaceError as e:
        log.error(f"清空数据失败: {e}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        log.error(f"清空数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/thumbnail/{manga_path:path}")
async def get_manga_thumbnail(
    manga_path: str,
    size: int = 300,
    interface: CoreInterface = Depends(get_interface)
):
    """获取漫画缩略图"""
    try:
        # URL解码
        import urllib.parse
        manga_path = urllib.parse.unquote(manga_path)

        thumbnail_data = interface.get_manga_thumbnail(manga_path, max_size=size)

        if thumbnail_data:
            return {"thumbnail": thumbnail_data}
        else:
            raise HTTPException(status_code=404, detail="无法获取漫画缩略图")

    except CoreInterfaceError as e:
        log.error(f"获取缩略图失败: {e}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        log.error(f"获取缩略图失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/thumbnail")
async def get_manga_thumbnail_post(
    request: dict,
    interface: CoreInterface = Depends(get_interface)
):
    """获取漫画缩略图（POST方式，避免URL编码问题）"""
    try:
        manga_path = request.get("manga_path")
        size = request.get("size", 300)

        if not manga_path:
            raise HTTPException(status_code=400, detail="缺少manga_path参数")

        # log.info(f"获取缩略图: {manga_path}")
        thumbnail_data = interface.get_manga_thumbnail(manga_path, max_size=size)

        if thumbnail_data:
            return {"thumbnail": thumbnail_data}
        else:
            raise HTTPException(status_code=404, detail="无法获取漫画缩略图")

    except CoreInterfaceError as e:
        log.error(f"获取缩略图失败: {e}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        log.error(f"获取缩略图失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 漫画查看器 API ====================

@router.post("/current")
async def set_current_manga(
    request: SetCurrentMangaRequest,
    interface: CoreInterface = Depends(get_interface)
):
    """设置当前查看的漫画"""
    try:
        # 这里需要在接口层实现状态管理
        # 暂时返回成功，后续可以扩展
        return {
            "success": True,
            "manga_path": request.manga_path,
            "page": request.page,
            "message": "当前漫画设置成功"
        }
    except Exception as e:
        log.error(f"设置当前漫画失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/viewer/info")
async def get_manga_info(
    request: dict,
    interface: CoreInterface = Depends(get_interface)
):
    """获取漫画详细信息（用于查看器）"""
    try:
        manga_path = request.get("manga_path")
        if not manga_path:
            raise HTTPException(status_code=400, detail="缺少manga_path参数")

        log.info(f"查找漫画信息: {manga_path}")

        # 从漫画列表中查找对应的漫画
        manga_list = interface.get_manga_list()
        target_manga = None

        for manga in manga_list:
            if manga.file_path == manga_path:
                target_manga = manga
                break

        if not target_manga:
            log.warning(f"漫画未找到: {manga_path}")
            log.info(f"可用漫画列表前5个: {[m.file_path for m in manga_list[:5]]}")
            raise HTTPException(status_code=404, detail="漫画未找到")

        return {
            "file_path": target_manga.file_path,
            "title": target_manga.title,
            "tags": target_manga.tags,
            "total_pages": target_manga.total_pages,
            "is_valid": target_manga.is_valid,
            "last_modified": target_manga.last_modified,
            "file_type": target_manga.file_type,
            "file_size": target_manga.file_size
        }

    except CoreInterfaceError as e:
        log.error(f"获取漫画信息失败: {e}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        log.error(f"获取漫画信息失败: {e}")
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

        log.info(f"获取漫画页面: {manga_path}, 页码: {page_num}")

        # 调用核心接口获取页面图片
        image_data = interface.get_manga_page(manga_path, page_num)

        if image_data:
            return {"image": image_data}
        else:
            raise HTTPException(status_code=404, detail="页面图片未找到")

    except CoreInterfaceError as e:
        log.error(f"获取漫画页面失败: {e}")
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        log.error(f"获取漫画页面失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 批量压缩功能 ====================

class BatchCompressionRequest(BaseModel):
    webp_quality: int = 85
    min_compression_ratio: float = 0.25

@router.post("/batch-compress")
async def batch_compress_manga(
    request: BatchCompressionRequest,
    interface: CoreInterface = Depends(get_interface)
):
    """批量压缩漫画库中的所有漫画文件"""
    try:
        result = interface.batch_compress_manga(
            webp_quality=request.webp_quality,
            min_compression_ratio=request.min_compression_ratio
        )
        return result
    except Exception as e:
        log.error(f"批量压缩失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))




# ==================== 自动过滤功能 ====================

class AutoFilterRequest(BaseModel):
    filter_method: str = "dimension_analysis"
    threshold: float = 0.15

class ApplyFilterRequest(BaseModel):
    filter_results: Dict[str, Any]

@router.post("/auto-filter-preview")
async def auto_filter_preview(
    request: AutoFilterRequest,
    interface: CoreInterface = Depends(get_interface)
):
    """预览自动过滤结果"""
    try:
        result = interface.auto_filter_manga(
            filter_method=request.filter_method,
            threshold=request.threshold
        )
        return result
    except Exception as e:
        log.error(f"自动过滤预览失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/apply-auto-filter")
async def apply_auto_filter(
    request: ApplyFilterRequest,
    interface: CoreInterface = Depends(get_interface)
):
    """应用自动过滤结果"""
    try:
        success = interface.apply_filter_results(request.filter_results)
        return {
            "success": success,
            "message": "过滤结果已应用",
            "removed_count": len(request.filter_results.get("removed_manga", []))
        }
    except Exception as e:
        log.error(f"应用自动过滤失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 缓存管理功能 ====================

@router.get("/cache/stats")
async def get_cache_stats(interface: CoreInterface = Depends(get_interface)):
    """获取缓存统计信息"""
    try:
        stats = interface.thumbnail_cache.get_cache_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        log.error(f"获取缓存统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cache/cleanup")
async def cleanup_cache(
    request: dict = None,
    interface: CoreInterface = Depends(get_interface)
):
    """清理缓存"""
    try:
        max_age_days = 30
        max_cache_size_mb = 500

        if request:
            max_age_days = request.get("max_age_days", 30)
            max_cache_size_mb = request.get("max_cache_size_mb", 500)

        interface.thumbnail_cache.cleanup_old_cache(max_age_days, max_cache_size_mb)

        # 返回清理后的统计信息
        stats = interface.thumbnail_cache.get_cache_stats()
        return {"success": True, "message": "缓存清理完成", "stats": stats}
    except Exception as e:
        log.error(f"清理缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
