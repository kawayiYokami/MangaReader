# core/harmonization_map_manager.py
import json
import os
import logging
from typing import Dict, Optional, List

log = logging.getLogger(__name__)

class HarmonizationMapManager:
    """
    管理和谐词映射，使用 JSON 文件进行存储。
    映射结构: {"原文": "和谐后文本"}
    """
    def __init__(self, json_file_path: str = 'cache/harmonization_map.json'):
        """
        初始化 HarmonizationMapManager。

        Args:
            json_file_path: JSON 文件的路径。
        """
        self.json_file_path = json_file_path
        self._ensure_dir_exists()
        self.mappings: Dict[str, str] = self._load_mappings()

    def _ensure_dir_exists(self):
        """确保 JSON 文件所在的目录存在"""
        directory = os.path.dirname(self.json_file_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory)
                log.info(f"创建目录: {directory}")
            except OSError as e:
                log.error(f"创建目录 {directory} 失败: {e}")

    def _load_mappings(self) -> Dict[str, str]:
        """从 JSON 文件加载映射。"""
        if not os.path.exists(self.json_file_path):
            log.warning(f"和谐映射文件 {self.json_file_path} 不存在，将创建一个新的空映射。")
            return {}
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                mappings = json.load(f)
                if not isinstance(mappings, dict):
                    log.error(f"和谐映射文件 {self.json_file_path} 格式错误，应为字典。返回空映射。")
                    return {}
                # 确保所有键和值都是字符串
                return {str(k): str(v) for k, v in mappings.items()}
        except json.JSONDecodeError as e:
            log.error(f"解析和谐映射文件 {self.json_file_path} 失败: {e}。返回空映射。")
            return {}
        except Exception as e:
            log.error(f"加载和谐映射文件 {self.json_file_path} 时发生未知错误: {e}。返回空映射。")
            return {}

    def _save_mappings(self) -> bool:
        """将当前映射保存到 JSON 文件。"""
        try:
            with open(self.json_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.mappings, f, ensure_ascii=False, indent=4)
            log.info(f"和谐映射已成功保存到 {self.json_file_path}")
            return True
        except IOError as e:
            log.error(f"保存和谐映射到文件 {self.json_file_path} 失败: {e}")
            return False
        except Exception as e:
            log.error(f"保存和谐映射时发生未知错误: {e}")
            return False

    def add_or_update_mapping(self, original_text: str, harmonized_text: str) -> bool:
        """
        添加或更新一个和谐映射。

        Args:
            original_text: 原文。
            harmonized_text: 和谐后的文本。
        
        Returns:
            bool: 操作是否成功。
        """
        if not original_text: # 不允许空原文
            log.warning("尝试添加空的原文映射，操作被忽略。")
            return False
            
        self.mappings[str(original_text)] = str(harmonized_text)
        return self._save_mappings()

    def get_mapping(self, original_text: str) -> Optional[str]:
        """
        根据原文获取和谐后的文本。

        Args:
            original_text: 原文。

        Returns:
            Optional[str]: 如果找到映射，则返回和谐后的文本，否则返回 None。
        """
        return self.mappings.get(str(original_text))

    def delete_mapping(self, original_text: str) -> bool:
        """
        根据原文删除一个和谐映射。

        Args:
            original_text: 原文。
        
        Returns:
            bool: 如果成功删除则返回 True，如果原文不存在则返回 False。
        """
        original_text_str = str(original_text)
        if original_text_str in self.mappings:
            del self.mappings[original_text_str]
            return self._save_mappings()
        log.warning(f"尝试删除映射 '{original_text_str}'，但未找到该条目。")
        return False

    def get_all_mappings(self) -> Dict[str, str]:
        """
        获取所有和谐映射。

        Returns:
            Dict[str, str]: 包含所有映射的字典。
        """
        return self.mappings.copy() # 返回副本以防止外部修改

    def clear_all_mappings(self) -> bool:
        """
        清空所有和谐映射。
        
        Returns:
            bool: 操作是否成功。
        """
        self.mappings.clear()
        return self._save_mappings()

    def apply_mapping_to_text(self, text: str) -> str:
        """
        将所有已定义的和谐映射规则应用到给定的文本字符串。
        规则按原文长度降序应用，以处理包含关系（例如 "apple pie" 应在 "apple" 之前被替换）。

        Args:
            text: 需要处理的原始文本。

        Returns:
            str: 应用和谐映射规则后的文本。
        """
        if not self.mappings or not text:
            log.debug("和谐映射为空或输入文本为空，不执行替换。")
            return text

        # 按原文长度降序排序，以优先替换更长的匹配项
        sorted_mappings = sorted(self.mappings.items(), key=lambda item: len(item[0]), reverse=True)

        processed_text = text
        for original, harmonized in sorted_mappings:
            if original in processed_text: # 优化：仅当原文存在时才替换
                processed_text = processed_text.replace(original, harmonized)
        
        if text != processed_text:
            log.debug(f"文本已应用和谐化映射: 原文='{text[:100]}...', 处理后='{processed_text[:100]}...'")
        else:
            log.debug(f"文本未发生改变，无需和谐化: '{text[:100]}...'")

        return processed_text

    def reload_mappings(self):
        """
        从文件重新加载映射，覆盖内存中的当前映射。
        """
        self.mappings = self._load_mappings()
        log.info(f"已从 {self.json_file_path} 重新加载和谐映射。")

# 单例模式的实例获取（可选）
_map_manager_instance: Optional[HarmonizationMapManager] = None

def get_harmonization_map_manager_instance(json_file_path: str = 'cache/harmonization_map.json') -> HarmonizationMapManager:
    """
    获取 HarmonizationMapManager 的单例。
    如果实例不存在或路径已更改，则创建一个新实例。
    """
    global _map_manager_instance
    if _map_manager_instance is None or _map_manager_instance.json_file_path != json_file_path:
        _map_manager_instance = HarmonizationMapManager(json_file_path)
    return _map_manager_instance