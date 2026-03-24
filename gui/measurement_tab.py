"""
Measurement tab — take new or load existing interferometer measurement.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QSpinBox, QLineEdit, QCheckBox,
    QTextEdit, QMessageBox, QProgressBar, QFileDialog,
)
from PyQt5.QtCore import Qt

from .workers import MeasurementWorker, LoadSurfaceWorker


class MeasurementTab(QWidget):
    """Controls for taking / loading a mirror measurement."""

    # This signal-like callback is set by the main window so the
    # results tab can be notified when a surface is ready.
    on_surface_ready = None   # callable(result_dict, slot_index)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QVBoxLayout(self)

        # --- Mirror parameters ---
        params_box = QGroupBox("Mirror Parameters")
        pg = QGridLayout(params_box)

        pg.addWidget(QLabel("Mirror #:"), 0, 0)
        self.mirror_spin = QSpinBox()
        self.mirror_spin.setRange(1, 99)
        self.mirror_spin.setValue(22)
        pg.addWidget(self.mirror_spin, 0, 1)

        pg.addWidget(QLabel("Alignment iterations:"), 1, 0)
        self.align_spin = QSpinBox()
        self.align_spin.setRange(1, 20)
        self.align_spin.setValue(7)
        pg.addWidget(self.align_spin, 1, 1)

        pg.addWidget(QLabel("New folder label:"), 2, 0)
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("(optional, e.g. sanity_check)")
        pg.addWidget(self.folder_edit, 2, 1)

        root.addWidget(params_box)

        # --- Advanced / load options ---
        adv_box = QGroupBox("Load Options  (used when loading saved data)")
        ag = QGridLayout(adv_box)

        ag.addWidget(QLabel("save_date index:"), 0, 0)
        self.date_spin = QSpinBox()
        self.date_spin.setRange(-99, 999)
        self.date_spin.setValue(-1)
        ag.addWidget(self.date_spin, 0, 1)

        ag.addWidget(QLabel("save_instance index:"), 1, 0)
        self.instance_spin = QSpinBox()
        self.instance_spin.setRange(-99, 999)
        self.instance_spin.setValue(-1)
        ag.addWidget(self.instance_spin, 1, 1)

        root.addWidget(adv_box)

        # --- Action buttons ---
        btn_row = QHBoxLayout()

        self.take_new_btn = QPushButton("Take New Measurement")
        self.take_new_btn.clicked.connect(self._take_new)
        btn_row.addWidget(self.take_new_btn)

        self.load_btn = QPushButton("Load Saved Measurement")
        self.load_btn.clicked.connect(self._load_saved)
        btn_row.addWidget(self.load_btn)

        self.load_npy_btn = QPushButton("Load .npy File…")
        self.load_npy_btn.clicked.connect(self._load_npy_file)
        btn_row.addWidget(self.load_npy_btn)

        root.addLayout(btn_row)

        # --- Slot selector (which comparison slot to fill) ---
        slot_row = QHBoxLayout()
        slot_row.addWidget(QLabel("Load into slot:"))
        self.slot_a_btn = QPushButton("A  (primary)")
        self.slot_b_btn = QPushButton("B  (comparison)")
        self.slot_a_btn.setCheckable(True)
        self.slot_b_btn.setCheckable(True)
        self.slot_a_btn.setChecked(True)
        self.slot_a_btn.clicked.connect(lambda: self._select_slot(0))
        self.slot_b_btn.clicked.connect(lambda: self._select_slot(1))
        slot_row.addWidget(self.slot_a_btn)
        slot_row.addWidget(self.slot_b_btn)
        root.addLayout(slot_row)
        self._active_slot = 0

        # --- Progress ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

        # --- Log ---
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(160)
        root.addWidget(self.log)

        root.addStretch()

    # -------------------------------------------------------------- helpers
    def _select_slot(self, idx):
        self._active_slot = idx
        self.slot_a_btn.setChecked(idx == 0)
        self.slot_b_btn.setChecked(idx == 1)

    def _new_folder_or_none(self):
        txt = self.folder_edit.text().strip()
        return txt if txt else None

    def _set_busy(self, busy):
        self.take_new_btn.setEnabled(not busy)
        self.load_btn.setEnabled(not busy)
        self.load_npy_btn.setEnabled(not busy)
        self.progress_bar.setVisible(busy)

    def _log(self, msg):
        self.log.append(msg)

    # -------------------------------------------------------- take new
    def _take_new(self):
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.warning(self, "Busy", "A measurement is already running.")
            return

        self._set_busy(True)
        self._worker = MeasurementWorker(
            mirror_num=self.mirror_spin.value(),
            take_new=True,
            save_date=self.date_spin.value(),
            save_instance=self.instance_spin.value(),
            new_folder=self._new_folder_or_none(),
            number_alignment_iterations=self.align_spin.value(),
        )
        self._worker.progress.connect(self._log)
        self._worker.finished.connect(self._on_measurement_done)
        self._worker.error.connect(self._on_measurement_error)
        self._worker.start()

    # -------------------------------------------------------- load saved
    def _load_saved(self):
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.warning(self, "Busy", "A task is already running.")
            return

        self._set_busy(True)
        self._worker = LoadSurfaceWorker(
            mirror_num=self.mirror_spin.value(),
            save_date=self.date_spin.value(),
            save_instance=self.instance_spin.value(),
            new_folder=self._new_folder_or_none(),
        )
        self._worker.progress.connect(self._log)
        self._worker.finished.connect(self._on_measurement_done)
        self._worker.error.connect(self._on_measurement_error)
        self._worker.start()

    # -------------------------------------------------------- load .npy
    def _load_npy_file(self):
        import re
        import numpy as np
        import sys, os
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
        from interferometer.config import get_mirror_params
        from shared.General_zernike_matrix import General_zernike_matrix

        path, _ = QFileDialog.getOpenFileName(
            self, "Open .npy surface file", "", "NumPy files (*.npy)")
        if not path:
            return

        try:
            # Auto-detect mirror number from path (e.g. \M23\ or /M4/)
            match = re.search(r'[\\/]M(\d+)[\\/]', path)
            if match:
                detected_num = int(match.group(1))
                self.mirror_spin.setValue(detected_num)
                self._log(f"Auto-detected Mirror #{detected_num} from path")

            surface = np.load(path)
            mirror_num = str(self.mirror_spin.value())
            config = get_mirror_params(mirror_num)
            OD, ID = config["OD"], config["ID"]
            clear_outer, clear_inner = 0.5 * OD, 0.5 * ID
            Z = General_zernike_matrix(44, int(clear_outer * 1e6),
                                       int(clear_inner * 1e6))
            result = {
                'surface': surface,
                'config': config,
                'save_path': os.path.dirname(path),
                'Z': Z,
                'clear_outer': clear_outer,
                'clear_inner': clear_inner,
                'mirror_num': mirror_num,
            }
            self._log(f"Loaded .npy file: {path}")
            self._deliver_result(result)
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", str(exc))

    # -------------------------------------------------------- callbacks
    def _on_measurement_done(self, result):
        self._set_busy(False)
        self._deliver_result(result)

    def _on_measurement_error(self, tb):
        self._set_busy(False)
        self._log("ERROR:\n" + tb)
        QMessageBox.critical(self, "Error", "Operation failed — see log for details.")

    def _deliver_result(self, result):
        if self.on_surface_ready is not None:
            self.on_surface_ready(result, self._active_slot)
