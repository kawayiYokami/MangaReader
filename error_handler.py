#!/usr/bin/env python3
"""
全局错误处理器，防止程序闪退
"""

import sys
import traceback
import time

def handle_exception(exc_type, exc_value, exc_traceback):
    """全局异常处理器"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    print("\n" + "="*60)
    print("程序发生未处理的异常!")
    print("="*60)
    print(f"异常类型: {exc_type.__name__}")
    print(f"异常信息: {exc_value}")
    print("="*60)
    print("详细堆栈信息:")
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    print("="*60)
    print("\n程序将在30秒后退出，以便查看错误信息...")

    # 给用户足够时间查看错误
    for i in range(30, 0, -1):
        print(f"\r剩余时间: {i} 秒", end="", flush=True)
        time.sleep(1)
    print("\n")

# 设置全局异常处理器
sys.excepthook = handle_exception

print("错误处理器已加载 - 程序异常时不会立即退出")