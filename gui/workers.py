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
                 new_folder, number_alignment_iterations, num_avg, number_measurements, parent=None):
        super().__init__(parent)
        self.mirror_num = str(mirror_num)
        self.take_new = take_new
        self.save_date = save_date
        self.save_instance = save_instance
        self.new_folder = new_folder
        self.number_alignment_iterations = number_alignment_iterations
        self.num_avg = num_avg
        self.number_measurements = number_measurements

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
                        number_alignment_iterations=self.number_alignment_iterations,
                        num_avg=self.num_avg,
                        number_measurements=self.number_measurements)
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


class LongExposureWorker(QThread):
    """Periodically take auto-aligned measurements for a long-exposure stability test.

    Folder structure created under the mirror base path::

        {YYYYMMDD}/{HHMMSS}_long_exposure/{HHMMSS}/   (one subfolder per measurement)

    The extended result dict adds to the standard result_dict keys:
        elapsed_minutes  - elapsed time since test start
        focus_pos_mm     - Newport Ch3 position after alignment (nan if unavailable)
        session_folder   - path to the long-exposure session folder
    """

    measurement_done = pyqtSignal(dict)  # extended result dict after each measurement
    progress = pyqtSignal(str)           # status messages for the log
    error = pyqtSignal(str)              # traceback string on failure
    finished = pyqtSignal()              # emitted when test ends (normal or stopped)

    def __init__(self, mirror_num, period_minutes, total_duration_minutes,
                 align_iters, parent=None):
        super().__init__(parent)
        self.mirror_num = str(mirror_num)
        self.period_minutes = period_minutes
        self.total_duration_minutes = total_duration_minutes
        self.align_iters = align_iters
        self._stop = False

    def request_stop(self):
        """Signal the worker to stop after finishing the current measurement."""
        self._stop = True

    def _read_ch3_focus(self):
        """Open an independent Newport connection, read Ch3 position, close.

        Returns position in mm, or float('nan') if the stage is unreachable.
        """
        try:
            from LFASTfiber.libs.libNewport import smc100
            s = smc100('COM3', nchannels=3)
            pos_str = s.getPosition(channel=3)
            s.close()
            return float(pos_str.split('TP')[-1])
        except Exception:
            return float('nan')

    def run(self):
        try:
            import sys, os, time, datetime, shutil
            sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
            sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

            from interferometer.config import get_mirror_params
            from interferometer.interferometer_utils import take_new_measurement
            from interferometer.data_loader import load_single_surface
            from shared.General_zernike_matrix import General_zernike_matrix

            config = get_mirror_params(self.mirror_num)
            OD, ID = config['OD'], config['ID']
            clear_outer, clear_inner = 0.5 * OD, 0.5 * ID
            mirror_path = config['base_path']

            # Session folder: {mirror_path}/{YYYYMMDD}/{HHMMSS}_long_exposure/
            # The 4D WebService depth limit is 3 levels from mirror_path (matching
            # standard YYYYMMDD/N/savefile). Our final structure is 4 levels deep, so
            # we stage each measurement in a shallow temp dir (_le_tmp/HHMMSS/) and
            # then move it to the final location after the 4D save completes.
            #
            # Forward slashes are required throughout — the 4D WebService is an HTTP
            # service and silently rejects Windows backslash paths.
            now = datetime.datetime.now()
            mp = mirror_path.replace('\\', '/').rstrip('/') + '/'
            date_folder = mp + now.strftime('%Y%m%d') + '/'
            os.makedirs(date_folder, exist_ok=True)
            session_folder = date_folder + now.strftime('%H%M%S') + '_long_exposure/'
            os.makedirs(session_folder, exist_ok=True)
            self.progress.emit(f"Session folder: {session_folder}")

            # Staging dir one level deep from mirror_path — keeps 4D WebService path
            # depth at exactly 3 (_le_tmp/HHMMSS/N), same as standard YYYYMMDD/N/N.
            tmp_root = mp + '_le_tmp/'
            os.makedirs(tmp_root, exist_ok=True)

            self.progress.emit("Generating Zernike matrix...")
            Z = General_zernike_matrix(
                44, int(clear_outer * 1e6), int(clear_inner * 1e6))

            period_seconds = self.period_minutes * 60.0
            total_seconds = self.total_duration_minutes * 60.0
            test_start = time.monotonic()
            measurement_count = 0

            while not self._stop:
                # measurement_count=0 fires immediately (next_meas_at_s=0)
                next_meas_at_s = measurement_count * period_seconds

                # Sleep in 1-second chunks until the scheduled time, checking stop flag
                while not self._stop:
                    remaining = next_meas_at_s - (time.monotonic() - test_start)
                    if remaining <= 0:
                        break
                    time.sleep(min(1.0, remaining))

                if self._stop:
                    break

                # After the first measurement, stop if total duration exceeded
                elapsed_s = time.monotonic() - test_start
                if measurement_count > 0 and elapsed_s >= total_seconds:
                    self.progress.emit("Total test duration reached.")
                    break

                elapsed_minutes = elapsed_s / 60.0
                meas_time_str = datetime.datetime.now().strftime('%H%M%S')

                # Staging measurement folder: mirror_path/_le_tmp/HHMMSS/
                # 3 levels from mirror_path base: _le_tmp/HHMMSS/N — matches standard depth.
                tmp_subfolder = tmp_root + meas_time_str + '/'
                os.makedirs(tmp_subfolder, exist_ok=True)

                self.progress.emit(
                    f"[t={elapsed_minutes:.1f} min] Measurement {measurement_count} "
                    f"({self.align_iters} alignment iterations)...")

                # Take measurement — 4D saves files into tmp_subfolder
                stream = _SignalStream(self.progress)
                old_stdout = sys.stdout
                sys.stdout = stream
                try:
                    take_new_measurement(
                        tmp_subfolder,
                        number_alignment_iterations=self.align_iters)
                finally:
                    sys.stdout = old_stdout
                    stream.flush()

                # Read Ch3 AFTER alignment has settled
                self.progress.emit("Reading Newport Ch3 focus position...")
                focus_pos = self._read_ch3_focus()

                # Move measurement folder from tmp into the final session hierarchy.
                final_subfolder = session_folder + meas_time_str + '/'
                self.progress.emit(f"Moving measurement to: {final_subfolder}")
                shutil.move(tmp_subfolder.rstrip('/'), final_subfolder.rstrip('/'))
                os.makedirs(final_subfolder, exist_ok=True)  # ensure dest exists after move

                self.progress.emit("Loading surface data...")
                surface = load_single_surface(
                    final_subfolder,
                    clear_outer=clear_outer,
                    clear_inner=clear_inner,
                    Z=Z)

                result = {
                    'surface': surface,
                    'config': config,
                    'save_path': final_subfolder,
                    'Z': Z,
                    'clear_outer': clear_outer,
                    'clear_inner': clear_inner,
                    'mirror_num': self.mirror_num,
                    'elapsed_minutes': elapsed_minutes,
                    'focus_pos_mm': focus_pos,
                    'session_folder': session_folder,
                }
                self.measurement_done.emit(result)
                measurement_count += 1

        except Exception:
            self.error.emit(traceback.format_exc())
        finally:
            # Clean up the empty tmp staging directory if empty
            try:
                tmp_root_path = mirror_path.replace('\\', '/').rstrip('/') + '/_le_tmp'
                if os.path.isdir(tmp_root_path) and not os.listdir(tmp_root_path):
                    os.rmdir(tmp_root_path)
            except Exception:
                pass
            self.finished.emit()
