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
from core.config import config, ReadingOrder, DisplayMode, Theme
from utils import manga_logger as log

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

log.info(f"字体目录 (FONT_DIR) 设置为: {FONT_DIR}")
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

@router.get("/health")
async def settings_health():
    """设置模块健康检查"""
    return {"status": "healthy", "module": "settings"}

@router.get("/all")
async def get_all_settings():
    """获取所有设置项"""
    try:
        settings = []
        
        # 主题设置
        settings.append(SettingItem(
            key="ThemeMode",
            name="主题模式",
            description="应用程序的主题模式",
            value=config.themeMode.value.value if hasattr(config.themeMode.value, 'value') else str(config.themeMode.value),
            type="enum",
            options=[
                {"value": "Light", "label": "浅色主题"},
                {"value": "Dark", "label": "深色主题"},
                {"value": "Auto", "label": "跟随系统"}
            ]
        ))
        
        # 阅读方向
        settings.append(SettingItem(
            key="readingOrder",
            name="阅读方向",
            description="漫画的阅读方向",
            value=config.reading_order.value.value if hasattr(config.reading_order.value, 'value') else str(config.reading_order.value),
            type="enum",
            options=[
                {"value": "从右到左", "label": "从右到左（日式）"},
                {"value": "从左到右", "label": "从左到右（西式）"}
            ]
        ))
        
        # 显示模式
        settings.append(SettingItem(
            key="displayMode",
            name="显示模式",
            description="漫画的显示模式",
            value=config.display_mode.value.value if hasattr(config.display_mode.value, 'value') else str(config.display_mode.value),
            type="enum",
            options=[
                {"value": "单页显示", "label": "单页显示"},
                {"value": "双页显示", "label": "双页显示"},
                {"value": "自适应", "label": "自适应"}
            ]
        ))
        
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

        # 翻译引擎类型
        settings.append(SettingItem(
            key="translator_type",
            name="翻译引擎",
            description="选择使用的翻译引擎",
            value=config.translator_type.value,
            type="enum",
            options=[
                {"value": "Google", "label": "Google翻译"},
                {"value": "智谱", "label": "智谱AI"}
            ]
        ))

        # 智谱AI翻译设置
        settings.append(SettingItem(
            key="zhipu_api_key",
            name="智谱AI API Key",
            description="智谱AI翻译服务的API Key",
            value="***" if config.zhipu_api_key.value else "",  # 隐藏API密钥
            type="string"
        ))
        settings.append(SettingItem(
            key="zhipu_model",
            name="智谱AI模型",
            description="智谱AI翻译使用的模型",
            value=config.zhipu_model.value,
            type="enum",
            options=[
                {"value": "glm-4-flash", "label": "glm-4-flash"},
                {"value": "glm-4", "label": "glm-4"},
                {"value": "glm-3-turbo", "label": "glm-3-turbo"},
                {"value": "glm-4-flash-250414", "label": "glm-4-flash-250414"}
            ]
        ))

        # Google翻译设置
        settings.append(SettingItem(
            key="google_api_key",
            name="Google API Key",
            description="Google翻译服务的API Key",
            value="***" if config.google_api_key.value else "",  # 隐藏API密钥
            type="string"
        ))
        
        # 字体设置
        settings.append(SettingItem(
            key="fontName",
            name="字体名称",
            description="翻译文本使用的字体名称",
            value=config.font_name.value,
            type="string" # 这个值是从 available-fonts 的 file_name 中选取的
        ))

        return {"settings": settings}
        
    except Exception as e:
        log.error(f"获取设置失败: {e}")
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
            log.warning(f"无法解码字体名称记录: {key} in font {str(getattr(font, 'reader', {}).get('file', 'N/A'))}")
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
    log.debug(f"开始扫描字体目录: {absolute_font_dir}")

    if absolute_font_dir.exists() and absolute_font_dir.is_dir():
        try:
            all_files = os.listdir(absolute_font_dir) # os.listdir 也能接受 Path 对象
            log.debug(f"在目录 {absolute_font_dir} 中找到的文件: {all_files}")

            font_files = [f for f in all_files if f.lower().endswith(('.ttf', '.otf'))]
            log.debug(f"过滤后的字体文件 (.ttf, .otf): {font_files}")

            for filename in font_files:
                font_path = absolute_font_dir / filename # 使用 Path 对象的 / 操作符
                log.debug(f"正在处理字体文件: {font_path}")
                try:
                    # TTFont 构造函数可以接受 Path 对象或字符串路径
                    font = TTFont(font_path) 
                    display_name = _get_preferred_font_name(font)

                    if not display_name:
                        display_name = os.path.splitext(filename) # filename 是字符串
                        log.warning(f"  > 无法从元数据提取字体名称，回退到文件名: '{display_name}' for file '{filename}'")
                    
                    fonts.append({
                        "file_name": filename, # 返回文件名字符串
                        "display_name": display_name
                    })
                except Exception as e:
                    log.error(f"处理字体文件 {str(font_path)} 时出错: {e}", exc_info=True)
        except Exception as e:
             log.error(f"扫描字体目录 {str(absolute_font_dir)} 时出错: {e}", exc_info=True)
    else:
        log.warning(f"字体目录不存在或不是一个目录: {str(absolute_font_dir)}")

    log.debug(f"最终返回的字体列表: {fonts}")
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
        log.error(f"获取设置 {setting_key} 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{setting_key}")
