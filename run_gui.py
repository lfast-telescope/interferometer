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

import sys
import traceback
import logging

logging.basicConfig(
    filename="error_log.txt",
    level=logging.INFO,
    filemode="w",
    format="%(asctime)s %(levelname)s %(message)s",
    force=True
)
logging.info("Logging started")
def log_uncaught_exceptions(exctype, value, tb):
    logging.error("Uncaught exception", exc_info=(exctype, value, tb))
    # Optionally, print to stderr as well
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = log_uncaught_exceptions

# Ensure the mirror_control root is on the path regardless of
# where this script is launched from.

# Add both the current directory and its parent to sys.path for PyInstaller compatibility
_this_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.abspath(os.path.join(_this_dir, '..'))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from interferometer.gui.main_window import run_gui

if __name__ == '__main__':
    run_gui()
