"""
翻译功能 API - V2 (Refactored)

提供核心的漫画翻译服务接口。
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Request, status, Form
from fastapi.responses import Response, FileResponse
from starlette.background import BackgroundTask
from typing import Optional
import tempfile
import os
import asyncio
import shutil
from pathlib import Path
from urllib.parse import unquote

from core.config import config
from core.manga.manga_text_replacer import MangaTextReplacer
from core.ocr.ocr_manager import OCRManager
from core.harmonization_map_manager import get_harmonization_map_manager_instance
from core.translation.translator import TranslatorFactory
from core.manga_translation.processor import MangaPageProcessor
from core.manga_translation.service import MangaTranslationService
from core.core_cache.cache_factory import get_cache_factory_instance
import logging

router = APIRouter()

# --- Service Instantiation & Dependency Injection ---

# 1. Create a single, shared instance of the TranslatorFactory
# This factory holds all configurations but initializes translators lazily.
translator_config = {
    "zhipu_api_key": config.zhipu_api_key.value,
    "zhipu_model": config.zhipu_model.value,
    "openai_api_key": config.openai_api_key.value,
    "openai_model": config.openai_model.value,
    "openai_api_base_url": config.openai_api_base_url.value,
    "gemini_api_key": config.gemini_api_key.value,
    "gemini_model": config.gemini_model.value,
}
translator_factory = TranslatorFactory(**translator_config)

# --- Service Instantiation & Dependency Injection ---

# 确保只创建一次服务实例
_manga_translation_service_instance: Optional[MangaTranslationService] = None

def get_manga_translation_service() -> MangaTranslationService:
    """
    Dependency provider that returns the single instance of MangaTranslationService.
    Initializes the service lazily on first access.
    """
    global _manga_translation_service_instance # 声明使用全局变量
    if _manga_translation_service_instance is None:
        try:
            logging.info("正在延迟创建 MangaTranslationService 单例实例...")
            ocr_manager = OCRManager()
            ocr_manager.load_model() # 确保OCR模型也在需要时加载

            text_replacer = MangaTextReplacer()
            harmonization_manager = get_harmonization_map_manager_instance()
            
            # Translator factory is already a singleton
            # Translator is now fetched here, inside the lazy init
            translator = translator_factory.get_translator(config.translator_type.value)

            page_processor = MangaPageProcessor(
                ocr_manager=ocr_manager,
                translator=translator,
                text_replacer=text_replacer,
                harmonization_manager=harmonization_manager
            )

            image_cache = get_cache_factory_instance().get_manager("persistent_translation")

            _manga_translation_service_instance = MangaTranslationService(
                page_processor=page_processor,
                image_cache=image_cache
            )
            logging.info("MangaTranslationService 单例延迟创建成功。")
        except Exception as e:
            logging.critical(f"致命错误：延迟创建 MangaTranslationService 单例失败: {e}", exc_info=True)
            raise # 仍然抛出异常，因为服务无法创建

    return _manga_translation_service_instance

# --- API Endpoints ---

@router.get("/health", summary="Health Check")
async def health_check():
    """Check if the translation API is running."""
    return {"status": "healthy", "module": "translation_v2"}

@router.post(
    "/translate-file-and-download",
    summary="Translate a manga archive and download the result directly",
)
async def translate_file_and_download_api(
    file: UploadFile = File(...),
    target_lang: str = Form("zh"),
    service: MangaTranslationService = Depends(get_manga_translation_service)
):
    """
    Accepts a single manga archive, translates it synchronously, and returns the
    result as a file stream for direct download. This is a blocking operation.
    It mirrors the architecture of the /compress-file-and-download endpoint for simplicity and robustness.
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename cannot be empty.")
    if not file.filename.lower().endswith(('.zip', '.cbz')):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .zip and .cbz files are supported.")

    temp_upload_path = None
    translated_temp_path = None
    try:
        # Save the uploaded file to a temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_upload_file:
            shutil.copyfileobj(file.file, temp_upload_file)
            temp_upload_path = temp_upload_file.name

        # 调用同步翻译服务
        logging.info(f"正在为 {temp_upload_path} 调用同步翻译服务")
        translated_temp_path = await asyncio.to_thread(
            service.translate_manga_file,
            manga_path=temp_upload_path,
            target_language=target_lang
        )

        if not translated_temp_path or not os.path.exists(translated_temp_path):
            logging.error(f"文件 {file.filename} 翻译失败，服务未返回有效的文件路径。")
            raise HTTPException(status_code=500, detail="翻译失败，服务未产出结果文件。")

        # Prepare for download
        unquoted_filename = unquote(file.filename)
        original_name_without_ext = Path(unquoted_filename).stem
        download_filename = f"{original_name_without_ext}_translated.zip"

        # Use BackgroundTask to ensure cleanup happens after the response is sent
        cleanup_tasks = BackgroundTask(cleanup_temp_files, paths=[temp_upload_path, translated_temp_path])

        return FileResponse(
            path=translated_temp_path,
            filename=download_filename,
            media_type='application/zip',
            background=cleanup_tasks
        )

    except Exception as e:
        logging.error(f"为 {file.filename} 进行翻译和下载时出错: {e}", exc_info=True)
        # Cleanup temp files immediately on error
        cleanup_temp_files([temp_upload_path, translated_temp_path])
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


def cleanup_temp_files(paths: list):
    """Utility function to delete a list of temporary files."""
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.unlink(path)
                logging.info(f"已清理临时文件: {path}")
            except OSError as e:
                logging.error(f"删除临时文件 {path} 时出错: {e}")

@router.post(
    "/page",
    summary="Get a single translated page (CACHE ONLY)",
)
async def get_translated_page_from_cache_api(
    manga_path: str,
    page_index: int,
    target_lang: Optional[str] = "zh",
    service: MangaTranslationService = Depends(get_manga_translation_service)
):
    """
    Retrieves a single translated page from the cache.
    This endpoint is now simplified and **only** serves from the cache.
    It does NOT trigger background translation tasks.
    If the page is not in the cache, it returns a 404 Not Found error.
    """
    try:
        # The service no longer has get_translated_page, we interact with the cache directly
        # through the service's cache attribute.
        translator_type = config.translator_type.value
        cached_image_bytes = service.cache.get_cached_translation(
            original_archive_path=manga_path,
            page_num=page_index,
            language=target_lang,
            translator_name=translator_type
        )

        if cached_image_bytes:
            return Response(content=cached_image_bytes, media_type="image/webp")
        else:
            # Explicitly return 404 if not found in cache.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="在缓存中未找到已翻译页面。")

    except Exception as e:
        logging.error(f"获取 {manga_path} 第 {page_index} 页的缓存页面时出错: {e}", exc_info=True)
        # Re-raise known HTTP exceptions, otherwise return a generic 500
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/text", summary="Translate a simple text string")
async def translate_text_api(text: str, target_lang: str = "zh"):
    """
    Translates a simple text string using the currently configured default translator.
    """
    try:
        # Use the factory to get the current translator instance
        translator = translator_factory.get_translator(config.translator_type.value)
        
        # translate_batch expects a list
        translated_texts = await translator.translate_batch([text], target_lang)
        
        return {
            "success": True,
            "original_text": text,
            "translated_text": translated_texts[0] if translated_texts else text,
            "target_lang": target_lang
        }
    except Exception as e:
       logging.error(f"文本翻译失败: {e}", exc_info=True)
       raise HTTPException(status_code=500, detail=f"文本翻译失败: {e}")
