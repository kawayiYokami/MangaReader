"""
设置管理 API

提供应用配置管理功能的RESTful接口。
复用core.config的配置系统。
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
# from enum import Enum # Enum 已在 core.config 中导入和使用，此处可能不需要直接用
import os
from fontTools.ttLib import TTFont
import sys # 新增导入
from pathlib import Path # 新增导入

# 导入核心业务逻辑
import logging
from core.config import config
from utils.manga_logger import set_level

router = APIRouter()

# --- 修改开始: 动态定义 FONT_DIR ---
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # 打包后运行 (PyInstaller)
    # sys._MEIPASS 是 PyInstaller 创建的包含所有解压后资源的临时文件夹路径
    # 假设 PyInstaller 命令将项目根目录下的 font/ 文件夹内容
    # 复制到了 _MEIPASS/font/ (即 _MEIPASS 的根下一级)
    FONT_DIR = (Path(sys._MEIPASS) / "font").resolve()
else:
    # 开发环境运行
    # __file__ 在这里是 .../web/api/settings.py
    # Path(__file__).resolve().parent -> .../web/api/
    # .parent -> .../web/
    # .parent -> .../ (项目根目录 e:/github/manga)
    project_root = Path(__file__).resolve().parent.parent.parent
    FONT_DIR = (project_root / "font").resolve()

logging.info(f"字体目录 (FONT_DIR) 设置为: {FONT_DIR}")
# --- 修改结束 ---

# 数据模型
class SettingItem(BaseModel):
    """设置项模型"""
    key: str
    name: str
    description: str
    value: Any
    type: str  # "string", "int", "float", "bool", "enum"
    options: Optional[List[Dict[str, Any]]] = None  # 对于枚举类型
    min_value: Optional[float] = None  # 对于数值类型
    max_value: Optional[float] = None  # 对于数值类型

class SettingUpdateRequest(BaseModel):
    """设置更新请求模型"""
    key: str
    value: Any

class ModelListRequest(BaseModel):
    apiKey: str
    baseUrl: Optional[str] = None

@router.get("/health")
async def settings_health():
    """设置模块健康检查"""
    return {"status": "healthy", "module": "settings"}

@router.get("/all")
async def get_all_settings():
    """获取所有设置项"""
    try:
        settings = []
        
        settings.append(SettingItem(
            key="mergeTags",
            name="合并标签",
            description="是否合并相似的标签",
            value=config.merge_tags.value,
            type="bool"
        ))
        
        # 日志级别
        settings.append(SettingItem(
            key="logLevel",
            name="日志级别",
            description="应用程序的日志记录级别",
            value=config.log_level.value,
            type="enum",
            options=[
                {"value": "DEBUG", "label": "调试"},
                {"value": "INFO", "label": "信息"},
                {"value": "WARNING", "label": "警告"},
                {"value": "ERROR", "label": "错误"},
                {"value": "CRITICAL", "label": "严重错误"}
            ]
        ))
        
        # OCR 设置
        settings.append(SettingItem(
            key="ocrConfidenceThreshold",
            name="OCR置信度阈值",
            description="OCR识别结果的置信度阈值",
            value=config.ocr_confidence_threshold.value,
            type="float",
            min_value=0.0,
            max_value=1.0
        ))

        # ==================== 页面缓存设置 ====================
        settings.append(SettingItem(
            key="pageCacheEnabled",
            name="启用页面缓存",
            description="是否启用页面缓存功能",
            value=config.page_cache_enabled.value,
            type="bool"
        ))
        settings.append(SettingItem(
            key="pageCacheQuality",
            name="页面缓存质量",
            description="缓存页面的图像质量 (10-100)",
            value=config.page_cache_quality.value,
            type="int",
            min_value=10,
            max_value=100
        ))
        settings.append(SettingItem(
            key="pageCacheMaxSizeMb",
            name="页面缓存最大体积 (MB)",
            description="页面缓存占用的最大磁盘空间 (100-20480 MB)",
            value=config.page_cache_max_size_mb.value,
            type="int",
            min_value=100,
            max_value=20480
        ))
        settings.append(SettingItem(
            key="pageCacheStandardHeight",
            name="页面缓存标准高度",
            description="缓存时图像将被统一到的标准高度 (720-4000 px)",
            value=config.page_cache_standard_height.value,
            type="int",
            min_value=720,
            max_value=4000
        ))
        # --- 页面缓存决策阈值 ---
        settings.append(SettingItem(
            key="pageCacheDecisionRatio",
            name="缓存决策：压缩率阈值",
            description="当(原图/缓存)压缩比超过此值时，倾向于缓存 (0.05-1.0)",
            value=config.page_cache_decision_ratio.value,
            type="float",
            min_value=0.05,
            max_value=1.0
        ))
        settings.append(SettingItem(
            key="pageCacheDecisionSizeMb",
            name="缓存决策：文件大小阈值 (MB)",
            description="当原图文件大小超过此值时，倾向于缓存 (0.5-10.0 MB)",
            value=config.page_cache_decision_size_mb.value,
            type="float",
            min_value=0.5,
            max_value=10.0
        ))
        settings.append(SettingItem(
            key="pageCacheDecisionDimension",
            name="缓存决策：尺寸阈值",
            description="当原图最大边超过此值时，倾向于缓存 (1000-8000 px)",
            value=config.page_cache_decision_dimension.value,
            type="int",
            min_value=1000,
            max_value=8000
        ))

        return {"settings": settings}
        
    except Exception as e:
        logging.error(f"获取设置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

def _get_preferred_font_name(font: TTFont) -> str:
    """
    从 TTFont 对象中提取首选的字体显示名称。
    优先顺序: 中文全名/首选家族名 -> 英文全名 -> 英文家族名
    """
    names = font['name'].names
    best_name = ""

    priorities = [
        (4, 3, 2052), (16, 3, 2052), (4, 3, 1028), (16, 3, 1028),
        (4, 1, 25), (16, 1, 25), (4, 1, 19), (16, 1, 19),
        (4, 3, 1033), (4, 1, 0), (4, 0, 0),
        (16, 3, 1033), (16, 1, 0), (16, 0, 0),
        (1, 3, 1033), (1, 1, 0), (1, 0, 0),
    ]

    found_names = {}
    for record in names:
        key = (record.nameID, record.platformID, record.langID)
        try:
            found_names[key] = record.toUnicode()
        except UnicodeDecodeError:
            logging.warning(f"无法解码字体名称记录: {key} in font {str(getattr(font, 'reader', {}).get('file', 'N/A'))}")
            found_names[key] = record.string.decode('latin-1', errors='replace')

    for p_nameID, p_platformID, p_langID in priorities:
        if (p_nameID, p_platformID, p_langID) in found_names:
            best_name = found_names[(p_nameID, p_platformID, p_langID)]
            break

    if not best_name:
        for record in names:
            if record.nameID == 4:
                try: best_name = record.toUnicode(); break
                except UnicodeDecodeError: pass
        if not best_name:
             for record in names:
                 if record.nameID == 1:
                     try: best_name = record.toUnicode(); break
                     except UnicodeDecodeError: pass
    return best_name

@router.get("/available-fonts")
async def get_available_fonts():
    """获取可用的字体列表"""
    fonts = []
    # FONT_DIR 已经是 Path 对象并且是绝对路径
    absolute_font_dir = FONT_DIR
    logging.debug(f"开始扫描字体目录: {absolute_font_dir}")

    if absolute_font_dir.exists() and absolute_font_dir.is_dir():
        try:
            all_files = os.listdir(absolute_font_dir) # os.listdir 也能接受 Path 对象
            logging.debug(f"在目录 {absolute_font_dir} 中找到的文件: {all_files}")

            font_files = [f for f in all_files if f.lower().endswith(('.ttf', '.otf'))]
            logging.debug(f"过滤后的字体文件 (.ttf, .otf): {font_files}")

            for filename in font_files:
                font_path = absolute_font_dir / filename # 使用 Path 对象的 / 操作符
                try:
                    # TTFont 构造函数可以接受 Path 对象或字符串路径
                    font = TTFont(font_path)
                    display_name = _get_preferred_font_name(font)

                    if not display_name:
                        display_name = os.path.splitext(filename)[0] # filename 是字符串
                        logging.warning(f"  > 无法从元数据提取字体名称，回退到文件名: '{display_name}' for file '{filename}'")
                    
                    fonts.append({
                        "file_name": filename, # 返回文件名字符串
                        "display_name": display_name
                    })
                except Exception as e:
                    logging.error(f"处理字体文件 {str(font_path)} 时出错: {e}", exc_info=True)
        except Exception as e:
             logging.error(f"扫描字体目录 {str(absolute_font_dir)} 时出错: {e}", exc_info=True)
    else:
        logging.warning(f"字体目录不存在或不是一个目录: {str(absolute_font_dir)}")

    logging.debug(f"最终返回的字体列表: {fonts}")
    return {"success": True, "fonts": fonts}

@router.get("/{setting_key}")
async def get_setting(setting_key: str):
    """获取单个设置项"""
    try:
        if not hasattr(config, setting_key):
            raise HTTPException(status_code=404, detail=f"设置项 {setting_key} 不存在")
        
        setting_value = getattr(config, setting_key).value
        
        if hasattr(setting_value, 'value'): # 处理枚举
            setting_value = setting_value.value
        
        return {
            "key": setting_key,
            "value": setting_value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"获取设置 {setting_key} 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{setting_key}")
async def update_setting(setting_key: str, request: SettingUpdateRequest):
    """更新单个设置项"""
    logging.info(f"收到更新设置请求: key={setting_key}, value={request.value}")
    
    new_value = request.value
    config_item = None
    
    # 修复: 特殊处理 logLevel，因为它在 config 中的 key 是 log_level
    if setting_key == "logLevel":
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if new_value in valid_levels:
            config.log_level.value = new_value
            set_level(new_value) # 动态更新全局日志级别
            config_item = config.log_level
        else:
            raise HTTPException(status_code=400, detail="无效的日志等级")
    else:
        # -- 修复: 将前端的camelCase key转换为后端的snake_case key
        key_map = {
            "pageCacheEnabled": "page_cache_enabled",
            "pageCacheQuality": "page_cache_quality",
            "pageCacheMaxSizeMb": "page_cache_max_size_mb",
            "pageCacheStandardHeight": "page_cache_standard_height",
            "pageCacheDecisionRatio": "page_cache_decision_ratio",
            "pageCacheDecisionSizeMb": "page_cache_decision_size_mb",
            "pageCacheDecisionDimension": "page_cache_decision_dimension",
            "ocrConfidenceThreshold": "ocr_confidence_threshold",
            "mergeTags": "merge_tags",
        }
        backend_key = key_map.get(setting_key, setting_key)

        if not hasattr(config, backend_key):
            logging.error(f"更新失败: 设置项 {backend_key} (from {setting_key}) 不存在")
            raise HTTPException(status_code=404, detail=f"设置项 {setting_key} 不存在")

        config_item = getattr(config, backend_key)

        # 对于其他配置项，直接赋值
        # 类型验证由 ConfigItem 的 setter 自动处理
        try:
            config_item.value = new_value
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"无效的值: {e}")

    try:
        logging.info(f"准备保存配置, key={setting_key}, new_value_to_save={config_item.value}")
        config.save()
        logging.info("配置已保存。")
        
        final_value = config_item.value
        if hasattr(final_value, 'value'): # 处理枚举回显
            final_value = final_value.value

        return {
            "success": True,
            "message": f"设置 {setting_key} 已更新",
            "key": setting_key,
            "value": final_value
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"更新或保存设置 {setting_key} 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset")
async def reset_settings():
    """重置所有设置为默认值"""
    try:
        # 重置配置为默认值
        config.merge_tags.value = True
        config.log_level.value = "ERROR"
        
        config.save()
        
        return {
            "success": True,
            "message": "所有设置已重置为默认值"
        }
        
    except Exception as e:
        logging.error(f"重置设置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export")
async def export_settings():
    """导出当前设置"""
    try:
        settings_data = {}
        settings_keys = [
            "merge_tags", "log_level",
            "ocrConfidenceThreshold" # 添加遗漏的配置
        ]

        for key in settings_keys:
            if hasattr(config, key):
                value = getattr(config, key).value
                if hasattr(value, 'value'): # 处理枚举
                    value = value.value
                settings_data[key] = value
        
        # 实际应该使用当前时间
        from datetime import datetime
        settings_data["export_time"] = datetime.utcnow().isoformat() + "Z"
        settings_data["version"] = "1.0.0" # 可以考虑从应用某处获取版本号

        return {
            "settings": settings_data,
            "export_time": settings_data["export_time"],
            "version": settings_data["version"]
        }
        
    except Exception as e:
        logging.error(f"导出设置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import")
async def import_settings(settings_data: Dict[str, Any]):
    """导入设置"""
    try:
        imported_settings = settings_data.get("settings", {}) # 假设导入的数据在 "settings" 键下
        if not isinstance(imported_settings, dict):
             raise HTTPException(status_code=400, detail="导入的数据格式不正确，期望在'settings'键下有字典。")

        imported_count = 0
        failed_keys = []
        
        for key, value in imported_settings.items():
            try:
                if hasattr(config, key):
                    config_item = getattr(config, key)
                    config_item.value = value
                    imported_count += 1
                else:
                    failed_keys.append(key)
            except Exception as e:
                logging.warning(f"导入设置 {key} 失败: {e}")
                failed_keys.append(key)
        
        config.save()
        
        return {
            "success": len(failed_keys) == 0,
            "message": f"成功导入 {imported_count} 个设置",
            "imported_count": imported_count,
            "failed_keys": failed_keys
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"导入设置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
