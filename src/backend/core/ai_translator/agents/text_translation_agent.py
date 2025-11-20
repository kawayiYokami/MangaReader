# file: core/ai_translator/agents/text_translation_agent.py
"""
文本翻译智能体
===============

负责处理传统的文本翻译任务，包括构建请求和解析响应。
这是对原 prompt_builder.py 功能的迁移和封装。
"""
import logging
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent
from ..data_models import (
    APIConfig,
    TranslationResult,
    TranslationStatus,
    TranslationMode,
)

class TextTranslationAgent(BaseAgent):
    """
    一个专门用于执行文本翻译任务的智能体。
    它的行为由外部传入的 system_prompt_template 决定。
    """

    def build_system_prompt(
        self,
        *,
        target_lang: str,
        manga_title: Optional[str],
        mode: TranslationMode,
        special_prompt: Optional[str],
        **kwargs: Any
    ) -> str:
        """使用模板和动态参数构建最终的系统提示。"""
        
        # 1. 构建动态的上下文片段
        manga_title_context = ""
        if manga_title:
            manga_title_context = f"\n当前翻译的漫画是《{manga_title}》，请在翻译时考虑其特有的世界观和角色对话风格。"

        mode_instruction = ""
        if mode == TranslationMode.MULTI:
            mode_instruction = (
                "\n用户会以 `<i><s>...</s></i>` 的格式提供多个文本。"
                "你的回答也必须严格遵循此格式，将每个 `<s>` 标签内的文本翻译后放回原位。"
                "如果某个 `<s>` 标签内的文本不需要翻译（例如拟声词、SFX），请在返回的 `<s>` 标签中添加 `nt=\"1\"` 属性，并原样保留文本。"
                "示例：输入 `<i><s>こんにちは</s></i><i><s>ドーン</s></i>`，应返回 `<i><s>你好</s></i><i><s nt=\"1\">ドーン</s></i>`。"
            )

        special_prompt_section = ""
        if special_prompt:
            special_prompt_section = f"\n\n--- 本次任务的特殊指令 ---\n{special_prompt}"

        # 2. 使用模板进行格式化
        return self.system_prompt_template.format(
            target_lang=target_lang,
            manga_title_context=manga_title_context,
            mode_instruction=mode_instruction,
            special_prompt_section=special_prompt_section
        )

    def build_request_payload(
        self,
        *,
        config: APIConfig,
        texts: List[str],
        mode: TranslationMode,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        构建发送给文本 AI API 的请求体。
        """
        # 注意：kwargs 现在包含了构建 system_prompt 所需的所有参数
        system_prompt = self.build_system_prompt(mode=mode, **kwargs)
        user_prompt = self._build_user_prompt(texts, mode)
        
        # 构建 OpenAI 兼容的 payload
        payload = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": config.temperature,
        }
        return payload

    def parse_response(
        self, 
        response_data: Dict[str, Any],
        original_texts: List[str],
        **kwargs: Any
    ) -> List[TranslationResult]:
        """
        解析来自文本 AI API 的响应。
        """
        try:
            response_text = response_data["choices"][0]["message"]["content"]
            unpacked_results = self._unpack_response(response_text, len(original_texts))

            results = [
                TranslationResult(
                    original_text=original,
                    translated_text=res["text"],
                    status=TranslationStatus.SUCCESS if res["needs_translation"] else TranslationStatus.NOT_TRANSLATED,
                    needs_translation=res["needs_translation"],
                    error_message=None
                )
                for original, res in zip(original_texts, unpacked_results)
            ]
            return results

        except (KeyError, IndexError, TypeError) as e:
            logging.error(f"解析文本翻译响应失败: {e}", exc_info=True)
            return [
                TranslationResult(
                    original_text=text,
                    status=TranslationStatus.FAILURE,
                    error_message=f"Failed to parse AI response: {e}"
                ) for text in original_texts
            ]

    @staticmethod
    def _build_user_prompt(texts: List[str], mode: TranslationMode) -> str:
        """
        根据模式构建用户提示。
        迁移自 prompt_builder.py。
        """
        if mode == TranslationMode.SINGLE:
            return texts[0]
        else:
            # 使用 XML 风格的紧凑格式
            packed_text = "".join(f"<i><s>{text}</s></i>" for text in texts)
            return packed_text

    @staticmethod
    def _unpack_response(response_text: str, expected_count: int) -> List[Dict[str, Any]]:
        """
        解析模型的 XML 风格响应。
        迁移自 prompt_builder.py。
        """
        from xml.etree import ElementTree as ET
        
        results = []
        try:
            # 为了解析，需要一个根元素
            root = ET.fromstring(f"<root>{response_text}</root>")
            for item in root.findall('i'):
                original_s = item.find('s')
                if original_s is not None:
                    is_not_translatable = original_s.attrib.get('nt') == '1'
                    results.append({
                        "text": original_s.text or "",
                        "needs_translation": not is_not_translatable
                    })
        except ET.ParseError:
            logging.error(f"XML 解析失败: '{response_text}'")
            # 如果解析失败，返回预期数量的错误结果
            return [{"text": f"Error: Invalid XML format from AI: {response_text}", "needs_translation": True}] * expected_count

        # 校验数量
        if len(results) == 0 and expected_count > 0:
            logging.warning(f"AI 返回了有效的 XML，但其中不包含任何翻译标签 <i>。响应: '{response_text}'")
            return [{"text": f"Error: AI response was empty or malformed: {response_text}", "needs_translation": True}] * expected_count
        
        if len(results) != expected_count:
            logging.warning(f"AI 返回的文本数量 ({len(results)}) 与预期 ({expected_count}) 不符。")
            # 填充或截断以匹配预期数量
            if len(results) > expected_count:
                return results[:expected_count]
            else:
                missing_count = expected_count - len(results)
                results.extend([{"text": "Error: Missing translation", "needs_translation": True}] * missing_count)
        
        return results