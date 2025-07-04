"""
翻译功能 API

提供OCR识别、文本翻译、批量处理等功能的RESTful接口。
复用core中的翻译相关业务逻辑。
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Request
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import os
import time
import tempfile
import asyncio
from pathlib import Path
from functools import wraps

# 导入核心业务逻辑
from core.translation.image_translator import ImageTranslator
from core.ocr.ocr_manager import OCRManager
from core.translation.translator import TranslatorFactory
from core.config import config
from web.core_interface import CoreInterface, get_core_interface
from utils import manga_logger as log

router = APIRouter()

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

# Web版本不支持文件替换功能，相关装饰器已移除

# 依赖注入：获取Core接口实例
def get_interface() -> CoreInterface:
    """获取Core接口实例"""
    return get_core_interface()

# 数据模型
class TranslationRequest(BaseModel):
    """翻译请求模型"""
    source_lang: str = "auto"
    target_lang: str = "zh"
    translator_engine: str = "智谱"

class OCRResult(BaseModel):
    """OCR结果模型"""
    text: str
    confidence: float
    bbox: List[int]  # [x, y, width, height]

class TranslationResult(BaseModel):
    """翻译结果模型"""
    original_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    confidence: float

@router.get("/health")
async def translation_health():
    """翻译模块健康检查"""
    return {"status": "healthy", "module": "translation"}

@router.get("/engines")
async def get_translation_engines():
    """获取可用的翻译引擎"""
    try:
        # 从TranslatorFactory获取可用引擎
        engines = ["Google", "智谱"]  # 根据实际情况调整
        
        return {
            "engines": engines,
            "default": "智谱"
        }
        
    except Exception as e:
        log.error(f"获取翻译引擎失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/languages")
async def get_supported_languages():
    """获取支持的语言列表"""
    try:
        languages = {
            "source": [
                {"code": "auto", "name": "自动检测"},
                {"code": "ja", "name": "日语"},
                {"code": "en", "name": "英语"},
                {"code": "ko", "name": "韩语"},
                {"code": "zh", "name": "中文"}
            ],
            "target": [
                {"code": "zh", "name": "中文"},
                {"code": "en", "name": "英语"},
                {"code": "ja", "name": "日语"},
                {"code": "ko", "name": "韩语"}
            ]
        }
        
        return languages
        
    except Exception as e:
        log.error(f"获取语言列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ocr")
async def perform_ocr(
    file: UploadFile = File(...),
    page_num: int = 0
):
    """对上传的图片执行OCR识别"""
    try:
        # 验证文件类型
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="只支持图片文件")
        
        # 保存临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # 执行OCR
            ocr_manager = OCRManager()
            ocr_results = ocr_manager.extract_text(temp_file_path, page_num)
            
            # 转换结果格式
            results = []
            for result in ocr_results:
                results.append(OCRResult(
                    text=result.text,
                    confidence=result.confidence,
                    bbox=result.bbox
                ))
            
            return {
                "success": True,
                "results": results,
                "total_texts": len(results)
            }
            
        finally:
            # 清理临时文件
            os.unlink(temp_file_path)
            
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"OCR识别失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/translate-text")
async def translate_text(
    text: str,
    target_lang: str = "zh",
    engine: str = "智谱"
):
    """翻译文本"""
    try:
        # 导入翻译器
        from core.translation.image_translator import get_image_translator
        
        image_translator = get_image_translator()
        
        # 使用 image_translator 中已经异步化的 translate_text 方法
        translated_text = await image_translator.translate_text(
            text=text,
            target_language=target_lang
        )
        
        return {
            "success": True,
            "original_text": text,
            "translated_text": translated_text,
            "target_lang": target_lang
        }
        
    except Exception as e:
        log.error(f"文本翻译失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"文本翻译失败: {e}")

@router.post("/translate-image")
async def translate_image(
    file: UploadFile = File(...),
    target_lang: str = "zh"
):
    """翻译单张图片中的文字"""
    import cv2
    import numpy as np
    from fastapi.responses import Response
    from core.translation.image_translator import get_image_translator

    try:
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="只支持图片文件")

        content = await file.read()
        nparr = np.frombuffer(content, np.uint8)
        image_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image_np is None:
            raise HTTPException(status_code=400, detail="无法解码图片")

        image_translator = get_image_translator()
        
        result_image_np = await image_translator.translate_image(
            image_input=image_np,
            target_language=target_lang
        )

        # 将结果图片编码为WebP格式以便传输
        success, buffer = cv2.imencode(".webp", result_image_np)
        if not success:
            raise HTTPException(status_code=500, detail="翻译结果图片编码失败")

        return Response(content=buffer.tobytes(), media_type="image/webp")

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"图片翻译失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"图片翻译失败: {str(e)}")

@router.post("/translate-manga-async")
async def translate_manga_async(
    file: UploadFile = File(...),
    source_lang: str = "auto",
    target_lang: str = "zh-CN",
    translator_engine: str = "智谱",
    webp_quality: int = 100
):
    """异步翻译漫画文件 - 立即返回任务ID"""
    import uuid
    import threading

    # 生成任务ID
    task_id = str(uuid.uuid4())

    try:
        # 保存上传的文件
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        # 设置任务状态
        _translation_tasks[task_id] = {
            "status": "processing",
            "progress": 0,
            "file_name": file.filename,
            "temp_file_path": temp_file_path,
            "start_time": time.time()
        }

        # 在后台线程中执行翻译
        def background_translation():
            try:
                _execute_translation_task(task_id, temp_file_path, target_lang, translator_engine, webp_quality)
            except Exception as e:
                log.error(f"后台翻译任务失败: {e}")
                _translation_tasks[task_id]["status"] = "error"
                _translation_tasks[task_id]["error"] = str(e)

        thread = threading.Thread(target=background_translation)
        thread.daemon = True

        # 记录线程信息，用于强制终止
        _translation_threads[task_id] = thread

        thread.start()

        return {
            "success": True,
            "task_id": task_id,
            "message": "翻译任务已启动"
        }

    except Exception as e:
        log.error(f"启动异步翻译任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 全局任务存储
_translation_tasks = {}
_translation_threads = {}  # 存储翻译线程，用于强制终止

def _execute_translation_task(task_id, temp_file_path, target_lang, translator_engine, webp_quality):
    """执行翻译任务的同步包裹器"""
    try:
        # 使用 asyncio.run 在新线程中运行异步任务
        asyncio.run(_async_execute_translation_task(task_id, temp_file_path, target_lang, translator_engine, webp_quality))
    except Exception as e:
        log.error(f"翻译任务 {task_id} 的同步包裹器异常: {e}", exc_info=True)
        task = _translation_tasks.get(task_id, {})
        task["status"] = "error"
        task["error"] = str(e)
    finally:
        # 确保临时文件最终被清理
        if os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                log.info(f"清理临时文件: {temp_file_path}")
            except OSError as e:
                log.error(f"清理临时文件失败: {e}")

async def _async_execute_translation_task(task_id, temp_file_path, target_lang, translator_engine, webp_quality):
    """异步执行翻译任务的核心逻辑"""
    from core.translation.image_translator import get_image_translator, set_current_translation_process
    import threading
    import os
    import zipfile
    import shutil

    task = _translation_tasks[task_id]
    extract_dir = tempfile.mkdtemp(prefix="extract-")
    output_dir = tempfile.mkdtemp(prefix="output-")

    try:
        if task.get("cancelled", False):
            log.info(f"任务 {task_id} 在开始前已被取消")
            task["status"] = "cancelled"
            return

        process_info = {
            "task_id": task_id, "thread_id": threading.get_ident(), "process_id": os.getpid(),
            "file_name": task["file_name"], "start_time": task["start_time"]
        }
        set_current_translation_process(process_info)
        task["progress"] = 10

        image_translator = get_image_translator()

        def extract_sync():
            with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
                return [
                    os.path.join(extract_dir, member_info.filename)
                    for member_info in zip_ref.infolist()
                    if member_info.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'))
                    and not member_info.is_dir() and zip_ref.extract(member_info, extract_dir)
                ]
        
        image_files = await asyncio.to_thread(extract_sync)

        if not image_files:
            raise Exception("压缩包中未找到图片文件")

        image_files.sort()
        task["progress"] = 30

        output_paths = [os.path.join(output_dir, f"page_{i+1:03d}_translated.webp") for i, _ in enumerate(image_files)]
        task["progress"] = 50

        await image_translator.batch_translate_images_optimized(
            image_inputs=image_files,
            output_paths=output_paths,
            target_language=target_lang
        )

        task["progress"] = 100
        task["status"] = "completed"
        task["output_files"] = output_paths
        task["output_dir"] = output_dir # 保存输出目录以便后续清理

    except Exception as e:
        log.error(f"异步翻译任务 {task_id} 执行失败: {e}", exc_info=True)
        task["status"] = "error"
        task["error"] = str(e)
    finally:
        set_current_translation_process(None)
        # 清理解压目录
        if os.path.exists(extract_dir):
            await asyncio.to_thread(shutil.rmtree, extract_dir, ignore_errors=True)
        
        # 注意：输出目录 (output_dir) 需要在下载后清理，这里不清理

@router.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
    """获取翻译任务状态"""
    if task_id not in _translation_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = _translation_tasks[task_id]
    return {
        "success": True,
        "status": task["status"],
        "progress": task.get("progress", 0),
        "error": task.get("error"),
        "output_files": task.get("output_files", [])
    }

@router.post("/cancel-task/{task_id}")
async def cancel_task(task_id: str):
    """取消翻译任务 - 真正杀掉线程"""
    if task_id not in _translation_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = _translation_tasks[task_id]
    task["cancelled"] = True
    task["status"] = "cancelled"

    # 获取并强制终止线程
    if task_id in _translation_threads:
        thread = _translation_threads[task_id]

        if thread.is_alive():
            log.warning(f"🛑 强制终止翻译线程: {task_id}")

            # Python没有直接杀掉线程的方法，但我们可以使用ctypes强制终止
            import ctypes
            import sys

            try:
                # 获取线程ID
                thread_id = thread.ident
                if thread_id:
                    # 在Windows上强制终止线程
                    if sys.platform == "win32":
                        import ctypes.wintypes
                        kernel32 = ctypes.windll.kernel32
                        handle = kernel32.OpenThread(1, False, thread_id)
                        if handle:
                            kernel32.TerminateThread(handle, 0)
                            kernel32.CloseHandle(handle)
                            log.warning(f"🛑 Windows线程已强制终止: {thread_id}")
                    else:
                        # 在Unix系统上发送信号
                        import signal
                        import os
                        try:
                            os.kill(thread_id, signal.SIGTERM)
                            log.warning(f"🛑 Unix线程已发送终止信号: {thread_id}")
                        except:
                            pass

            except Exception as e:
                log.error(f"强制终止线程失败: {e}")

        # 清理线程记录
        del _translation_threads[task_id]

    # 同时调用原来的取消方法
    try:
        from core.translation.image_translator import kill_current_translation
        kill_current_translation()
    except Exception as e:
        log.warning(f"调用原取消方法失败: {e}")

    return {
        "success": True,
        "message": "翻译线程已强制终止"
    }

@router.post("/translate-manga")
async def translate_manga(
    file: UploadFile = File(...),
    target_lang: str = "zh"
):
    """(已废弃) 同步翻译漫画文件 - 功能已合并到 /translate-manga-async"""
    raise HTTPException(status_code=410, detail="此同步API已废弃，请使用 /api/translation/translate-manga-async 异步接口。")

@router.get("/history")
async def get_translation_history():
    """获取翻译历史"""
    try:
        # 这里可以从缓存或数据库获取翻译历史
        # 暂时返回空列表
        return {
            "history": [],
            "total": 0
        }
        
    except Exception as e:
        log.error(f"获取翻译历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/history")
async def clear_translation_history():
    """清空翻译历史"""
    try:
        # 清空翻译缓存
        from core.core_cache.cache_factory import get_cache_factory_instance
        translation_cache = get_cache_factory_instance().get_manager("translation")
        translation_cache.clear()
        
        return {
            "success": True,
            "message": "翻译历史已清空"
        }
        
    except Exception as e:
        log.error(f"清空翻译历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class DownloadTaskRequest(BaseModel):
    task_name: str
    output_files: List[str]

@router.post("/download-task")
async def download_translation_task(
    request: DownloadTaskRequest
):
    """下载单个翻译任务的ZIP包"""
    try:
        import zipfile
        import tempfile
        from fastapi.responses import FileResponse
        from datetime import datetime

        # 创建临时ZIP文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for i, temp_file in enumerate(request.output_files):
                    if os.path.exists(temp_file):
                        filename = f"page_{i+1:03d}.webp"
                        zipf.write(temp_file, filename)

            # 生成下载文件名
            safe_name = "".join(c for c in request.task_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            download_name = f"{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

            return FileResponse(
                path=temp_zip.name,
                filename=download_name,
                media_type='application/zip'
            )

    except Exception as e:
        log.error(f"下载翻译任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class DownloadBatchRequest(BaseModel):
    tasks: List[Dict[str, Any]]

class LosslessCompressionRequest(BaseModel):
    file_path: str
    webp_quality: int = 75  # Google推荐的默认质量
    preserve_original_names: bool = False  # 是否保留原始文件名

class UploadResponse(BaseModel):
    success: bool
    message: str
    temp_path: str = None

@router.post("/download-batch")
async def download_translation_batch(
    request: DownloadBatchRequest
):
    """下载批量翻译任务的ZIP包"""
    try:
        import zipfile
        import tempfile
        from fastapi.responses import FileResponse
        from datetime import datetime

        # 创建临时ZIP文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for task in request.tasks:
                    task_name = task.get("name", "unknown")
                    output_files = task.get("output_files", [])

                    # 为每个任务创建文件夹
                    safe_task_name = "".join(c for c in task_name if c.isalnum() or c in (' ', '-', '_')).rstrip()

                    for i, temp_file in enumerate(output_files):
                        if os.path.exists(temp_file):
                            filename = f"{safe_task_name}/page_{i+1:03d}.webp"
                            zipf.write(temp_file, filename)

            # 生成下载文件名
            download_name = f"batch_translation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

            return FileResponse(
                path=temp_zip.name,
                filename=download_name,
                media_type='application/zip'
            )

    except Exception as e:
        log.error(f"批量下载翻译任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel-translation")
async def cancel_translation():
    """取消翻译操作 - 直接杀掉翻译实例"""
    try:
        from core.translation.image_translator import kill_current_translation, get_current_translation_process

        # 获取当前翻译进程信息
        current_process = get_current_translation_process()

        if current_process:
            log.warning(f"🛑 发现正在运行的翻译进程: {current_process}")

            # 直接杀掉翻译实例
            killed = kill_current_translation()

            if killed:
                return {
                    "success": True,
                    "message": "翻译进程已强制终止"
                }
            else:
                return {
                    "success": False,
                    "message": "未能终止翻译进程"
                }
        else:
            return {
                "success": True,
                "message": "没有正在运行的翻译进程"
            }

    except Exception as e:
        log.error(f"取消翻译失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/translation-status")
async def get_translation_status():
    """获取翻译状态"""
    try:
        from core.translation.image_translator import get_current_translation_process

        current_process = get_current_translation_process()
        is_translating = current_process is not None

        return {
            "success": True,
            "is_translating": is_translating,
            "current_process": current_process,
            "is_cancelled": False  # 简化状态管理
        }

    except Exception as e:
        log.error(f"获取翻译状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


