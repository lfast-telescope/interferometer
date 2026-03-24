"""
Worker threads for long-running operations.

All hardware and compute-heavy operations run in QThread subclasses
so the GUI remains responsive.  Results are communicated back via
Qt signals.
"""

import sys
from PyQt5.QtCore import QThread, pyqtSignal
import numpy as np
import traceback


class _SignalStream:
    """File-like object that emits each written line via a Qt signal."""
    def __init__(self, signal):
        self._signal = signal
        self._buf = ""
    def write(self, text):
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line:
                self._signal.emit(line)
    def flush(self):
        if self._buf:
            self._signal.emit(self._buf)
            self._buf = ""


class MeasurementWorker(QThread):
    """Run take_new_measurement in a background thread."""

    finished = pyqtSignal(dict)       # emits result dict on success
    error = pyqtSignal(str)           # emits traceback string on failure
    progress = pyqtSignal(str)        # status messages for the log

    def __init__(self, mirror_num, take_new, save_date, save_instance,
                 new_folder, number_alignment_iterations, parent=None):
        super().__init__(parent)
        self.mirror_num = str(mirror_num)
        self.take_new = take_new
        self.save_date = save_date
        self.save_instance = save_instance
        self.new_folder = new_folder
        self.number_alignment_iterations = number_alignment_iterations

    def run(self):
        try:
            import sys, os
            sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
            sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

            from interferometer.config import get_mirror_params
            from interferometer.interferometer_utils import take_new_measurement, setup_paths
            from interferometer.data_loader import load_single_surface
            from shared.General_zernike_matrix import General_zernike_matrix

            config = get_mirror_params(self.mirror_num)
            OD, ID = config["OD"], config["ID"]
            clear_outer, clear_inner = 0.5 * OD, 0.5 * ID

            mirror_path = config["base_path"]
            os.makedirs(mirror_path, exist_ok=True)

            self.progress.emit(f"Setting up paths for Mirror {self.mirror_num}...")
            save_subfolder = setup_paths(mirror_path, self.take_new,
                                         self.save_date, self.save_instance,
                                         self.new_folder)

            self.progress.emit("Generating Zernike matrix...")
            Z = General_zernike_matrix(44, int(clear_outer * 1e6),
                                       int(clear_inner * 1e6))

            if self.take_new:
                self.progress.emit(
                    f"Taking new measurement ({self.number_alignment_iterations} "
                    f"alignment iterations)...")
                stream = _SignalStream(self.progress)
                old_stdout = sys.stdout
                sys.stdout = stream
                try:
                    take_new_measurement(
                        save_subfolder,
                        number_alignment_iterations=self.number_alignment_iterations)
                finally:
                    sys.stdout = old_stdout
                    stream.flush()

            self.progress.emit("Loading surface data...")
            surface = load_single_surface(
                save_subfolder,
                clear_outer=clear_outer,
                clear_inner=clear_inner,
                Z=Z)

            result = {
                'surface': surface,
                'config': config,
                'save_path': save_subfolder,
                'Z': Z,
                'clear_outer': clear_outer,
                'clear_inner': clear_inner,
                'mirror_num': self.mirror_num,
            }
            self.progress.emit("Measurement complete.")
            self.finished.emit(result)

        except Exception:
            self.error.emit(traceback.format_exc())


class LoadSurfaceWorker(QThread):
    """Load an existing surface from disk."""

    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, mirror_num, save_date, save_instance, new_folder=None,
                 parent=None):
        super().__init__(parent)
        self.mirror_num = str(mirror_num)
        self.save_date = save_date
        self.save_instance = save_instance
        self.new_folder = new_folder

    def run(self):
        try:
            import sys, os
            sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
            sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

            from interferometer.config import get_mirror_params
            from interferometer.interferometer_utils import setup_paths
            from interferometer.data_loader import load_single_surface
            from shared.General_zernike_matrix import General_zernike_matrix

            config = get_mirror_params(self.mirror_num)
            OD, ID = config["OD"], config["ID"]
            clear_outer, clear_inner = 0.5 * OD, 0.5 * ID

            mirror_path = config["base_path"]
            self.progress.emit(f"Loading saved data for Mirror {self.mirror_num}...")
            save_subfolder = setup_paths(mirror_path, False,
                                         self.save_date, self.save_instance,
                                         self.new_folder)

            self.progress.emit("Generating Zernike matrix...")
            Z = General_zernike_matrix(44, int(clear_outer * 1e6),
                                       int(clear_inner * 1e6))

            self.progress.emit("Loading surface data...")
            surface = load_single_surface(
                save_subfolder,
                clear_outer=clear_outer,
                clear_inner=clear_inner,
                Z=Z)

            result = {
                'surface': surface,
                'config': config,
                'save_path': save_subfolder,
                'Z': Z,
                'clear_outer': clear_outer,
                'clear_inner': clear_inner,
                'mirror_num': self.mirror_num,
            }
            self.progress.emit("Load complete.")
            self.finished.emit(result)

        except Exception:
            self.error.emit(traceback.format_exc())