async def update_setting(setting_key: str, request: SettingUpdateRequest):
    """更新单个设置项"""
    log.info(f"收到更新设置请求: key={setting_key}, value={request.value}")
    try:
        if not hasattr(config, setting_key):
            log.error(f"更新失败: 设置项 {setting_key} 不存在")
            raise HTTPException(status_code=404, detail=f"设置项 {setting_key} 不存在")
        
        config_item = getattr(config, setting_key)
        new_value = request.value
        
        if setting_key == "ThemeMode":
            log.info(f"正在处理主题模式更新，新值为: {new_value}")
            if new_value == "Light": config_item.value = Theme.LIGHT
            elif new_value == "Dark": config_item.value = Theme.DARK
            elif new_value == "Auto": config_item.value = Theme.AUTO
            else:
                log.error(f"无效的主题模式: {new_value}")
                raise HTTPException(status_code=400, detail="无效的主题模式")
                
        elif setting_key == "readingOrder":
            if new_value == ReadingOrder.RIGHT_TO_LEFT.value: config_item.value = ReadingOrder.RIGHT_TO_LEFT.value
            elif new_value == ReadingOrder.LEFT_TO_RIGHT.value: config_item.value = ReadingOrder.LEFT_TO_RIGHT.value
            else: raise HTTPException(status_code=400, detail="无效的阅读方向")
                
        elif setting_key == "displayMode":
            if new_value == DisplayMode.SINGLE.value: config_item.value = DisplayMode.SINGLE.value
            elif new_value == DisplayMode.DOUBLE.value: config_item.value = DisplayMode.DOUBLE.value
            elif new_value == DisplayMode.ADAPTIVE.value: config_item.value = DisplayMode.ADAPTIVE.value
            else: raise HTTPException(status_code=400, detail="无效的显示模式")
        
        elif setting_key == "translatorType":
            if new_value in ["Google", "智谱"]: config_item.value = new_value
            else:
                log.error(f"更新设置 translatorType 失败: 无效的翻译引擎类型 '{new_value}'")
                raise HTTPException(status_code=400, detail="无效的翻译引擎类型")
        elif setting_key == "zhipu_api_key": config_item.value = new_value
        elif setting_key == "zhipu_model":
            if new_value in ["glm-4-flash", "glm-4", "glm-3-turbo", "glm-4-flash-250414"]: config_item.value = new_value
            else: raise HTTPException(status_code=400, detail="无效的智谱AI模型")
        elif setting_key == "google_api_key": config_item.value = new_value
        elif setting_key == "fontName": config_item.value = new_value
        elif setting_key == "logLevel": # 注意这里应该是 logLevel 不是 log_level
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if new_value in valid_levels:
                config_item.value = new_value
                # 确保 MangaLogger 实例存在并更新其级别
                if hasattr(log, 'MangaLogger'): # manga_logger.py 中定义的类名
                    manga_logger_instance = log.MangaLogger.get_instance()
                    if manga_logger_instance:
                        manga_logger_instance.set_level(new_value)
                log.info(f"日志等级已更新为: {new_value}")
            else:
                raise HTTPException(status_code=400, detail="无效的日志等级")
        else:
            config_item.value = new_value
        
        log.info(f"准备保存配置, key={setting_key}, new_value_to_save={config_item.value}")
        config.save()
        log.info(f"配置已保存。")
        
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
        log.error(f"更新设置 {setting_key} 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset")
async def reset_settings():
    """重置所有设置为默认值"""
    try:
        # 重置配置为默认值
        config.themeMode.value = Theme.AUTO
        config.reading_order.value = ReadingOrder.LEFT_TO_RIGHT.value # 确保使用枚举的值
        config.display_mode.value = DisplayMode.DOUBLE.value
        config.merge_tags.value = True
        config.log_level.value = "ERROR"
        config.translator_type.value = "智谱"
        config.zhipu_api_key.value = ""
        config.zhipu_model.value = "glm-4-flash"
        config.google_api_key.value = ""
        config.font_name.value = "SourceHanSerifCN-Heavy.ttf" # 恢复默认字体或空字符串
        
        config.save()
        
        return {
            "success": True,
            "message": "所有设置已重置为默认值"
        }
        
    except Exception as e:
        log.error(f"重置设置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export")
async def export_settings():
    """导出当前设置"""
    try:
        settings_data = {}
        settings_keys = [
            "themeMode", "reading_order", "display_mode",
            "merge_tags", "log_level",
            "translator_type", "zhipu_model", "font_name",
            "ocrConfidenceThreshold" # 添加遗漏的配置
        ]

        for key in settings_keys:
            if hasattr(config, key):
                value = getattr(config, key).value
                if hasattr(value, 'value'): # 处理枚举
                    value = value.value
                settings_data[key] = value

        settings_data["zhipu_api_key_set"] = bool(config.zhipu_api_key.value)
        settings_data["google_api_key_set"] = bool(config.google_api_key.value)
        
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
        log.error(f"导出设置失败: {e}")
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
                    # 特殊处理枚举类型，确保赋的是枚举成员或其 .value
                    if key == "ThemeMode":
                        config_item.value = Theme(value) if isinstance(value, str) else value
                    elif key == "readingOrder":
                         # 假设导入的是 "从右到左" 这样的字符串值
                        enum_member = next((e for e in ReadingOrder if e.value == value), None)
                        if enum_member: config_item.value = enum_member.value
                        else: raise ValueError(f"无效的 readingOrder 值: {value}")
                    elif key == "displayMode":
                        enum_member = next((e for e in DisplayMode if e.value == value), None)
                        if enum_member: config_item.value = enum_member.value
                        else: raise ValueError(f"无效的 displayMode 值: {value}")
                    else:
                        config_item.value = value
                    imported_count += 1
                else:
                    failed_keys.append(key)
            except Exception as e:
                log.warning(f"导入设置 {key} 失败: {e}")
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
        log.error(f"导入设置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
