# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for the LFAST Interferometer GUI.

Build with:
    cd mirror_control/interferometer
    pyinstaller interferometer_gui.spec
"""

import os
import sys

block_cipher = None

# Paths
HERE = os.path.abspath(os.path.dirname(SPECPATH if 'SPECPATH' in dir() else '.'))
ROOT = os.path.abspath(os.path.join(HERE, '..'))

a = Analysis(
    ['run_gui.py'],
    pathex=[ROOT, HERE],
    binaries=[],
    datas=[],
    hiddenimports=[
        'interferometer.config',
        'interferometer.interferometer_utils',
        'interferometer.data_loader',
        'interferometer.surface_processing',
        'interferometer.plotting_utils',
        'interferometer.plotting_interface',
        'shared.General_zernike_matrix',
        'shared.zernike_utils',
        'shared.wavefront_propagation',
        'hcipy',
        'scipy.signal',
        'scipy.interpolate',
        'scipy.optimize',
        'h5py',
        'cv2',
        'matplotlib.backends.backend_qt5agg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LFAST_Interferometer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # No console window
    icon=None,              # Add .ico path here if desired
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LFAST_Interferometer',
)
