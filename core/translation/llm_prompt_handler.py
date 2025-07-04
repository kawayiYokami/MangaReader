# file: core/translation/llm_prompt_handler.py
import json
from typing import List, Dict, Tuple
from core.data_models import TranslationResult

class LLMPromptHandler:
    """
    一个专门处理LLM翻译任务中Prompt打包和结果解析的工具。

    它的核心功能是：
    1.  打包（pack）：将一个长的文本列表，智能地打包成一个或多个满足特定长度约束的、
        带索引的JSON字符串块（chunks）。
    2.  解包（unpack）：将从LLM API返回的多个JSON字符串块，安全地解析并合并成
        一个统一的、易于使用的原始文本到译文的映射。
    """

    def __init__(self, max_chars: int = 80000):
        """
        初始化Prompt处理器。

        Args:
            max_chars (int): 每个打包后JSON字符串块的最大字符数。
                           这是一个保守的估计，以避免超出大多数模型的token限制。
                           例如，100k token约等于400k字符，我们使用80k作为安全值。
        """
        if max_chars <= 100:
            raise ValueError("max_chars必须大于100，以确保至少能容纳一个条目。")
        self.max_chars = max_chars

    def pack_texts(self, texts: List[str]) -> List[str]:
        """
        将文本列表打包成多个符合长度限制的JSON字符串块。

        Args:
            texts (List[str]): 原始待翻译的文本列表。

        Returns:
            List[str]: 一个JSON字符串列表，每个字符串都是一个准备发给API的独立任务。
        """
        if not texts:
            return []

        chunks = []
        current_chunk_dict = {}
        
        for i, text in enumerate(texts):
            # 尝试将下一个文本添加到当前块
            potential_next_item = {str(i): text}
            
            # 估算添加新条目后整个字典转换成JSON字符串的长度
            # 我们需要考虑逗号、引号、索引等额外字符的开销
            current_json_str = json.dumps(current_chunk_dict, ensure_ascii=False)
            # 估算下一个条目的JSON长度
            next_item_str = json.dumps(potential_next_item, ensure_ascii=False)[1:-1] # 移除{},保留内容
            
            # 如果当前块是空的，额外开销是2个花括号{}
            # 如果不是空的，额外开销是1个逗号,
            overhead = 2 if not current_chunk_dict else 1
            
            if len(current_json_str) + len(next_item_str) + overhead > self.max_chars:
                # 当前块已满，将其JSON字符串存入列表
                if current_chunk_dict:
                    chunks.append(json.dumps(current_chunk_dict, ensure_ascii=False))
                
                # 为新条目开始一个新块
                current_chunk_dict = {str(i): text}
            else:
                # 当前块未满，添加新条目
                current_chunk_dict[str(i)] = text

        # 添加最后一个未满的块
        if current_chunk_dict:
            chunks.append(json.dumps(current_chunk_dict, ensure_ascii=False))

        return chunks

    def unpack_results(self,
                         api_responses_json_strings: List[str],
                         original_texts: List[str]) -> Dict[str, TranslationResult]:
        """
        解析并合并来自API的多个JSON字符串响应。
        现在它会处理更复杂的、包含 `text` 和 `translated` 标志的JSON结构。

        Args:
            api_responses_json_strings (List[str]): 从LLM API收到的JSON字符串响应列表。
            original_texts (List[str]): 原始的、未经任何处理的待翻译文本列表，顺序必须与打包时一致。

        Returns:
            Dict[str, TranslationResult]: 一个从原始文本映射到其 TranslationResult 对象的字典。
        """
        final_translation_map: Dict[str, TranslationResult] = {}

        for json_str in api_responses_json_strings:
            try:
                translated_chunk_dict = json.loads(json_str)
            except json.JSONDecodeError:
                print(f"[LLMPromptHandler] Error: Failed to decode JSON from API response: {json_str[:200]}...")
                continue

            if not isinstance(translated_chunk_dict, dict):
                print(f"[LLMPromptHandler] Warning: API response is not a dictionary: {json_str[:200]}...")
                continue

            for index_str, result_obj in translated_chunk_dict.items():
                try:
                    original_index = int(index_str)
                    if not (0 <= original_index < len(original_texts)):
                        print(f"[LLMPromptHandler] Warning: Index {original_index} from API is out of bounds.")
                        continue
                    
                    original_text = original_texts[original_index]

                    if isinstance(result_obj, dict) and 'text' in result_obj and 'translated' in result_obj:
                        final_translation_map[original_text] = TranslationResult(
                            text=str(result_obj['text']),
                            translated=bool(result_obj['translated'])
                        )
                    else:
                        # 对于不符合新格式的旧式响应或错误响应，提供回退机制
                        # 我们默认它为已翻译，以保持旧的行为
                        print(f"[LLMPromptHandler] Warning: Result object for index {index_str} has invalid format. Falling back. Object: {str(result_obj)}")
                        final_translation_map[original_text] = TranslationResult(
                            text=str(result_obj), # 直接将对象转为字符串
                            translated=True      # 假设为已翻译
                        )

                except (ValueError, IndexError):
                    print(f"[LLMPromptHandler] Warning: Could not process index '{index_str}' from API response.")
                except Exception as e:
                    print(f"[LLMPromptHandler] Error: An unexpected error occurred while processing result for index '{index_str}': {e}")
                    
        return final_translation_map
