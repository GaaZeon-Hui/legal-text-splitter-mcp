# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for legal document split system desktop app."""

import sys
import os
from pathlib import Path

_PARENT = Path(SPECPATH).parent

a = Analysis(
    [str(_PARENT / 'packaging' / 'app.py')],
    pathex=[str(_PARENT)],
    binaries=[],
    datas=[
        (str(_PARENT / 'static'), 'static'),
        (str(_PARENT / 'app'), 'app'),
        (str(_PARENT / 'service'), 'service'),
        (str(_PARENT / '拆分-打包'), '拆分-打包'),
    ],
    hiddenimports=[
        'nicegui',
        'fastapi',
        'uvicorn',
        'httpx',
        'openpyxl',
        'pymysql',
        'service.main',
        'service.split_service',
        'analyze_scored',
        'analyze_split_types',
        '_protection_config',
        '_type_patterns_config',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'unittest',
        'xmlrpc',
        'pydoc',
        'matplotlib',
        'pandas',
        'scipy',
        'PIL',
        'pillow',
        'cffi',
        'lxml',
        'sqlalchemy',
        'sqlite3',
        'psycopg2',
        'numpy',
        'aiohttp',
        'watchfiles',
        'pygments',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='法规拆分',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(_PARENT / 'packaging' / 'icon.ico'),
)
