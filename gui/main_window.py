"""
Main window — assembles tabs and wires signals.
"""

import sys
import os

from PyQt5.QtWidgets import QMainWindow, QTabWidget, QApplication
from PyQt5.QtCore import Qt

from .steering_tab import SteeringTab
from .measurement_tab import MeasurementTab
from .results_tab import ResultsTab


class MainWindow(QMainWindow):
    """Top-level window for the Interferometer GUI."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LFAST Interferometer Control")
        self.resize(1200, 800)

        # --- Central tab widget ---
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.steering_tab = SteeringTab()
        self.measurement_tab = MeasurementTab()
        self.results_tab = ResultsTab()

        self.tabs.addTab(self.steering_tab, "Beam Steering")
        self.tabs.addTab(self.measurement_tab, "Measurement")
        self.tabs.addTab(self.results_tab, "Results / Compare")

        # Wire measurement → results
        self.measurement_tab.on_surface_ready = self._on_surface_ready

    def _on_surface_ready(self, result_dict, slot_index):
        """Forward from measurement tab to results tab and switch view."""
        self.results_tab.set_surface(result_dict, slot_index)
        self.tabs.setCurrentWidget(self.results_tab)

    def closeEvent(self, event):
        self.steering_tab.cleanup()
        super().closeEvent(event)


def run_gui():
    """Entry-point function — create the QApplication and show the window."""
    # Use non-interactive Agg-compatible backend for embedded matplotlib
    import matplotlib
    matplotlib.use('Qt5Agg')

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
