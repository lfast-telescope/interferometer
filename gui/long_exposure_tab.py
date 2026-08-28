"""
Long Exposure tab — run a timed stability test with periodic auto-aligned
measurements and live plotting.

Layout
------
Top-left  : parameter controls + Start/Stop buttons + log output
Top-right : time-series plot (elapsed min vs RMS of C, twin axis for Ch3 focus)
Bottom    : A / B / C comparison plot (A=first, B=latest, C=B-A)
"""

import json
import os
import sys
import numpy as np
import matplotlib.gridspec as gridspec

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QSpinBox, QDoubleSpinBox,
    QTextEdit, QSplitter, QSizePolicy,
)
from PyQt5.QtCore import Qt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from interferometer.surface_processing import prepare_surface
from interferometer.plotting_utils import compute_cmap_and_contour
from .mpl_widget import MplWidget
from .workers import LongExposureWorker

# Uncorrected: remove tip, tilt, piston
_RMS_COEFS = [0, 1, 2, 4]


class LongExposureTab(QWidget):
    """Tab for running a long-exposure mirror stability test."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._first_result = None    # reference measurement (A)
        self._latest_result = None   # most recent measurement (B)
        self._series_data = []       # list of {'elapsed': float, 'rms_nm': float, 'focus_mm': float}
        self._session_folder = None  # set when test starts
        self._worker = None
        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        root = QVBoxLayout(self)

        # ---- Top splitter: left=params, right=timeseries ----
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        # --- Params panel (top-left) ---
        params_box = QGroupBox("Long Exposure Parameters")
        pg = QVBoxLayout(params_box)

        mirror_row = QHBoxLayout()
        mirror_row.addWidget(QLabel("Mirror #:"))
        self.mirror_spin = QSpinBox()
        self.mirror_spin.setRange(1, 99)
        self.mirror_spin.setValue(22)
        mirror_row.addWidget(self.mirror_spin)
        mirror_row.addStretch()
        pg.addLayout(mirror_row)

        period_row = QHBoxLayout()
        period_row.addWidget(QLabel("Measurement period (min):"))
        self.period_spin = QDoubleSpinBox()
        self.period_spin.setRange(0.1, 999.0)
        self.period_spin.setDecimals(1)
        self.period_spin.setValue(5.0)
        period_row.addWidget(self.period_spin)
        period_row.addStretch()
        pg.addLayout(period_row)

        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel("Total test duration (min):"))
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(1.0, 99999.0)
        self.duration_spin.setDecimals(1)
        self.duration_spin.setValue(60.0)
        duration_row.addWidget(self.duration_spin)
        duration_row.addStretch()
        pg.addLayout(duration_row)

        align_row = QHBoxLayout()
        align_row.addWidget(QLabel("Alignment iterations:"))
        self.align_spin = QSpinBox()
        self.align_spin.setRange(1, 20)
        self.align_spin.setValue(7)
        align_row.addWidget(self.align_spin)
        align_row.addStretch()
        pg.addLayout(align_row)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.setStyleSheet("background-color: #2e8b2e; color: white; font-weight: bold;")
        self.start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setStyleSheet("background-color: #8b2e2e; color: white; font-weight: bold;")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        btn_row.addWidget(self.stop_btn)
        pg.addLayout(btn_row)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(80)
        pg.addWidget(self.log)

        params_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        top_layout.addWidget(params_box, stretch=1)

        # --- Time-series plot (top-right) ---
        self.plot_timeseries = MplWidget(self, width=7, height=4)
        self.plot_timeseries.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        top_layout.addWidget(self.plot_timeseries, stretch=2)

        # ---- Comparison plot (bottom) ----
        self.plot_compare = MplWidget(self, width=12, height=4)
        self.plot_compare.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # ---- Vertical splitter ----
        v_splitter = QSplitter(Qt.Vertical)
        v_splitter.addWidget(top_widget)
        v_splitter.addWidget(self.plot_compare)
        v_splitter.setSizes([400, 350])

        root.addWidget(v_splitter, stretch=1)

    # ---------------------------------------------------------------- slots

    def _log(self, msg):
        self.log.append(msg)

    def _on_start(self):
        if self._worker is not None and self._worker.isRunning():
            return

        # Reset state
        self._first_result = None
        self._latest_result = None
        self._series_data = []
        self._session_folder = None
        self.plot_timeseries.clear()
        self.plot_compare.clear()
        self.log.clear()

        self._worker = LongExposureWorker(
            mirror_num=self.mirror_spin.value(),
            period_minutes=self.period_spin.value(),
            total_duration_minutes=self.duration_spin.value(),
            align_iters=self.align_spin.value(),
        )
        self._worker.measurement_done.connect(self._on_measurement_done)
        self._worker.progress.connect(self._log)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def _on_stop(self):
        if self._worker is not None and self._worker.isRunning():
            self._log("Stop requested — finishing current measurement...")
            self._worker.request_stop()
        self.stop_btn.setEnabled(False)

    def _on_error(self, tb):
        self._log(f"ERROR:\n{tb}")

    def _on_worker_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._log("Test complete.")
        self._save_timeseries_plot()
        self._save_session_data()

    # ---------------------------------------------------------- processing

    def _on_measurement_done(self, result):
        """Called after each measurement completes."""
        if self._session_folder is None:
            self._session_folder = result.get('session_folder')

        if self._first_result is None:
            self._first_result = result
            self._latest_result = result
        else:
            self._latest_result = result

        # Compute uncorrected RMS of the difference surface (B - A)
        rms_nm = self._compute_diff_rms(self._first_result, self._latest_result)

        focus_mm = result.get('focus_pos_mm', float('nan'))
        elapsed = result.get('elapsed_minutes', 0.0)
        subfolder = os.path.basename(result.get('save_path', ''))
        self._series_data.append({
            'elapsed': elapsed,
            'rms_nm': rms_nm,
            'focus_mm': abs(focus_mm) if not np.isnan(focus_mm) else float('nan'),
            'subfolder': subfolder,
        })

        try:
            self._update_comparison_plot()
        except Exception:
            import traceback
            self._log(f"[comparison plot error]\n{traceback.format_exc()}")

        try:
            self._update_timeseries_plot()
        except Exception:
            import traceback
            self._log(f"[timeseries plot error]\n{traceback.format_exc()}")

    def _compute_diff_rms(self, first, latest):
        """Compute RMS of (latest - first) with uncorrected Zernike removal."""
        try:
            diff_raw = latest['surface'] - first['surface']
            config = first['config']
            Z = first['Z']
            diff_proc = prepare_surface(diff_raw, Z, _RMS_COEFS, config, crop_ca=False)
            vals = diff_proc[~np.isnan(diff_proc)] * 1e3  # µm → nm (consistent with results_tab)
            if len(vals) == 0:
                return float('nan')
            return float(np.sqrt(np.mean(vals ** 2)))
        except Exception:
            return float('nan')

    def _process_surface(self, result):
        """Apply uncorrected Zernike removal to a result's surface."""
        return prepare_surface(
            result['surface'], result['Z'], _RMS_COEFS,
            result['config'], crop_ca=False)

    # ------------------------------------------------------------ plotting

    def _update_comparison_plot(self):
        """Redraw the A / B / C comparison (bottom plot)."""
        self.plot_compare.clear()

        first = self._first_result
        latest = self._latest_result
        if first is None or latest is None:
            self.plot_compare.draw()
            return

        sa = self._process_surface(first)
        sb = self._process_surface(latest)
        delta = sb - sa

        # Shared colour bounds across all three surfaces
        all_vals = []
        for s in (sa, sb, delta):
            v = s[~np.isnan(s)] * 1000  # to nm
            if len(v) > 0:
                all_vals.append(v)
        combined = np.concatenate(all_vals) if all_vals else np.array([0.0])
        vmin, vmax, contour_levels = compute_cmap_and_contour(combined)

        fig = self.plot_compare.fig
        widths = [1, 1, 1, 0.06]
        gs = gridspec.GridSpec(1, 4, figure=fig, width_ratios=widths, wspace=0.05)
        ax_a = fig.add_subplot(gs[0, 0])
        ax_b = fig.add_subplot(gs[0, 1])
        ax_c = fig.add_subplot(gs[0, 2])
        cax  = fig.add_subplot(gs[0, 3])

        mirror_num = first['mirror_num']
        elapsed_b = latest.get('elapsed_minutes', 0.0)
        labels = [
            f"A — M{mirror_num} (t=0)",
            f"B — M{mirror_num} (t={elapsed_b:.1f} min)",
            "C — Δ (B − A)",
        ]

        im = None
        for ax, surf, label in zip([ax_a, ax_b, ax_c], [sa, sb, delta], labels):
            plot_nm = surf * 1000
            vals = plot_nm[~np.isnan(plot_nm)]
            rms = float(np.sqrt(np.mean(vals ** 2))) if len(vals) > 0 else 0.0
            pv = float(np.nanpercentile(vals, 99) - np.nanpercentile(vals, 1)) if len(vals) > 0 else 0.0
            im = ax.imshow(plot_nm, vmin=vmin, vmax=vmax, cmap='viridis')
            if contour_levels is not None and len(contour_levels) > 0:
                ax.contour(plot_nm, contour_levels, colors='w', linewidths=0.5)
            ax.set_title(f"{label}\n{rms:.0f} nm rms", fontsize=9)
            ax.set_xlabel(f"PV = {pv:.0f} nm", fontsize=9)
            ax.set_xticks([])
            ax.set_yticks([])

        if im is not None:
            fig.colorbar(im, cax=cax, label='nm')

        self.plot_compare.draw()

    def _update_timeseries_plot(self):
        """Redraw the time-series plot (top-right)."""
        self.plot_timeseries.clear()
        if not self._series_data:
            self.plot_timeseries.draw()
            return

        elapsed  = [d['elapsed']  for d in self._series_data]
        rms_vals = [d['rms_nm']   for d in self._series_data]
        focus_vals = [d['focus_mm'] for d in self._series_data]

        fig = self.plot_timeseries.fig
        ax1 = fig.add_subplot(111)
        color_rms   = '#1f77b4'
        color_focus = '#ff7f0e'

        ax1.plot(elapsed, rms_vals, color=color_rms, marker='o',
                 markersize=4, linewidth=1.5, label='RMS (nm)')
        ax1.set_xlabel('Elapsed time (min)')
        ax1.set_ylabel('RMS of C (nm)', color=color_rms)
        ax1.tick_params(axis='y', labelcolor=color_rms)
        ax1.grid(True, alpha=0.3)

        # Only show focus axis if we have valid (non-nan) values
        valid_focus = [v for v in focus_vals if not np.isnan(v)]
        if valid_focus:
            ax2 = ax1.twinx()
            ax2.plot(elapsed, focus_vals, color=color_focus, marker='s',
                     markersize=4, linewidth=1.5, linestyle='--', label='|Ch3 Focus| (mm)')
            ax2.set_ylabel('|Ch3 Focus| (mm)', color=color_focus)
            ax2.tick_params(axis='y', labelcolor=color_focus)
            # Combined legend
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2,
                       loc='upper left', fontsize=8)
        else:
            ax1.legend(loc='upper left', fontsize=8)

        ax1.set_title('Long Exposure Stability', fontsize=10)
        self.plot_timeseries.draw()

    def _save_timeseries_plot(self):
        """Save the time-series figure to the session folder as time_series.jpg."""
        if self._session_folder is None or not self._series_data:
            return
        out_path = os.path.join(self._session_folder, 'time_series.jpg')
        try:
            self.plot_timeseries.fig.savefig(out_path, dpi=150, bbox_inches='tight')
            self._log(f"Time-series plot saved to: {out_path}")
        except Exception as exc:
            self._log(f"Warning: could not save time-series plot: {exc}")

    def _save_session_data(self):
        """Save session metadata and time-series data as session_data.json."""
        if self._session_folder is None or not self._series_data:
            return
        # Determine mirror_num from first result
        mirror_num = None
        if self._first_result is not None:
            mirror_num = self._first_result.get('mirror_num')
        # Replace NaN with None so json.dumps doesn't choke
        measurements = []
        for d in self._series_data:
            measurements.append({
                'elapsed': None if (isinstance(d['elapsed'], float) and np.isnan(d['elapsed'])) else d['elapsed'],
                'rms_nm':  None if (isinstance(d['rms_nm'],  float) and np.isnan(d['rms_nm']))  else d['rms_nm'],
                'focus_mm': None if (isinstance(d['focus_mm'], float) and np.isnan(d['focus_mm'])) else d['focus_mm'],
                'subfolder': d.get('subfolder', ''),
            })
        payload = {'mirror_num': mirror_num, 'measurements': measurements}
        out_path = os.path.join(self._session_folder, 'session_data.json')
        try:
            with open(out_path, 'w') as f:
                json.dump(payload, f, indent=2)
            self._log(f"Session data saved to: {out_path}")
        except Exception as exc:
            self._log(f"Warning: could not save session data: {exc}")

    # ------------------------------------------------------- cleanup

    def cleanup(self):
        """Called by MainWindow.closeEvent — stop worker and save plot."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.request_stop()
            self._worker.wait(5000)
        self._save_timeseries_plot()
        self._save_session_data()
