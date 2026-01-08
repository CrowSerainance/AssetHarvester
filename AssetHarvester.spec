# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('README.md', '.'), ('requirements.txt', '.'), ('docs', 'docs'), ('tools/README.md', 'tools'), ('tools/scripts/README.md', 'tools/scripts')],
    hiddenimports=['sqlalchemy.dialects.sqlite', 'src.core.database', 'src.core.hasher', 'src.core.comparator', 'src.core.cataloger', 'src.core.config', 'src.core.paths', 'src.extractors.grf_extractor', 'src.extractors.vfs_extractor', 'src.extractors.generic_extractor', 'src.extractors.grf_decompression_fallback', 'src.parsers.spr_parser_fallback'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'IPython'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AssetHarvester',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AssetHarvester',
)
