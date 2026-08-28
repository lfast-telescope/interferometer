"""
Analysis tab — compare cross-sections, RMS error, and encircled energy
across multiple test dates / instances for a mirror.
"""

import sys, os, json
import numpy as np
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QFileDialog, QScrollArea, QCheckBox, QComboBox,
    QSplitter, QFrame, QStackedWidget,
)
from PyQt5.QtCore import Qt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from interferometer.plotting_utils import compute_cmap_and_contour
from interferometer.surface_processing import prepare_surface, radial_averaged_surface
from .mpl_widget import MplWidget


# Pre-defined correction presets (same as results_tab)
COEF_PRESETS = {
    'uncorrected': [0, 1, 2, 4],
    'sph corrected': [0, 1, 2, 4],
    'edge corrected': [0, 1, 2, 3, 4, 5, 6, 9, 10, 14, 15, 20, 21, 27, 28, 35, 36, 44],
    'all modes removed': [0, 1, 2, 3, 4, 5, 6, 9, 10, 14, 15, 20, 21, 27, 28, 35, 36, 44],
    'high frequencies removed': [0, 1, 2, 4],
}


class _DateRow(QFrame):
    """A single date-folder row: checkbox + optional period combo + instance combo + timestamp."""

    def __init__(self, date_name, base_path, parent=None):
        super().__init__(parent)
        self.date_name = date_name
        self._base_path = base_path
        self._has_periods = False  # True when am/pm subfolders exist

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self.chk = QCheckBox(date_name)
        self.chk.setChecked(False)
        layout.addWidget(self.chk)

        # Period combo (am/pm) — hidden when not applicable
        self.period_combo = QComboBox()
        self.period_combo.setFixedWidth(55)
        self.period_combo.currentIndexChanged.connect(self._on_period_changed)
        self.period_combo.setVisible(False)
        layout.addWidget(self.period_combo)

        # Instance combo (test number)
        self.combo = QComboBox()
        self.combo.currentIndexChanged.connect(self._update_timestamp)
        layout.addWidget(self.combo)

        # Timestamp label
        self.ts_label = QLabel("")
        self.ts_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.ts_label)

        self._detect_structure()

    def _detect_structure(self):
        """Detect whether this date folder has am/pm subfolders or direct test instances."""
        date_path = os.path.join(self._base_path, self.date_name)
        children = sorted([
            d for d in os.listdir(date_path)
            if os.path.isdir(os.path.join(date_path, d))
        ])
        # Check for am/pm layer
        period_dirs = [d for d in children if d.lower() in ('am', 'pm')]
        if period_dirs:
            self._has_periods = True
            self.period_combo.addItems(period_dirs)
            # Default to "am" if present
            am_idx = next((i for i, p in enumerate(period_dirs) if p.lower() == 'am'), 0)
            self.period_combo.setCurrentIndex(am_idx)
            self.period_combo.setVisible(True)
            self._populate_instances()
        else:
            self._has_periods = False
            self.period_combo.setVisible(False)
            self._set_instances(children)

    def _on_period_changed(self, _idx):
        self._populate_instances()

    def _populate_instances(self):
        """Populate the instance combo from the current period subfolder."""
        period = self.period_combo.currentText()
        period_path = os.path.join(self._base_path, self.date_name, period)
        if not os.path.isdir(period_path):
            self._set_instances([])
            return
        instances = sorted([
            s for s in os.listdir(period_path)
            if os.path.isdir(os.path.join(period_path, s))
        ])
        self._set_instances(instances)

    def _set_instances(self, instances):
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems(instances)
        if instances:
            self.combo.setCurrentIndex(len(instances) - 1)
        self.combo.blockSignals(False)
        self._update_timestamp()

    def _update_timestamp(self, _idx=None):
        path = self.resolved_path()
        if path and os.path.isdir(path):
            mtime = os.path.getctime(path)
            ts = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
            self.ts_label.setText(ts)
        else:
            self.ts_label.setText("")

    def resolved_path(self):
        """Return the full path to the currently selected test subfolder."""
        parts = [self._base_path, self.date_name]
        if self._has_periods and self.period_combo.currentText():
            parts.append(self.period_combo.currentText())
        instance = self.combo.currentText()
        if instance:
            parts.append(instance)
        return os.path.join(*parts) if instance else None

    def is_selected(self):
        return self.chk.isChecked()

    def selected_label(self):
        """Return a display label for the selected test."""
        parts = [self.date_name]
        if self._has_periods:
            parts.append(self.period_combo.currentText())
        parts.append(self.combo.currentText())
        return '/'.join(parts)


