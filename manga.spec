# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['scripts/run_desktop_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/backend', 'src/backend'), # 包含所有后端代码
        ('src/frontend/dist', 'src/frontend/dist'), # 添加前端构建文件
        ('src/common/fonts', 'src/common/fonts'), # 添加字体文件
        ('app', 'app'), # 添加应用配置
        ('pyproject.toml', 'pyproject.toml'), # 添加项目配置
    ],
    hiddenimports=[
        # Web 框架
        'uvicorn',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        'uvicorn.protocols.websockets.auto',
        'fastapi',
        'fastapi.staticfiles',
        'starlette.middleware.cors',

        # 桌面
        'pywebview',
        'webview.dom',

        # 图像处理（仅Pillow）
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'PIL.ImageOps',

        # 其他核心
        'yaml',
        'lmdb',
        'openai',
        'python_multipart',
        'fonttools',

        # 项目模块
        'src.backend.core',
        'src.backend.web',
        'src.backend.web.api',
        'src.backend.web.websocket',
        'src.backend.utils',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['error_handler.py'],
    excludes=[
        # 开发工具
        'pytest',
        'unittest',
        'test',
        'tests',
        'setuptools',
        'pip',
        'wheel',

        # IDE和代码分析工具
        'jedi',
        'jedi.*',
        'parso',
        'astroid',
        'astroid.*',
        'pylint',

        # 未使用的科学计算库
        'scipy',
        'scipy.*',
        'numpy',
        'pandas',
        'matplotlib',
        'sympy',

        # OpenCV（已移除）
        'cv2',
        'opencv',
        'opencv_python',
        'opencv_contrib_python',

        # 未使用的编译工具
        'Cython',
        'Cython.*',

        # 未使用的网络库
        'zmq',
        'zmq.*',

        # 未使用的压缩库
        'zstandard',

        # 未使用的XML处理
        'lxml',
        'lxml.*',

        # 未使用的标准库
        'tkinter',
        'turtle',
        'curses',
        'email',
        'html',
        'http.server',
        'xmlrpc',
        'pydoc',
    ],
    noarchive=False,
    optimize=2,  # 启用最高级别优化
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
    strip=False,  # Windows 不支持 strip
    upx=True,     # 启用 UPX 压缩
    console=False,
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
    strip=False,  # Windows 不支持 strip
    upx=True,     # 启用 UPX 压缩
    upx_exclude=[
        'vcruntime140.dll',  # 不压缩运行时
        'python311.dll',
    ],
    name='manga',
)
