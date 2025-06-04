"""
设置管理 API

提供应用配置管理功能的RESTful接口。
复用core.config的配置系统。
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from enum import Enum

# 导入核心业务逻辑
from core.config import config, ReadingOrder, DisplayMode
from qfluentwidgets import Theme
from utils import manga_logger as log

router = APIRouter()

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
        
        # 翻译设置
        settings.append(SettingItem(
            key="translateTitle",
            name="自动翻译",
            description="是否启用自动翻译功能",
            value=config.translate_title.value,
            type="bool"
        ))
        
        settings.append(SettingItem(
            key="simplifyChinese",
            name="简体化",
            description="将繁体中文转换为简体中文",
            value=config.simplify_chinese.value,
            type="bool"
        ))
        
        settings.append(SettingItem(
            key="mergeTags",
            name="合并标签",
            description="是否合并相似的标签",
            value=config.merge_tags.value,
            type="bool"
        ))
        
        # WebP质量
        settings.append(SettingItem(
            key="webpQuality",
            name="WebP质量",
            description="WebP图片的压缩质量",
            value=config.webp_quality.value,
            type="int",
            min_value=0,
            max_value=100
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
        
        return {"settings": settings}
        
    except Exception as e:
        log.error(f"获取设置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        
        # 更新配置值
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
        config.translate_title.value = False
        config.simplify_chinese.value = False
        config.merge_tags.value = True
        config.webp_quality.value = 80
        config.log_level.value = "ERROR"
        
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
            "translate_title", "simplify_chinese", "merge_tags",
            "webp_quality", "log_level"
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
