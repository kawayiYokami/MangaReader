"""
设置管理 API

提供应用配置管理功能的RESTful接口。
复用core.config的配置系统。
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from enum import Enum
import os
from fontTools.ttLib import TTFont

# 导入核心业务逻辑
from core.config import config, ReadingOrder, DisplayMode
from qfluentwidgets import Theme
from utils import manga_logger as log

router = APIRouter()

# 字体目录，根据实际部署情况调整
FONT_DIR = "font"

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
            key="themeMode",
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
                {"value": "单页", "label": "单页显示"},
                {"value": "双页", "label": "双页显示"},
                {"value": "连续", "label": "连续滚动"}
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
            key="translatorType",
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
            key="zhipuApiKey",
            name="智谱AI API Key",
            description="智谱AI翻译服务的API Key",
            value=config.zhipu_api_key.value,
            type="string"
        ))
        settings.append(SettingItem(
            key="zhipuModel",
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
            key="googleApiKey",
            name="Google API Key",
            description="Google翻译服务的API Key",
            value=config.google_api_key.value,
            type="string"
        ))
        
        # 字体设置
        settings.append(SettingItem(
            key="fontName",
            name="字体名称",
            description="翻译文本使用的字体名称",
            value=config.font_name.value,
            type="string"
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

    # 定义名称查找优先级 (NameID, PlatformID, LanguageID)
    # Language IDs: 2052 (zh-CN), 1028 (zh-TW), 25 (zh-Hans Mac), 19 (zh-Hant Mac), 0/1033 (en)
    # Name IDs: 4 (Full Name), 16 (Typographic Family Name), 1 (Family Name)
    priorities = [
        # 中文 Windows (优先全名/首选名)
        (4, 3, 2052), (16, 3, 2052),
        (4, 3, 1028), (16, 3, 1028),
        # 中文 Mac (优先全名/首选名)
        (4, 1, 25), (16, 1, 25),
        (4, 1, 19), (16, 1, 19),
        # 英文/通用 (全名优先)
        (4, 3, 1033), (4, 1, 0), (4, 0, 0), # Windows English, Mac Roman, Any Unicode
        (16, 3, 1033), (16, 1, 0), (16, 0, 0),
        # 英文/通用 (家族名次之)
        (1, 3, 1033), (1, 1, 0), (1, 0, 0),
    ]

    found_names = {}
    for record in names:
        key = (record.nameID, record.platformID, record.langID)
        # 存储所有找到的名称记录，以便按优先级查找
        # 确保使用 toUnicode() 解码
        try:
            found_names[key] = record.toUnicode()
        except UnicodeDecodeError:
            log.warning(f"无法解码字体名称记录: {key} in font {font.sfntVersion}") # 添加警告
            found_names[key] = record.string.decode('latin-1', errors='replace') # 尝试备用解码

    # 按优先级查找
    for p_nameID, p_platformID, p_langID in priorities:
        if (p_nameID, p_platformID, p_langID) in found_names:
            best_name = found_names[(p_nameID, p_platformID, p_langID)]
            log.debug(f"  > 找到了优先名称 (ID={p_nameID}, Plat={p_platformID}, Lang={p_langID}): '{best_name}'")
            break # 找到最高优先级的就停止

    # 如果上面都没找到，再做一次不区分语言的全名和家族名查找 (作为最后手段)
    if not best_name:
        for record in names:
            if record.nameID == 4: # 全名
                try: best_name = record.toUnicode(); break
                except UnicodeDecodeError: pass
        if not best_name:
             for record in names:
                 if record.nameID == 1: # 家族名
                     try: best_name = record.toUnicode(); break
                     except UnicodeDecodeError: pass

    return best_name

@router.get("/available-fonts")
async def get_available_fonts():
    """获取可用的字体列表"""
    fonts = []
    absolute_font_dir = os.path.abspath(FONT_DIR)
    log.debug(f"开始扫描字体目录: {absolute_font_dir}") # Log 1: Absolute path

    if os.path.exists(absolute_font_dir) and os.path.isdir(absolute_font_dir):
        try:
            all_files = os.listdir(absolute_font_dir)
            log.debug(f"在目录 {absolute_font_dir} 中找到的文件: {all_files}") # Log 2: All files found

            font_files = [f for f in all_files if f.lower().endswith(('.ttf', '.otf'))]
            log.debug(f"过滤后的字体文件 (.ttf, .otf): {font_files}") # Log 3: Filtered font files

            for filename in font_files:
                font_path = os.path.join(absolute_font_dir, filename)
                log.debug(f"正在处理字体文件: {font_path}") # Log 4: Processing file
                try:
                    font = TTFont(font_path)
                    # 使用新的辅助函数提取首选名称
                    display_name = _get_preferred_font_name(font)

                    # 如果辅助函数未能提取到名称，则回退到文件名
                    if not display_name:
                        display_name = os.path.splitext(filename)[0]
                        log.warning(f"  > 无法从元数据提取字体名称，回退到文件名: '{display_name}' for file '{filename}'")
                    else:
                         log.debug(f"  > 最终选择的字体名称: '{display_name}' for file '{filename}'")

                    fonts.append({
                        "file_name": filename,
                        "display_name": display_name
                    })
                except Exception as e:
                    # Log 5: Specific error during font parsing
                    log.error(f"处理字体文件 {filename} 时出错: {e}", exc_info=True)
        except Exception as e:
             log.error(f"扫描字体目录 {absolute_font_dir} 时出错: {e}", exc_info=True)
    else:
        log.warning(f"字体目录不存在或不是一个目录: {absolute_font_dir}")

    log.debug(f"最终返回的字体列表: {fonts}") # Log 6: Final list
    return {"success": True, "fonts": fonts}

@router.get("/{setting_key}")
async def get_setting(setting_key: str):
    """获取单个设置项"""
    try:
        if not hasattr(config, setting_key):
            raise HTTPException(status_code=404, detail=f"设置项 {setting_key} 不存在")
        
        setting_value = getattr(config, setting_key).value
        
        # 处理枚举类型
        if hasattr(setting_value, 'value'):
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
    try:
        if not hasattr(config, setting_key):
            raise HTTPException(status_code=404, detail=f"设置项 {setting_key} 不存在")
        
        # 获取配置项
        config_item = getattr(config, setting_key)
        
        # 根据设置类型进行值转换和验证
        new_value = request.value
        
        # 特殊处理枚举类型
        if setting_key == "themeMode":
            if new_value == "Light":
                new_value = Theme.LIGHT
            elif new_value == "Dark":
                new_value = Theme.DARK
            elif new_value == "Auto":
                new_value = Theme.AUTO
            else:
                raise HTTPException(status_code=400, detail="无效的主题模式")
                
        elif setting_key == "readingOrder":
            if new_value == "从右到左":
                new_value = ReadingOrder.RIGHT_TO_LEFT
            elif new_value == "从左到右":
                new_value = ReadingOrder.LEFT_TO_RIGHT
            else:
                raise HTTPException(status_code=400, detail="无效的阅读方向")
                
        elif setting_key == "displayMode":
            if new_value == "单页":
                new_value = DisplayMode.SINGLE_PAGE
            elif new_value == "双页":
                new_value = DisplayMode.DOUBLE_PAGE
            elif new_value == "连续":
                new_value = DisplayMode.CONTINUOUS
            else:
                raise HTTPException(status_code=400, detail="无效的显示模式")
        
        elif setting_key == "translatorType":
            if new_value in ["Google", "智谱"]:
                config_item.value = new_value
            else:
                log.error(f"更新设置 translatorType 失败: 无效的翻译引擎类型 '{new_value}'")
                raise HTTPException(status_code=400, detail="无效的翻译引擎类型")
        elif setting_key == "zhipuApiKey":
            config_item.value = new_value
        elif setting_key == "zhipuModel":
            if new_value in ["glm-4-flash", "glm-4", "glm-3-turbo", "glm-4-flash-250414"]:
                config_item.value = new_value
            else:
                raise HTTPException(status_code=400, detail="无效的智谱AI模型")
        elif setting_key == "googleApiKey":
            config_item.value = new_value
        elif setting_key == "fontName":
            # 验证字体名称是否存在于可用字体列表中（可选，但推荐）
            # 简化处理：直接设置，前端会负责校验和显示
            config_item.value = new_value
        else:
            # 对于其他通用设置，直接更新
            config_item.value = new_value
        
        # 保存配置
        config.save()
        
        return {
            "success": True,
            "message": f"设置 {setting_key} 已更新",
            "key": setting_key,
            "value": new_value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"更新设置 {setting_key} 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset")
async def reset_settings():
    """重置所有设置为默认值"""
    try:
        # 重置配置为默认值
        config.themeMode.value = Theme.AUTO
        config.reading_order.value = ReadingOrder.RIGHT_TO_LEFT
        config.display_mode.value = DisplayMode.SINGLE_PAGE
        config.merge_tags.value = True
        config.log_level.value = "ERROR"
        config.translator_type.value = "智谱"
        config.zhipu_api_key.value = ""
        config.zhipu_model.value = "glm-4-flash"
        config.google_api_key.value = ""
        config.font_name.value = ""
        
        # 保存配置
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
        
        # 导出主要设置
        settings_keys = [
            "themeMode", "reading_order", "display_mode",
            "merge_tags", "log_level",
            "translator_type", "zhipu_api_key", "zhipu_model",
            "google_api_key", "font_name"
        ]
        
        for key in settings_keys:
            if hasattr(config, key):
                value = getattr(config, key).value
                # 处理枚举类型
                if hasattr(value, 'value'):
                    value = value.value
                settings_data[key] = value
        
        return {
            "settings": settings_data,
            "export_time": "2024-01-01T00:00:00Z",  # 实际应该使用当前时间
            "version": "1.0.0"
        }
        
    except Exception as e:
        log.error(f"导出设置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import")
async def import_settings(settings_data: Dict[str, Any]):
    """导入设置"""
    try:
        imported_count = 0
        failed_keys = []
        
        for key, value in settings_data.items():
            try:
                if hasattr(config, key):
                    config_item = getattr(config, key)
                    config_item.value = value
                    imported_count += 1
                else:
                    failed_keys.append(key)
            except Exception as e:
                log.warning(f"导入设置 {key} 失败: {e}")
                failed_keys.append(key)
        
        # 保存配置
        config.save()
        
        return {
            "success": len(failed_keys) == 0,
            "message": f"成功导入 {imported_count} 个设置",
            "imported_count": imported_count,
            "failed_keys": failed_keys
        }
        
    except Exception as e:
        log.error(f"导入设置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
