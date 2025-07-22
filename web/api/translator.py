# file: web/api/translator.py
"""
AI 翻译器相关 API
"""
from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any
from dataclasses import asdict

from core.config import config
from core.ai_translator.config_manager import api_config_manager
from core.ai_translator.agents.agent_manager import agent_definition_manager
from core.ai_translator.data_models import APIConfig, ImageTranslationResult
from core.ai_translator.facade import AITranslatorFacade

router = APIRouter()

# 全局的 Facade 实例
ai_translator_facade = AITranslatorFacade()

@router.get("/api/translators/configs", response_model=List[APIConfig])
async def get_translator_configs():
    """
    获取所有可用的 AI 翻译器配置。
    """
    return api_config_manager.list_configs()

@router.get("/api/translators/agents")
async def get_translator_agents():
    """
    获取所有可用的翻译智能体定义。
    """
    # AgentDefinition 没有直接的序列化方法，我们手动提取所需字段
    definitions = agent_definition_manager.list_definitions()
    return [
        {
            "name": agent.name,
            "description": agent.description,
            "agent_type": agent.agent_type
        }
        for agent in definitions
    ]

@router.post("/api/translators/configs", status_code=204)
async def update_translator_configs(configs: List[APIConfig]):
    """
    更新并保存 AI 翻译器配置列表。
    """
    try:
        # 将 dataclass 对象列表转换为字典列表
        configs_dict = [asdict(c) for c in configs]
        config.set('api_translator_configs', 'api_translator_configs', configs_dict)
        
        # 触发配置热重载
        api_config_manager.reload()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存配置失败: {e}")

@router.post("/api/actions/translate_page", response_model=List[ImageTranslationResult])
async def translate_page_action(payload: Dict[str, Any] = Body(...)):
    """
    对指定的漫画页面执行 AI 翻译。
    所有参数通过请求体传递。
    """
    try:
        # 从 payload 中提取所有必要参数
        manga_path = payload.get("manga_path")
        page_index = payload.get("page_index")
        image_data = payload.get("image_data") # base64 编码的图片数据
        config_name = payload.get("config_name")
        target_lang = payload.get("target_lang", "CHS") # 默认为中文

        # 验证基本参数
        if not all([manga_path, page_index is not None, image_data, config_name]):
             raise HTTPException(status_code=400, detail="缺少必要的翻译参数: manga_path, page_index, image_data, config_name")

        # 硬编码智能体名称
        agent_name = "manga_script_generation"

        # Base64 解码
        import base64
        image_bytes = base64.b64decode(image_data)

        results = await ai_translator_facade.translate_image(
            images_data=[image_bytes],
            config_name=config_name,
            agent_name=agent_name,
            manga_path=manga_path,
            page_index=page_index,
            target_lang=target_lang
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"翻译失败: {e}")