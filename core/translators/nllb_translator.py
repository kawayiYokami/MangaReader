# core/translators/nllb_translator.py
# from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import os
import traceback
from core.translator import BaseTranslator # Import BaseTranslator
from utils import manga_logger as log # Import logger

class NLLBTranslator(BaseTranslator): # Inherit from BaseTranslator
    """
    使用 NLLB (No Language Left Behind) 模型进行翻译的翻译器。
    """
    DEFAULT_MODEL_NAME = 'facebook/nllb-200-distilled-600M'
    DEFAULT_SOURCE_LANG_CODE = "jpn_Jpan" # Default source for tokenizer
    DEFAULT_NLLB_TARGET_LANG_CODE = "zho_Hans" # Default NLLB target language (Simplified Chinese)

    # NLLB specific language codes map for common app languages
    NLLB_LANG_CODE_MAP = {
        "zh": "zho_Hans",
        "zh-cn": "zho_Hans",
        "zh-hans": "zho_Hans",
        "zh-tw": "zho_Hant",
        "zh-hant": "zho_Hant",
        "en": "eng_Latn",
        "ja": "jpn_Jpan",
        "ko": "kor_Hang",
        # Add more mappings as needed
    }

    def __init__(self,
                 model_name: str | None = None,
                 cache_dir: str | None = None,
                 source_lang_code: str | None = None):
        super().__init__() # Call BaseTranslator's init
    #     self.model_name = model_name if model_name else self.DEFAULT_MODEL_NAME
        
    #     if cache_dir is None:
    #         script_dir = os.path.dirname(os.path.abspath(__file__))
    #         project_root = os.path.dirname(os.path.dirname(script_dir))
    #         self.cache_dir = os.path.join(project_root, "models")
    #     else:
    #         self.cache_dir = cache_dir
            
    #     self.source_lang_code = source_lang_code if source_lang_code else self.DEFAULT_SOURCE_LANG_CODE
        
    #     self.tokenizer = None
    #     self.model = None
    #     self._load_model()

    # def _load_model(self):
    #     try:
    #         log.info(f"正在从 '{self.model_name}' 加载 NLLB 分词器 (源语言: {self.source_lang_code})，缓存目录: {self.cache_dir if self.cache_dir else '默认'}")
    #         self.tokenizer = AutoTokenizer.from_pretrained(
    #             self.model_name,
    #             src_lang=self.source_lang_code,
    #             cache_dir=self.cache_dir
    #         )
    #         log.info(f"正在从 '{self.model_name}' 加载 NLLB 模型，缓存目录: {self.cache_dir if self.cache_dir else '默认'}")
    #         self.model = AutoModelForSeq2SeqLM.from_pretrained(
    #             self.model_name,
    #             cache_dir=self.cache_dir
    #         )
    #         log.info(f"NLLB 模型 '{self.model_name}' 加载成功。")
    #     except Exception as e:
    #         log.error(f"加载 NLLB 模型 '{self.model_name}' 时出错: {e}")
    #         log.error(traceback.format_exc())
    #         self.tokenizer = None
    #         self.model = None

    # def _get_nllb_target_lang_code(self, target_lang: str | None) -> str:
    #     """Maps general language codes to NLLB specific codes."""
    #     if target_lang is None:
    #         log.warning(f"NLLBTranslator: target_lang is None, defaulting to '{self.DEFAULT_NLLB_TARGET_LANG_CODE}'.")
    #         return self.DEFAULT_NLLB_TARGET_LANG_CODE
    #     return self.NLLB_LANG_CODE_MAP.get(target_lang.lower(), target_lang) # Fallback to target_lang itself

    # def _translate_text(self, text: str, target_lang: str) -> str | None:
    #     """
    #     实际执行单个文本翻译的方法，由 BaseTranslator.translate 调用。
    #     """
    #     if not self.model or not self.tokenizer:
    #         log.error(f"错误：NLLB 模型 '{self.model_name}' 未正确加载。")
    #         return None

    #     nllb_target_code = self._get_nllb_target_lang_code(target_lang)
    #     log.debug(f"NLLB: _translate_text: '{text[:30]}...' from '{self.source_lang_code}' to '{target_lang}' (NLLB code: '{nllb_target_code}')")

    #     translated_texts = self._translate_batch_internal([text], nllb_target_lang_code=nllb_target_code)
        
    #     if translated_texts and not translated_texts[0].startswith("错误：") and not translated_texts[0].startswith("翻译错误:"):
    #         return translated_texts[0]
    #     else:
    #         log.warning(f"NLLB 翻译失败 for text: {text[:30]}... to {target_lang}")
    #         if translated_texts:
    #              log.warning(f"NLLB 翻译器内部错误: {translated_texts[0]}")
    #         return None

    # def _translate_batch_internal(self, texts: list[str], nllb_target_lang_code: str) -> list[str]:
    #     """
    #     Internal method to translate a batch of texts using NLLB.
    #     The `target_lang_code` here is the NLLB-specific code (e.g., "zho_Hans").
    #     """
    #     if not self.model or not self.tokenizer:
    #         # This check is also in _translate_text, but good for direct calls if any
    #         return [f"错误：NLLB 模型 '{self.model_name}' 未正确加载。" for _ in texts]

    #     try:
    #         inputs = self.tokenizer(texts, return_tensors="pt", padding=True, truncation=True) # Added truncation

    #         try:
    #             if not hasattr(self.tokenizer, 'convert_tokens_to_ids'):
    #                  raise AttributeError("Tokenizer does not have 'convert_tokens_to_ids' method.")
                
    #             target_lang_token_id_or_list = self.tokenizer.convert_tokens_to_ids(nllb_target_lang_code)
                
    #             if isinstance(target_lang_token_id_or_list, list):
    #                 if not target_lang_token_id_or_list:
    #                     raise ValueError(f"convert_tokens_to_ids returned an empty list for {nllb_target_lang_code}")
    #                 forced_bos_token_id = target_lang_token_id_or_list[0]
    #             elif isinstance(target_lang_token_id_or_list, int):
    #                 forced_bos_token_id = target_lang_token_id_or_list
    #             else:
    #                 raise TypeError(f"convert_tokens_to_ids returned unexpected type {type(target_lang_token_id_or_list)} for {nllb_target_lang_code}")

    #             if hasattr(self.tokenizer, 'unk_token_id') and forced_bos_token_id == self.tokenizer.unk_token_id:
    #                 log.warning(f"警告: NLLB 目标语言代码 '{nllb_target_lang_code}' 被转换为 UNK token ID。可能是不支持的语言代码。")
    #                 return [f"错误：NLLB Tokenizer 无法识别目标语言 '{nllb_target_lang_code}' (转换为UNK)。" for _ in texts]

    #         except AttributeError as ae:
    #              log.error(f"错误: NLLB Tokenizer ({type(self.tokenizer)}) 不支持 convert_tokens_to_ids 方法: {ae}")
    #              return [f"错误：NLLB Tokenizer 无法设置目标语言 '{nllb_target_lang_code}' (方法缺失)。" for _ in texts]
    #         except Exception as e_conv:
    #             log.error(f"错误: 当转换目标语言代码 '{nllb_target_lang_code}' 为 ID 时出错: {e_conv}")
    #             log.error(traceback.format_exc())
    #             return [f"错误：NLLB Tokenizer 无法处理目标语言 '{nllb_target_lang_code}'。" for _ in texts]
            
    #         translated_tokens = self.model.generate(
    #             **inputs.to(self.model.device), # Ensure tensors are on the same device as model
    #             forced_bos_token_id=forced_bos_token_id,
    #             max_length=512
    #         )
            
    #         translated_texts = self.tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)
    #         return translated_texts
    #     except Exception as e:
    #         log.error(f"使用 NLLB 模型 '{self.model_name}' 翻译时出错: {e}")
    #         log.error(traceback.format_exc())
    #         return [f"翻译错误: {str(e)}" for _ in texts]