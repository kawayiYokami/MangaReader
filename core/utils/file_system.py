#!/usr/bin/env python3
"""
文件系统操作工具模块
"""

import os
import shutil
from utils import manga_logger as log

def safe_replace_file(source_path: str, destination_path: str) -> bool:
    """
    安全地用源文件替换目标文件。

    此函数执行以下操作:
    1. 检查源文件是否存在。
    2. 使用 shutil.copy2 复制文件和元数据。
    3. 捕获潜在的IO/OS错误。
    4. 无论成功与否，都确保删除源（临时）文件。

    Args:
        source_path (str): 源文件的路径 (通常是临时文件)。
        destination_path (str): 目标文件的路径 (将被覆盖的原始文件)。

    Returns:
        bool: 如果替换成功则返回 True，否则返回 False。
    """
    if not os.path.exists(source_path):
        log.error(f"源文件不存在，无法执行替换: {source_path}")
        return False

    try:
        # copy2 会同时复制文件内容和元数据（如修改时间等）
        shutil.copy2(source_path, destination_path)
        log.debug(f"成功将 '{source_path}' 复制到 '{destination_path}'")
        return True
    except (IOError, OSError) as e:
        log.error(f"文件替换期间发生错误 (从 '{source_path}' 到 '{destination_path}'): {e}")
        return False
    finally:
        # 确保源文件（临时文件）总是被清理掉
        try:
            os.remove(source_path)
            log.debug(f"已成功删除临时文件: {source_path}")
        except OSError as e:
            log.error(f"删除临时文件失败: {source_path}, 错误: {e}")
