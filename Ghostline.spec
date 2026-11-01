# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_all

extra_datas = [
    ('bin', 'bin'),
    ('ghostline.ico', '.'),
    ('ghostline/fixtures', 'ghostline/fixtures'),
    ('ghostline/build_info.json', 'ghostline'),
    ('ghostline/models', 'ghostline/models'),
    ('assets/icons', 'assets/icons'),
]
extra_datas += collect_data_files('faster_whisper')
extra_datas += collect_data_files('ctranslate2')
try:
    extra_datas += collect_data_files('onnxruntime')
except Exception:
    pass

extra_binaries = []
extra_binaries += collect_dynamic_libs('ctranslate2')
try:
    extra_binaries += collect_dynamic_libs('onnxruntime')
except Exception:
    pass

a = Analysis(
    ['ghostline\\app.py'],
    pathex=[],
    binaries=extra_binaries,
    datas=extra_datas,
    hiddenimports=[
        'ghostline',
        'ghostline.build_info',
        'ghostline.config',
        'ghostline.app',
        'ghostline.core.ocr_engine',
        'ghostline.core.classifier',
        'ghostline.core.llm_client',
        'ghostline.core.pipeline',
        'ghostline.core.capture',
        'ghostline.core.capture_exclusion',
        'ghostline.core.hover_detector',
        'ghostline.core.credentials',
        'ghostline.core.providers',
        'ghostline.core.providers.base',
        'ghostline.core.providers.ollama_provider',
        'ghostline.core.providers.gemini_provider',
        'ghostline.core.providers.openai_compatible_provider',
        'ghostline.core.providers.anthropic_provider',
        'ghostline.core.providers.router',
        'ghostline.ui.main_window',
        'ghostline.ui.hud_overlay',
        'ghostline.ui.hud_manager',
        'ghostline.ui.qt_history_panel',
        'ghostline.ui.theme',
        'ghostline.ui.theme.tokens',
        'ghostline.ui.theme.icons',
        'ghostline.ui.theme.builder',
        'ghostline.ui.render_harness',
        'ghostline.ui.qt_theme',
        'ghostline.ui.qt_main_window',
        'ghostline.ui.qt_hud_overlay',
        'ghostline.ui.qt_audio_panel',
        'ghostline.ui.tray_indicator',
        'ghostline.ui.presentation',
        'ghostline.ui.code_renderer',
        'ghostline.ui.audio_panel',
        'ghostline.audio.capture',
        'ghostline.audio.transcription',
        'ghostline.audio.assistant',
        'ghostline.audio.telemetry',
        'ghostline.hardware',
        'ghostline.hardware.lighting',
        'ghostline.hardware.brightness',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtSvg',
        'PyQt6.QtSvgWidgets',
        'pyqtdarktheme',
        'pystray',
        'pystray._win32',
        'PIL._tkinter_finder',
        'win32gui',
        'win32con',
        'win32api',
        'win32event',
        'winerror',
        'pywintypes',
        'win32crypt',
        'pythoncom',
        'win32com',
        'win32com.client',
        'certifi',
        'numpy',
        'scipy',
        'scipy.signal',
        'pyaudiowpatch',
        'faster_whisper',
        'mss'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Ghostline',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',
    icon=['ghostline.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Ghostline',
)