class _LongExposureSessionRow(QFrame):
    """A row representing one long-exposure session folder."""

    def __init__(self, date_name, session_name, session_path, parent=None):
        super().__init__(parent)
        self.session_path = session_path
        # Strip _long_exposure suffix for display
        display_name = session_name.replace('_long_exposure', '')
        label = f"{date_name} / {display_name}"

        # Load session_data.json
        json_path = os.path.join(session_path, 'session_data.json')
        self.session_data = None
        if os.path.isfile(json_path):
            try:
                with open(json_path) as f:
                    self.session_data = json.load(f)
            except Exception:
                pass

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self.chk = QCheckBox(label)
        self.chk.setChecked(False)
        layout.addWidget(self.chk)

        # Summary: N measurements, total duration
        if self.session_data and self.session_data.get('measurements'):
            meas = self.session_data['measurements']
            n = len(meas)
            last_elapsed = meas[-1].get('elapsed') or 0.0
            summary = f"  {n} measurements, {last_elapsed:.1f} min"
        else:
            summary = "  (no session_data.json)"
        summary_label = QLabel(summary)
        summary_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(summary_label)
        layout.addStretch()

    def is_selected(self):
        return self.chk.isChecked()


class AnalysisTab(QWidget):
    """Compare cross-sections, RMS, and encircled energy across tests."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._base_path = None
        self._date_rows = []
        self._le_rows = []
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QVBoxLayout(self)

        # --- Top row: Folder selection + Mode + Processing Options ---
        top_row = QHBoxLayout()

        folder_box = QGroupBox("Mirror Folder")
        folder_layout = QHBoxLayout(folder_box)
        self.open_btn = QPushButton("Select Mirror Folder…")
        self.open_btn.clicked.connect(self._select_folder)
        folder_layout.addWidget(self.open_btn)
        self.folder_label = QLabel("(no folder selected)")
        self.folder_label.setWordWrap(True)
        folder_layout.addWidget(self.folder_label, stretch=1)
        top_row.addWidget(folder_box, stretch=1)

        mode_box = QGroupBox("Mode")
        mode_layout = QHBoxLayout(mode_box)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Surface Comparison", "Long Exposure"])
        self.mode_combo.setCurrentIndex(1)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        top_row.addWidget(mode_box)

        proc_box = QGroupBox("Processing Options")
        proc_layout = QHBoxLayout(proc_box)
        proc_layout.addWidget(QLabel("Correction:"))
        self.coef_combo = QComboBox()
        self.coef_combo.addItems(list(COEF_PRESETS.keys()))
        self.coef_combo.currentIndexChanged.connect(self._refresh_plots)
        proc_layout.addWidget(self.coef_combo)
        self.crop_ca_chk = QCheckBox("Crop clear aperture")
        self.crop_ca_chk.setChecked(False)
        self.crop_ca_chk.stateChanged.connect(self._refresh_plots)
        proc_layout.addWidget(self.crop_ca_chk)
        top_row.addWidget(proc_box)

        root.addLayout(top_row)

        # --- Stacked selector (Surface Comparison / Long Exposure) ---
        self.selector_stack = QStackedWidget()

        # Page 0: Surface Comparison selector
        self.selector_box = QGroupBox("Select Dates && Tests")
        self.selector_box.setVisible(True)
        selector_outer = QVBoxLayout(self.selector_box)

        btn_row = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(lambda: self._set_all_checked(False))
        self.plot_btn = QPushButton("Plot")
        self.plot_btn.clicked.connect(self._refresh_plots)
        btn_row.addWidget(self.select_all_btn)
        btn_row.addWidget(self.deselect_all_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.plot_btn)
        selector_outer.addLayout(btn_row)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMaximumHeight(200)
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.scroll_widget)
        selector_outer.addWidget(self.scroll_area)

        self.selector_stack.addWidget(self.selector_box)   # index 0

        # Page 1: Long Exposure session selector
        self.le_selector_box = QGroupBox("Long Exposure Sessions")
        le_outer = QVBoxLayout(self.le_selector_box)

        le_btn_row = QHBoxLayout()
        self.le_select_all_btn = QPushButton("Select All")
        self.le_select_all_btn.clicked.connect(lambda: self._set_le_all_checked(True))
        self.le_deselect_all_btn = QPushButton("Deselect All")
        self.le_deselect_all_btn.clicked.connect(lambda: self._set_le_all_checked(False))
        self.le_plot_btn = QPushButton("Plot")
        self.le_plot_btn.clicked.connect(self._refresh_le_plots)
        le_btn_row.addWidget(self.le_select_all_btn)
        le_btn_row.addWidget(self.le_deselect_all_btn)
        le_btn_row.addStretch()
        le_btn_row.addWidget(self.le_plot_btn)
        le_outer.addLayout(le_btn_row)

        self.le_scroll_area = QScrollArea()
        self.le_scroll_area.setWidgetResizable(True)
        self.le_scroll_area.setMaximumHeight(400)
        self.le_scroll_widget = QWidget()
        self.le_scroll_layout = QVBoxLayout(self.le_scroll_widget)
        self.le_scroll_layout.setAlignment(Qt.AlignTop)
        self.le_scroll_area.setWidget(self.le_scroll_widget)
        le_outer.addWidget(self.le_scroll_area)

        self.selector_stack.addWidget(self.le_selector_box)  # index 1
        self.selector_stack.setCurrentIndex(1)  # default to Long Exposure

        root.addWidget(self.selector_stack)

        # --- Plot area (shared) ---
        self.plot_widget = MplWidget(self, width=14, height=5)
        root.addWidget(self.plot_widget, stretch=1)

    # --------------------------------------------------------- mode switch
    def _on_mode_changed(self, idx):
        self.selector_stack.setCurrentIndex(idx)
        self.plot_widget.clear()

    # --------------------------------------------------------- folder pick
    def _select_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Mirror Folder (e.g. M24)",
            "C:/Users/lfast-admin/Documents/mirrors")
        if not path:
            return
        self._base_path = path
        self.folder_label.setText(path)
        self._populate_dates()
        self._populate_le_sessions()

    def _populate_dates(self):
        # Clear old rows
        for row in self._date_rows:
            self.scroll_layout.removeWidget(row)
            row.deleteLater()
        self._date_rows.clear()

        if not self._base_path or not os.path.isdir(self._base_path):
            self.selector_box.setVisible(False)
            return

        entries = sorted(os.listdir(self._base_path))
        date_dirs = [
            d for d in entries
            if os.path.isdir(os.path.join(self._base_path, d))
        ]

        for date_name in date_dirs:
            row = _DateRow(date_name, self._base_path)
            self._date_rows.append(row)
            self.scroll_layout.addWidget(row)

        self.selector_box.setVisible(len(self._date_rows) > 0)

    def _set_all_checked(self, checked):
        for row in self._date_rows:
            row.chk.setChecked(checked)

    def _set_le_all_checked(self, checked):
        for row in self._le_rows:
            row.chk.setChecked(checked)

    # ------------------------------------------------ long exposure sessions
    def _populate_le_sessions(self):
        """Scan the mirror folder for long-exposure session subfolders."""
        for row in self._le_rows:
            self.le_scroll_layout.removeWidget(row)
            row.deleteLater()
        self._le_rows.clear()

        if not self._base_path or not os.path.isdir(self._base_path):
            return

        date_dirs = sorted([
            d for d in os.listdir(self._base_path)
            if os.path.isdir(os.path.join(self._base_path, d))
        ])

        for date_name in date_dirs:
            date_path = os.path.join(self._base_path, date_name)
            try:
                session_dirs = sorted([
                    s for s in os.listdir(date_path)
                    if s.endswith('_long_exposure')
                    and os.path.isdir(os.path.join(date_path, s))
                ])
            except OSError:
                continue
            for session_name in session_dirs:
                session_path = os.path.join(date_path, session_name)
                row = _LongExposureSessionRow(date_name, session_name, session_path)
                self._le_rows.append(row)
                self.le_scroll_layout.addWidget(row)

    def _refresh_le_plots(self):
        """Plot RMS time-series for all selected long-exposure sessions."""
        selected_rows = [r for r in self._le_rows if r.is_selected() and r.session_data]
        if not selected_rows:
            return

        self.plot_widget.clear()
        fig = self.plot_widget.fig
        ax1 = fig.add_subplot(111)

        for row in selected_rows:
            meas = row.session_data.get('measurements', [])
            if not meas:
                continue
            label = row.chk.text()
            elapsed  = [m['elapsed'] for m in meas if m.get('elapsed') is not None]
            rms_vals = [m['rms_nm']  for m in meas if m.get('rms_nm')  is not None]

            if elapsed and rms_vals:
                ax1.plot(elapsed, rms_vals, marker='o', markersize=4,
                         linewidth=1.5, label=label)

        ax1.set_xlabel('Elapsed time (min)')
        ax1.set_ylabel('RMS of Δ surface (nm)')
        ax1.grid(True, alpha=0.3)
        ax1.set_title('Long Exposure Stability Comparison')
        ax1.legend(loc='upper left', fontsize=8)

        self.plot_widget.draw()

    # --------------------------------------------------------- plotting
    def _refresh_plots(self):
        selected = [
            (row.resolved_path(), row.selected_label())
            for row in self._date_rows
            if row.is_selected() and row.resolved_path()
        ]
        if not selected:
            return

        self.plot_widget.clear()

        surfaces, labels = self._load_selected_surfaces(selected)
        if not surfaces:
            self.plot_widget.draw()
            return

        ax_cs = self.plot_widget.fig.add_subplot(1, 2, 1)
        ax_rms = self.plot_widget.fig.add_subplot(1, 2, 2)

        self._plot_cross_sections(surfaces, labels, ax_cs)
        self._plot_rms_and_ee(surfaces, labels, ax_rms)

        self.plot_widget.draw()

    def _load_selected_surfaces(self, selected):
        from interferometer.data_loader import load_single_surface
        from interferometer.config import get_mirror_params
        from shared.General_zernike_matrix import General_zernike_matrix

        # Infer mirror number from folder name (e.g. "M24" -> "24")
        folder_name = os.path.basename(self._base_path)
        mirror_num = ''.join(c for c in folder_name if c.isdigit()) or "22"
        config = get_mirror_params(mirror_num)
        clear_outer = 0.5 * config["OD"]
        clear_inner = 0.5 * config["ID"]
        Z = General_zernike_matrix(44, int(clear_outer * 1e6),
                                   int(clear_inner * 1e6))

        preset_name = self.coef_combo.currentText()
        coefs = COEF_PRESETS.get(preset_name, [0, 1, 2, 4])
        crop = self.crop_ca_chk.isChecked()

        surfaces = []
        labels = []
        for subfolder, label in selected:
            if not os.path.isdir(subfolder):
                continue
            try:
                raw = load_single_surface(
                    subfolder, clear_outer=clear_outer,
                    clear_inner=clear_inner, Z=Z)
                surface = raw
                if preset_name in ('sph corrected', 'all modes removed'):
                    surface = surface - radial_averaged_surface(surface, config)
                high_freq_removed = preset_name == 'high frequencies removed'
                processed = prepare_surface(surface, Z, coefs, config, crop_ca=crop,
                                            high_freq_removed=high_freq_removed)
                surfaces.append(processed)
                labels.append(label)
            except Exception as exc:
                print(f"Skipping {label}: {exc}")
        return surfaces, labels

    def _plot_cross_sections(self, surfaces, labels, ax):
        from hcipy import make_pupil_grid, Field, radial_profile

        for surface, label in zip(surfaces, labels):
            plot_ref = surface.copy() * 1000
            grid = make_pupil_grid(plot_ref.shape, diameter=0.76)
            vals_field = Field(plot_ref.ravel(), grid)
            cs = radial_profile(vals_field, 0.005)
            ax.plot(cs[0], cs[1], label=label)

        ax.axhline(0, color='k', linestyle=':', linewidth=0.8, alpha=0.5)
        ax.set_xlim(0, 0.4)
        ax.set_xlabel('Radial distance (m)')
        ax.set_ylabel('Wavefront error (nm)')
        ax.set_title('Radial Cross-Section')
        ax.legend(fontsize='small')

    def _plot_rms_and_ee(self, surfaces, labels, ax_rms):
        from shared.wavefront_propagation import propagate_wavefront
        from interferometer.config import get_mirror_params

        folder_name = os.path.basename(self._base_path)
        mirror_num = ''.join(c for c in folder_name if c.isdigit()) or "22"
        config = get_mirror_params(mirror_num)

        rms_vals = []
        ee_vals = []
        for surface in surfaces:
            vals = surface[~np.isnan(surface)] * 1000
            rms_vals.append(np.sqrt(np.mean(vals ** 2)))
            try:
                _, throughput, _, _ = propagate_wavefront(
                    surface, config['OD'], config['ID'])
                ee_vals.append(throughput * 100)
            except Exception:
                ee_vals.append(np.nan)

        x = np.arange(len(labels))

        ln1 = ax_rms.plot(x, rms_vals, '-o', color='steelblue', markersize=6, zorder=3, label='RMS error')
        ax_rms.set_xticks(x)
        ax_rms.set_xticklabels(labels, rotation=45, ha='right', fontsize=7)
        ax_rms.set_ylabel('RMS wavefront error (nm)', color='steelblue')
        ax_rms.invert_yaxis()
        ax_rms.tick_params(axis='y', labelcolor='steelblue')
        for xi, val in zip(x, rms_vals):
            ax_rms.annotate(f'{val:.0f}', (xi, val), textcoords='offset points',
                            xytext=(0, 6), ha='center', fontsize=7, color='steelblue')

        ax_ee = ax_rms.twinx()
        ln2 = ax_ee.plot(x, ee_vals, '-s', color='darkorange', markersize=6, zorder=3, label='Coupling eff.')
        ax_ee.set_ylabel('Fiber coupling efficiency (%)', color='darkorange')
        ax_ee.tick_params(axis='y', labelcolor='darkorange')
        for xi, val in zip(x, ee_vals):
            if not np.isnan(val):
                ax_ee.annotate(f'{val:.1f}%', (xi, val), textcoords='offset points',
                               xytext=(0, -12), ha='center', fontsize=7, color='darkorange')

        lines = ln1 + ln2
        ax_rms.legend(lines, [l.get_label() for l in lines], fontsize='small', loc='best')
        ax_rms.set_title('RMS Error & Fiber Coupling')
