# -*- mode: python ; coding: utf-8 -*-
# 保守版本 - 只移除 OpenCV，其他保持默认

a = Analysis(
    ['scripts/run_desktop_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/backend', 'src/backend'),
        ('src/frontend/dist', 'src/frontend/dist'),
        ('app', 'app'),
        ('pyproject.toml', 'pyproject.toml'),
    ],
    hiddenimports=[
        # Web 框架 (完整导入)
        'uvicorn',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        'uvicorn.protocols.websockets.auto',
        'fastapi',
        'fastapi.staticfiles',
        'fastapi.middleware',
        'fastapi.middleware.cors',
        'fastapi.middleware.gzip',
        'fastapi.responses',
        'starlette',
        'starlette.middleware',
        'starlette.middleware.cors',
        'starlette.responses',

        # 桌面
        'pywebview',
        'webview',
        'webview.dom',

        # 图像处理（Pillow完整）
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'PIL.ImageOps',

        # 日志
        'coloredlogs',
        'humanfriendly',

        # 其他核心
        'requests',
        'urllib3',
        'yaml',
        'pyyaml',
        'lmdb',
        'openai',
        'multipart',
        'python_multipart',
        'fonttools',
        'fontTools',
        'fontTools.ttLib',
        'filelock',
        'pathlib',
        'asyncio',
        'threading',
        'json',
        'logging',
        'sqlite3',

        # 项目模块
        'src.backend',
        'src.backend.core',
        'src.backend.core.ai_translator',
        'src.backend.core.manga',
        'src.backend.core.core_cache',
        'src.backend.core.image',
        'src.backend.core.utils',
        'src.backend.web',
        'src.backend.web.api',
        'src.backend.web.websocket',
        'src.backend.web.utils',
        'src.backend.utils',
        'src.backend.utils.manga_logger',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['error_handler.py'],
    excludes=[
        # 只排除 OpenCV
        'cv2',
        'opencv_python',
        'opencv_contrib_python',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='manga',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 启用控制台调试
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['.debug\\Paomedia-Small-N-Flat-Book.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='manga',
)