#!/usr/bin/env python3
"""
测试所有必要模块是否可以正确导入
"""

import sys
import traceback
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 需要测试的模块列表
modules_to_test = [
    # 标准库模块
    'sqlite3',
    'pathlib',
    'asyncio',
    'threading',
    'json',
    'logging',

    # 第三方库
    'pywebview',
    'uvicorn',
    'fastapi',
    'fastapi.staticfiles',
    'fastapi.middleware.cors',
    'PIL',
    'cv2',
    'requests',
    'yaml',
    'coloredlogs',
    'filelock',
    'fonttools',
    'openai',
    'multipart',

    # 项目模块
    'src.backend',
    'src.backend.utils.manga_logger',
    'src.backend.web.api_server',
]

print("开始测试模块导入...")
print("=" * 50)

failed_modules = []

for module_name in modules_to_test:
    try:
        __import__(module_name)
        print(f"✓ {module_name}")
    except ImportError as e:
        print(f"✗ {module_name}: {e}")
        failed_modules.append(module_name)
    except Exception as e:
        print(f"✗ {module_name}: {e}")
        failed_modules.append(module_name)

print("=" * 50)

if failed_modules:
    print(f"\n失败的模块 ({len(failed_modules)} 个):")
    for module in failed_modules:
        print(f"  - {module}")

    print(f"\n详细错误信息:")
    for module_name in failed_modules:
        print(f"\n模块: {module_name}")
        try:
            __import__(module_name)
        except Exception as e:
            traceback.print_exc()
else:
    print("✓ 所有模块导入成功!")

print("\n按任意键退出...")
input()