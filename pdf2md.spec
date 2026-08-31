# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for pdf2md — text extraction + ocrmypdf engine only."""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect all ocrmypdf submodules and data files (fonts, ICC profiles)
ocrmypdf_datas = collect_data_files('ocrmypdf')
ocrmypdf_hiddenimports = collect_submodules('ocrmypdf')

# pymupdf4llm picks its extraction engine at import time: if `pymupdf.layout`
# imports (which needs onnxruntime plus the bundled ONNX layout models), it uses
# the ML layout engine; otherwise it silently degrades to a heuristic engine that
# drops every text line whose bbox falls inside an image rect. PDFs that render
# each paragraph over a full-width raster then come out nearly empty, so these
# must be bundled even though onnxruntime is large.
pymupdf_datas = collect_data_files('pymupdf')
onnxruntime_datas = collect_data_files('onnxruntime')
layout_hiddenimports = (
    collect_submodules('pymupdf.layout') + collect_submodules('onnxruntime')
)

a = Analysis(
    ['pdf2md/__main__.py'],
    pathex=[],
    binaries=[],
    datas=ocrmypdf_datas + pymupdf_datas + onnxruntime_datas,
    hiddenimports=ocrmypdf_hiddenimports + layout_hiddenimports + [
        'pymupdf4llm',
        'pymupdf4llm.helpers',
        'pymupdf4llm.helpers.pymupdf_rag',
        'pdf2md',
        'pdf2md.cli',
        'pdf2md.converter',
        'pdf2md.router',
        'pdf2md.text_extract',
        'pdf2md.layout',
        'pdf2md.postprocess',
        'pdf2md.io_utils',
        'pdf2md.lang_detect',
        'pdf2md.engines',
        'pdf2md.engines.base',
        'pdf2md.engines.ocrmypdf_engine',
        'pdf2md.engines.marker_engine',
        'pdf2md.engines.paddle_engine',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Heavy ML/AI frameworks not needed for text extraction + ocrmypdf
        'torch', 'torchvision', 'torchaudio',
        'tensorflow', 'keras',
        'transformers', 'huggingface_hub', 'tokenizers', 'safetensors',
        'lightning', 'pytorch_lightning',
        'scipy', 'sklearn', 'scikit-learn',
        'pandas', 'numpy.f2py',
        'matplotlib', 'mpl_toolkits',
        'sympy',
        'IPython', 'ipykernel', 'ipywidgets', 'jupyter',
        'notebook', 'nbconvert', 'nbformat',
        'pytest', 'py', '_pytest',
        'nltk',
        # NOTE: onnxruntime must NOT be excluded; pymupdf4llm's layout
        # engine needs it. See the comment at the top of this file.
        'av', 'cv2', 'opencv',
        'sqlalchemy', 'alembic',
        'grpc', 'grpcio',
        'uvicorn', 'fastapi', 'starlette',
        'httpx', 'httpcore', 'aiohttp',
        # 'pygments',  # needed by rich -> ocrmypdf
        'yt_dlp',
        'tkinter', '_tkinter',
        'win32com', 'pythoncom', 'pywintypes',
        'openpyxl', 'xlrd',
        'fsspec',
        'opentelemetry',
        'jsonschema',
        'websockets',
        'marker',  # marker engine won't work in exe anyway without models
        'paddleocr', 'paddlepaddle', 'paddle',
        'surya',
        # PaddleOCR / Marker sub-deps
        'onnx', 'onnxconverter_common',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='pdf2md',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
