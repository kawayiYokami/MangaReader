# file: core/ai_translator/agents/image_translation_agent.py
"""
图片翻译智能体
===============

负责处理图片翻译任务，包括构建多模态请求和解析响应。
"""
import logging
import time
import yaml
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent
from ..data_models import (
    APIConfig,
    DialogueLine,
    ImageTranslationResult,
    TranslationScript,
    TranslationStatus,
)
from ..image_utils import preprocess_and_encode_image


class ImageTranslationAgent(BaseAgent):
    """
    一个专门用于执行端到端图片翻译任务的智能体。
    """

    def build_system_prompt(
        self,
        **kwargs: Any
    ) -> str:
        """使用模板和动态参数构建最终的系统提示。"""
        # 只传递模板中实际存在的占位符
        return self.system_prompt_template.format(**kwargs)

    def build_request_payload(
        self,
        *,
        config: APIConfig,
        images_data: List[bytes],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        构建发送给多模态 AI API 的请求体。
        """
        image_data = images_data[0]
        base64_image, (width, height) = preprocess_and_encode_image(image_data)

        # 动态地将尺寸注入到 system_prompt 中
        prompt_kwargs = {"width": width, "height": height}
        prompt_kwargs.update(kwargs)
        system_prompt = self.build_system_prompt(**prompt_kwargs)
        
        user_prompt_content = [
            {"type": "text", "text": "请处理这张图片。"},
            {"type": "image_url", "image_url": {"url": base64_image}},
        ]
        
        payload = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt_content},
            ],
            "temperature": config.temperature,
        }
        logging.debug(f"构建的图片翻译请求体 (部分): model={config.model}, image_count={len(images_data)}")
        return payload

    def _parse_script_yaml(self, content: str) -> List[ImageTranslationResult]:
        """解析来自剧本生成 agent 的 YAML 响应。"""
        logging.debug("尝试将响应解析为剧本 YAML 格式...")
        cleaned_str = content.strip()

        # 处理AI在遇到空页面等情况时返回的非YAML通用语
        if cleaned_str == "暂无返回":
            logging.info("AI返回'暂无返回'，视为空白页处理，返回空剧本。")
            return [ImageTranslationResult(
                status=TranslationStatus.SUCCESS,
                translation_script=TranslationScript(script=[]),
                raw_response={"message": "Handled '暂无返回' as empty page."}
            )]

        cleaned_yaml_str = cleaned_str.removeprefix("```yaml").removesuffix("```").strip()
        
        # 有时AI会在开头加上 ---
        if cleaned_yaml_str.startswith("---"):
            cleaned_yaml_str = cleaned_yaml_str[3:].lstrip()

        ai_data = yaml.safe_load(cleaned_yaml_str)
        
        if not isinstance(ai_data, dict) or "script" not in ai_data:
            raise ValueError("YAML 根节点必须是一个包含 'script' 键的字典。")

        dialogue_lines = []
        raw_script = ai_data.get("script", [])
        if not isinstance(raw_script, list):
             raise ValueError("'script' 键的值必须是一个列表。")

        for item in raw_script:
            line_data = item.get("dialogue_line")
            if not isinstance(line_data, dict):
                logging.warning(f"跳过格式不正确的剧本条目: {item}")
                continue
            
            dialogue_lines.append(
                DialogueLine(
                    speaker_id=int(line_data.get("speaker_id", 0)),
                    original_text=line_data.get("original_text", ""),
                    translated_text=line_data.get("translated_text", ""),
                )
            )
        
        script = TranslationScript(script=dialogue_lines)
        logging.info(f"成功从剧本响应中解析出 {len(dialogue_lines)} 行对话。")
        
        return [ImageTranslationResult(
            status=TranslationStatus.SUCCESS,
            translation_script=script,
            raw_response=ai_data
        )]

    def parse_response(
        self, response_data: Dict[str, Any], **kwargs: Any
    ) -> List[ImageTranslationResult]:
        """
        解析来自 AI API 的响应。
        """
        if "error" in response_data:
            error_msg = response_data["error"].get("message", "Unknown API error")
            logging.error(f"图片翻译任务失败: {error_msg}")
            return [ImageTranslationResult(status=TranslationStatus.FAILURE, error_message=error_msg)]

        content_str = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content_str:
            logging.warning("AI 返回的 content 字段为空。")
            return [ImageTranslationResult(status=TranslationStatus.FAILURE, error_message="AI response content is empty.")]

        try:
            return self._parse_script_yaml(content_str)
        except (yaml.YAMLError, ValueError, TypeError, KeyError) as e:
            logging.error(f"解析剧本 YAML 失败: {e}", exc_info=True)
            logging.debug(f"无法解析的原始响应内容:\n---\n{content_str}\n---")
            return [ImageTranslationResult(status=TranslationStatus.FAILURE, error_message=f"Failed to parse AI response: {e}")]