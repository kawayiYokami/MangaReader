# file: core/ai_translator/__init__.py
"""
AI 翻译器模块
==============

一个现代的、异步的、可配置的翻译引擎。

该模块包提供了一个统一的门面（Facade），用于调用各种大语言模型提供商（如 OpenAI, Gemini 等）
的服务来翻译文本。它负责处理 API 配置、请求分发、速率限制和结果缓存。

主要使用入口:
    from core.ai_translator import ai_translator
    await ai_translator.translate(...)
"""

from .facade import AITranslatorFacade

# 创建一个全局共享的翻译器门面单例，方便外部调用
ai_translator = AITranslatorFacade()

# 公开暴露核心的门面类和单例实例
__all__ = [
    "ai_translator",
    "AITranslatorFacade",
]