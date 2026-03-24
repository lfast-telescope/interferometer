#!/usr/bin/env python
"""
Launch the LFAST Interferometer GUI.

Usage:
    python run_gui.py

To build an executable:
    pip install pyinstaller
    pyinstaller interferometer_gui.spec
"""

import sys
import os

# Ensure the mirror_control root is on the path regardless of
# where this script is launched from.
_this_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.abspath(os.path.join(_this_dir, '..'))
if _root not in sys.path:
    sys.path.insert(0, _root)

from interferometer.gui.main_window import run_gui

if __name__ == '__main__':
    run_gui()
