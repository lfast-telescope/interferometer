"""
Results / Compare tab — view processed surfaces, adjust correction modes,
and compare two measurements side-by-side.
"""

import sys, os
import numpy as np
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QComboBox, QCheckBox, QPushButton, QMessageBox, QSplitter,
    QSlider, QLineEdit, QStyle, QStyleOptionSlider,
)
from PyQt5.QtCore import Qt


class _JumpSlider(QSlider):
    """QSlider that jumps to the clicked position instead of paging."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 2px;
                background: #cc3300;
                margin: 0px;
            }
            QSlider::handle:horizontal {
                background: white;
                border: 1px solid #999;
                width: 10px;
                height: 14px;
                margin: -7px 0;
                border-radius: 1px;
            }
            QSlider::sub-page:horizontal {
                background: #cc3300;
            }
            QSlider::add-page:horizontal {
                background: #cc3300;
            }
        """)

    def mousePressEvent(self, event):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        groove = self.style().subControlRect(
            QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
        handle = self.style().subControlRect(
            QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
        if self.orientation() == Qt.Horizontal:
            pos = event.x()
            span = groove.width() - handle.width()
            offset = groove.x() + handle.width() // 2
        else:
            pos = event.y()
            span = groove.height() - handle.height()
            offset = groove.y() + handle.height() // 2
        val = QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), pos - offset, span)
        self.setValue(val)
        event.accept()

# Ensure imports work when running from different entry points
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from interferometer.surface_processing import prepare_surface, radial_averaged_surface
from interferometer.plotting_interface import (
    plot_processed_surface, plot_mirror_cs, compare_surfaces,
)
from interferometer.plotting_utils import compute_cmap_and_contour
from .mpl_widget import MplWidget


# Pre-defined correction presets (same as main.py)
COEF_PRESETS = {
    'uncorrected': [0, 1, 2, 4],
    'sph corrected': [0, 1, 2, 4],
    'edge corrected': [0, 1, 2, 3, 4, 5, 6, 9, 10, 14, 15, 20, 21, 27, 28, 35, 36, 44],
    'all modes removed': [0, 1, 2, 3, 4, 5, 6, 9, 10, 14, 15, 20, 21, 27, 28, 35, 36, 44],
}


class ResultsTab(QWidget):
    """Display and compare processed mirror surfaces."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Two data slots for comparison
        self._data = [None, None]      # list of result dicts (or None)
        self._processed = [None, None] # processed surface arrays
        self._compare_active = False   # only show comparison after button press
        self._defocus_amplitude = 0.0  # defocus to add after processing
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QVBoxLayout(self)

        # --- Options bar ---
        opts_box = QGroupBox("Processing Options")
        opts_layout = QHBoxLayout(opts_box)

        opts_layout.addWidget(QLabel("Correction:"))
        self.coef_combo = QComboBox()
        self.coef_combo.addItems(list(COEF_PRESETS.keys()))
        self.coef_combo.currentIndexChanged.connect(self._on_options_changed)
        opts_layout.addWidget(self.coef_combo)

        self.crop_ca_chk = QCheckBox("Crop clear aperture")
        self.crop_ca_chk.setChecked(False)
        self.crop_ca_chk.stateChanged.connect(self._on_options_changed)
        opts_layout.addWidget(self.crop_ca_chk)

        self.cs_chk = QCheckBox("Show cross-section")
        self.cs_chk.setChecked(False)
        self.cs_chk.stateChanged.connect(self._on_options_changed)
        opts_layout.addWidget(self.cs_chk)

        self.psf_chk = QCheckBox("Show PSF")
        self.psf_chk.setChecked(False)
        self.psf_chk.stateChanged.connect(self._on_options_changed)
        opts_layout.addWidget(self.psf_chk)

        # --- Defocus controls (hidden, kept for future use) ---
        self.defocus_label = QLabel("Defocus:")
        self.defocus_label.setVisible(False)
        opts_layout.addWidget(self.defocus_label)
        self.defocus_slider = _JumpSlider(Qt.Horizontal)
        self.defocus_slider.setRange(-100, 100)  # maps to -1.0 .. 1.0
        self.defocus_slider.setValue(0)
        self.defocus_slider.setSingleStep(1)
        self.defocus_slider.setPageStep(10)
        self.defocus_slider.setMaximumWidth(480)
        self.defocus_slider.valueChanged.connect(self._on_defocus_slider_changed)
        self.defocus_slider.setVisible(False)
        opts_layout.addWidget(self.defocus_slider)

        self.defocus_input = QLineEdit("0.00")
        self.defocus_input.setFixedWidth(50)
        self.defocus_input.editingFinished.connect(self._on_defocus_text_changed)
        self.defocus_input.setVisible(False)
        opts_layout.addWidget(self.defocus_input)

        self.refresh_btn = QPushButton("Refresh Plots")
        self.refresh_btn.clicked.connect(self._refresh)
        opts_layout.addWidget(self.refresh_btn)

        root.addWidget(opts_box)

        # --- Status labels ---
        status_row = QHBoxLayout()
        self.slot_a_label = QLabel("Slot A: (empty)")
        self.slot_b_label = QLabel("Slot B: (empty)")
        self.slot_a_label.setStyleSheet("font-weight: bold;")
        self.slot_b_label.setStyleSheet("font-weight: bold;")
        status_row.addWidget(self.slot_a_label)
        status_row.addWidget(self.slot_b_label)
        root.addLayout(status_row)

        # --- Plot area (splitter with two canvases) ---
        self.splitter = QSplitter(Qt.Horizontal)

        self.plot_a = MplWidget(self, width=6, height=5)
        self.plot_b = MplWidget(self, width=6, height=5)
        self.splitter.addWidget(self.plot_a)
        self.splitter.addWidget(self.plot_b)
        self.splitter.setSizes([500, 500])

        # --- Comparison area ---
        comp_box = QGroupBox("Comparison (A − B)")
        comp_layout = QVBoxLayout(comp_box)
        self.compare_btn = QPushButton("Compare A vs B")
        self.compare_btn.clicked.connect(self._compare)
        comp_layout.addWidget(self.compare_btn)
        self.plot_compare = MplWidget(self, width=12, height=4)
        comp_layout.addWidget(self.plot_compare)

        # --- Vertical splitter between slots and comparison ---
        self.v_splitter = QSplitter(Qt.Vertical)
        self.v_splitter.addWidget(self.splitter)
        self.v_splitter.addWidget(comp_box)
        self.v_splitter.setSizes([500, 300])

        root.addWidget(self.v_splitter, stretch=1)

    # --------------------------------------------------- public interface
    def set_surface(self, result_dict, slot_index):
        """Called by MeasurementTab when a surface is ready."""
        self._data[slot_index] = result_dict
        label_text = (
            f"Slot {'A' if slot_index == 0 else 'B'}: "
            f"M{result_dict['mirror_num']}  —  {result_dict['save_path']}"
        )
        if slot_index == 0:
            self.slot_a_label.setText(label_text)
        else:
            self.slot_b_label.setText(label_text)
        self._refresh()

    # --------------------------------------------------- internal
    def _current_coefs(self):
        name = self.coef_combo.currentText()
        return COEF_PRESETS.get(name, [0, 1, 2, 4])

    def _process(self, slot_index):
        """Run prepare_surface for the given slot and cache the result."""
        data = self._data[slot_index]
        if data is None:
            self._processed[slot_index] = None
            return
        coefs = self._current_coefs()
        crop = self.crop_ca_chk.isChecked()
        preset_name = self.coef_combo.currentText()
        surface = data['surface']
        if preset_name in ('sph corrected', 'all modes removed'):
            # Subtract radial average first, then remove Zernike modes
            surface = surface - radial_averaged_surface(surface, data['config'])
        processed = prepare_surface(
            surface, data['Z'], coefs, data['config'], crop_ca=crop)
        self._processed[slot_index] = processed

    def _on_options_changed(self, _=None):
        self._refresh()

    def _on_defocus_slider_changed(self, value):
        self._defocus_amplitude = value / 100.0
        self.defocus_input.blockSignals(True)
        self.defocus_input.setText(f"{self._defocus_amplitude:.2f}")
        self.defocus_input.blockSignals(False)
        self._refresh()

    def _on_defocus_text_changed(self):
        try:
            val = float(self.defocus_input.text())
        except ValueError:
            return
        self._defocus_amplitude = val
        slider_val = int(round(val * 100))
        self.defocus_slider.blockSignals(True)
        self.defocus_slider.setValue(max(-100, min(100, slider_val)))
        self.defocus_slider.blockSignals(False)
        self._refresh()

    def _apply_defocus(self, surface, data):
        """Apply defocus to a processed surface if amplitude is non-zero."""
        if self._defocus_amplitude == 0.0 or data is None or surface is None:
            return surface
        from shared.wavefront_propagation import add_defocus
        return add_defocus(surface, data['Z'], amplitude=self._defocus_amplitude)

    def _compute_shared_bounds(self):
        """Compute shared vmin/vmax/contour_levels across both processed slots."""
        all_vals = []
        for surface in self._processed:
            if surface is not None:
                v = surface[~np.isnan(surface)] * 1000  # nm
                if len(v) > 0:
                    all_vals.append(v)
        if not all_vals:
            return None, None, None
        combined = np.concatenate(all_vals)
        left_bound, right_bound, contour_levels = compute_cmap_and_contour(combined)
        return left_bound, right_bound, contour_levels

    def _refresh(self):
        """Re-process and re-plot both slots, then update comparison."""
        for i in range(2):
            self._process(i)

        for i in range(2):
            self._plot_slot(i)

        # Auto-update comparison only if it was previously activated
        if self._compare_active:
            self._show_compare()

    def _plot_slot(self, idx):
        widget = self.plot_a if idx == 0 else self.plot_b
        widget.clear()
        surface = self._processed[idx]
        data = self._data[idx]
        if surface is None or data is None:
            widget.draw()
            return

        surface = self._apply_defocus(surface, data)

        mirror_name = f"M{data['mirror_num']}"
        plot_ref = surface.copy() * 1000  # to nm
        vals = plot_ref[~np.isnan(plot_ref)]
        vmin, vmax, contour_levels = compute_cmap_and_contour(vals) if len(vals) > 0 else (None, None, None)
        rms = np.sqrt(np.mean(vals**2)) if len(vals) > 0 else 0

        show_cs = self.cs_chk.isChecked()
        show_psf = self.psf_chk.isChecked()

        # Determine number of panels
        panels = ['surface']
        if show_cs:
            panels.append('cs')
        if show_psf:
            panels.append('psf')
        n_panels = len(panels)

        if n_panels == 1:
            # Single centered subplot with dedicated colorbar axis
            gs = gridspec.GridSpec(1, 3, figure=widget.fig,
                                  width_ratios=[0.3, 1, 0.05])
            ax = widget.fig.add_subplot(gs[0, 1])
            cax = widget.fig.add_subplot(gs[0, 2])
            spacer = widget.fig.add_subplot(gs[0, 0])
            spacer.set_visible(False)

            pcm = ax.imshow(plot_ref, vmin=vmin, vmax=vmax, cmap='viridis')
            if contour_levels is not None and len(contour_levels) > 0:
                ax.contour(plot_ref, contour_levels, colors='w', linewidths=0.5)
            widget.fig.colorbar(pcm, cax=cax, label='nm')
            ax.set_title(f"{mirror_name}  {rms:.0f} nm rms")
            ax.set_xticks([]); ax.set_yticks([])
        else:
            # Equal-width columns for each panel
            gs = gridspec.GridSpec(1, n_panels, figure=widget.fig,
                                  width_ratios=[1] * n_panels, wspace=0.15)
            col = 0

            # -- Surface panel (always first) --
            ax_surf = widget.fig.add_subplot(gs[0, col])
            pcm = ax_surf.imshow(plot_ref, vmin=vmin, vmax=vmax, cmap='viridis')
            if contour_levels is not None and len(contour_levels) > 0:
                ax_surf.contour(plot_ref, contour_levels, colors='w', linewidths=0.5)
            widget.fig.colorbar(pcm, ax=ax_surf, shrink=0.7, label='nm')
            ax_surf.set_title(f"{mirror_name}  {rms:.0f} nm rms")
            ax_surf.set_xticks([]); ax_surf.set_yticks([])
            col += 1

            # -- Cross-section panel --
            if show_cs:
                ax_cs = widget.fig.add_subplot(gs[0, col])
                from interferometer.plotting_utils import plot_many_mirror_cs
                plot_many_mirror_cs(
                    f"{mirror_name} radial",
                    [surface], ["surface"],
                    fig=widget.fig, ax=ax_cs)
                col += 1

            # -- PSF panel --
            if show_psf:
                ax_psf = widget.fig.add_subplot(gs[0, col])
                self._render_psf(surface, data, widget.fig, ax_psf, rms)
                col += 1

        widget.draw()

    def _render_psf(self, surface, data, fig, ax, rms):
        """Compute and render the PSF into a single axis."""
        from shared.wavefront_propagation import propagate_wavefront
        config = data['config']
        Z = data['Z']
        wf_foc, throughput, x_foc, y_foc = propagate_wavefront(
            surface, config['OD'], config['ID'], Z, use_best_focus=True)
        output_foc = np.log10(wf_foc)
        foc_scale = [-3, -5.5]
        ax.pcolormesh(x_foc, y_foc, output_foc, cmap='inferno',
                      vmax=foc_scale[0], vmin=foc_scale[1])
        ax.set_aspect('equal')
        ax.yaxis.tick_right()
        ax.set_ylabel('arcsec')
        ax.yaxis.set_label_position('right')
        patch = mpatches.Circle([0, 0], radius=1.315, color='c',
                                fill=False, linewidth=1)
        ax.add_artist(patch)
        ax.set_title(f"{int(throughput * 100)}% efficiency", fontsize=9)

    def _compare(self):
        """Activate comparison and plot it (called from button press)."""
        self._compare_active = True
        self._show_compare()

    def _show_compare(self):
        """Plot A and B side by side with a delta surface."""
        self.plot_compare.clear()

        if self._processed[0] is None or self._processed[1] is None:
            self.plot_compare.draw()
            return

        sa, sb = self._processed[0], self._processed[1]
        da, db = self._data[0], self._data[1]

        sa = self._apply_defocus(sa, da)
        sb = self._apply_defocus(sb, db)

        delta = sa - sb

        # Shared bounds across A, B, and delta
        all_vals = []
        for s in [sa, sb, delta]:
            v = s[~np.isnan(s)] * 1000
            if len(v) > 0:
                all_vals.append(v)
        combined = np.concatenate(all_vals) if all_vals else np.array([0])
        vmin, vmax, contour_levels = compute_cmap_and_contour(combined)

        show_cs = self.cs_chk.isChecked()

        # Layout: A | B | Δ | colorbar | (optional cross-section)
        if show_cs:
            widths = [1, 1, 1, 0.06, 1]
            gs = gridspec.GridSpec(1, 5, figure=self.plot_compare.fig,
                                  width_ratios=widths, wspace=0.05)
        else:
            widths = [1, 1, 1, 0.06]
            gs = gridspec.GridSpec(1, 4, figure=self.plot_compare.fig,
                                  width_ratios=widths, wspace=0.05)

        ax1 = self.plot_compare.fig.add_subplot(gs[0, 0])
        ax2 = self.plot_compare.fig.add_subplot(gs[0, 1])
        ax3 = self.plot_compare.fig.add_subplot(gs[0, 2])
        cax = self.plot_compare.fig.add_subplot(gs[0, 3])

        for ax, surf, label in [
            (ax1, sa, f"M{da['mirror_num']} (A)"),
            (ax2, sb, f"M{db['mirror_num']} (B)"),
            (ax3, delta, "Δ (A−B)"),
        ]:
            plot_nm = surf.copy() * 1000
            vals = plot_nm[~np.isnan(plot_nm)]
            rms = np.sqrt(np.mean(vals**2)) if len(vals) > 0 else 0
            im = ax.imshow(plot_nm, vmin=vmin, vmax=vmax, cmap='viridis')
            if contour_levels is not None and len(contour_levels) > 0:
                ax.contour(plot_nm, contour_levels, colors='w', linewidths=0.5)
            ax.set_title(f"{label}\n{rms:.0f} nm rms", fontsize=9)
            ax.set_xticks([]); ax.set_yticks([])

        self.plot_compare.fig.colorbar(im, cax=cax, label='nm')

        if show_cs:
            ax_cs = self.plot_compare.fig.add_subplot(gs[0, 4])
            from interferometer.plotting_utils import plot_many_mirror_cs
            plot_many_mirror_cs(
                "Radial comparison",
                [sa, sb, delta],
                [f"A (M{da['mirror_num']})", f"B (M{db['mirror_num']})", "Δ (A−B)"],
                fig=self.plot_compare.fig, ax=ax_cs)

        self.plot_compare.fig.suptitle(
            f"Comparison: M{da['mirror_num']} (A) vs M{db['mirror_num']} (B)",
            fontsize=11)
        self.plot_compare.draw()

